from pathlib import Path

from PIL import ImageFont


WINDOWS_FONT_DIR = Path("C:/Windows/Fonts")
FONT_CANDIDATES = [
    "msyhbd.ttc",
    "simheib.ttf",
    "simhei.ttf",
    "msyh.ttc",
    "simsun.ttc",
]


def find_chinese_font(custom_font: str | None = None) -> str:
    if custom_font:
        path = Path(custom_font)
        if path.exists():
            return str(path)
        raise FileNotFoundError(f"Font file not found: {custom_font}")

    for name in FONT_CANDIDATES:
        path = WINDOWS_FONT_DIR / name
        if path.exists():
            return str(path)

    raise FileNotFoundError(
        "No Chinese font found. Pass --font with a .ttf/.ttc path, "
        "for example C:\\Windows\\Fonts\\msyhbd.ttc."
    )


def load_font(font_path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(font_path, size=size)

