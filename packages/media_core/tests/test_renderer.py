import numpy as np
from PIL import Image

from media_core.font_utils import find_chinese_font
from media_core.legacy_config import VideoConfig
from media_core.renderer import CaptionRenderer


def test_background_position_changes_cover_crop_focus():
    config = VideoConfig(
        width=100,
        height=100,
        font_size=24,
        background_image_dim=0.0,
        background_motion_amount=0.0,
    )
    renderer = CaptionRenderer(config, find_chinese_font(None), [])
    background = Image.new("RGB", (200, 100))
    for x in range(background.width):
        color = (255, 0, 0) if x < background.width // 2 else (0, 0, 255)
        for y in range(background.height):
            background.putpixel((x, y), color)

    left = np.asarray(renderer._background_frame(background, 0, 1, "zoom_in", (0.0, 0.5)))
    right = np.asarray(renderer._background_frame(background, 0, 1, "zoom_in", (1.0, 0.5)))

    assert left[..., 0].mean() > left[..., 2].mean()
    assert right[..., 2].mean() > right[..., 0].mean()
