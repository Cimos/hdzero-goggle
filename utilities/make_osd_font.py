#!/usr/bin/env python3
"""Build the DroneDaddy Betaflight OSD font for HDZero goggles.

Starts from the stock Betaflight font (kept in utilities/fonts/stock_*.bmp) and
replaces only:
  - the text glyphs (space, punctuation, digits, capitals) with CubePilot-Regular
    (Saira-600 as fallback for any missing glyph);
  - the boot logo cells 160..255 (a 24 x 4 cell block) with the DroneDaddy logo.
Every symbol cell (arrows, batteries, heading marks, units, ...) is copied from
stock untouched.

Stock bitmap convention (24-bit BMP, 16 columns x 32 rows of cells):
  (127,127,127) = transparent, (255,255,255) = glyph, (0,0,0) = outline.
The goggles render colour (the stock logo is yellow/black, batteries are green),
so the logo keeps its blue and pink.

Usage: python3 utilities/make_osd_font.py [--logo PATH] [--preview-dir DIR]
"""
import argparse
import io
import os
import shutil

import numpy as np
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
FONT_DIR = os.path.join(HERE, "fonts")
OUT_DIR = os.path.join(REPO, "mkapp", "app", "resource", "OSD", "FC")

TRANSPARENT = (127, 127, 127)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# name, cell w, cell h, outline px
SIZES = [("BTFL_000", 24, 36, 1), ("BTFL_FHD_000", 36, 54, 2)]
COLS = 16

# Text cells to replace. In the Betaflight font 0x60..0x7F are arrows and other
# symbols (no lowercase), and 0x24 '$' holds the "max" symbol, so those stay.
TEXT_CODES = [c for c in range(0x20, 0x60) if c != 0x24]

LOGO_FIRST, LOGO_COLS, LOGO_ROWS = 160, 24, 4

CAP_FRACTION = 0.72  # cap height as a share of cell height
BOLD = 0.5           # extra stroke per side, in px per outline px
SS = 8               # supersampling factor for glyph rendering


def woff2_to_font(path, px):
    t = TTFont(path)
    t.flavor = None
    buf = io.BytesIO()
    t.save(buf)
    cmap = t.getBestCmap()
    return buf.getvalue(), cmap


def load_fonts():
    fonts = []
    for name in ("CubePilot-Regular.woff2", "Saira-600.woff2"):
        data, cmap = woff2_to_font(os.path.join(FONT_DIR, name), 0)
        fonts.append((name, data, cmap))
    return fonts


def outline(mask, r):
    """Dilate a boolean mask by r px (square neighbourhood)."""
    out = mask.copy()
    h, w = mask.shape
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            sh = np.zeros_like(mask)
            ys, yd = (slice(dy, h), slice(0, h - dy)) if dy >= 0 else (slice(0, h + dy), slice(-dy, h))
            xs, xd = (slice(dx, w), slice(0, w - dx)) if dx >= 0 else (slice(0, w + dx), slice(-dx, w))
            sh[ys, xs] = mask[yd, xd]
            out |= sh
    return out


def render_text_cell(ch, fonts, cw, chh, ol):
    """Return an RGB cell (chh x cw x 3) for one character."""
    cell = np.zeros((chh, cw, 3), np.uint8)
    cell[:] = TRANSPARENT
    if ch == " ":
        return cell, None
    for fname, data, cmap in fonts:
        # CubePilot maps some punctuation ([ \\ ] ^) to empty glyphs: skip those
        if ord(ch) in cmap and ImageFont.truetype(io.BytesIO(data), 100).getbbox(ch)[3] > \
                ImageFont.truetype(io.BytesIO(data), 100).getbbox(ch)[1]:
            break
    else:
        return cell, None
    cap = round(chh * CAP_FRACTION) - 2 * ol          # ink cap height
    max_w = cw - 2 * ol - 2                            # ink width, 1 px gap each side
    # size the font so 'H' is exactly `cap` tall at SS scale
    # the display font is light; thicken strokes so they read at OSD size
    sw = round(BOLD * ol * SS)
    probe = ImageFont.truetype(io.BytesIO(data), 100 * SS)
    hb = probe.getbbox("H")
    size = 100 * SS * (cap * SS - 2 * sw) / (hb[3] - hb[1])
    font = ImageFont.truetype(io.BytesIO(data), round(size))
    hb = font.getbbox("H", stroke_width=sw)
    bb = font.getbbox(ch, stroke_width=sw)
    if bb[2] <= bb[0] or bb[3] <= bb[1]:
        return cell, fname
    img = Image.new("L", (bb[2] - bb[0], bb[3] - bb[1]), 0)
    ImageDraw.Draw(img).text((-bb[0], -bb[1]), ch, font=font, fill=255,
                             stroke_width=sw, stroke_fill=255)
    gw = (bb[2] - bb[0]) / SS
    gh = (bb[3] - bb[1]) / SS
    # squeeze horizontally if the glyph is wider than the cell allows
    tw = max(1, min(round(gw), max_w))
    th = max(1, round(gh))
    th = min(th, chh - 2 * ol)
    small = np.array(img.resize((tw, th), Image.LANCZOS)) >= 128
    # place on a common baseline: caps centred vertically in the cell
    cap_top = (chh - cap) // 2
    y0 = cap_top + round((bb[1] - hb[1]) / SS)
    y0 = max(ol, min(y0, chh - ol - th))
    x0 = (cw - tw) // 2
    mask = np.zeros((chh, cw), bool)
    mask[y0:y0 + th, x0:x0 + tw] = small
    edge = outline(mask, ol) & ~mask
    cell[edge] = BLACK
    cell[mask] = WHITE
    return cell, fname


