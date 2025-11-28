#!/usr/bin/env python3
"""
FILE: rtl_mqtt_bridge.py
DESCRIPTION:
  The main executable script.
  - UPDATED: Now includes a Threaded Buffer for throttling/averaging data.
"""
import subprocess
import json
import time
import threading
import sys
import importlib.util
import fnmatch
import socket
import statistics # <--- Needed for averaging

# --- PRE-FLIGHT DEPENDENCY CHECK ---
def check_dependencies():
    missing_apt = []
    if not subprocess.run(["which", "rtl_433"], capture_output=True).stdout:
        missing_apt.append("rtl-433")
    if importlib.util.find_spec("paho") is None:
        missing_apt.append("python3-paho-mqtt")

    if missing_apt:
        print("CRITICAL: MISSING DEPENDENCIES. Install: " + " ".join(missing_apt))
        sys.exit(1)

check_dependencies()

import paho.mqtt.client as mqtt
import config
from utils import clean_mac, calculate_dew_point, get_system_mac
from mqtt_handler import HomeNodeMQTT
from field_meta import FIELD_META 
from system_monitor import system_stats_loop

# --- BUFFER GLOBALS ---
DATA_BUFFER = {} # { "unique_device_id": { "field_name": [val1, val2], "metadata": {...} } }
BUFFER_LOCK = threading.Lock()

# ---------------- HELPERS ----------------
def flatten(d, sep: str = "_") -> dict:
    obj = {}
    def recurse(t, parent: str = ""):
        if isinstance(t, list):
            for i, v in enumerate(t):
                recurse(v, f"{parent}{sep}{i}" if parent else str(i))
        elif isinstance(t, dict):
            for k, v in t.items():
                recurse(v, f"{parent}{sep}{k}" if parent else k)
        else:
            if parent: obj[parent] = t
    recurse(d)
    return obj

def is_blocked_device(clean_id: str, model: str) -> bool:
    patterns = getattr(config, "DEVICE_BLACKLIST", None)
    if not patterns: return False
    for pattern in patterns:
        if fnmatch.fnmatch(str(clean_id), pattern): return True
        if fnmatch.fnmatch(str(model), pattern): return True
    return False

# ---------------- BUFFERING / DISPATCH ----------------
def dispatch_reading(clean_id, field, value, dev_name, model, mqtt_handler):
    """
    Decides whether to send data immediately or buffer it for averaging.
    """
    interval = getattr(config, "RTL_THROTTLE_INTERVAL", 0)

    # If throttle is disabled (0), send straight to MQTT
    if interval <= 0:
        mqtt_handler.send_sensor(clean_id, field, value, dev_name, model, is_rtl=True)
        return

    # Otherwise, add to buffer
    with BUFFER_LOCK:
        if clean_id not in DATA_BUFFER:
            DATA_BUFFER[clean_id] = {}
        
        # We store the metadata (name/model) alongside the values so the flusher knows them
        if "__meta__" not in DATA_BUFFER[clean_id]:
            DATA_BUFFER[clean_id]["__meta__"] = {"name": dev_name, "model": model}

        if field not in DATA_BUFFER[clean_id]:
            DATA_BUFFER[clean_id][field] = []
        
        DATA_BUFFER[clean_id][field].append(value)

def throttle_flush_loop(mqtt_handler):
    """
    Background thread that runs every RTL_THROTTLE_INTERVAL.
    Averages numbers, takes the last value for strings, and sends.
    """
    interval = getattr(config, "RTL_THROTTLE_INTERVAL", 30)
    if interval <= 0:
        print("[THROTTLE] Disabled (Real-time mode).")
        return

    print(f"[THROTTLE] Averaging data every {interval} seconds.")
    
    while True:
        time.sleep(interval)
        
        # 1. Swap buffer (Thread-safe extraction)
        with BUFFER_LOCK:
            if not DATA_BUFFER:
                continue
            # Shallow copy the dict to process it, then clear global
            current_batch = DATA_BUFFER.copy()
            DATA_BUFFER.clear()

        # 2. Process batch
        count_sent = 0
        for clean_id, device_data in current_batch.items():
            meta = device_data.get("__meta__", {})
            dev_name = meta.get("name", "Unknown")
            model = meta.get("model", "Unknown")

            for field, values in device_data.items():
                if field == "__meta__": continue
                if not values: continue

                final_val = None
                
                # Logic: If numbers -> Average. If String/Other -> Take Last.
                try:
                    # Check if the first item is a number
                    if isinstance(values[0], (int, float)):
                        final_val = round(statistics.mean(values), 2)
                        # If it looks like an int (e.g. 100.0), cast it back to int for cleaner display
                        if final_val.is_integer():
                            final_val = int(final_val)
                    else:
                        final_val = values[-1] # Take latest
                except:
                    final_val = values[-1] # Fallback

                mqtt_handler.send_sensor(clean_id, field, final_val, dev_name, model, is_rtl=True)
                count_sent += 1
        
        if getattr(config, "DEBUG_RAW_JSON", False) and count_sent > 0:
            print(f"[THROTTLE] Flushed {count_sent} averaged readings.")


