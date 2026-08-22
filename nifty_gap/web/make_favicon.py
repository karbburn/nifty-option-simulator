"""Generate favicon files for Nifty Gap Lab.

Draws the brand mark directly (petrol tile + white candles, mirroring the
header logo) so no large source asset is required. Outputs land under
``nifty_gap/web/static/`` and are committed so Render deploys from git.

Usage: python -m nifty_gap.web.make_favicon
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent / "static"

BG = (14, 90, 99, 255)  # --accent petrol (#0e5a63)

SIZES: dict[str, tuple[int, ...]] = {
    "favicon.ico": (16, 32, 48),
    "apple-touch-icon.png": (180,),
    "icon-192.png": (192,),
}


def brand_mark(size: int) -> Image.Image:
    """Render the two-candle glyph on a rounded tile at any size."""
    k = size / 24.0  # design grid: 24x24 like the header SVG
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    radius = max(2, int(5.5 * k))
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=BG)

    def wick(x: float, y0: float, y1: float, alpha: int = 255) -> None:
        d.line(
            [(round(x * k), round(y0 * k)), (round(x * k), round(y1 * k))],
            fill=(255, 255, 255, alpha),
            width=max(1, round(1.8 * k)),
        )

    def body(x0: float, y0: float, x1: float, y1: float, alpha: int = 255) -> None:
        d.rounded_rectangle(
            [round(x0 * k), round(y0 * k), round(x1 * k), round(y1 * k)],
            radius=max(1, int(1.2 * k)),
            fill=(255, 255, 255, alpha),
        )

    # left candle (lower), right candle (higher, dimmed) — same as header mark
    wick(9, 4.5, 19.5)
    body(6, 9, 12, 16)
    wick(17, 3, 21, 150)
    body(14, 6, 20, 14, 150)
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, sizes in SIZES.items():
        if name.endswith(".ico"):
            master = brand_mark(max(sizes))
            master.save(OUT / name, sizes=[(s, s) for s in sizes])
        else:
            (s,) = sizes
            brand_mark(s).save(OUT / name)
    for f in sorted(OUT.iterdir()):
        print(f"{f.name}: {f.stat().st_size} bytes")


if __name__ == "__main__":
    main()