def render_logo_block(logo_path, cw, chh, ol):
    W, H = LOGO_COLS * cw, LOGO_ROWS * chh
    block = np.zeros((H, W, 3), np.uint8)
    block[:] = TRANSPARENT
    logo = Image.open(logo_path).convert("RGBA")
    bb = logo.getbbox()
    logo = logo.crop(bb)
    margin = 2 * ol + 2
    scale = min((W - 2 * margin) / logo.width, (H - 2 * margin) / logo.height)
    lw, lh = round(logo.width * scale), round(logo.height * scale)
    small = np.array(logo.resize((lw, lh), Image.LANCZOS)).astype(np.float32)
    alpha = small[:, :, 3]
    mask_small = alpha >= 128
    rgb = small[:, :, :3].clip(0, 255).astype(np.uint8)
    x0, y0 = (W - lw) // 2, (H - lh) // 2
    mask = np.zeros((H, W), bool)
    mask[y0:y0 + lh, x0:x0 + lw] = mask_small
    colour = np.zeros((H, W, 3), np.uint8)
    colour[y0:y0 + lh, x0:x0 + lw] = rgb
    edge = outline(mask, ol) & ~mask
    block[edge] = BLACK
    block[mask] = colour[mask]
    # never emit the exact transparent key inside the logo
    key = mask & np.all(block == TRANSPARENT, axis=2)
    block[key] = (128, 128, 128)
    return block


def cell_slice(n, cw, chh):
    r, c = divmod(n, COLS)
    return slice(r * chh, (r + 1) * chh), slice(c * cw, (c + 1) * cw)


def build(name, cw, chh, ol, fonts, logo_path):
    stock_path = os.path.join(FONT_DIR, "stock_%s.bmp" % name)
    out_path = os.path.join(OUT_DIR, name + ".bmp")
    if not os.path.exists(stock_path):
        shutil.copy2(out_path, stock_path)
    sheet = np.array(Image.open(stock_path).convert("RGB"))
    assert sheet.shape == (32 * chh, COLS * cw, 3), sheet.shape
    used = {}
    for code in TEXT_CODES:
        cell, fname = render_text_cell(chr(code), fonts, cw, chh, ol)
        ys, xs = cell_slice(code, cw, chh)
        sheet[ys, xs] = cell
        if fname:
            used.setdefault(fname, []).append(chr(code))
    block = render_logo_block(logo_path, cw, chh, ol)
    for i in range(LOGO_COLS * LOGO_ROWS):
        r, c = divmod(i, LOGO_COLS)
        ys, xs = cell_slice(LOGO_FIRST + i, cw, chh)
        sheet[ys, xs] = block[r * chh:(r + 1) * chh, c * cw:(c + 1) * cw]
    Image.fromarray(sheet, "RGB").save(out_path, format="BMP")
    return out_path, sheet, block, used


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logo", required=True, help="DroneDaddy logo PNG (RGBA)")
    ap.add_argument("--preview-dir", help="write osdfont_preview_*.png here")
    a = ap.parse_args()
    fonts = load_fonts()
    for name, cw, chh, ol in SIZES:
        out, sheet, block, used = build(name, cw, chh, ol, fonts, a.logo)
        print("%s  %d bytes  fonts: %s" % (out, os.path.getsize(out),
              {k: len(v) for k, v in used.items()}))
        if a.preview_dir and name == "BTFL_000":
            im = Image.fromarray(sheet)
            im.resize((im.width * 2, im.height * 2), Image.NEAREST).save(
                os.path.join(a.preview_dir, "osdfont_preview_sd.png"))
            im = Image.fromarray(block)
            im.resize((im.width * 2, im.height * 2), Image.NEAREST).save(
                os.path.join(a.preview_dir, "osdfont_preview_logo.png"))
        if a.preview_dir and name == "BTFL_FHD_000":
            Image.fromarray(sheet).save(os.path.join(a.preview_dir, "osdfont_preview_fhd.png"))


if __name__ == "__main__":
    main()
