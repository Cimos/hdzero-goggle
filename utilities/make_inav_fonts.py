#!/usr/bin/env python3
"""Build the DroneDaddy INAV OSD fonts: HDZero goggle BMPs and an analog .mcm.

Uses the same pieces as the Betaflight fonts (make_osd_font.py for the goggles,
make_analog_font.py for analog chips) and applies them to INAV's character map
(src/main/drivers/osd_symbols.h in iNavFlight/inav). INAV fonts have 512
characters. Replaced:
  - the ASCII text cells: ! # % & ( ) * + , - . / 0-9 : ; < = > @ A-Z [ \\ ] ^ _
    { | }. There is no lowercase (0x60..0x7A are unit symbols) and INAV
    upper-cases craft and pilot names before drawing them. 0x22, 0x24, 0x27
    and 0x3F are symbols in INAV (Ah/km, Ah/mi, VTX power, Ah/NM) and stay.
  - the digits with half a decimal dot (0xA1..0xAA trailing, 0xB1..0xBA
    leading). INAV draws "12.5" as '1', '2' with a trailing half dot, '5' with
    a leading half dot, so these must match the text digits.
  - the INAV logo (0x101, 10 x 4 cells), the large pilot logo (0x1D8, 10 x 4)
    and the small pilot logo (0x1D5, 3 x 1) with the DroneDaddy logo. On the
    analog font the small pilot logo is only 36 x 18 px, too small for the
    word mark, so it gets a "DD" made from the logo's two capital D's.
The analog font keeps INAV's stock pixels for # % & * < > @ [ \\ ] ^, which
lose strokes in the display font at 12x18 (Betaflight's analog font keeps the
same set bar * < >). Every other cell is copied from stock untouched. The
analog font also keeps the metadata characters 255 and 256 ("INAV" + font
version) and bytes 54..63 of every character, which INAV and max7456tool use.

Goggle cells keep the stock convention: (127,127,127) see-through, white glyph,
black outline, and the logo in its own blue and pink. Analog cells are black,
white or see-through, so the logo is white with a black outline and a black
seam between "Drone" and "Daddy".

Usage:
  python3 utilities/make_inav_fonts.py --logo <png> [--preview-dir DIR]
Always rebuilds from the stock copies in utilities/fonts/.
"""
import argparse
import os

import numpy as np
from PIL import Image, ImageDraw

import make_osd_font as dig
GOGGLE_BOLD = dig.BOLD          # make_analog_font sets dig.BOLD = 0.0 on import
import make_analog_font as ana  # noqa: E402

FONT_DIR = dig.FONT_DIR
OUT_DIR = dig.OUT_DIR
ADIR = ana.ADIR
ANALOG_STOCK = os.path.join(ADIR, "stock_inav_default.mcm")
ANALOG_OUT = os.path.join(ADIR, "DroneDaddy_INAV.mcm")

NCHARS = 512
COLS = dig.COLS

# name, cell w, cell h, outline px
GOGGLE_SIZES = [("INAV_000", 24, 36, 1), ("INAV_FHD_000", 36, 54, 2)]

# osd_symbols.h: 0x21 ! / 0x23 # / 0x25 % / 0x26 & / 0x28..0x3E / 0x40..0x5F /
# 0x7B..0x7D are ASCII; 0x22, 0x24, 0x27, 0x3F are symbols.
INAV_TEXT = [0x21, 0x23, 0x25, 0x26] + list(range(0x28, 0x3F)) + \
    list(range(0x40, 0x60)) + [0x7B, 0x7C, 0x7D]
DOT_TRAIL, DOT_LEAD = 0xA1, 0xB1   # SYM_ZERO_HALF_TRAILING_DOT / _LEADING_DOT

# (name, first char, cols, rows)
LOGOS = [
    ("inav_logo", 0x101, 10, 4),    # SYM_LOGO_START, SYM_LOGO_WIDTH x HEIGHT
    ("pilot_large", 0x1D8, 10, 4),  # SYM_PILOT_LOGO_LRG_START, drawn 10 x 4
    ("pilot_small", 0x1D5, 3, 1),   # SYM_PILOT_LOGO_SML_L/C/R
]

# Analog: same rule as the Betaflight analog font. At 12x18 the detailed
# symbols lose strokes in the display font, so they keep INAV's stock pixels:
# # % & @ [ \ ] ^ as for Betaflight, plus * (shrinks to a blob) and < >
# (the diagonals break into steps with a notch at the point).
ANALOG_KEEP = {0x23, 0x25, 0x26, 0x40, 0x5B, 0x5C, 0x5D, 0x5E, 0x2A, 0x3C, 0x3E}
ANALOG_TEXT = [c for c in INAV_TEXT if c not in ANALOG_KEEP]


