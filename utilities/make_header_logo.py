#!/usr/bin/env python3
"""Generate LVGL 8 32-bit true-colour DroneDaddy header logo sources."""

from pathlib import Path
import argparse

from PIL import Image


REPO = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path(
    "/home/madman/.claude/jobs/bdff39a6/tmp/dd/DroneDaddy_DTF_Pack/"
    "02_Transparent_PNG_300dpi/1B_Horizontal_BluePink_300mmW_300dpi.png"
)
DEFAULT_OUTPUTS = (
    REPO / "src/image/goggle/img_logo.c",
    REPO / "src/image/goggle2/img_logo.c",
)
WIDTH, HEIGHT = 264, 96
PADDING_X, PADDING_Y = 8, 8
BACKGROUND = (19, 19, 19, 255)


def render_logo(source: Path) -> Image.Image:
    logo = Image.open(source).convert("RGBA")
    scale = min(
        (WIDTH - 2 * PADDING_X) / logo.width,
        (HEIGHT - 2 * PADDING_Y) / logo.height,
    )
    size = (round(logo.width * scale), round(logo.height * scale))
    logo = logo.resize(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), BACKGROUND)
    canvas.alpha_composite(logo, ((WIDTH - size[0]) // 2, (HEIGHT - size[1]) // 2))
    return canvas


def emit_c(image: Image.Image) -> str:
    rgba = image.tobytes()
    bgra = bytearray()
    for offset in range(0, len(rgba), 4):
        red, green, blue, alpha = rgba[offset : offset + 4]
        bgra.extend((blue, green, red, alpha))

    rows = []
    for offset in range(0, len(bgra), 16):
        rows.append("  " + ", ".join(f"0x{value:02x}" for value in bgra[offset : offset + 16]) + ",")
    data = "\n".join(rows)
    return f'''#if defined(LV_LVGL_H_INCLUDE_SIMPLE)
#include "lvgl.h"
#else
#include "lvgl/lvgl.h"
#endif

#ifndef LV_ATTRIBUTE_MEM_ALIGN
#define LV_ATTRIBUTE_MEM_ALIGN
#endif

#ifndef LV_ATTRIBUTE_IMG_IMG_LOGO
#define LV_ATTRIBUTE_IMG_IMG_LOGO
#endif

#if LV_COLOR_DEPTH != 32
#error "DroneDaddy img_logo requires LV_COLOR_DEPTH == 32"
#endif

const LV_ATTRIBUTE_MEM_ALIGN LV_ATTRIBUTE_LARGE_CONST LV_ATTRIBUTE_IMG_IMG_LOGO uint8_t img_logo_map[] = {{
{data}
}};

const lv_img_dsc_t img_logo = {{
  .header.cf = LV_IMG_CF_TRUE_COLOR,
  .header.always_zero = 0,
  .header.reserved = 0,
  .header.w = {WIDTH},
  .header.h = {HEIGHT},
  .data_size = {WIDTH * HEIGHT} * LV_COLOR_SIZE / 8,
  .data = img_logo_map,
}};
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, action="append")
    args = parser.parse_args()
    outputs = args.output or DEFAULT_OUTPUTS
    generated = emit_c(render_logo(args.source))
    for output in outputs:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(generated)


if __name__ == "__main__":
    main()
