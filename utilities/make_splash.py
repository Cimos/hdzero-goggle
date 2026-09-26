#!/usr/bin/env python3
"""Generate the DroneDaddy startup splash used in the app filesystem."""

from pathlib import Path
import argparse

from PIL import Image


REPO = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path(
    "/home/madman/.claude/jobs/bdff39a6/tmp/dd/DroneDaddy_DTF_Pack/"
    "02_Transparent_PNG_300dpi/1B_Horizontal_BluePink_300mmW_300dpi.png"
)
DEFAULT_OUTPUT = REPO / "mkapp/app/resource/splash.png"
WIDTH, HEIGHT = 1928, 1088


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    logo = Image.open(args.source).convert("RGBA")
    target_width = round(WIDTH * 0.55)
    target_height = round(logo.height * target_width / logo.width)
    logo = logo.resize((target_width, target_height), Image.Resampling.LANCZOS)

    splash = Image.new("RGB", (WIDTH, HEIGHT), "black")
    position = ((WIDTH - target_width) // 2, (HEIGHT - target_height) // 2)
    splash.paste(logo, position, logo)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    splash.save(args.output, format="PNG", optimize=True)


if __name__ == "__main__":
    main()
