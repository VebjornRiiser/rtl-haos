#!/usr/bin/env sh
set -eu

if ! command -v rtl_433 >/dev/null 2>&1; then
  echo "[RTL433][FAIL] rtl_433 not found"
  exit 1
fi

echo "[RTL433] Starting rtl_433 briefly (JSON output)..."
OUT="$(timeout 8 rtl_433 -d 0 -F json 2>&1 || true)"
echo "$OUT"

# Fail fast errors
echo "$OUT" | grep -qi "No supported devices found" && {
  echo "[RTL433][FAIL] No supported RTL-SDR devices found."
  exit 1
}
echo "$OUT" | grep -qi "usb_open error" && {
  echo "[RTL433][FAIL] USB open error."
  exit 1
}

# Confirm it actually started with a device
echo "$OUT" | grep -Eqi "Using device|Found .* tuner|Rafael Micro|Realtek RTL" && {
  echo "[RTL433][OK] rtl_433 started and opened the dongle."
  exit 0
}

echo "[RTL433][FAIL] rtl_433 did not show expected startup/device lines."
exit 1
