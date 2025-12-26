# Multi-Radio Setup

This page is duplicated from the README for easier linking.
## Radio status entity naming

RTL-HAOS publishes a host-level **Radio Status** entity per radio (e.g. `radio_status_101`).

- By default, the suffix is derived from the radio's `id` (serial), then `index`, then the internal `slot`.
- If you want to keep legacy numbering like `radio_status_0` / `radio_status_1`, set `status_id` in each `rtl_config` entry.


## 🔧 Advanced: Multi-Radio Setup (Critical)

If you plan to use multiple RTL-SDR dongles (e.g., one for 433MHz and one for 915MHz), you **must** assign them unique serial numbers. By default, most dongles share the serial `00000001`, which causes conflicts where the system swaps "Radio A" and "Radio B" after a reboot.

### ⚠️ Step 1: Safety First (Backup EEPROM)

Before modifying your hardware, it is good practice to dump the current EEPROM image. This allows you to restore the dongle if something goes wrong.

1.  Stop any running services (e.g., `sudo systemctl stop rtl-bridge`).
2.  Plug in **ONE** dongle.
3.  Run the backup command:
    ```bash
    rtl_eeprom -r original_backup.bin
    ```
    _This saves a binary file `original_backup.bin` to your current folder._

### Step 2: Set New Serial Number

1.  With only one dongle plugged in, run:
    ```bash
    rtl_eeprom -s 101
    ```
    _(Replace `101` with your desired ID, e.g., 102, 103)._
2.  **Unplug and Replug** the dongle to apply the change.
3.  Verify the new serial:
    ```bash
    rtl_test
    # Output should show: SN: 101
    ```
4.  Repeat for your other dongles (one at a time).

> **Restoration:** If you ever need to restore the backup, use: `rtl_eeprom -w original_backup.bin`

---

