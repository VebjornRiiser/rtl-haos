# mqtt_handler.py
"""
FILE: mqtt_handler.py
DESCRIPTION:
  Manages the connection to the MQTT Broker.
  - UPDATED: Now tracks 'tracked_devices' (a set of all unique devices seen).
"""
import json
import threading
import sys
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

# Local imports
import config
from utils import clean_mac
from field_meta import FIELD_META

class HomeNodeMQTT:
    def __init__(self):
        self.client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
        self.TOPIC_AVAILABILITY = f"home/status/rtl_bridge{config.ID_SUFFIX}/availability"
        self.client.username_pw_set(config.MQTT_SETTINGS["user"], config.MQTT_SETTINGS["pass"])
        self.client.will_set(self.TOPIC_AVAILABILITY, "offline", retain=True)
        self.client.on_connect = self._on_connect

        self.discovery_published = set()
        self.last_sent_values = {}
        # NEW: Track unique physical devices seen
        self.tracked_devices = set()
        
        self.discovery_lock = threading.Lock()

    def _on_connect(self, c, u, f, rc, p=None):
        if rc == 0:
            c.publish(self.TOPIC_AVAILABILITY, "online", retain=True)
            print("[MQTT] Connected Successfully.")
        else:
            print(f"[MQTT] Connection Failed! Code: {rc}")

    def start(self):
        print(f"[STARTUP] Connecting to MQTT Broker at {config.MQTT_SETTINGS['host']}...")
        try:
            self.client.connect(config.MQTT_SETTINGS["host"], config.MQTT_SETTINGS["port"])
            self.client.loop_start()
        except Exception as e:
            print(f"[CRITICAL] MQTT Connect Failed: {e}")
            sys.exit(1)

    def stop(self):
        self.client.publish(self.TOPIC_AVAILABILITY, "offline", retain=True)
        self.client.loop_stop()
        self.client.disconnect()

    def _publish_discovery(self, sensor_name, state_topic, unique_id, device_name, device_model):
        unique_id = f"{unique_id}{config.ID_SUFFIX}"

        with self.discovery_lock:
            if unique_id in self.discovery_published:
                return

            default_meta = (None, "none", "mdi:eye", sensor_name.replace("_", " ").title())
            meta = FIELD_META.get(sensor_name, default_meta)

            try:
                unit, device_class, icon, friendly_name = meta
            except ValueError:
                unit, device_class, icon, friendly_name = default_meta

            # Whitelist Logic
            if sensor_name in getattr(config, 'MAIN_SENSORS', []):
                entity_cat = None 
            else:
                entity_cat = "diagnostic"

            payload = {
                "name": friendly_name,
                "state_topic": state_topic,
                "unique_id": unique_id,
                "device": {
                    "identifiers": [f"rtl433_{device_model}_{unique_id.split('_')[0]}"],
                    "manufacturer": "rtl_433",
                    "model": device_model,
                    "name": device_name 
                },
                "icon": icon,
            }

            if unit: payload["unit_of_measurement"] = unit
            if device_class != "none": payload["device_class"] = device_class
            if entity_cat: payload["entity_category"] = entity_cat

            if device_class in ["gas", "energy", "water", "monetary"]:
                payload["state_class"] = "total_increasing"
            if device_class in ["temperature", "humidity", "pressure", "illuminance", "voltage"]:
                 payload["state_class"] = "measurement"

            payload["expire_after"] = config.RTL_EXPIRE_AFTER
            payload["availability_topic"] = self.TOPIC_AVAILABILITY

            config_topic = f"homeassistant/sensor/{unique_id}/config"
            self.client.publish(config_topic, json.dumps(payload), retain=True)
            self.discovery_published.add(unique_id)

    def send_sensor(self, sensor_id, field, value, device_name, device_model, is_rtl=True):
        if value is None: return

        # NEW: Add to tracked devices list
        self.tracked_devices.add(device_name)

        clean_id = clean_mac(sensor_id) 
        unique_id_base = clean_id
        state_topic_base = clean_id

        unique_id = f"{unique_id_base}_{field}"
        state_topic = f"home/rtl_devices/{state_topic_base}/{field}" 

        self._publish_discovery(field, state_topic, unique_id, device_name, device_model)

        unique_id_v2 = f"{unique_id}{config.ID_SUFFIX}"
        
        value_changed = self.last_sent_values.get(unique_id_v2) != value

        if value_changed or is_rtl:
            self.client.publish(state_topic, str(value), retain=True)
            self.last_sent_values[unique_id_v2] = value
            
            if value_changed:
                print(f" -> TX {device_name} [{field}]: {value}")