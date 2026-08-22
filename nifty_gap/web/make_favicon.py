"""Generate favicon files from the source icon.

Source `assets/icon.png` is gitignored (4.7MB, 2048x2048). Run once and
commit the small outputs under `nifty_gap/web/static/` so Render deploys
from git without the source.

Usage: python -m nifty_gap.web.make_favicon
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "assets" / "icon.png"
OUT = Path(__file__).resolve().parent / "static"

SIZES: dict[str, tuple[int, ...]] = {
    "favicon.ico": (16, 32, 48),
    "apple-touch-icon.png": (180,),
    "icon-192.png": (192,),
}


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"source icon not found: {SRC}")
    img = Image.open(SRC).convert("RGBA")
    OUT.mkdir(parents=True, exist_ok=True)
    for name, sizes in SIZES.items():
        if name.endswith(".ico"):
            img.save(OUT / name, sizes=[(s, s) for s in sizes])
        else:
            (s,) = sizes
            img.resize((s, s), Image.LANCZOS).save(OUT / name)
    for f in sorted(OUT.iterdir()):
        print(f"{f.name}: {f.stat().st_size} bytes")


if __name__ == "__main__":
    main()
