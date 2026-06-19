from pathlib import Path
import random
from typing import Callable

from PIL import Image

from .config import VideoConfig
from .font_utils import find_chinese_font
from .music_library import plan_random_music
from .renderer import CaptionRenderer, TextToken


try:
    from moviepy import AudioFileClip, CompositeAudioClip, VideoClip, concatenate_audioclips, concatenate_videoclips
except ImportError:  # MoviePy 1.x fallback
    from moviepy.editor import AudioFileClip, CompositeAudioClip, VideoClip, concatenate_audioclips, concatenate_videoclips


TRANSITIONS = ["shrink", "slide_up", "slide_down", "slide_left", "slide_right", "stand_up", "tilt_away"]
BACKGROUND_MOTIONS = ["zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down"]


def build_video(
    sentences: list[str],
    output_path: str | Path,
    config: VideoConfig,
    keywords: list[str] | None = None,
    bgm_path: str | Path | None = None,
    font_path: str | None = None,
) -> Path:
    if not sentences:
        raise ValueError("No sentences found in input text.")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    renderer = CaptionRenderer(config, find_chinese_font(font_path), keywords or [])
    clips = [_make_caption_clip(renderer, sentence, config) for sentence in sentences]
    final_clip = concatenate_videoclips(clips, method="compose")

    bgm = _load_bgm(bgm_path, final_clip.duration, config.bgm_volume)
    if bgm is not None:
        final_clip = _with_audio(final_clip, bgm)

    final_clip.write_videofile(
        str(output_path),
        fps=config.fps,
        codec=config.video_codec,
        audio_codec=config.audio_codec,
        preset="medium",
        threads=4,
        logger=None,
    )

    final_clip.close()
    for clip in clips:
        clip.close()
    if bgm is not None:
        bgm.close()

    return output_path


def build_video_from_token_segments(
    segments: list[list[TextToken]],
    output_path: str | Path,
    config: VideoConfig,
    bgm_path: str | Path | None = None,
    font_path: str | None = None,
    narration_paths: list[str | Path] | None = None,
    background_paths: list[str | Path | None] | None = None,
    random_bgm: bool = False,
    log_callback: Callable[[str], None] | None = None,
) -> Path:
    if not segments:
        raise ValueError("No text found in input box.")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    renderer = CaptionRenderer(config, find_chinese_font(font_path), [])
    narration_clips = _load_narration_clips(narration_paths)
    backgrounds = _load_background_images(background_paths, len(segments))
    background_motions = _random_background_motions(len(segments))
    transitions = _random_transitions(len(segments))
    segment_durations = [
        _duration_for_segment(config, narration_clips, index)
        for index in range(len(segments))
    ]
    if random_bgm:
        music_plan = plan_random_music(segment_durations)
        if music_plan is not None:
            bgm_path = music_plan.track.path
            segment_durations = list(music_plan.segment_durations)
            if log_callback:
                log_callback(
                    f"随机选中音乐：{music_plan.track.path.name}（{music_plan.track.bpm:.0f} BPM）"
                )
        elif log_callback:
            log_callback("未找到内置音乐库，继续使用手动背景音乐或无背景音乐。")
    if config.caption_template == "queue":
        segment_tuple = tuple(tuple(segment) for segment in segments)
        clips = [
            _make_queue_clip(
                renderer,
                segment_tuple,
                index,
                config,
                duration=segment_durations[index],
                narration=narration_clips[index] if index < len(narration_clips) else None,
                background=backgrounds[index],
                background_motion=background_motions[index],
            )
            for index in range(len(segments))
        ]
    else:
        clips = [
            _make_token_clip(
                renderer,
                segment,
                config,
                duration=segment_durations[index],
                narration=narration_clips[index] if index < len(narration_clips) else None,
                transition=transitions[index],
                background=backgrounds[index],
                background_motion=background_motions[index],
            )
            for index, segment in enumerate(segments)
        ]
    final_clip = concatenate_videoclips(clips, method="compose")

    bgm = _load_bgm(bgm_path, final_clip.duration, config.bgm_volume)
    if bgm is not None:
        final_clip = _with_background_music(final_clip, bgm)

    final_clip.write_videofile(
        str(output_path),
        fps=config.fps,
        codec=config.video_codec,
        audio_codec=config.audio_codec,
        preset="medium",
        threads=4,
        logger=None,
    )

    final_clip.close()
    for clip in clips:
        clip.close()
    for clip in narration_clips:
        clip.close()
    if bgm is not None:
        bgm.close()

    return output_path


