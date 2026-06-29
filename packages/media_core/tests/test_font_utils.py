from pathlib import Path

from media_core.font_utils import find_ancient_font, find_chinese_font


def test_default_chinese_font_does_not_use_ancient_handwriting_font():
    font_name = Path(find_chinese_font()).name.lower()

    assert font_name not in {"hyshangweishoushu.ttf", "zhimangxing-regular.ttf"}


def test_ancient_font_still_uses_bundled_handwriting_font():
    font_name = Path(find_ancient_font()).name.lower()

    assert font_name in {"hyshangweishoushu.ttf", "zhimangxing-regular.ttf"}
