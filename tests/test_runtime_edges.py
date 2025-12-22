import inspect
import types


def test_utils_dewpoint_invalid_and_radio_config_warning():
    import utils

    assert utils.calculate_dew_point(temp_c="bad", humidity=50) is None

    warns = utils.validate_radio_config({"freq": "433.92M", "hop_interval": 10})
    assert any("hop" in w.lower() for w in warns)


def test_data_processor_has_a_dispatch_method_and_can_call_send_sensor(mocker):
    import data_processor
    import config

    sent = []

    class DummyMQTT:
        def send_sensor(self, *a, **k):
            sent.append((a, k))

    mocker.patch.object(config, "RTL_THROTTLE_INTERVAL", 0)

    dp = data_processor.DataProcessor(DummyMQTT())

    # Find a plausible "ingest a reading" method without assuming its name
    candidate = None
    for name in ("dispatch_reading", "process_reading", "handle_reading", "ingest_reading"):
        if hasattr(dp, name):
            candidate = getattr(dp, name)
            break

    assert candidate is not None, "DataProcessor should expose a reading ingest method"

    sig = inspect.signature(candidate)
    kwargs = {}
    for pname, p in sig.parameters.items():
        if pname == "self":
            continue
        lp = pname.lower()
        if "field" in lp:
            kwargs[pname] = "temp_c"
        elif "value" in lp:
            kwargs[pname] = 1.23
        elif "unit" in lp:
            kwargs[pname] = "°C"
        elif ("device" in lp and "id" in lp) or lp in ("device_id", "id"):
            kwargs[pname] = "dev"
        elif "name" in lp or "model" in lp:
            kwargs[pname] = "Bridge"
        elif lp == "is_rtl":
            kwargs[pname] = True
        elif p.default is not inspect._empty:
            pass
        else:
            kwargs[pname] = None

    candidate(**kwargs)
    assert sent, "Expected DataProcessor to forward to mqtt.send_sensor when throttle=0"