# ---------------------------------------------------------------- shared ----

def logo_cells(render, cols, rows):
    """Call a 24x4-only logo renderer at another cell grid size."""
    saved = dig.LOGO_COLS, dig.LOGO_ROWS
    dig.LOGO_COLS, dig.LOGO_ROWS = cols, rows
    try:
        return render()
    finally:
        dig.LOGO_COLS, dig.LOGO_ROWS = saved


def dotted_digits(render, dot_mask, cw, chh, ol, gap):
    """Return [(mask, note), (mask, note)] for a digit with a trailing and a
    leading half dot. Masks are two cells wide; the caller keeps its half.

    Stock INAV fonts split the decimal dot over two cells: the digit before the
    point carries the left half at its right edge, the digit after it carries
    the right half at its left edge, so the pair shows one whole dot. The dot
    here is the rendered '.' glyph, centred on the cell boundary. The digit
    keeps its place unless it comes closer than `gap` px to the dot: then it
    moves away, and if it is too wide to move it is drawn narrower.
    render(width) gives the digit's white mask in a cell `width` px wide.
    """
    ys, xs = np.nonzero(dot_mask)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    dot = dot_mask[y0:y1, x0:x1]
    w = x1 - x0
    left = (w + 1) // 2                     # dot columns left of the boundary
    right = w - left
    base = render(cw)
    out = []
    for trailing in (True, False):
        # columns the digit's white may use in its own cell
        lo, hi = (ol, cw - left - gap - 1) if trailing else (right + gap, cw - 1 - ol)
        cols = np.nonzero(base.any(axis=0))[0]
        if cols.max() - cols.min() <= hi - lo:
            shift = min(0, hi - cols.max()) if trailing else max(0, lo - cols.min())
            digit = np.roll(base, shift, axis=1)
            note = shift
        else:
            # widest rendering that fits the span (render_text_cell squeezes
            # to width - 2*ol - 2, and rounding can lose a column or two)
            for width in range(cw, 0, -1):
                narrow = render(width)
                nc = np.nonzero(narrow.any(axis=0))[0]
                nw = nc.max() - nc.min() + 1
                if nw <= hi - lo + 1:
                    break
            digit = np.zeros((chh, cw), bool)
            px = lo + (hi - lo + 1 - nw) // 2
            digit[:, px:px + nw] = narrow[:, nc.min():nc.max() + 1]
            note = "narrowed %d->%d px" % (cols.max() - cols.min() + 1, nw)
        m = np.zeros((chh, 2 * cw), bool)
        m[y0:y1, cw - left:cw - left + w] = dot
        if trailing:
            m[:, :cw] |= digit
        else:
            m[:, cw:] |= digit
        out.append((m, note))
    return out


def mask_to_rgb(m, ol):
    cell = np.zeros(m.shape + (3,), np.uint8)
    cell[:] = dig.TRANSPARENT
    cell[dig.outline(m, ol) & ~m] = dig.BLACK
    cell[m] = dig.WHITE
    return cell


def white(cell):
    return np.all(cell == dig.WHITE, axis=2)


# ---------------------------------------------------------------- goggle ----

def cell_slice(n, cw, chh):
    r, c = divmod(n, COLS)
    return slice(r * chh, (r + 1) * chh), slice(c * cw, (c + 1) * cw)


