#!/usr/bin/env python3
"""
FILE: main.py
DESCRIPTION:
  The main executable script.
  - Checks dependencies.
  - Starts MQTT Handler.
  - Starts Data Processor (Throttling).
  - Starts RTL Managers (Radios).
  - Starts System Monitor.
  - UPDATED: DEBUG JSON Values are now BOLD WHITE for high contrast.
"""
import os
import sys
import re

# --- 0. FORCE COLOR ENVIRONMENT ---
os.environ["TERM"] = "xterm-256color"
os.environ["CLICOLOR_FORCE"] = "1"

import builtins
from datetime import datetime
import threading
import time
import importlib.util
import subprocess

# --- 1. GLOBAL LOGGING & COLOR SETUP ---
# Standard ANSI with Bold (1;) to force "Bright" colors on HAOS.

c_cyan    = "\033[1;36m"   # Bold Cyan (Keys / Source IDs)
c_blue    = "\033[1;34m"   # Bold Blue (Infrastructure / DEBUG Header)
c_green   = "\033[1;32m"   # Bold Green (DATA Header / INFO / Startup)
c_yellow  = "\033[1;33m"   # Bold Yellow (WARN Only)
c_red     = "\033[1;31m"   # Bold Red (ERROR)
c_white   = "\033[1;37m"   # Bold White (ALL Values: JSON & DATA)
c_dim     = "\033[37m"     # Standard White (Timestamp / Brackets)
c_reset   = "\033[0m"

_original_print = builtins.print

def get_source_color(tag_text):
    """
    Determines the color of the [Bracketed] source tag.
    """
    clean = tag_text.lower().replace("[", "").replace("]", "")
    
    # Infrastructure -> Blue (Matches System/Debug)
    if "mqtt" in clean: return c_blue
    if "rtl" in clean: return c_blue
    if "startup" in clean: return c_green
    if "nuke" in clean: return c_red
    
    # Radio Data / IDs -> Cyan
    return c_cyan

def highlight_json(text):
    """
    Simple Regex-based JSON syntax highlighter using High Contrast Palette.
    Keys = Cyan
    Values (String, Number, Bool) = White
    """
    # 1. Color Keys (Strings followed by colon) -> Cyan
    #    Pattern: "key":
    text = re.sub(r'("[^"]+")\s*:', f'{c_cyan}\\1{c_reset}:', text)
    
    # 2. Color String Values (Colon followed by string) -> White
    #    Pattern: : "value"
    text = re.sub(r':\s*("[^"]+")', f': {c_white}\\1{c_reset}', text)
    
    # 3. Color Numbers (Colon followed by digits) -> White
    #    Pattern: : 123 or : 12.34 or : -12
    text = re.sub(r':\s*(-?\d+\.?\d*)', f': {c_white}\\1{c_reset}', text)
    
    # 4. Color Booleans/Null -> White
    #    Pattern: : true, : false, : null
    text = re.sub(r':\s*(true|false|null)', f': {c_white}\\1{c_reset}', text)
    
    return text

def timestamped_print(*args, **kwargs):
    """
    Smart Logging v22 (High Contrast JSON):
    """
    now = datetime.now().strftime("%H:%M:%S")
    time_prefix = f"{c_dim}[{now}]{c_reset}"
    
    msg = " ".join(map(str, args))
    lower_msg = msg.lower()
    
    # --- 1. DETERMINE HEADER LEVEL ---
    header = f"{c_green}INFO: {c_reset}" # Default
    special_formatting_applied = False
    
    # A. ERROR (Red)
    if any(x in lower_msg for x in ["error", "critical", "failed", "crashed"]):
        header = f"{c_red}ERROR:{c_reset}"
        msg = msg.replace("CRITICAL:", "").replace("ERROR:", "").strip()

    # B. WARNING (Yellow)
    elif "warning" in lower_msg:
        header = f"{c_yellow}WARN: {c_reset}"
        msg = msg.replace("WARNING:", "").strip()

    # C. DEBUG (Blue)
    elif "debug" in lower_msg:
        header = f"{c_blue}DEBUG:{c_reset}"
        msg = msg.replace("[DEBUG]", "").replace("[debug]", "").strip()
        
        # *** APPLY JSON HIGHLIGHTING (Values -> White) ***
        if "{" in msg and "}" in msg:
            msg = highlight_json(msg)

    # D. DATA (Green -> Cyan -> White)
    elif "-> tx" in lower_msg:
        header = f"{c_green}DATA: {c_reset}"
        msg = msg.replace("-> TX", "").strip()
        
        # Parse specialized format
        match = re.match(r".*?(\[.*?\]):\s+(.*)", msg)
        if match:
            src_tag = match.group(1)
            val = match.group(2)
            msg = f"{c_cyan}{src_tag}{c_reset} {c_white}{val}{c_reset}"
            special_formatting_applied = True

    # --- 2. UNIVERSAL SOURCE DETECTION ---
    if not special_formatting_applied:
        match = re.match(r"^(\[.*?\])\s*(.*)", msg)
        if match:
            source_tag = match.group(1)
            rest_of_msg = match.group(2)
            
            # Clean "RX:"
            rest_of_msg = rest_of_msg.replace("RX:", "").strip()
            
            # Color Source
            s_color = get_source_color(source_tag)
            msg = f"{s_color}{source_tag}{c_reset} {rest_of_msg}"

    # Print Final
    _original_print(f"{time_prefix} {header} {msg}", flush=True, **kwargs)

# Override the built-in print
builtins.print = timestamped_print
# ------------------------------------

