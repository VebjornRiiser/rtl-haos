# rtl_433 replay fixtures

Place one or more rtl_433 replay recordings in this directory to enable the replay-mode integration test:

- `tests/test_rtl433_integration.py::test_rtl433_replay_fixture_emits_json`

## Quick start: record a fixture (hardware required)

You can record raw I/Q samples with `rtl_sdr` and then replay them with rtl_433 using `-r`.

Example (433.92 MHz, 2 Msps, 20 seconds):

```bash
mkdir -p tests/fixtures/rtl433
rtl_sdr -f 433920000 -s 2000000 -n 40000000 tests/fixtures/rtl433/sample_433_2msps_20s.cu8
```

Then run the replay test:

```bash
RUN_RTL433_TESTS=1 pytest -m integration -k rtl433_replay
```

## Notes

- Exact supported replay formats vary by rtl_433 build and distro.
- If rtl_433 cannot decode your recording, try:
  - recording on the correct center frequency and sample rate,
  - increasing gain,
  - recording longer,
  - or using a different device/protocol.
