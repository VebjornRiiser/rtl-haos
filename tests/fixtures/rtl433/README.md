# rtl_433 replay fixtures

Place one or more rtl_433 replay recordings in this directory to enable the replay-mode integration test:

- `tests/test_rtl433_integration.py::test_rtl433_replay_fixture_emits_json`

## Optional: field_meta coverage guard (JSON fixtures)

If you save *rtl_433 JSON lines* output into this folder, the unit test
`tests/test_field_meta_fixture_unknowns.py` will verify that every field the
add-on would publish has a `FIELD_META` (or model-specific override) entry.

Example capture (20 seconds):

```bash
rtl_433 -F json -T 20 > tests/fixtures/rtl433/events.jsonl
pytest -q tests/test_field_meta_fixture_unknowns.py
```

If the test fails, it prints paste-ready `FIELD_META` stubs for any missing keys.

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
