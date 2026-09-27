#!/usr/bin/env python3
"""Build the DroneDaddy ArduPilot OSD fonts: HDZero goggle and analog.

Goggle font (ARDU_000.bmp, ARDU_FHD_000.bmp). The goggles load these when the
flight controller reports variant "ARDU" over MSP DisplayPort, which is
ArduPilot's default. Starts from the stock copies in utilities/fonts/ and
replaces only the text cells with CubePilot glyphs; every symbol cell stays
stock.

Analog font (MAX7456 / AT7456E). Starts from ArduPilot's default analog font
(clarity.mcm, which ArduPilot builds into font0.bin), kept here as
utilities/fonts/analog/stock_ardu_font0.mcm (ardupilot master 4c98c92). Writes:
  utilities/fonts/analog/DroneDaddy_ArduPilot.mcm   editable .mcm source
  utilities/fonts/analog/ardupilot_sd/font0.bin     copy to the SD card root
ArduPilot reads fontN.bin (N = OSD_FONT) from the SD card root before the copy
built into the firmware, so font0.bin there replaces the default font with no
parameter change. The .bin is the .mcm without its header and with only the
54 used bytes of each 64-byte character, as ArduPilot's mcm2bin.py makes it.

Map facts that decide what is text (ArduPilot libraries/AP_OSD):
  - no lowercase: 0x60..0x7F hold arrows and other symbols, and OSD messages
    are upper-cased before drawing;
  - some ASCII codes are symbols: 0x22 distance, 0x23 flaps, 0x24 down
    triangle, 0x26 / 0x27 horizon centre lines. These stay stock;
  - decimal packing is on by default (OSD_OPTIONS bit 0): "2.6" is drawn as
    0xC2 (digit, left half of the point) + 0xD6 (right half of the point,
    digit). Those 20 cells are digits, so they are rebuilt in CubePilot too,
    or every decimal number would mix two typefaces;
  - ArduPilot draws no boot logo, so no logo is added.

Usage: python3 utilities/make_ardu_fonts.py [--preview-dir DIR]
"""
import argparse
import os

import numpy as np
from PIL import Image, ImageDraw

import make_osd_font as dig
GOGGLE_BOLD = dig.BOLD
import make_analog_font as ana  # noqa: E402  (sets dig.BOLD = 0.0)
ANALOG_BOLD = 0.0

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")
ADIR = os.path.join(FONT_DIR, "analog")
OUT_DIR = dig.OUT_DIR

# name, cell w, cell h, outline px
GOGGLE_SIZES = [("ARDU_000", 24, 36, 1), ("ARDU_FHD_000", 36, 54, 2)]
GOGGLE_CELLS = 512  # the goggle sheets carry two 256-cell pages; ArduPilot uses page 0

SYMBOL_ASCII = {0x22, 0x23, 0x24, 0x26, 0x27}
GOGGLE_TEXT = [c for c in range(0x20, 0x60) if c not in SYMBOL_ASCII]

# at 12x18 the detailed shapes (% @ [ \\ ] ^) read better in the stock pixels,
# as in the Betaflight analog font; CubePilot's '*' is a tiny raised mark there
ANALOG_KEEP = SYMBOL_ASCII | {0x25, 0x2A, 0x40, 0x5B, 0x5C, 0x5D, 0x5E}
ANALOG_TEXT = [c for c in range(0x21, 0x60) if c not in ANALOG_KEEP]

PACK_POINT_AFTER = 0xC0   # '0'..'9' + 0x90: digit, then left half of the point
PACK_POINT_BEFORE = 0xD0  # '0'..'9' + 0xA0: right half of the point, then digit

STOCK_MCM = os.path.join(ADIR, "stock_ardu_font0.mcm")
OUT_MCM = os.path.join(ADIR, "DroneDaddy_ArduPilot.mcm")
OUT_BIN = os.path.join(ADIR, "ardupilot_sd", "font0.bin")


def text_mask(ch, fonts, cw, chh, ol):
    cell, fname = dig.render_text_cell(ch, fonts, cw, chh, ol)
    return np.all(cell == dig.WHITE, axis=2), fname


def packed_masks(fonts, cw, chh, ol, gap):
    """{code: (white mask, outline mask)} for the 20 decimal-packed cells.

    The typeface's own point is split across the boundary of the pair, so the
    two halves meet when 0xCx is followed by 0xDx. Each digit is rendered to
    fit the span left beside its half of the point (squeezed only if wider),
    `gap` px clear of the point, and centred in that span.
    """
    dot, _ = text_mask(".", fonts, cw, chh, ol)
    xs = np.nonzero(dot.any(axis=0))[0]
    dot = dot[:, xs.min():xs.max() + 1]
    w = dot.shape[1]
    left, right = (w + 1) // 2, w // 2
    out = {}
    for first, base, lo, hi in ((PACK_POINT_AFTER, 0, ol, cw - left - gap),
                                (PACK_POINT_BEFORE, cw, right + gap, cw - ol)):
        span = hi - lo
        for d in range(10):
            # a cell this wide gives render_text_cell a max ink width of `span`
            m, _ = text_mask(str(d), fonts, span + 2 * ol + 2, chh, ol)
            xs = np.nonzero(m.any(axis=0))[0]
            ink = m[:, xs.min():xs.max() + 1]
            x0 = base + lo + (span - ink.shape[1]) // 2
            pair = np.zeros((chh, 2 * cw), bool)
            pair[:, x0:x0 + ink.shape[1]] = ink
            pair[:, cw - left:cw + right] |= dot
            edge = dig.outline(pair, ol) & ~pair
            out[first + d] = (pair[:, base:base + cw], edge[:, base:base + cw])
    return out, (w, left, right)


