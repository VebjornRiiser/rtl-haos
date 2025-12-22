import pytest
import system_monitor


def test_format_list_for_ha_truncates_and_sorts():
    out = system_monitor.format_list_for_ha(["b", "a", 1])
    assert out.startswith("1, a, b")

    long = ["x" * 300]
    out2 = system_monitor.format_list_for_ha(long)
    assert out2.endswith("...")
    assert len(out2) <= 250


def test_system_stats_loop_one_iteration_sends_device_count(mocker):
    mocker.patch.object(system_monitor, "PSUTIL_AVAILABLE", False)

    mqtt_handler = mocker.Mock()
    mqtt_handler.tracked_devices = {"A", "B", "C"}

    # break after first iteration (sleep is at end of loop)
    mocker.patch("system_monitor.time.sleep", side_effect=InterruptedError("stop"))

    with pytest.raises(InterruptedError):
        system_monitor.system_stats_loop(mqtt_handler, "dev123", "Bridge")

    mqtt_handler.send_sensor.assert_any_call(
        "dev123",
        "sys_device_count",
        3,
        "Bridge (dev123)",
        "Bridge",
        is_rtl=True,
    )
