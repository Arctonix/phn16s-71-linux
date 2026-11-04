# 60 Hz / 120 Hz for the Acer Predator Helios Neo 16S AI OLED (PHN16S-71) on Linux

The PHN16S-71's 2560x1600 OLED is "locked" at 240 Hz: Windows and Linux only offer 240 Hz, even on
battery, and Acer support has said there is no setting or update to change it. That is the most common
complaint about this laptop's battery life.

**The panel is not locked.** Its factory EDID (the list of modes the panel reports to the computer)
simply contains only one timing: 2560x1600 @ 240 Hz. This repo adds 60 Hz and 120 Hz timings derived from
the native one, so the panel really runs at 60 Hz (it does not just drop frames).

## Results

Measured on battery, idle desktop, same brightness, RTX powered off (Fedora 45, kernel 7.2.15):

| Refresh rate        | Battery draw |
|---------------------|-------------:|
| 240 Hz (+VRR)       | **~37 W**    |
| 60 Hz (+VRR)        | **~23–24 W** |

About **13 W less at idle**, roughly a third of total system draw.
With the ~76 Wh battery that is the difference between ~2 h and ~3.2 h of idle runtime.

All three rates keep VRR (adaptive sync) and are offered in GNOME Settings > Displays:
`60`, `120`, `240` Hz, each with and without VRR.

## How it works

- The native timing is 2560x1600, 1125.275 MHz pixel clock, htotal 2640, vtotal 1776 (240 Hz).
- 120 Hz and 60 Hz use **the same pixel clock and horizontal timing** and only lengthen the vertical blank
  (vtotal 3552 and 7104). That is exactly what VRR already does to this panel at runtime, so the panel is
  driven within its normal operating range.
- The timings go into the DisplayID 2.0 Type VII block of the EDID extension. To make room, two
  informational blocks are dropped (Product Identification and Display Interface Features); everything
  else, including the panel's Adaptive Sync block, is kept.
- `tools/make-edid.py` does this from the panel's own EDID; `edid/` has the factory EDID and the result.

## Install (Fedora)

Requirements: Intel iGPU driving the panel (i915, the default "Optimus/hybrid" mode), and a kernel with
`CONFIG_DRM_LOAD_EDID_FIRMWARE=y` (Fedora has it).

```bash
git clone <this repo> && cd phn16s-71-linux
sudo ./install-edid.sh
reboot
```

The script reads your panel's EDID, refuses to run if it is not a Samsung ATNA60DL03-0, builds the
modified EDID, puts it in the initramfs and adds `drm.edid_firmware=eDP-1:edid/phn16s-71-60-120-240.bin`
to the kernel command line. Undo with `sudo ./uninstall-edid.sh` and reboot.

Check it worked:

```bash
cmp /sys/class/drm/card1-eDP-1/edid /usr/lib/firmware/edid/phn16s-71-60-120-240.bin && echo active
journalctl -k -b | grep -i "fixed mode"   # i915 lists 60, 120 and 240 Hz
```

### Other distributions

1. Build the file: `python3 tools/make-edid.py /sys/class/drm/card1-eDP-1/edid phn16s-71-60-120-240.bin`
   (before any override is active), and copy it to `/usr/lib/firmware/edid/`.
2. Include it in the initramfs (i915 loads early):
   - Arch (mkinitcpio): add the path to `FILES=()` in `/etc/mkinitcpio.conf`, then `mkinitcpio -P`.
   - Debian/Ubuntu (initramfs-tools): add a hook that runs `copy_file firmware <path>`, then `update-initramfs -u`.
3. Add `drm.edid_firmware=eDP-1:edid/phn16s-71-60-120-240.bin` to the kernel command line.

### Windows

Not tested. The same EDID file can in principle be loaded with CRU (Custom Resolution Utility, "Import")
as an EDID override for the internal panel. If you try it, please report back.

## Extras in this repo

Optional helpers written while setting this laptop up. Each folder has the script and its systemd unit.

- **`extras/refresh-on-battery`**: switches the internal panel to 60 Hz when unplugged and back to your
  previous mode when plugged in (GNOME, user service). Only acts on plug/unplug, so manual choices are kept.
- **`extras/acer-mode-key`**: makes the power-mode key work. On this model the key sends a vendor HID report
  (`04 85 ff`, usage page 0x88) that the kernel ignores. The service cycles the firmware profiles
  Eco → Quiet → Balanced → Performance → Turbo (Eco/Quiet/Balanced on battery) with a notification,
  and drops Performance/Turbo to Balanced on unplug.
- **`extras/battery-health`**: keeps Acer's battery health mode (~80 % charge limit) on at boot.

See [docs/notes.md](docs/notes.md) for measured firmware power limits, fan behaviour and other findings.

## Tested on

- Acer Predator Helios Neo 16S AI PHN16S-71, BIOS V1.26, Core Ultra 9 275HX, RTX 5070 Ti Laptop
- Panel Samsung ATNA60DL03-0 (EDID manufacturer SDC, product 0x41AB)
- Fedora 45, kernel 7.2.15, GNOME (Mutter 51), Wayland, NVIDIA 615.78 (hybrid mode)

One machine so far. Use at your own risk; the uninstall script restores the factory EDID.

## License

MIT, see [LICENSE](LICENSE).
