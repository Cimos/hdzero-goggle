#!/usr/bin/env python3
"""Build a DroneDaddy Betaflight font for analog OSD chips (MAX7456 / AT7456E).

Starts from Betaflight's stock analog font (utilities/fonts/analog/stock_default.mcm),
replaces the ASCII text cells with glyphs in the CubePilot typeface and the
boot logo cells (160..255, drawn as 24 x 4) with the DroneDaddy logo, and
writes an .mcm file for Betaflight Configurator's Font Manager.

Analog OSD chips have three pixel states only: black, white and see-through.
So the logo is white with a black outline, and a black seam separates the
blue "Drone" half from the pink "Daddy" half so the two words stay readable.

Usage:
  python3 utilities/make_analog_font.py --logo <png> [--preview-dir DIR]
Writes utilities/fonts/analog/DroneDaddy_Betaflight.mcm and a 288x72 logo PNG
(the size Configurator's "Upload logo" button expects).
"""
import argparse
import os

import numpy as np
from PIL import Image

import make_osd_font as dig

HERE = os.path.dirname(os.path.abspath(__file__))
ADIR = os.path.join(HERE, "fonts", "analog")
STOCK = os.path.join(ADIR, "stock_default.mcm")
OUT = os.path.join(ADIR, "DroneDaddy_Betaflight.mcm")

CW, CH, OL = 12, 18, 1
# the digital font thickens the light CubePilot strokes; at 12x18 that closes
# counters and merges '=' into a block, so analog renders at natural weight
dig.BOLD = 0.0
BLACK_V, SEE_V, WHITE_V = 0b00, 0b01, 0b10
# 0x24 is the MAX symbol and 0x2A a propeller icon in the analog font: keep both.
# At 12x18 the detailed symbols (# % & @ [ \\ ] ^) lose strokes or turn to mush
# in the display font, so they keep Betaflight's hand-drawn stock pixels.
KEEP_STOCK = {0x24, 0x2A, 0x23, 0x25, 0x26, 0x40, 0x5B, 0x5C, 0x5D, 0x5E}
TEXT_CODES = [c for c in range(0x21, 0x60) if c not in KEEP_STOCK]

BLUE = np.array([0x20, 0xA7, 0xFF])
PINK = np.array([0xF4, 0x9A, 0xBA])


def read_mcm(path):
    lines = [l.strip() for l in open(path) if l.strip()]
    assert lines[0] == "MAX7456", "not an MCM font file"
    data = [int(b, 2) for b in lines[1:]]
    assert len(data) == 256 * 64, len(data)
    return data


def write_mcm(path, data):
    with open(path, "w", newline="\n") as f:
        f.write("MAX7456\n")
        for b in data:
            f.write(f"{b:08b}\n")


def get_px(data, ch, x, y):
    i = y * CW + x
    return (data[ch * 64 + i // 4] >> (6 - 2 * (i % 4))) & 3


def set_cell(data, ch, vals):
    """vals: CH x CW array of 2-bit values."""
    flat = vals.reshape(-1)
    for j in range(54):
        b = 0
        for k in range(4):
            b = (b << 2) | int(flat[j * 4 + k])
        data[ch * 64 + j] = b
    for j in range(54, 64):
        data[ch * 64 + j] = 0x55  # unused tail, stock pads with see-through


def rgb_to_vals(cell):
    vals = np.full(cell.shape[:2], SEE_V, np.uint8)
    vals[np.all(cell == dig.WHITE, axis=2)] = WHITE_V
    vals[np.all(cell == dig.BLACK, axis=2)] = BLACK_V
    return vals


def logo_block(logo_path):
    """288 x 72 block of 2-bit values: white words, black outline and seam."""
    W, H = dig.LOGO_COLS * CW, dig.LOGO_ROWS * CH
    logo = Image.open(logo_path).convert("RGBA")
    logo = logo.crop(logo.getbbox())
    margin = 3
    s = min((W - 2 * margin) / logo.width, (H - 2 * margin) / logo.height)
    lw, lh = round(logo.width * s), round(logo.height * s)
    a = np.array(logo.resize((lw, lh), Image.LANCZOS)).astype(float)
    ink = a[:, :, 3] >= 128
    rgb = a[:, :, :3]
    is_blue = ink & (np.linalg.norm(rgb - BLUE, axis=2) < np.linalg.norm(rgb - PINK, axis=2))
    is_pink = ink & ~is_blue
    x0, y0 = (W - lw) // 2, (H - lh) // 2
    blue = np.zeros((H, W), bool)
    pink = np.zeros((H, W), bool)
    blue[y0:y0 + lh, x0:x0 + lw] = is_blue
    pink[y0:y0 + lh, x0:x0 + lw] = is_pink
    mask = blue | pink
    seam = dig.outline(blue, 1) & pink       # pink pixels touching blue
    vals = np.full((H, W), SEE_V, np.uint8)
    vals[dig.outline(mask, OL) & ~mask] = BLACK_V
    vals[mask] = WHITE_V
    vals[seam] = BLACK_V
    return vals


def preview(data, path, up=3):
    im = Image.new("RGB", (16 * (CW + 1) * up, 16 * (CH + 1) * up), (40, 40, 40))
    px = im.load()
    col = {BLACK_V: (0, 0, 0), WHITE_V: (255, 255, 255)}
    for c in range(256):
        for y in range(CH):
            for x in range(CW):
                v = col.get(get_px(data, c, x, y), (127, 127, 127))
                ox, oy = ((c % 16) * (CW + 1) + x) * up, ((c // 16) * (CH + 1) + y) * up
                for dy in range(up):
                    for dx in range(up):
                        px[ox + dx, oy + dy] = v
    im.save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--logo", required=True)
    ap.add_argument("--preview-dir")
    args = ap.parse_args()

    data = read_mcm(STOCK)
    fonts = dig.load_fonts()
    for code in TEXT_CODES:
        cell, _ = dig.render_text_cell(chr(code), fonts, CW, CH, OL)
        set_cell(data, code, rgb_to_vals(cell))

    block = logo_block(args.logo)
    for r in range(dig.LOGO_ROWS):
        for c in range(dig.LOGO_COLS):
            set_cell(data, dig.LOGO_FIRST + r * dig.LOGO_COLS + c,
                     block[r * CH:(r + 1) * CH, c * CW:(c + 1) * CW])
    write_mcm(OUT, data)

    # 288x72 logo image for Configurator's "Upload logo" (black/white/grey)
    lut = np.array([[0, 0, 0], [127, 127, 127], [255, 255, 255], [127, 127, 127]], np.uint8)
    logo_png = os.path.join(ADIR, "DroneDaddy_logo_288x72.png")
    Image.fromarray(lut[block]).save(logo_png)
    print("wrote", OUT, "and", logo_png)

    if args.preview_dir:
        preview(data, os.path.join(args.preview_dir, "analog_font_preview.png"))
        Image.fromarray(lut[block]).resize((288 * 3, 72 * 3), Image.NEAREST).save(
            os.path.join(args.preview_dir, "analog_logo_preview.png"))


if __name__ == "__main__":
    main()
