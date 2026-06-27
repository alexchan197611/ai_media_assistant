from dataclasses import dataclass
from pathlib import Path
import sys


WEB_PROJECT_ROOT = Path(__file__).resolve().parents[4]
PROJECT_ROOT = WEB_PROJECT_ROOT
RESOURCE_ROOT = WEB_PROJECT_ROOT / "storage" / "resources"
FROZEN = getattr(sys, "frozen", False)
EXE_DIR = Path(sys.executable).resolve().parent if FROZEN else WEB_PROJECT_ROOT
BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", EXE_DIR)) if FROZEN else RESOURCE_ROOT
DEFAULT_OUTPUT_ROOT = WEB_PROJECT_ROOT / "storage" / "outputs"


@dataclass(frozen=True)
class VideoConfig:
    width: int = 1080
    height: int = 1920
    fps: int = 30
    segment_duration: float = 2.0
    background_color: tuple[int, int, int] = (0, 0, 0)
    text_color: tuple[int, int, int, int] = (255, 255, 255, 255)
    highlight_color: tuple[int, int, int, int] = (255, 214, 10, 255)
    font_size: int = 108
    highlight_scale: float = 1.08
    max_text_width_ratio: float = 0.82
    line_spacing: int = 28
    intro_duration: float = 0.35
    outro_duration: float = 0.28
    outro_scale: float = 0.72
    heartbeat_interval_ms: int = 700
    caption_position_y: float = 0.5
    caption_template: str = "queue"
    background_image_dim: float = 0.48
    background_motion_amount: float = 0.08
    bgm_volume: float = 0.30
    video_codec: str = "libx264"
    audio_codec: str = "aac"


DEFAULT_INPUT = WEB_PROJECT_ROOT / "input.txt" if not FROZEN else EXE_DIR / "input.txt"
DEFAULT_BGM = RESOURCE_ROOT / "bgm.mp3" if not FROZEN else EXE_DIR / "assets" / "bgm.mp3"
DEFAULT_OUTPUT = DEFAULT_OUTPUT_ROOT / "video.mp4"
DEFAULT_OUTPUT_DIR = DEFAULT_OUTPUT_ROOT
ANCIENT_FONT = BUNDLE_ROOT / "fonts" / "HYShangWeiShouShu.ttf"
ANCIENT_FALLBACK_FONT = BUNDLE_ROOT / "fonts" / "ZhiMangXing-Regular.ttf"
ANCIENT_BACKGROUND = BUNDLE_ROOT / "ancient" / "ancient_background.png"
ANCIENT_VOICE = BUNDLE_ROOT / "ancient" / "ancient_voice.wav"
ANCIENT_REFERENCE_TEXT = "你相信吗,一个不会乐器,不会唱歌,甚至五音不全的人今天也能在一分钟内,制作出自己的原创歌曲"
