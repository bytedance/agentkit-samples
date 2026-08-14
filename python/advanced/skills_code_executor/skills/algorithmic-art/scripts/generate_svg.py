#!/usr/bin/env python3

import argparse
import html
import random
import re


HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?$")
DEFAULT_PALETTE = "#0b132b,#1c2541,#5bc0be,#f4d35e"


def parse_palette(value: str) -> list[str]:
    colors = [color.strip() for color in value.split(",") if color.strip()]
    if len(colors) < 2:
        raise argparse.ArgumentTypeError("palette must contain at least two colors")
    if any(not HEX_COLOR.fullmatch(color) for color in colors):
        raise argparse.ArgumentTypeError("palette colors must use #RGB or #RRGGBB")
    return colors


def shape_count(value: str) -> int:
    count = int(value)
    if not 4 <= count <= 80:
        raise argparse.ArgumentTypeError("count must be between 4 and 80")
    return count


def build_svg(title: str, seed: int, palette: list[str], count: int) -> str:
    rng = random.Random(seed)
    width = 960
    height = 640
    elements = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}">'
        ),
        f"<title>{html.escape(title)}</title>",
        f'<rect width="{width}" height="{height}" fill="{palette[0]}"/>',
    ]

    for index in range(count):
        color = palette[1 + index % (len(palette) - 1)]
        x = rng.randint(40, width - 40)
        y = rng.randint(40, height - 40)
        radius = rng.randint(12, 90)
        opacity = rng.uniform(0.25, 0.85)
        elements.append(
            f'<circle cx="{x}" cy="{y}" r="{radius}" fill="{color}" '
            f'fill-opacity="{opacity:.2f}"/>'
        )

        if index:
            previous_x = rng.randint(0, width)
            previous_y = rng.randint(0, height)
            elements.append(
                f'<line x1="{previous_x}" y1="{previous_y}" x2="{x}" y2="{y}" '
                f'stroke="{color}" stroke-opacity="0.35" stroke-width="2"/>'
            )

    elements.append("</svg>")
    return "\n".join(elements)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic SVG artwork.")
    parser.add_argument("--title", default="Algorithmic Art")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--palette", type=parse_palette, default=DEFAULT_PALETTE)
    parser.add_argument("--count", type=shape_count, default=24)
    args = parser.parse_args()

    palette = (
        parse_palette(args.palette) if isinstance(args.palette, str) else args.palette
    )
    print(build_svg(args.title, args.seed, palette, args.count))


if __name__ == "__main__":
    main()
