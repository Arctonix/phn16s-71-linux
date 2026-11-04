#!/usr/bin/env bash
# Add 60 Hz and 120 Hz modes to the PHN16S-71 OLED (Samsung ATNA60DL03-0) on Linux.
#
# - Reads YOUR panel's own EDID and builds the modified one from it (tools/make-edid.py).
# - Refuses to run on any other panel.
# - Puts the file in the initramfs (i915 loads before the root filesystem is mounted)
#   and adds drm.edid_firmware=<connector>:edid/<file> to the kernel command line.
#
# Written for Fedora (dracut + grubby). See README.md for other distributions.
# Undo with ./uninstall-edid.sh
set -euo pipefail

NAME=phn16s-71-60-120-240.bin
FW_DIR=/usr/lib/firmware/edid
DRACUT_CONF=/etc/dracut.conf.d/99-phn16s-71-edid.conf
HERE="$(cd "$(dirname "$0")" && pwd)"

[[ $EUID -eq 0 ]] || { echo "Run with sudo." >&2; exit 1; }
command -v dracut >/dev/null && command -v grubby >/dev/null || {
    echo "This script is for Fedora-style systems (dracut + grubby). See README.md for manual steps." >&2; exit 1; }

conn_dir=$(ls -d /sys/class/drm/card*-eDP-* 2>/dev/null | head -1)
[[ -n "$conn_dir" ]] || { echo "No eDP panel found." >&2; exit 1; }
connector=$(basename "$conn_dir" | sed -E 's/^card[0-9]+-//')  # card1-eDP-1 -> eDP-1

if grep -q "drm.edid_firmware" /proc/cmdline; then
    echo "An EDID override is already active (drm.edid_firmware on the kernel command line)." >&2
    echo "Run ./uninstall-edid.sh, reboot, then run this again so the panel's real EDID can be read." >&2
    exit 1
fi

tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
cat "$conn_dir/edid" > "$tmp/panel.bin"
# Manufacturer + product code (bytes 8-11) must be Samsung SDC 0x41AB (ATNA60DL03-0).
if [[ "$(xxd -s 8 -l 4 -p "$tmp/panel.bin")" != "$(xxd -s 8 -l 4 -p "$HERE/edid/stock-ATNA60DL03-0.bin")" ]]; then
    echo "This panel is not a Samsung ATNA60DL03-0. Not touching it." >&2; exit 1
fi
if ! cmp -s "$tmp/panel.bin" "$HERE/edid/stock-ATNA60DL03-0.bin"; then
    echo "Note: your panel's EDID differs slightly from the one in this repo; building from yours."
fi

python3 "$HERE/tools/make-edid.py" "$tmp/panel.bin" "$tmp/$NAME"
install -Dm644 "$tmp/$NAME" "$FW_DIR/$NAME"
printf 'install_items+=" %s/%s "\n' "$FW_DIR" "$NAME" > "$DRACUT_CONF"
command -v restorecon >/dev/null && restorecon "$FW_DIR/$NAME" "$DRACUT_CONF" || true

arg="drm.edid_firmware=$connector:edid/$NAME"
echo "Adding kernel argument: $arg"
grubby --update-kernel=ALL --args="$arg"
if [[ -f /etc/kernel/cmdline ]] && ! grep -q drm.edid_firmware /etc/kernel/cmdline; then
    sed -i "\$ s|\$| $arg|" /etc/kernel/cmdline   # used for future kernels
fi

echo "Rebuilding the initramfs for $(uname -r) ..."
dracut -f "/boot/initramfs-$(uname -r).img" "$(uname -r)"
lsinitrd "/boot/initramfs-$(uname -r).img" | grep -q "$NAME" || { echo "EDID file missing from initramfs!" >&2; exit 1; }

echo
echo "Done. Reboot, then pick 60 / 120 / 240 Hz in Settings > Displays."
echo "Check after reboot:  cmp /sys/class/drm/$(basename "$conn_dir")/edid $FW_DIR/$NAME && echo override active"