def _make_caption_clip(renderer: CaptionRenderer, sentence: str, config: VideoConfig):
    def make_frame(t: float):
        return renderer.frame(sentence, t, config.segment_duration)

    try:
        return VideoClip(frame_function=make_frame, duration=config.segment_duration)
    except TypeError:
        return VideoClip(make_frame=make_frame, duration=config.segment_duration)


def _make_token_clip(
    renderer: CaptionRenderer,
    tokens: list[TextToken],
    config: VideoConfig,
    duration: float | None = None,
    narration=None,
    transition: str = "shrink",
    background: Image.Image | None = None,
    background_motion: str = "zoom_in",
):
    token_tuple = tuple(tokens)
    clip_duration = duration or config.segment_duration

    def make_frame(t: float):
        return renderer.frame_tokens(
            token_tuple,
            t,
            clip_duration,
            transition=transition,
            background=background,
            background_motion=background_motion,
        )

    try:
        clip = VideoClip(frame_function=make_frame, duration=clip_duration)
    except TypeError:
        clip = VideoClip(make_frame=make_frame, duration=clip_duration)
    if narration is not None:
        clip = _with_audio(clip, narration)
    return clip


def _make_queue_clip(
    renderer: CaptionRenderer,
    segments: tuple[tuple[TextToken, ...], ...],
    index: int,
    config: VideoConfig,
    duration: float | None = None,
    narration=None,
    background: Image.Image | None = None,
    background_motion: str = "zoom_in",
):
    clip_duration = duration or config.segment_duration

    def make_frame(t: float):
        return renderer.frame_queue(
            segments,
            index,
            t,
            clip_duration,
            background=background,
            background_motion=background_motion,
        )

    try:
        clip = VideoClip(frame_function=make_frame, duration=clip_duration)
    except TypeError:
        clip = VideoClip(make_frame=make_frame, duration=clip_duration)
    if narration is not None:
        clip = _with_audio(clip, narration)
    return clip


def _random_transitions(count: int) -> list[str]:
    rng = random.Random()
    transitions: list[str] = []
    previous = ""
    for _ in range(count):
        choices = [item for item in TRANSITIONS if item != previous]
        selected = rng.choice(choices)
        transitions.append(selected)
        previous = selected
    return transitions


def _random_background_motions(count: int) -> list[str]:
    rng = random.Random()
    motions: list[str] = []
    previous = ""
    for _ in range(count):
        choices = [item for item in BACKGROUND_MOTIONS if item != previous]
        selected = rng.choice(choices)
        motions.append(selected)
        previous = selected
    return motions


def _load_background_images(
    paths: list[str | Path | None] | None,
    count: int,
) -> list[Image.Image | None]:
    values = list(paths or [])
    values.extend([None] * max(0, count - len(values)))
    images: list[Image.Image | None] = []
    for value in values[:count]:
        path = Path(value) if value else None
        if path is None or not path.exists():
            images.append(None)
            continue
        try:
            with Image.open(path) as source:
                images.append(source.convert("RGB").copy())
        except OSError:
            images.append(None)
    return images


def _load_narration_clips(paths: list[str | Path] | None):
    if not paths:
        return []
    return [AudioFileClip(str(path)) for path in paths]


def _duration_for_segment(config: VideoConfig, narration_clips: list, index: int) -> float:
    if index >= len(narration_clips):
        return config.segment_duration
    audio_duration = float(narration_clips[index].duration)
    minimum = config.intro_duration + config.outro_duration + 0.12
    return max(audio_duration, minimum)


def _load_bgm(path: str | Path | None, duration: float, volume: float):
    if not path:
        return None
    path = Path(path)
    if not path.exists():
        return None

    audio = AudioFileClip(str(path))
    if float(audio.duration) < duration:
        repeats = max(2, int(duration / max(0.001, float(audio.duration))) + 1)
        audio = concatenate_audioclips([audio] * repeats)
    audio = _subclip(audio, 0, duration)
    return _volume(audio, volume)


def _subclip(clip, start: float, end: float):
    if hasattr(clip, "subclipped"):
        return clip.subclipped(start, end)
    return clip.subclip(start, end)


def _volume(clip, factor: float):
    if hasattr(clip, "with_volume_scaled"):
        return clip.with_volume_scaled(factor)
    return clip.volumex(factor)


def _with_audio(video_clip, audio_clip):
    if hasattr(video_clip, "with_audio"):
        return video_clip.with_audio(audio_clip)
    return video_clip.set_audio(audio_clip)


def _with_background_music(video_clip, bgm_clip):
    existing_audio = getattr(video_clip, "audio", None)
    if existing_audio is None:
        return _with_audio(video_clip, bgm_clip)
    mixed = CompositeAudioClip([existing_audio, bgm_clip])
    return _with_audio(video_clip, mixed)