# ---------------- RTL433 LOOP ----------------
def rtl_loop(radio_config: dict, mqtt_handler: HomeNodeMQTT) -> None:
    device_id = radio_config.get("id", "0")
    frequency = radio_config.get("freq", "433.92M")
    radio_name = radio_config.get("name", f"RTL_{device_id}")
    sample_rate = radio_config.get("rate", "250k")

    cmd = [
        "rtl_433", "-d", f":{device_id}", "-f", frequency, "-s", sample_rate,
        "-F", "json", "-M", "time:iso", "-M", "protocol", "-M", "level",
    ]

    print(f"[RTL] Starting {radio_name} on {frequency}...")

    while True:
        proc = None
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

            for line in proc.stdout:
                if not line: continue
                safe_line = line.strip()
                if "No supported devices" in safe_line:
                    print(f"[{radio_name} CRITICAL ERROR] USB Device not found!")
                if not safe_line.startswith("{") or not safe_line.endswith("}"):
                    continue

                try:
                    data = json.loads(safe_line)
                except:
                    continue

                model = data.get("model", "Generic")
                sid = data.get("id") or data.get("channel") or "unknown"
                clean_id = clean_mac(sid)
                dev_name = f"{model} ({clean_id})"

                # --- FILTERING ---
                whitelist = getattr(config, "DEVICE_WHITELIST", [])
                if whitelist:
                    is_allowed = False
                    for pattern in whitelist:
                        if fnmatch.fnmatch(str(clean_id), pattern) or fnmatch.fnmatch(model, pattern):
                            is_allowed = True
                            break
                    if not is_allowed: continue
                else:
                    if is_blocked_device(clean_id, model): continue

                if getattr(config, "DEBUG_RAW_JSON", False):
                    print(f"[{radio_name}] RX: {safe_line}")

                # --- DATA PROCESSING ---
                # 1. Utilities (Divide by 10 logic)
                if "Neptune-R900" in model:
                    if data.get("consumption") is not None:
                        real_val = float(data["consumption"]) / 10.0
                        dispatch_reading(clean_id, "meter_reading", real_val, dev_name, model, mqtt_handler)
                        del data["consumption"]

                if "SCM" in model or "ERT" in model:
                    if data.get("consumption") is not None:
                        dispatch_reading(clean_id, "Consumption", data["consumption"], dev_name, model, mqtt_handler)
                        del data["consumption"]

                # 2. Dew Point
                t_c = None
                if "temperature_C" in data: t_c = data["temperature_C"]
                elif "temp_C" in data: t_c = data["temp_C"]
                elif "temperature_F" in data: t_c = (data["temperature_F"] - 32.0) * 5.0 / 9.0
                elif "temperature" in data: t_c = data["temperature"] # Assumption

                if t_c is not None and data.get("humidity") is not None:
                    dp_f = calculate_dew_point(t_c, data["humidity"])
                    if dp_f is not None:
                        dispatch_reading(clean_id, "dew_point", dp_f, dev_name, model, mqtt_handler)

                # 3. Generic Flatten & Send
                flat = flatten(data)
                for key, value in flat.items():
                    if key in getattr(config, 'SKIP_KEYS', []): continue

                    # Normalize Temp to F
                    if key in ["temperature_C", "temp_C"] and isinstance(value, (int, float)):
                        val_f = round(value * 1.8 + 32.0, 1)
                        dispatch_reading(clean_id, "temperature", val_f, dev_name, model, mqtt_handler)
                    elif key in ["temperature_F", "temp_F", "temperature"] and isinstance(value, (int, float)):
                        dispatch_reading(clean_id, "temperature", value, dev_name, model, mqtt_handler)
                    else:
                        dispatch_reading(clean_id, key, value, dev_name, model, mqtt_handler)

            if proc: proc.wait()
            time.sleep(5)

        except Exception as e:
            print(f"[{radio_name}] Error: {e}. Restarting...")
            time.sleep(30)


def main():
    print("--- RTL-MQTT BRIDGE + SYSTEM MONITOR STARTING ---")

    mqtt_handler = HomeNodeMQTT()
    mqtt_handler.start()

    # Start RTL Threads
    rtl_config = getattr(config, "RTL_CONFIG", None)
    if rtl_config:
        for radio in rtl_config:
            threading.Thread(target=rtl_loop, args=(radio, mqtt_handler), daemon=True).start()
    else:
        threading.Thread(target=rtl_loop, args=({}, mqtt_handler), daemon=True).start()

    # Start System Monitor
    base_device_id = get_system_mac().replace(":", "").lower()
    base_model_name = socket.gethostname().title()
    threading.Thread(target=system_stats_loop, args=(mqtt_handler, base_device_id, base_model_name), daemon=True).start()

    # Start Throttle Flusher (New Thread)
    threading.Thread(target=throttle_flush_loop, args=(mqtt_handler,), daemon=True).start()

    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Stopping MQTT...")
        mqtt_handler.stop()

if __name__ == "__main__":
    main()