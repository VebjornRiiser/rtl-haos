# utils.py
"""
FILE: utils.py
DESCRIPTION:
  Shared helper functions used across the project.
  - clean_mac(): Sanitizes device IDs for MQTT topics.
  - calculate_dew_point(): Math formula to calculate Dew Point from Temp/Humidity.
  - get_system_mac(): Generates a unique ID for the bridge itself based on hardware.
"""
import re
import math
import psutil  # <--- Added for reliable MAC detection

# Global cache for MAC to prevent re-reading
_SYSTEM_MAC = None

def get_system_mac():
    global _SYSTEM_MAC
    if _SYSTEM_MAC: 
        return _SYSTEM_MAC
        
    try:
        # Iterate over all network interfaces to find the real hardware address
        addrs = psutil.net_if_addrs()
        for interface_name, interface_addresses in addrs.items():
            # Skip the loopback interface (localhost)
            if interface_name == "lo":
                continue
                
            for address in interface_addresses:
                # AF_LINK is the constant for MAC Address on Linux/Unix
                if address.family == psutil.AF_LINK and address.address:
                    _SYSTEM_MAC = address.address.lower()
                    return _SYSTEM_MAC
                    
    except Exception as e:
        print(f"[WARN] Could not find MAC via psutil: {e}")

    # Fallback: FIXED value so the ID never changes randomly
    # If psutil fails, we default to this dummy address
    _SYSTEM_MAC = "00:00:00:00:00:01"
    return _SYSTEM_MAC

def clean_mac(mac):
    """Cleans up MAC/ID string for use in topic/unique IDs."""
    cleaned = re.sub(r'[^A-Za-z0-9]', '', str(mac))
    return cleaned.lower() if cleaned else "unknown"

def calculate_dew_point(temp_c, humidity):
    """Calculates Dew Point (F) using Magnus Formula."""
    if temp_c is None or humidity is None:
        return None
    if humidity <= 0:
        return None 
    try:
        b = 17.62
        c = 243.12
        gamma = (b * temp_c / (c + temp_c)) + math.log(humidity / 100.0)
        dp_c = (c * gamma) / (b - gamma)
        return round(dp_c * 1.8 + 32, 1) # Return Fahrenheit
    except Exception:
        return None