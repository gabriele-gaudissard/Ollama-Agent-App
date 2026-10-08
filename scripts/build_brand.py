"""Rebuild the original Veyq vector mark and Windows icon (development only).

Requires resvg-py and Pillow. Shapes are explicit original vector paths.
"""
from io import BytesIO
from pathlib import Path
import resvg_py
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "assets" / "brand"
MARK = '<path d="M24 30H44L64 75L84 30H104L74 99H54Z" fill="{ink}"/><path d="M64 47H110V56H64Z" fill="{background}"/>'


def svg(width, height, content, title):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc"><title id="title">{title}</title><desc id="desc">Original Veyq split-V mark: action with a controlled boundary.</desc>{content}</svg>\n'


def build():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for theme, surface, ink, text in (("dark", "#111620", "#9df3ce", "#e8edf7"), ("light", "#f2f6f4", "#175d49", "#14251e")):
        symbol = f'<rect x="1" y="1" width="126" height="126" rx="28" fill="{surface}"/>' + MARK.format(ink=ink, background=surface)
        mark = svg(128, 128, symbol, f"Veyq mark — {theme}")
        (OUTPUT / f"mark-{theme}.svg").write_text(mark, encoding="utf-8")
        lockup = f'<rect width="368" height="160" rx="24" fill="{surface}"/><g transform="translate(16 16)">{symbol}</g><text x="166" y="106" fill="{text}" font-family="Segoe UI,Arial,sans-serif" font-size="80" font-weight="600" letter-spacing="-4">Veyq</text>'
        wordmark = svg(368, 160, lockup, f"Veyq logo — {theme}")
        (OUTPUT / f"logo-{theme}.svg").write_text(wordmark, encoding="utf-8")
        (OUTPUT / f"logo-{theme}.png").write_bytes(resvg_py.svg_to_bytes(svg_string=wordmark, width=1560))
        if theme == "dark":
            rendered = resvg_py.svg_to_bytes(svg_string=mark, width=512)
            image = Image.open(BytesIO(rendered)).convert("RGBA")
            image.save(OUTPUT / "veyq-dark.ico", format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
            (OUTPUT / "icon-dark.png").write_bytes(rendered)
    print("Built light/dark logos and seven-size Windows icon.")


if __name__ == "__main__":
    build()
