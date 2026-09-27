#!/usr/bin/env python3
"""Recolour the goggle OSD status icons to the DroneDaddy brand.

Reads the stock icons from utilities/osd_icons_stock/{GOGGLE,FHD}/ and writes
the branded set to mkapp/app/resource/OSD/GOGGLE/ (36x36, 720p OSD) and
mkapp/app/resource/OSD/GOGGLE/FHD/ (54x54, 1080p OSD). Always rebuilds from
the stock copies, so running it twice gives the same result.

Pass --sd DIR to also write a copy laid out for the SD card
(DIR/resource/OSD/GOGGLE/...), which the goggles prefer over the built-in set.

Rules:
- 0x7F7F7F is the OSD see-through colour and there is no alpha, so no drawn
  pixel may equal it. Near-key grey fringe pixels that touch the see-through
  area are cleared to the key, which removes the grey halo over dark video.
- White and light-grey foreground becomes brand blue #20A7FF, scaled by
  brightness so anti-aliased edges blend into the black outline.
- Coloured level fills (fan speed, antenna bars, link quality, VTX temp)
  follow a blue to pink ramp as the level rises.
- Warning colours stay: recording dot, no SD card, VRX overheat, VTX flame (7-8).
- Black outline and the mid-grey unlit bars are kept.
"""
import argparse
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STOCK = os.path.join(HERE, "osd_icons_stock")
OUT = os.path.join(REPO, "mkapp", "app", "resource", "OSD", "GOGGLE")

KEY = np.array([0x7F, 0x7F, 0x7F])
BLUE = np.array([0x20, 0xA7, 0xFF])
PINK = np.array([0xF4, 0x9A, 0xBA])

# name -> level 0..1 (None = keep warning colours, only recolour the white)
ICONS = {}
ICONS.update({f"fan{i}": i / 5 for i in range(6)})
ICONS.update({f"ant{i}": (i - 1) / 5 for i in range(1, 7)})
ICONS.update({f"VLQ{i}": (i - 1) / 8 for i in range(1, 10)})
ICONS.update({f"VtxTemp{i}": (i - 1) / 5 for i in range(1, 7)})
ICONS.update({f"VtxTemp{i}": None for i in range(7, 9)})  # flame = overheat warning
ICONS.update({f"VrxTemp{i}": None for i in range(1, 8)})
ICONS.update({"recording": None, "noSdcard": None})


def ramp(t):
    return BLUE + (PINK - BLUE) * max(0.0, min(1.0, t))


def defringe(a):
    """Clear near-key greys that border the see-through area."""
    a = a.copy()
    is_key = np.all(a == KEY, axis=2)
    mx, mn = a.max(axis=2), a.min(axis=2)
    near = (mx - mn < 12) & (np.abs(a.mean(axis=2) - 127) <= 9) & ~is_key
    pad = np.pad(is_key, 1)
    touches = pad[:-2, 1:-1] | pad[2:, 1:-1] | pad[1:-1, :-2] | pad[1:-1, 2:]
    a[near & touches] = KEY
    return a


def recolour(img, level):
    a = defringe(np.array(img.convert("RGB")).astype(float))
    out = a.copy()
    is_key = np.all(a == KEY, axis=2)
    mx, mn = a.max(axis=2), a.min(axis=2)
    chroma = mx - mn
    scale = (mx / 255.0)[..., None]

    white = (chroma <= 60) & (mx > 140) & ~is_key
    out[white] = (BLUE * scale)[white]

    if level is not None:
        fill = (chroma > 60) & ~is_key
        out[fill] = (ramp(level) * scale)[fill]
        tinted_dark = (mx < 60) & (chroma > 20) & ~is_key
        out[tinted_dark] = (ramp(level) * scale)[tinted_dark]

    out = np.clip(np.round(out), 0, 255).astype(np.uint8)
    # a drawn pixel must never land on the key
    clash = np.all(out == KEY.astype(np.uint8), axis=2) & ~is_key
    out[clash] = (0x80, 0x80, 0x80)
    return Image.fromarray(out, "RGB")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sd", help="also write an SD card copy under this folder")
    args = ap.parse_args()

    for sub, outdir in (("GOGGLE", OUT), ("FHD", os.path.join(OUT, "FHD"))):
        targets = [outdir]
        if args.sd:
            sd = os.path.join(args.sd, "resource", "OSD", "GOGGLE")
            targets.append(sd if sub == "GOGGLE" else os.path.join(sd, "FHD"))
        for t in targets:
            os.makedirs(t, exist_ok=True)
        for name, level in ICONS.items():
            src = os.path.join(STOCK, sub, name + ".bmp")
            img = recolour(Image.open(src), level)
            for t in targets:
                img.save(os.path.join(t, name + ".bmp"), "BMP")
        print(f"{sub}: {len(ICONS)} icons -> {', '.join(targets)}")


if __name__ == "__main__":
    main()
