#!/usr/bin/env sh
set -eu

if ! command -v rtl_test >/dev/null 2>&1; then
  echo "[STREAM][FAIL] rtl_test not found"
  exit 1
fi

echo "[STREAM] Running rtl_test -t for a longer window to catch dropouts..."
OUT="$(timeout 15 rtl_test -t 2>&1 || true)"
echo "$OUT"

# Hard fails
echo "$OUT" | grep -qi "No supported devices found" && {
  echo "[STREAM][FAIL] No supported RTL-SDR devices found."
  exit 1
}
echo "$OUT" | grep -qi "usb_open error" && {
  echo "[STREAM][FAIL] USB open error."
  exit 1
}

# Dropout indicators (best-effort; different builds vary slightly)
echo "$OUT" | grep -Eqi "lost at least|dropped|overrun|underrun" && {
  echo "[STREAM][FAIL] Sample dropouts detected (USB power/throughput/CPU contention)."
  exit 1
}

echo "$OUT" | grep -Eqi "Using device|Found .* tuner|Rafael Micro|Realtek RTL" && {
  echo "[STREAM][OK] No obvious dropouts reported."
  exit 0
}

echo "[STREAM][WARN] Could not confirm device signature in output; treating as failure for determinism."
exit 1
