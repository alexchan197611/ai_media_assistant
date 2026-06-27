from pathlib import Path

from PIL import ImageFont

from .legacy_config import ANCIENT_FALLBACK_FONT, ANCIENT_FONT, BUNDLE_ROOT


WINDOWS_FONT_DIR = Path("C:/Windows/Fonts")
FONT_PATH_CANDIDATES = [
    BUNDLE_ROOT / "fonts" / "ZhiMangXing-Regular.ttf",
    BUNDLE_ROOT / "fonts" / "HYShangWeiShouShu.ttf",
    WINDOWS_FONT_DIR / "msyhbd.ttc",
    WINDOWS_FONT_DIR / "simheib.ttf",
    WINDOWS_FONT_DIR / "simhei.ttf",
    WINDOWS_FONT_DIR / "msyh.ttc",
    WINDOWS_FONT_DIR / "simsun.ttc",
    Path("/System/Library/Fonts/PingFang.ttc"),
    Path("/System/Library/Fonts/STHeiti Light.ttc"),
    Path("/System/Library/Fonts/STHeiti Medium.ttc"),
    Path("/Library/Fonts/Arial Unicode.ttf"),
    Path("/System/Library/Fonts/Supplemental/Songti.ttc"),
    Path("/System/Library/Fonts/Supplemental/Heiti TC.ttc"),
]


def find_chinese_font(custom_font: str | None = None) -> str:
    if custom_font:
        path = Path(custom_font)
        if path.exists():
            return str(path)
        raise FileNotFoundError(f"Font file not found: {custom_font}")

    for path in FONT_PATH_CANDIDATES:
        if path.exists():
            return str(path)

    raise FileNotFoundError(
        "No Chinese font found. Put a .ttf/.ttc font in storage/resources/fonts, "
        "or set a font path in the Web settings."
    )


def load_font(font_path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(font_path, size=size)


def find_ancient_font() -> str:
    if ANCIENT_FONT.exists():
        return str(ANCIENT_FONT)
    if ANCIENT_FALLBACK_FONT.exists():
        return str(ANCIENT_FALLBACK_FONT)
    return find_chinese_font()
