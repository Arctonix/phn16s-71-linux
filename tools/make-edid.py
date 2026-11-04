#!/usr/bin/env python3
"""Add lower refresh rates to a DisplayID 2.0 EDID that only lists one timing.

Made for the Samsung ATNA60DL03-0 OLED in the Acer Predator Helios Neo 16S AI
(PHN16S-71), whose factory EDID lists only 2560x1600 @ 240 Hz.

Each extra mode reuses the native timing (same pixel clock, same horizontal
timing) and only stretches the vertical blank, the same way VRR does. The panel
is therefore driven exactly as it already is under VRR, just at a fixed rate.

To make room in the 128-byte DisplayID extension, the Product Identification
(0x20) and Display Interface Features (0x26) blocks are dropped. Everything else
is kept, including the Adaptive Sync block (panel VRR range 60-240 Hz).

Usage:
  make-edid.py STOCK.bin OUT.bin [--rates 60,120,240] [--preferred 60]
  make-edid.py --check FILE.bin        # print the timings in FILE.bin
"""
import argparse
import sys

TAG_TYPE_VII = 0x22
# Dropped to make room: Product Identification (0x20) and Display Interface
# Features (0x26). Both are informational; the base EDID block already states
# the 10-bit RGB DisplayPort interface. The Adaptive Sync block (0x2b) is kept.
DROP_TAGS = {0x20, 0x26}


def die(msg):
    sys.exit(f"make-edid: {msg}")


def checksum(data):
    return (-sum(data)) & 0xFF


def parse_ext(ext):
    if ext[0] != 0x70:
        die("block 1 is not a DisplayID extension (tag 0x70)")
    if ext[1] != 0x20:
        die(f"DisplayID version 0x{ext[1]:02x}, expected 2.0 (0x20)")
    sec_len = ext[2]
    payload = ext[5:5 + sec_len]
    blocks, i = [], 0
    while i + 3 <= len(payload):
        tag, rev, n = payload[i], payload[i + 1], payload[i + 2]
        if tag == 0 and rev == 0 and n == 0:
            break  # padding
        blocks.append((tag, rev, bytes(payload[i + 3:i + 3 + n])))
        i += 3 + n
    return ext[1:5], sec_len, blocks


def dtd_fields(d):
    pclk_khz = (d[0] | d[1] << 8 | d[2] << 16) + 1
    u16 = lambda o: d[o] | d[o + 1] << 8
    return {
        "pclk_khz": pclk_khz,
        "preferred": bool(d[3] & 0x80),
        "hactive": u16(4) + 1,
        "hblank": u16(6) + 1,
        "vactive": u16(12) + 1,
        "vblank": u16(14) + 1,
    }


def refresh(f):
    return f["pclk_khz"] * 1000 / ((f["hactive"] + f["hblank"]) * (f["vactive"] + f["vblank"]))


def make_dtd(native, rate, preferred):
    d = bytearray(native)
    f = dtd_fields(native)
    htotal = f["hactive"] + f["hblank"]
    vtotal = round(f["pclk_khz"] * 1000 / (htotal * rate))
    vblank = vtotal - f["vactive"]
    if vblank < f["vblank"]:
        die(f"{rate} Hz would need a shorter blank than the native mode; only lower rates are supported")
    if vblank - 1 > 0xFFFF:
        die(f"{rate} Hz is too low for this pixel clock")
    d[14], d[15] = (vblank - 1) & 0xFF, (vblank - 1) >> 8
    d[3] = (d[3] & 0x7F) | (0x80 if preferred else 0)
    return bytes(d)


def build(stock, rates, preferred):
    if len(stock) < 256 or stock[:8] != bytes.fromhex("00ffffffffffff00"):
        die("input is not a 256-byte EDID")
    base, ext = bytearray(stock[:128]), bytearray(stock[128:256])
    header, sec_len, blocks = parse_ext(ext)

    t7 = [b for b in blocks if b[0] == TAG_TYPE_VII]
    if len(t7) != 1 or len(t7[0][2]) < 20:
        die("expected exactly one Type VII timing block")
    native = t7[0][2][:20]
    nf = dtd_fields(native)
    native_hz = refresh(nf)
    print(f"native timing: {nf['hactive']}x{nf['vactive']} @ {native_hz:.3f} Hz, "
          f"pixel clock {nf['pclk_khz'] / 1000:.3f} MHz", file=sys.stderr)

    dtds = []
    for r in sorted(rates):
        if abs(r - native_hz) < 0.5:
            dtds.append(make_dtd(native, native_hz, r == preferred))
        else:
            dtds.append(make_dtd(native, r, r == preferred))

    out_blocks = []
    for tag, rev, data in blocks:
        if tag in DROP_TAGS:
            continue
        if tag == TAG_TYPE_VII:
            data = b"".join(dtds)
        out_blocks.append(bytes([tag, rev, len(data)]) + data)
    payload = b"".join(out_blocks)
    if len(payload) > sec_len:
        die(f"new data ({len(payload)} bytes) does not fit in the DisplayID section ({sec_len} bytes)")
    payload += bytes(sec_len - len(payload))

    new_ext = bytearray(128)
    new_ext[0] = 0x70
    new_ext[1:5] = header
    new_ext[5:5 + sec_len] = payload
    new_ext[5 + sec_len] = checksum(new_ext[1:5 + sec_len])
    new_ext[127] = checksum(new_ext[:127])
    base[127] = checksum(base[:127])
    return bytes(base) + bytes(new_ext)


def show(edid):
    _, _, blocks = parse_ext(bytearray(edid[128:256]))
    for tag, _, data in blocks:
        if tag == TAG_TYPE_VII:
            for i in range(0, len(data) - 19, 20):
                f = dtd_fields(data[i:i + 20])
                print(f"{f['hactive']}x{f['vactive']} @ {refresh(f):8.3f} Hz"
                      f"  vtotal {f['vactive'] + f['vblank']}{'  (preferred)' if f['preferred'] else ''}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("output", nargs="?")
    ap.add_argument("--rates", default="60,120,240")
    ap.add_argument("--preferred", type=float, default=60)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    data = open(a.input, "rb").read()
    if a.check:
        show(data)
        return
    if not a.output:
        ap.error("OUTPUT is required")
    rates = [float(x) for x in a.rates.split(",")]
    out = build(data, rates, a.preferred)
    open(a.output, "wb").write(out)
    show(out)


if __name__ == "__main__":
    main()
