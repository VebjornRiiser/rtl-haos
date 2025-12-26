# Development

How to run tests and work on RTL-HAOS locally.

## Testing

### Unit tests (default)

Run the normal unit test suite (fast, deterministic):

```bash
pytest
```

### Opt-in `rtl_433` integration tests

These tests execute the external `rtl_433` binary and are **skipped by default** (so GitHub Actions / CI stays green).

Run the integration tests:

```bash
RUN_RTL433_TESTS=1 pytest -m integration
```

Run only the replay test:

```bash
RUN_RTL433_TESTS=1 pytest -m integration -k rtl433_replay
```

#### Recording a replay fixture (recommended)

Replay fixtures live in `tests/fixtures/rtl433/` (see `tests/fixtures/rtl433/README.md`). Capture files like `.cu8` are intentionally **gitignored**.

Record a short capture:

```bash
mkdir -p tests/fixtures/rtl433
./scripts/record_rtl433_fixture.sh 433.92M 250k 20 tests/fixtures/rtl433/sample.cu8
```

Sanity-check the capture decodes:

```bash
rtl_433 -r tests/fixtures/rtl433/sample.cu8 -F json | head
```

### Opt-in hardware smoke tests (RTL-SDR required)

These require an RTL-SDR device available to the test host. They do **not** require receiving RF events; they only verify `rtl_433` starts and exits cleanly.

```bash
RUN_HARDWARE_TESTS=1 pytest -m hardware
```

### Run everything locally (unit + integration + hardware)

```bash
RUN_RTL433_TESTS=1 RUN_HARDWARE_TESTS=1 pytest
```

### Script argument guardrails (no hardware)

The fixture-recording script supports unit suffixes and a dry-run mode:

```bash
./scripts/record_rtl433_fixture.sh --dry-run 433.92M 250k 10 tests/fixtures/rtl433/test.cu8
```

If you forget a suffix (e.g. `433.92` instead of `433.92M`, or `250` instead of `250k`), the script will fail fast with a helpful hint.