def build_goggle(name, cw, chh, ol, fonts, logo_path):
    stock_path = os.path.join(FONT_DIR, "stock_%s.bmp" % name)
    out_path = os.path.join(OUT_DIR, name + ".bmp")
    stock = np.array(Image.open(stock_path).convert("RGB"))
    assert stock.shape == (NCHARS // COLS * chh, COLS * cw, 3), stock.shape
    sheet = stock.copy()
    dig.BOLD = GOGGLE_BOLD
    replaced = set()
    cells = {}
    for code in INAV_TEXT:
        cell, _ = dig.render_text_cell(chr(code), fonts, cw, chh, ol)
        cells[code] = cell
        ys, xs = cell_slice(code, cw, chh)
        sheet[ys, xs] = cell
        replaced.add(code)
    shifts = {}
    for d in range(10):
        render = lambda width, ch=chr(0x30 + d): white(  # noqa: E731
            dig.render_text_cell(ch, fonts, width, chh, ol)[0])
        pair = dotted_digits(render, white(cells[0x2E]), cw, chh, ol, gap=ol + 1)
        for (m, note), base, half in zip(pair, (DOT_TRAIL, DOT_LEAD), (0, 1)):
            cell = mask_to_rgb(m, ol)[:, half * cw:(half + 1) * cw]
            ys, xs = cell_slice(base + d, cw, chh)
            sheet[ys, xs] = cell
            replaced.add(base + d)
            if note:
                shifts["%X" % (base + d)] = note
    blocks = {}
    for lname, first, lc, lr in LOGOS:
        block = logo_cells(lambda: dig.render_logo_block(logo_path, cw, chh, ol), lc, lr)
        blocks[lname] = block
        for i in range(lc * lr):
            r, c = divmod(i, lc)
            ys, xs = cell_slice(first + i, cw, chh)
            sheet[ys, xs] = block[r * chh:(r + 1) * chh, c * cw:(c + 1) * cw]
            replaced.add(first + i)
    Image.fromarray(sheet, "RGB").save(out_path, format="BMP")
    # every cell outside the replaced set must be exactly stock
    same = changed = 0
    for n in range(NCHARS):
        ys, xs = cell_slice(n, cw, chh)
        eq = np.array_equal(sheet[ys, xs], stock[ys, xs])
        if n not in replaced:
            assert eq, "cell 0x%X changed but is not in the replace list" % n
        same += eq
        changed += not eq
    return out_path, sheet, blocks, replaced, same, changed, shifts


# ---------------------------------------------------------------- analog ----

def read_mcm512(path):
    text = open(path, newline="").read()
    lines = text.split("\n")
    assert lines[0] == "MAX7456", "not an MCM font file"
    data = [int(b, 2) for b in lines[1:] if b]
    assert len(data) == NCHARS * 64, len(data)
    return data, text.endswith("\n")


def write_mcm512(path, data, trailing_newline):
    # INAV's stock files have no newline after the last byte; match them
    with open(path, "w", newline="\n") as f:
        f.write("MAX7456\n" + "\n".join(f"{b:08b}" for b in data))
        if trailing_newline:
            f.write("\n")


def cell_vals(data, ch):
    v = []
    for b in data[ch * 64:ch * 64 + 54]:
        v += [(b >> 6) & 3, (b >> 4) & 3, (b >> 2) & 3, b & 3]
    return np.array(v, np.uint8).reshape(ana.CH, ana.CW)


def put_cell(data, ch, vals):
    """Write the 54 pixel bytes, keep the 10 metadata bytes from stock."""
    tail = data[ch * 64 + 54:ch * 64 + 64]
    ana.set_cell(data, ch, vals)
    data[ch * 64 + 54:ch * 64 + 64] = tail


def dd_monogram(logo_path):
    """RGBA image of the logo's two capital D's (blue "Drone", pink "Daddy")."""
    a = np.array(Image.open(logo_path).convert("RGBA"))
    ink = a[:, :, 3] >= 128
    rgb = a[:, :, :3].astype(float)
    blue = ink & (np.linalg.norm(rgb - ana.BLUE, axis=2) < np.linalg.norm(rgb - ana.PINK, axis=2))
    parts = []
    for colour in (blue, ink & ~blue):
        # the leftmost pixel of each colour belongs to that word's capital D
        ys, xs = np.nonzero(colour)
        i = np.argmin(xs)
        lab = Image.fromarray((colour * 255).astype(np.uint8)).copy()
        ImageDraw.floodfill(lab, (int(xs[i]), int(ys[i])), 128)
        comp = np.array(lab) == 128
        ys, xs = np.nonzero(comp)
        sl = slice(ys.min(), ys.max() + 1), slice(xs.min(), xs.max() + 1)
        part = a[sl].copy()
        part[~comp[sl]] = 0
        parts.append((part, ys.min()))
    top = min(t for _, t in parts)
    gap = parts[0][0].shape[1] // 12
    H = max(p.shape[0] + t - top for p, t in parts)
    W = parts[0][0].shape[1] + gap + parts[1][0].shape[1]
    out = np.zeros((H, W, 4), np.uint8)
    x = 0
    for p, t in parts:
        out[t - top:t - top + p.shape[0], x:x + p.shape[1]] = p
        x += p.shape[1] + gap
    return Image.fromarray(out)


def analog_logo_vals(img, W, H, margin):
    """make_analog_font.logo_block for any image, block size and margin."""
    img = img.crop(img.getbbox())
    s = min((W - 2 * margin) / img.width, (H - 2 * margin) / img.height)
    lw, lh = round(img.width * s), round(img.height * s)
    a = np.array(img.resize((lw, lh), Image.LANCZOS)).astype(float)
    ink = a[:, :, 3] >= 128
    rgb = a[:, :, :3]
    is_blue = ink & (np.linalg.norm(rgb - ana.BLUE, axis=2) < np.linalg.norm(rgb - ana.PINK, axis=2))
    x0, y0 = (W - lw) // 2, (H - lh) // 2
    blue = np.zeros((H, W), bool)
    pink = np.zeros((H, W), bool)
    blue[y0:y0 + lh, x0:x0 + lw] = is_blue
    pink[y0:y0 + lh, x0:x0 + lw] = ink & ~is_blue
    mask = blue | pink
    vals = np.full((H, W), ana.SEE_V, np.uint8)
    vals[dig.outline(mask, ana.OL) & ~mask] = ana.BLACK_V
    vals[mask] = ana.WHITE_V
    vals[dig.outline(blue, 1) & pink] = ana.BLACK_V     # seam
    return vals


def build_analog(fonts, logo_path):
    CW, CH, OL = ana.CW, ana.CH, ana.OL
    stock, nl = read_mcm512(ANALOG_STOCK)
    # a plain read/write round trip must reproduce the stock file exactly
    tmp = ANALOG_OUT + ".tmp"
    write_mcm512(tmp, stock, nl)
    assert open(tmp, "rb").read() == open(ANALOG_STOCK, "rb").read()
    os.remove(tmp)
    data = list(stock)
    dig.BOLD = 0.0
    replaced = set()
    cells = {}
    for code in INAV_TEXT + [0x2E]:
        cell, _ = dig.render_text_cell(chr(code), fonts, CW, CH, OL)
        cells[code] = cell
    for code in ANALOG_TEXT:
        put_cell(data, code, ana.rgb_to_vals(cells[code]))
        replaced.add(code)
    shifts = {}
    for d in range(10):
        render = lambda width, ch=chr(0x30 + d): white(  # noqa: E731
            dig.render_text_cell(ch, fonts, width, CH, OL)[0])
        pair = dotted_digits(render, white(cells[0x2E]), CW, CH, OL, gap=1)
        for (m, note), base, half in zip(pair, (DOT_TRAIL, DOT_LEAD), (0, 1)):
            rgb = mask_to_rgb(m, OL)[:, half * CW:(half + 1) * CW]
            put_cell(data, base + d, ana.rgb_to_vals(rgb))
            replaced.add(base + d)
            if note:
                shifts["%X" % (base + d)] = note
    blocks = {}
    for lname, first, lc, lr in LOGOS:
        if lname == "pilot_small":
            block = analog_logo_vals(dd_monogram(logo_path), lc * CW, lr * CH, OL)
        else:
            block = logo_cells(lambda: ana.logo_block(logo_path), lc, lr)
        blocks[lname] = block
        for r in range(lr):
            for c in range(lc):
                put_cell(data, first + r * lc + c,
                         block[r * CH:(r + 1) * CH, c * CW:(c + 1) * CW])
                replaced.add(first + r * lc + c)
    assert 255 not in replaced and 256 not in replaced   # font metadata
    write_mcm512(ANALOG_OUT, data, nl)
    back, _ = read_mcm512(ANALOG_OUT)
    assert back == data
    same = changed = 0
    for n in range(NCHARS):
        eq = back[n * 64:(n + 1) * 64] == stock[n * 64:(n + 1) * 64]
        if n not in replaced:
            assert eq, "char 0x%X changed but is not in the replace list" % n
        # metadata bytes 54..63 must survive on every character
        assert back[n * 64 + 54:(n + 1) * 64] == stock[n * 64 + 54:(n + 1) * 64]
        same += eq
        changed += not eq
    return ANALOG_OUT, data, blocks, replaced, same, changed, shifts


# --------------------------------------------------------------- preview ----

ANALOG_RGB = np.array([[0, 0, 0], [127, 127, 127], [255, 255, 255], [127, 127, 127]],
                      np.uint8)
SEE = (58, 86, 130)   # preview colour for see-through pixels


def labelled_sheet(get_cell, cw, chh, first, count, up, path):
    lab = 22
    im = Image.new("RGB", (16 * (cw * up + lab + 4), (count // 16) * (chh * up + 4)),
                   (20, 20, 20))
    d = ImageDraw.Draw(im)
    for i in range(count):
        n = first + i
        cell = get_cell(n).copy()
        cell[np.all(cell == dig.TRANSPARENT, axis=2)] = SEE
        rr, cc = divmod(i, 16)
        x, y = cc * (cw * up + lab + 4), rr * (chh * up + 4)
        d.text((x + 1, y + 2), "%X" % n, fill=(230, 200, 90))
        im.paste(Image.fromarray(cell).resize((cw * up, chh * up), Image.NEAREST),
                 (x + lab, y))
    im.save(path)


def sample_line(get_cell, codes, cw, chh, up, path):
    row = np.concatenate([get_cell(c) for c in codes], axis=1).copy()
    row[np.all(row == dig.TRANSPARENT, axis=2)] = SEE
    Image.fromarray(row).resize((row.shape[1] * up, chh * up), Image.NEAREST).save(path)


def save_block(block, up, path):
    b = block.copy()
    b[np.all(b == dig.TRANSPARENT, axis=2)] = SEE
    Image.fromarray(b).resize((b.shape[1] * up, b.shape[0] * up), Image.NEAREST).save(path)


def sample_codes():
    """ "BAT 16.8V 12.5A 88%", a coordinate and "{ARM} *NAV*" as INAV codes."""
    def num(s):
        out = []
        for i, ch in enumerate(s):
            if ch == ".":
                continue
            c = ord(ch)
            if i + 1 < len(s) and s[i + 1] == ".":
                c = DOT_TRAIL + int(ch)
            elif i > 0 and s[i - 1] == ".":
                c = DOT_LEAD + int(ch)
            out.append(c)
        return out
    return ([ord(c) for c in "BAT "] + num("16.8") + [0x1F, 0x20] + num("12.5") +
            [0x6A, 0x20] + [ord(c) for c in "88% "] + [0x03] + num("-33.8674") +
            [0x20] + [ord(c) for c in "{ARM} *NAV* 0123456789"])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--logo", required=True, help="DroneDaddy logo PNG (RGBA)")
    ap.add_argument("--preview-dir", help="write preview PNGs here")
    a = ap.parse_args()
    fonts = dig.load_fonts()
    pv = a.preview_dir
    if pv:
        os.makedirs(pv, exist_ok=True)

    for name, cw, chh, ol in GOGGLE_SIZES:
        out, sheet, blocks, replaced, same, changed, shifts = \
            build_goggle(name, cw, chh, ol, fonts, a.logo)
        print("%s  %d bytes  %d cells replaced (%d differ from stock), %d stock"
              % (out, os.path.getsize(out), len(replaced), changed, NCHARS - len(replaced)))
        if shifts:
            print("  dotted digits moved (px) or narrowed to clear the dot:", shifts)
        if not pv:
            continue
        get = lambda n, s=sheet, w=cw, h=chh: s[cell_slice(n, w, h)]  # noqa: E731
        tag = "sd" if name == "INAV_000" else "fhd"
        up = 2 if tag == "sd" else 1
        Image.fromarray(sheet).save(os.path.join(pv, "goggle_%s_sheet.png" % tag))
        for first in (0, 128, 256, 384):
            labelled_sheet(get, cw, chh, first, 128, up, os.path.join(
                pv, "goggle_%s_%03X_%03X.png" % (tag, first, first + 127)))
        for lname, block in blocks.items():
            save_block(block, 3 if tag == "sd" else 2,
                       os.path.join(pv, "goggle_%s_%s.png" % (tag, lname)))
        sample_line(get, sample_codes(), cw, chh, up,
                    os.path.join(pv, "goggle_%s_sample.png" % tag))

    out, data, blocks, replaced, same, changed, shifts = build_analog(fonts, a.logo)
    print("%s  %d bytes  %d chars replaced (%d differ from stock), %d stock"
          % (out, os.path.getsize(out), len(replaced), changed, NCHARS - len(replaced)))
    if shifts:
        print("  dotted digits moved (px) or narrowed to clear the dot:", shifts)
    if pv:
        get = lambda n: ANALOG_RGB[cell_vals(data, n)]  # noqa: E731
        for first in (0, 256):
            labelled_sheet(get, ana.CW, ana.CH, first, 256, 3, os.path.join(
                pv, "analog_%03X_%03X.png" % (first, first + 255)))
        for lname, block in blocks.items():
            save_block(ANALOG_RGB[block], 4, os.path.join(pv, "analog_%s.png" % lname))
        sample_line(get, sample_codes(), ana.CW, ana.CH, 4,
                    os.path.join(pv, "analog_sample.png"))


if __name__ == "__main__":
    main()
