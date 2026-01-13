#!/usr/bin/env sh
set -eu

echo "[SMOKE] uname: $(uname -a || true)"
echo "[SMOKE] Checking USB bus mount..."
if [ ! -d /dev/bus/usb ]; then
  echo "[SMOKE][FAIL] /dev/bus/usb is missing (USB passthrough not enabled?)"
  exit 1
fi

# rtl_test comes from the rtl-sdr package (Alpine: rtl-sdr)
if ! command -v rtl_test >/dev/null 2>&1; then
  echo "[SMOKE][FAIL] rtl_test not found (rtl-sdr package missing?)"
  exit 1
fi

echo "[SMOKE] Running rtl_test -t (open/tune test)..."
OUT="$(timeout 8 rtl_test -t 2>&1 || true)"
echo "$OUT"

echo "$OUT" | grep -qi "No supported devices found" && {
  echo "[SMOKE][FAIL] No supported RTL-SDR devices found."
  exit 1
}
echo "$OUT" | grep -qi "usb_open error" && {
  echo "[SMOKE][FAIL] USB open error (permissions / driver / passthrough)."
  exit 1
}

echo "$OUT" | grep -Eqi "Using device|Found .* tuner|Rafael Micro|Realtek RTL" && {
  echo "[SMOKE][OK] RTL-SDR opened successfully."
  exit 0
}

echo "[SMOKE][FAIL] Could not confirm device opened (unexpected rtl_test output)."
exit 1
