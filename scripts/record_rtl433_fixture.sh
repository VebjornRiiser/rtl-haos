#!/usr/bin/env bash
set -euo pipefail

# Record rtl_sdr I/Q capture for rtl_433 replay tests.
#
# Supports BOTH calling styles:
#   A) ./scripts/record_rtl433_fixture.sh <freq> <rate> <seconds> <output_path>
#   B) ./scripts/record_rtl433_fixture.sh <output_path> <seconds> [freq] [rate]
#
# freq supports suffix: k/M/G (e.g. 433.92M, 915M, 433920000)
# rate supports suffix: k/M/G (e.g. 250k, 1M, 250000)
#
# Use --dry-run to validate/print parsed args without touching hardware.

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
  shift
fi

is_int() { [[ "${1:-}" =~ ^[0-9]+$ ]]; }
looks_float() { [[ "${1:-}" =~ ^[0-9]+(\.[0-9]+)?$ ]]; }
looks_suffixed() { [[ "${1:-}" =~ ^[0-9]+(\.[0-9]+)?[kKmMgG]$ ]]; }

parse_with_suffix_hz() {
  local v="${1:-}"
  local label="${2:-value}"

  # Require either:
  #  - plain integer (Hz), or
  #  - number with k/M/G suffix (allow decimals)
  #
  # If user provides a float without suffix (e.g. 433.92), that's ambiguous; error.
  if looks_float "$v" && ! is_int "$v"; then
    echo "ERROR: ${label} '${v}' is ambiguous (missing unit suffix). Use e.g. 433.92M or integer Hz." >&2
    return 2
  fi

  if is_int "$v"; then
    echo "$v"
    return 0
  fi

  if looks_suffixed "$v"; then
    python - "$v" <<'PY'
import sys, re
s=sys.argv[1]
m=re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)([kKmMgG])", s)
num=float(m.group(1))
suf=m.group(2).lower()
mult={"k":1e3,"m":1e6,"g":1e9}[suf]
print(int(round(num*mult)))
PY
    return 0
  fi

  echo "ERROR: ${label} '${v}' is invalid. Use integer Hz or k/M/G suffix (e.g. 250k, 433.92M)." >&2
  return 2
}

usage() {
  cat >&2 <<'EOF'
Usage:
  ./scripts/record_rtl433_fixture.sh [--dry-run] <freq> <rate> <seconds> <output_path>
  ./scripts/record_rtl433_fixture.sh [--dry-run] <output_path> <seconds> [freq] [rate]

Examples:
  ./scripts/record_rtl433_fixture.sh 433.92M 250k 20 tests/fixtures/rtl433/sample.cu8
  ./scripts/record_rtl433_fixture.sh tests/fixtures/rtl433/sample.cu8 20 433.92M 250k
EOF
}

# Defaults
FREQ_IN="433.92M"
RATE_IN="250k"
SECONDS="20"
OUT_PATH="tests/fixtures/rtl433/sample.cu8"

if [[ $# -lt 2 ]]; then
  usage
  exit 2
fi

# Decide which calling style we got:
# Style A: <freq> <rate> <seconds> <out>
# Style B: <out> <seconds> [freq] [rate]
if [[ "${1:-}" == *"/"* || "${1:-}" == *.cu8 || "${1:-}" == *.cs8 || "${1:-}" == *.wav ]]; then
  # Style B
  OUT_PATH="$1"
  SECONDS="$2"
  FREQ_IN="${3:-$FREQ_IN}"
  RATE_IN="${4:-$RATE_IN}"
else
  # Style A
  FREQ_IN="$1"
  RATE_IN="$2"
  SECONDS="${3:-$SECONDS}"
  OUT_PATH="${4:-$OUT_PATH}"
fi

if ! is_int "$SECONDS"; then
  echo "ERROR: seconds '${SECONDS}' must be an integer." >&2
  exit 2
fi

FREQ_HZ="$(parse_with_suffix_hz "$FREQ_IN" "freq")"
RATE_HZ="$(parse_with_suffix_hz "$RATE_IN" "sample rate")"

# Guardrail: a plain integer sample rate is interpreted as Hz, but values like "250"
# are almost always a missing "k" (250k). rtl_sdr also can't operate at rates this low.
if is_int "$RATE_IN"; then
  if (( RATE_HZ < 10000 )); then
    echo "ERROR: sample rate '${RATE_IN}' is too small (interpreted as ${RATE_HZ} Hz). Did you mean '${RATE_IN}k'?" >&2
    exit 2
  fi
fi


mkdir -p "$(dirname "$OUT_PATH")"
SAMPLES=$(( RATE_HZ * SECONDS ))

echo "Recording rtl_sdr capture:"
echo "  freq_in:   ${FREQ_IN}"
echo "  rate_in:   ${RATE_IN}"
echo "  freq_hz:   ${FREQ_HZ}"
echo "  rate_hz:   ${RATE_HZ}"
echo "  time:      ${SECONDS} s"
echo "  samples:   ${SAMPLES}"
echo "  out:       ${OUT_PATH}"

if [[ "$DRY_RUN" == "1" ]]; then
  exit 0
fi

if ! command -v rtl_sdr >/dev/null 2>&1; then
  echo "ERROR: rtl_sdr not found. Install rtl-sdr tools first." >&2
  exit 1
fi

rtl_sdr -f "${FREQ_HZ}" -s "${RATE_HZ}" -n "${SAMPLES}" "${OUT_PATH}"

echo
echo "Done. Now try:"
echo "  rtl_433 -r ${OUT_PATH} -F json | head"
echo "  RUN_RTL433_TESTS=1 pytest -m integration -k rtl433_replay"
