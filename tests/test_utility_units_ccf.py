import pytest

import config
import mqtt_handler

from ._mqtt_test_helpers import DummyClient, assert_float_str, last_discovery_payload, last_state_payload


def _patch_common(monkeypatch):
    """Stable MQTT + config baseline so tests only focus on behavior."""
    monkeypatch.setattr(mqtt_handler.mqtt, "Client", lambda *a, **k: DummyClient())
    monkeypatch.setattr(mqtt_handler, "clean_mac", lambda s: "deadbeef")

    # Deterministic discovery identifiers
    monkeypatch.setattr(config, "ID_SUFFIX", "_T", raising=False)
    monkeypatch.setattr(config, "BRIDGE_NAME", "Bridge", raising=False)
    monkeypatch.setattr(config, "BRIDGE_ID", "bridgeid", raising=False)
    monkeypatch.setattr(config, "RTL_EXPIRE_AFTER", 60, raising=False)
    monkeypatch.setattr(config, "VERBOSE_TRANSMISSIONS", False, raising=False)
    monkeypatch.setattr(config, "MAIN_SENSORS", ["Consumption"], raising=False)


def test_scmplus_ccf_updates_after_metertype(monkeypatch):
    """If MeterType arrives after Consumption, we should update config + re-publish state in CCF."""
    _patch_common(monkeypatch)
    monkeypatch.setattr(config, "GAS_VOLUME_UNIT", "ccf", raising=False)

    h = mqtt_handler.HomeNodeMQTT(version="vtest")
    c = h.client

    # 1) Consumption arrives first (SCMplus gas Consumption is raw ft³)
    h.send_sensor("device_x", "Consumption", 217504, "SCMplus deadbeef", "SCMplus")

    cfg1 = last_discovery_payload(c, domain="sensor", unique_id_with_suffix="deadbeef_Consumption_T")
    assert cfg1.get("device_class") == "gas"
    assert cfg1.get("unit_of_measurement") == "ft³"  # default before we learn commodity

    st1 = last_state_payload(c, "deadbeef", "Consumption")
    assert_float_str(st1, 217504.0)

    # 2) MeterType arrives later; triggers refresh of cached utility entities
    h.send_sensor("device_x", "MeterType", "Gas", "SCMplus deadbeef", "SCMplus")

    cfg2 = last_discovery_payload(c, domain="sensor", unique_id_with_suffix="deadbeef_Consumption_T")
    assert cfg2.get("device_class") == "gas"
    assert cfg2.get("unit_of_measurement") == "CCF"

    st2 = last_state_payload(c, "deadbeef", "Consumption")
    assert_float_str(st2, 2175.04)


def test_scmplus_ccf_conversion_is_noop_for_non_numeric(monkeypatch):
    """If a gas value isn't numeric, CCF conversion should not crash or mutate it."""
    _patch_common(monkeypatch)
    monkeypatch.setattr(config, "GAS_VOLUME_UNIT", "ccf", raising=False)

    h = mqtt_handler.HomeNodeMQTT(version="vtest")
    c = h.client

    # Learn commodity so conversion path is active
    h.send_sensor("device_x", "MeterType", "Gas", "SCMplus deadbeef", "SCMplus")

    # Non-numeric values should publish as-is
    h.send_sensor("device_x", "Consumption", "not-a-number", "SCMplus deadbeef", "SCMplus")
    st = last_state_payload(c, "deadbeef", "Consumption")
    assert st == "not-a-number"