from dataclasses import dataclass
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FROZEN = getattr(sys, "frozen", False)
EXE_DIR = Path(sys.executable).resolve().parent if FROZEN else PROJECT_ROOT
DEFAULT_OUTPUT_ROOT = Path("D:/Codex/outputs/ai_caption_video") if FROZEN else PROJECT_ROOT / "output"


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
    bgm_volume: float = 0.30
    video_codec: str = "libx264"
    audio_codec: str = "aac"


DEFAULT_INPUT = PROJECT_ROOT / "input.txt" if not FROZEN else EXE_DIR / "input.txt"
DEFAULT_BGM = PROJECT_ROOT / "assets" / "bgm.mp3" if not FROZEN else EXE_DIR / "assets" / "bgm.mp3"
DEFAULT_OUTPUT = DEFAULT_OUTPUT_ROOT / "video.mp4"
DEFAULT_OUTPUT_DIR = DEFAULT_OUTPUT_ROOT
