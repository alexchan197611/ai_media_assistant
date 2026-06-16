import argparse

from .config import DEFAULT_BGM, DEFAULT_INPUT, DEFAULT_OUTPUT, VideoConfig
from .text_utils import load_text, parse_keywords, split_chinese_sentences
from .video_builder import build_video


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate big-caption short videos from Chinese text.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Input text file path.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output mp4 path.")
    parser.add_argument("--bgm", default=str(DEFAULT_BGM), help="Optional background music mp3 path.")
    parser.add_argument("--font", default=None, help="Optional Chinese font .ttf/.ttc path.")
    parser.add_argument("--keywords", default="", help="Highlight keywords, separated by comma or space.")
    parser.add_argument("--duration", type=float, default=2.0, help="Seconds per sentence segment.")
    parser.add_argument("--fps", type=int, default=30, help="Video FPS.")
    parser.add_argument("--width", type=int, default=1080, help="Video width.")
    parser.add_argument("--height", type=int, default=1920, help="Video height.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = VideoConfig(
        width=args.width,
        height=args.height,
        fps=args.fps,
        segment_duration=args.duration,
    )

    text = load_text(args.input)
    sentences = split_chinese_sentences(text)
    output_path = build_video(
        sentences=sentences,
        output_path=args.output,
        config=config,
        keywords=parse_keywords(args.keywords),
        bgm_path=args.bgm,
        font_path=args.font,
    )
    print(f"Generated: {output_path}")
