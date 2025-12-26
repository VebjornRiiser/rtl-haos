#!/usr/bin/env bash
set -euo pipefail

# Convenience runner for opt-in integration/hardware tests.

RUN_RTL433_TESTS=1 pytest -m integration "$@"
