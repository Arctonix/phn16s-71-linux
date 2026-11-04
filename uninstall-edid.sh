#!/usr/bin/env bash
# Remove the PHN16S-71 EDID override (back to the factory 240 Hz-only EDID).
set -euo pipefail
NAME=phn16s-71-60-120-240.bin
[[ $EUID -eq 0 ]] || { echo "Run with sudo." >&2; exit 1; }

# Remove whatever drm.edid_firmware argument is present on the boot entries.
for a in $(grep -oE 'drm\.edid_firmware=[^ ]+' /proc/cmdline; grubby --info=ALL 2>/dev/null | grep -oE 'drm\.edid_firmware=[^ "]+' ); do
    grubby --update-kernel=ALL --remove-args="$a" || true
done
[[ -f /etc/kernel/cmdline ]] && sed -i -E 's/ ?drm\.edid_firmware=[^ ]+//g' /etc/kernel/cmdline
rm -f /etc/dracut.conf.d/99-phn16s-71-edid.conf "/usr/lib/firmware/edid/$NAME"
dracut -f "/boot/initramfs-$(uname -r).img" "$(uname -r)"
echo "Removed. Reboot to return to the factory EDID."
