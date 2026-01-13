#!/usr/bin/env bash
set -euo pipefail

echo "[HOST] Date: $(date -Is || date)"
echo "[HOST] Kernel/Arch: $(uname -a || true)"
echo "[HOST] User: $(id -un) (uid=$(id -u)) groups: $(id -nG || true)"

# Docker sanity
if ! command -v docker >/dev/null 2>&1; then
  echo "[HOST][FAIL] docker is not installed or not on PATH"
  exit 1
fi

echo "[HOST] docker version:"
docker version || { echo "[HOST][FAIL] docker version failed (daemon reachable?)"; exit 1; }

echo "[HOST] docker info (arch/os):"
docker info --format 'arch={{.Architecture}} os={{.OperatingSystem}} rootless={{.SecurityOptions}}' || true

# Platform forcing (common cause of exec format error)
if [[ -n "${DOCKER_DEFAULT_PLATFORM:-}" ]]; then
  echo "[HOST][WARN] DOCKER_DEFAULT_PLATFORM is set to: ${DOCKER_DEFAULT_PLATFORM}"
  if [[ "${DOCKER_DEFAULT_PLATFORM}" == "linux/amd64" ]]; then
    echo "[HOST][WARN] linux/amd64 on Raspberry Pi/ARM will often cause 'exec format error' unless QEMU/binfmt is configured."
  fi
fi

# Compose platform directives (if compose is available)
if docker compose version >/dev/null 2>&1; then
  echo "[HOST] docker compose version:"
  docker compose version || true
fi

# USB visibility on the host
if [[ ! -d /dev/bus/usb ]]; then
  echo "[HOST][WARN] /dev/bus/usb does not exist on host (is this a VM/containerized runner?)"
else
  echo "[HOST] /dev/bus/usb present"
fi

# lsusb availability
if command -v lsusb >/dev/null 2>&1; then
  echo "[HOST] lsusb output (filtered for RTL):"
  lsusb | grep -Ei 'rtl|realtek|0bda:|2832|2838' || echo "[HOST][WARN] No obvious RTL-SDR device found in lsusb output"
else
  echo "[HOST][WARN] lsusb not installed (apt-get install usbutils) — skipping dongle presence check"
fi

# Kernel DVB driver often grabs RTL-SDR sticks
if command -v lsmod >/dev/null 2>&1; then
  if lsmod | grep -q '^dvb_usb_rtl28xxu'; then
    echo "[HOST][WARN] Kernel module dvb_usb_rtl28xxu is loaded. This can prevent rtl-sdr/rtl_433 from opening the device."
    echo "[HOST][INFO] To blacklist:"
    echo "  echo 'blacklist dvb_usb_rtl28xxu' | sudo tee /etc/modprobe.d/blacklist-rtl.conf && sudo reboot"
  fi
fi

# Competing processes
if command -v pgrep >/dev/null 2>&1; then
  if pgrep -x rtl_433 >/dev/null 2>&1; then
    echo "[HOST][WARN] rtl_433 is already running on the host. It may hold exclusive access to the dongle."
    pgrep -ax rtl_433 || true
  fi
fi

echo "[HOST][OK] Host sanity checks complete."