def cell_rgb(mask, edge):
    cell = np.zeros(mask.shape + (3,), np.uint8)
    cell[:] = dig.TRANSPARENT
    cell[edge] = dig.BLACK
    cell[mask] = dig.WHITE
    return cell


def build_goggle(name, cw, chh, ol, fonts):
    dig.BOLD = GOGGLE_BOLD
    stock_path = os.path.join(FONT_DIR, "stock_%s.bmp" % name)
    out_path = os.path.join(OUT_DIR, name + ".bmp")
    assert os.path.exists(stock_path), "missing stock copy " + stock_path
    stock = np.array(Image.open(stock_path).convert("RGB"))
    assert stock.shape == (GOGGLE_CELLS // dig.COLS * chh, dig.COLS * cw, 3), stock.shape
    sheet = stock.copy()
    replaced, used = set(), {}
    for code in GOGGLE_TEXT:
        cell, fname = dig.render_text_cell(chr(code), fonts, cw, chh, ol)
        ys, xs = dig.cell_slice(code, cw, chh)
        sheet[ys, xs] = cell
        replaced.add(code)
        if fname:
            used.setdefault(fname, []).append(chr(code))
    packed, point = packed_masks(fonts, cw, chh, ol, gap=ol + 1)
    for code, (mask, edge) in packed.items():
        ys, xs = dig.cell_slice(code, cw, chh)
        sheet[ys, xs] = cell_rgb(mask, edge)
        replaced.add(code)
    Image.fromarray(sheet, "RGB").save(out_path, format="BMP")
    # check: every cell not replaced is byte-identical to stock
    same = 0
    for n in range(GOGGLE_CELLS):
        ys, xs = dig.cell_slice(n, cw, chh)
        if n not in replaced:
            assert np.array_equal(sheet[ys, xs], stock[ys, xs]), (name, n)
            same += 1
    back = np.array(Image.open(out_path).convert("RGB"))
    assert np.array_equal(back, sheet), name
    return out_path, stock, sheet, replaced, same, used, point


def build_analog(fonts):
    dig.BOLD = ANALOG_BOLD
    stock = ana.read_mcm(STOCK_MCM)
    data = list(stock)
    replaced = set()
    for code in ANALOG_TEXT:
        cell, _ = dig.render_text_cell(chr(code), fonts, ana.CW, ana.CH, ana.OL)
        ana.set_cell(data, code, ana.rgb_to_vals(cell))
        replaced.add(code)
    packed, point = packed_masks(fonts, ana.CW, ana.CH, ana.OL, gap=1)
    for code, (mask, edge) in packed.items():
        vals = np.full(mask.shape, ana.SEE_V, np.uint8)
        vals[edge] = ana.BLACK_V
        vals[mask] = ana.WHITE_V
        ana.set_cell(data, code, vals)
        replaced.add(code)
    ana.write_mcm(OUT_MCM, data)
    # SD card file: 54 used bytes per character, as mcm2bin.py writes it
    blob = bytes(b for i, b in enumerate(data) if i % 64 < 54)
    assert len(blob) == 54 * 256
    os.makedirs(os.path.dirname(OUT_BIN), exist_ok=True)
    with open(OUT_BIN, "wb") as f:
        f.write(blob)
    # checks
    assert ana.read_mcm(OUT_MCM) == data
    same = 0
    for c in range(256):
        if c not in replaced:
            assert data[c * 64:(c + 1) * 64] == stock[c * 64:(c + 1) * 64], c
            same += 1
    return data, stock, replaced, same, point


# ---------------------------------------------------------------- previews

def goggle_sheet_preview(sheet, cw, chh, path, up=2, count=256, mark=()):
    """Labelled sheet; replaced cells get a pink frame."""
    pad, gut = 16, 4
    im = Image.new("RGB", (pad + 16 * (cw * up + gut), pad + count // 16 * (chh * up + gut)),
                   (40, 30, 45))
    d = ImageDraw.Draw(im)
    for n in range(count):
        r, c = divmod(n, 16)
        ys, xs = dig.cell_slice(n, cw, chh)
        x, y = pad + c * (cw * up + gut), pad + r * (chh * up + gut)
        if n in mark:
            d.rectangle([x - 2, y - 2, x + cw * up + 1, y + chh * up + 1], outline=(244, 154, 186))
        im.paste(Image.fromarray(sheet[ys, xs]).resize((cw * up, chh * up), Image.NEAREST), (x, y))
    for c in range(16):
        d.text((pad + c * (cw * up + gut) + 2, 2), "%X" % c, fill=(255, 220, 120))
    for r in range(count // 16):
        d.text((3, pad + r * (chh * up + gut) + 4), "%X" % r, fill=(255, 220, 120))
    im.save(path)


def pack_string(s):
    """ArduPilot's convert_to_decimal_packed_characters() on one item."""
    b = [ord(ch) for ch in s]
    for i in range(1, len(b) - 1):
        if b[i] == ord(".") and chr(b[i - 1]).isdigit() and chr(b[i + 1]).isdigit():
            b[i - 1] += 0x90
            b[i + 1] += 0xA0
            del b[i]
            break
    return b


# OSD items as ArduPilot writes them (each item packed on its own)
SAMPLE = [["\x01" "87", "12.6\x06", "3.25\x9a", "0.8\x9a"],
          ["ALT", "105.3\xb1", "4.2\x9f", "\x89" "270\xa8"],
          ["\x1e\x1f" "14", "HDOP", "0.9", "STAB", "ARMED"],
          ["1234\x07", "25.0\xa1", "22.5\x0e", "-7.1\xa8"]]


def sample_rows():
    rows = []
    for items in SAMPLE:
        r = []
        for it in items:
            r += pack_string(it) + [0x20]
        rows.append(r[:-1])
    return rows


def goggle_sample(sheet, cw, chh, path, up=2):
    rows = sample_rows()
    wmax = max(len(r) for r in rows)
    im = Image.new("RGB", (wmax * cw, len(rows) * chh), (70, 90, 110))
    for y, r in enumerate(rows):
        for x, code in enumerate(r):
            ys, xs = dig.cell_slice(code, cw, chh)
            cell = sheet[ys, xs]
            key = np.all(cell == dig.TRANSPARENT, axis=2)
            bg = np.array(im.crop((x * cw, y * chh, (x + 1) * cw, (y + 1) * chh)))
            bg[~key] = cell[~key]
            im.paste(Image.fromarray(bg), (x * cw, y * chh))
    im.resize((im.width * up, im.height * up), Image.NEAREST).save(path)


def analog_sample(data, path, up=3):
    rows = sample_rows()
    wmax = max(len(r) for r in rows)
    cw, ch = ana.CW, ana.CH
    a = np.zeros((len(rows) * ch, wmax * cw, 3), np.uint8)
    a[:] = (70, 90, 110)
    for y, r in enumerate(rows):
        for x, code in enumerate(r):
            for py in range(ch):
                for px in range(cw):
                    v = ana.get_px(data, code, px, py)
                    if v == ana.WHITE_V:
                        a[y * ch + py, x * cw + px] = 255
                    elif v == ana.BLACK_V:
                        a[y * ch + py, x * cw + px] = 0
    im = Image.fromarray(a)
    im.resize((im.width * up, im.height * up), Image.NEAREST).save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--preview-dir", help="write preview PNGs here")
    a = ap.parse_args()
    fonts = dig.load_fonts()
    pv = a.preview_dir
    for name, cw, chh, ol in GOGGLE_SIZES:
        out, stock, sheet, replaced, same, used, point = build_goggle(name, cw, chh, ol, fonts)
        print("%s  %d bytes  replaced %d cells, %d identical to stock, point w/left/right %s, fonts %s"
              % (out, os.path.getsize(out), len(replaced), same, point,
                 {k: len(v) for k, v in used.items()}))
        if pv:
            tag = "sd" if name == "ARDU_000" else "fhd"
            goggle_sheet_preview(sheet, cw, chh, os.path.join(pv, "ardu_goggle_%s.png" % tag),
                                 up=2 if tag == "sd" else 1, mark=replaced)
            goggle_sheet_preview(stock, cw, chh, os.path.join(pv, "ardu_goggle_%s_stock.png" % tag),
                                 up=2 if tag == "sd" else 1)
            goggle_sample(sheet, cw, chh, os.path.join(pv, "ardu_goggle_%s_sample.png" % tag),
                          up=2 if tag == "sd" else 1)
    data, stock, replaced, same, point = build_analog(fonts)
    print("%s  %d bytes  replaced %d chars, %d identical to stock, point w/left/right %s"
          % (OUT_MCM, os.path.getsize(OUT_MCM), len(replaced), same, point))
    print("%s  %d bytes" % (OUT_BIN, os.path.getsize(OUT_BIN)))
    if pv:
        ana.preview(data, os.path.join(pv, "ardu_analog.png"))
        ana.preview(stock, os.path.join(pv, "ardu_analog_stock.png"))
        analog_sample(data, os.path.join(pv, "ardu_analog_sample.png"))


if __name__ == "__main__":
    main()