# --- PRE-FLIGHT DEPENDENCY CHECK ---
def check_dependencies():
    if not subprocess.run(["which", "rtl_433"], capture_output=True).stdout:
        print("CRITICAL: 'rtl_433' binary not found. Please install it.")
        sys.exit(1)

    if importlib.util.find_spec("paho") is None:
        print("CRITICAL: Python dependency 'paho-mqtt' not found.")
        sys.exit(1)

check_dependencies()

import config
from mqtt_handler import HomeNodeMQTT
from utils import get_system_mac
from system_monitor import system_stats_loop
from data_processor import DataProcessor
from rtl_manager import rtl_loop, discover_rtl_devices

def get_version():
    """Retrieves the version string from config.yaml."""
    try:
        cfg_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "config.yaml")
        if os.path.exists(cfg_path):
            with open(cfg_path, "r") as f:
                for line in f:
                    if line.strip().startswith("version:"):
                        ver = line.split(":", 1)[1].strip().replace('"', '').replace("'", "")
                        return f"v{ver}"
    except Exception:
        pass
    return "Unknown"

def show_logo(version):
    """Prints the ASCII logo (Blue) and Subtitle (Cyan/Yellow)."""
    logo_lines = [
        r"   ____  _____  _         _   _    _    ___  ____  ",
        r"  |  _ \|_   _|| |       | | | |  / \  / _ \/ ___| ",
        r"  | |_) | | |  | |  ___  | |_| | / _ \| | | \___ \ ",
        r"  |  _ <  | |  | | |___| |  _  |/ ___ \ |_| |___) |",
        r"  |_| \_\ |_|  |_____|   |_| |_/_/   \_\___/|____/ "
    ]
    
    # 1. Print Logo: Apply Blue to EACH line individually
    for line in logo_lines:
        sys.stdout.write(f"{c_blue}{line}{c_reset}\n")
    
    # 2. SPACER
    sys.stdout.write("\n")
    
    # 3. Print Subtitle: Cyan & Yellow
    sys.stdout.write(
        f"{c_cyan}>>> RTL-SDR Bridge for Home Assistant ({c_reset}"
        f"{c_yellow}{version}{c_reset}"
        f"{c_cyan}) <<<{c_reset}\n"
    )
    
    # 4. Separator
    sys.stdout.write("\n")
    sys.stdout.write("\n")
    sys.stdout.flush()

def main():
    ver = get_version()
    show_logo(ver)
    time.sleep(3)

    # 2. START MQTT
    mqtt_handler = HomeNodeMQTT(version=ver)
    mqtt_handler.start()

    # 3. START DATA PROCESSOR
    processor = DataProcessor(mqtt_handler)
    threading.Thread(target=processor.start_throttle_loop, daemon=True).start()

    # 4. GET SYSTEM IDENTITY
    sys_id = get_system_mac().replace(":", "").lower() 
    sys_model = config.BRIDGE_NAME
    sys_name = f"{sys_model} ({sys_id})"

    # --- HARDWARE MAPPING ---
    print("[STARTUP] Scanning USB bus for RTL-SDR devices...")
    detected_devices = discover_rtl_devices()
    
    serial_to_index = {}
    if detected_devices:
        for d in detected_devices:
            if 'id' in d and 'index' in d:
                serial_to_index[str(d['id'])] = d['index']
        print(f"[STARTUP] Hardware Map: {serial_to_index}")
    else:
        print("[STARTUP] Warning: No hardware detected during scan.")

    # 5. START RTL RADIO THREADS
    rtl_config = getattr(config, "RTL_CONFIG", None)

    if rtl_config:
        print(f"[STARTUP] Loading {len(rtl_config)} radios from manual config.")
        for radio in rtl_config:
            target_id = radio.get("id") 
            if target_id: target_id = str(target_id).strip()
            
            if target_id and target_id in serial_to_index:
                idx = serial_to_index[target_id]
                radio['index'] = idx
                r_name = radio.get("name", "Unknown")
                print(f"[STARTUP] Matched Config '{r_name}' (Serial {target_id}) to Physical Index {idx}")
            else:
                if target_id:
                     print(f"[STARTUP] Warning: Configured Serial {target_id} not found in scan. Driver may fail.")

            threading.Thread(
                target=rtl_loop,
                args=(radio, mqtt_handler, processor, sys_id, sys_model),
                daemon=True,
            ).start()
            time.sleep(5)
            
    else:
        if detected_devices:
            target_radio = detected_devices[0]
            print(f"[STARTUP] Auto-detected {len(detected_devices)} radios.")
            print(f"[STARTUP] Unconfigured Mode: Selecting first device only ({target_radio['name']}).")
            
            radio_setup = {
                "freq": config.RTL_DEFAULT_FREQ,
                "hop_interval": config.RTL_DEFAULT_HOP_INTERVAL,
                "rate": config.RTL_DEFAULT_RATE
            }
            radio_setup.update(target_radio)

            threading.Thread(
                target=rtl_loop,
                args=(radio_setup, mqtt_handler, processor, sys_id, sys_model),
                daemon=True,
            ).start()
        else:
            print("[STARTUP] No serials detected. Defaulting to generic device '0'.")
            auto_radio = {
                "name": "RTL_auto", "id": "0",
                "freq": config.RTL_DEFAULT_FREQ,             
                "hop_interval": config.RTL_DEFAULT_HOP_INTERVAL,
                "rate": config.RTL_DEFAULT_RATE
            }
            threading.Thread(
                target=rtl_loop,
                args=(auto_radio, mqtt_handler, processor, sys_id, sys_model),
                daemon=True,
            ).start()

    # 6. START SYSTEM MONITOR
    threading.Thread(
        target=system_stats_loop, 
        args=(mqtt_handler, sys_id, sys_model), 
        daemon=True
    ).start()

    # 7. MAIN LOOP
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Stopping MQTT...")
        mqtt_handler.stop()

if __name__ == "__main__":
    main()