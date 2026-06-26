from pathlib import Path
import hashlib
import math
import random
from typing import Callable

import numpy as np
from PIL import Image

from .legacy_config import VideoConfig
from .font_utils import find_chinese_font
from .music_library import select_random_music
from .renderer import CaptionRenderer, TextToken


try:
    from moviepy import AudioFileClip, CompositeAudioClip, VideoClip, concatenate_audioclips, concatenate_videoclips
except ImportError:  # MoviePy 1.x fallback
    from moviepy.editor import AudioFileClip, CompositeAudioClip, VideoClip, concatenate_audioclips, concatenate_videoclips


TRANSITIONS = ["shrink", "slide_up", "slide_down", "slide_left", "slide_right", "stand_up", "tilt_away"]
EMOTION_INTROS = ["center_zoom", "left_in", "right_in"]
EMOTION_OUTROS = ["stand_left", "stand_right", "shrink", "slide_left", "slide_right"]
BACKGROUND_MOTIONS = ["zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down"]
SEGMENT_GAP_SECONDS = 0.5


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
    narration_paths: list[str | Path | None] | None = None,
    background_paths: list[str | Path | None] | None = None,
    background_motions: list[str | None] | None = None,
    background_positions: list[tuple[float, float] | None] | None = None,
    caption_transition_keys: list[str] | None = None,
    random_bgm: bool = False,
    beat_sync: bool = False,
    bgm_bpm: float | None = None,
    log_callback: Callable[[str], None] | None = None,
) -> Path:
    if not segments:
        raise ValueError("No text found in input box.")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    renderer = CaptionRenderer(config, find_chinese_font(font_path), [])
    narration_clips = _load_narration_clips(narration_paths)
    backgrounds = _load_background_images(background_paths, len(segments))
    resolved_background_motions = _resolve_background_motions(background_motions, len(segments))
    resolved_background_positions = _resolve_background_positions(background_positions, len(segments))
    transitions = _caption_transitions(segments, config, caption_transition_keys)
    segment_durations = [
        _duration_for_segment(config, narration_clips, index)
        for index in range(len(segments))
    ]
    if random_bgm:
        music_track = select_random_music()
        if music_track is not None:
            bgm_path = music_track.path
            bgm_bpm = music_track.bpm
            if log_callback:
                log_callback(f"随机选中音乐：{music_track.path.name}")
        elif log_callback:
            log_callback("未找到内置音乐库，继续使用手动背景音乐或无背景音乐。")
    if beat_sync and bgm_bpm:
        aligned_durations = _align_segment_durations_to_beats(segment_durations, bgm_bpm)
        if aligned_durations != segment_durations:
            segment_durations = aligned_durations
            if log_callback:
                log_callback(f"已按 {bgm_bpm:g} BPM 微调片段边界，未缩短任何 TTS 音频。")
    visual_durations = [
        duration + (SEGMENT_GAP_SECONDS if index < len(segment_durations) - 1 else 0.0)
        for index, duration in enumerate(segment_durations)
    ]
    if config.caption_template == "queue":
        segment_tuple = tuple(tuple(segment) for segment in segments)
        clips = [
            _make_queue_clip(
                renderer,
                segment_tuple,
                index,
                config,
                duration=visual_durations[index],
                caption_duration=segment_durations[index],
                narration=narration_clips[index] if index < len(narration_clips) else None,
                background=backgrounds[index],
                background_motion=resolved_background_motions[index],
                background_position=resolved_background_positions[index],
            )
            for index in range(len(segments))
        ]
    elif config.caption_template == "ancient":
        segment_starts: list[float] = []
        timeline_cursor = 0.0
        for segment_duration in visual_durations:
            segment_starts.append(timeline_cursor)
            timeline_cursor += segment_duration
        clips = [
            _make_ancient_clip(
                renderer,
                segment,
                config,
                duration=visual_durations[index],
                caption_duration=segment_durations[index],
                narration=narration_clips[index] if index < len(narration_clips) else None,
                background=backgrounds[index],
                background_motion=resolved_background_motions[index],
                background_position=resolved_background_positions[index],
                timeline_start=segment_starts[index],
            )
            for index, segment in enumerate(segments)
        ]
    else:
        clips = [
            _make_token_clip(
                renderer,
                segment,
                config,
                duration=visual_durations[index],
                caption_duration=segment_durations[index],
                narration=narration_clips[index] if index < len(narration_clips) else None,
                transition=transitions[index],
                background=backgrounds[index],
                background_motion=resolved_background_motions[index],
                background_position=resolved_background_positions[index],
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
        if clip is not None:
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
    caption_duration: float | None = None,
    narration=None,
    transition: str = "shrink",
    background: Image.Image | None = None,
    background_motion: str = "zoom_in",
    background_position: tuple[float, float] = (0.5, 0.5),
):
    token_tuple = tuple(tokens)
    clip_duration = duration or config.segment_duration
    caption_end = min(caption_duration or clip_duration, clip_duration)

    def make_frame(t: float):
        if t >= caption_end:
            return np.array(renderer._background_frame(background, t, clip_duration, background_motion, background_position))
        return renderer.frame_tokens(
            token_tuple,
            t,
            clip_duration,
            transition=transition,
            background=background,
            background_motion=background_motion,
            background_position=background_position,
            caption_duration=caption_end,
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
    caption_duration: float | None = None,
    narration=None,
    background: Image.Image | None = None,
    background_motion: str = "zoom_in",
    background_position: tuple[float, float] = (0.5, 0.5),
):
    clip_duration = duration or config.segment_duration
    caption_end = min(caption_duration or clip_duration, clip_duration)

    def make_frame(t: float):
        if t >= caption_end:
            return np.array(renderer._background_frame(background, t, clip_duration, background_motion, background_position))
        return renderer.frame_queue(
            segments,
            index,
            t,
            clip_duration,
            background=background,
            background_motion=background_motion,
            background_position=background_position,
            caption_duration=caption_end,
        )

    try:
        clip = VideoClip(frame_function=make_frame, duration=clip_duration)
    except TypeError:
        clip = VideoClip(make_frame=make_frame, duration=clip_duration)
    if narration is not None:
        clip = _with_audio(clip, narration)
    return clip


def _make_ancient_clip(
    renderer: CaptionRenderer,
    tokens: list[TextToken],
    config: VideoConfig,
    duration: float | None = None,
    caption_duration: float | None = None,
    narration=None,
    background: Image.Image | None = None,
    background_motion: str = "zoom_in",
    background_position: tuple[float, float] = (0.5, 0.5),
    timeline_start: float = 0.0,
):
    token_tuple = tuple(tokens)
    clip_duration = duration or config.segment_duration
    caption_end = min(caption_duration or clip_duration, clip_duration)

    def make_frame(t: float):
        if t >= caption_end:
            return renderer.frame_ancient(
                tuple(),
                t,
                clip_duration,
                background=background,
                background_motion=background_motion,
                background_position=background_position,
                timeline_start=timeline_start,
                caption_duration=caption_end,
            )
        return renderer.frame_ancient(
            token_tuple,
            t,
            clip_duration,
            background=background,
            background_motion=background_motion,
            background_position=background_position,
            timeline_start=timeline_start,
            caption_duration=caption_end,
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


def caption_transition_for_key(key: str, config: VideoConfig) -> str:
    if config.caption_template != "senior_emotion":
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        return TRANSITIONS[digest[0] % len(TRANSITIONS)]
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    intro = EMOTION_INTROS[digest[0] % len(EMOTION_INTROS)]
    outro = EMOTION_OUTROS[digest[1] % len(EMOTION_OUTROS)]
    return f"intro:{intro}|outro:{outro}"


def _caption_transitions(segments: list[list[TextToken]], config: VideoConfig, keys: list[str] | None = None) -> list[str]:
    if config.caption_template != "senior_emotion":
        return _random_transitions(len(segments))
    resolved_keys = list(keys or [])
    return [
        caption_transition_for_key(resolved_keys[index] if index < len(resolved_keys) else ("".join(token.text for token in segment) or str(index)), config)
        for index, segment in enumerate(segments)
    ]


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


def _resolve_background_motions(values: list[str | None] | None, count: int) -> list[str]:
    supplied = list(values or [])
    if len(supplied) < count:
        supplied.extend(_random_background_motions(count - len(supplied)))
    fallback = _random_background_motions(count)
    return [
        value if value in BACKGROUND_MOTIONS else fallback[index]
        for index, value in enumerate(supplied[:count])
    ]


def _resolve_background_positions(values: list[tuple[float, float] | None] | None, count: int) -> list[tuple[float, float]]:
    supplied = list(values or [])
    supplied.extend([None] * max(0, count - len(supplied)))
    resolved: list[tuple[float, float]] = []
    for value in supplied[:count]:
        if value is None:
            resolved.append((random.uniform(0.35, 0.65), random.uniform(0.35, 0.65)))
            continue
        x, y = value
        resolved.append((min(max(float(x), 0.0), 1.0), min(max(float(y), 0.0), 1.0)))
    return resolved


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


def _load_narration_clips(paths: list[str | Path | None] | None):
    if not paths:
        return []
    clips = []
    for value in paths:
        path = Path(value) if value else None
        clips.append(AudioFileClip(str(path)) if path and path.exists() else None)
    return clips


def _duration_for_segment(config: VideoConfig, narration_clips: list, index: int) -> float:
    if index >= len(narration_clips):
        return config.segment_duration
    if narration_clips[index] is None:
        return config.segment_duration
    audio_duration = float(narration_clips[index].duration)
    minimum = config.intro_duration + config.outro_duration + 0.12
    return max(audio_duration, minimum)


def _align_segment_durations_to_beats(
    durations: list[float],
    bpm: float,
    max_extension: float = 0.22,
) -> list[float]:
    if len(durations) <= 1 or bpm <= 0:
        return durations

    beat = 60.0 / bpm
    if beat <= 0:
        return durations

    aligned = [float(duration) for duration in durations]
    cursor = 0.0
    for index in range(len(aligned) - 1):
        boundary = cursor + aligned[index]
        next_beat = beat * math.ceil((boundary - 1e-9) / beat)
        extension = next_beat - boundary
        if 0.001 < extension <= max_extension:
            aligned[index] += extension
            boundary = next_beat
        cursor = boundary
    return aligned


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
