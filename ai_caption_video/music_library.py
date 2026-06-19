from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math
from pathlib import Path
import re
import secrets
import threading

import numpy as np

from .config import EXE_DIR, FROZEN, PROJECT_ROOT


BGM_LIBRARY_DIR = (EXE_DIR if FROZEN else PROJECT_ROOT) / "assets" / "bgm_library"


@dataclass(frozen=True)
class MusicTrack:
    path: Path
    mood: str
    bpm: float


@dataclass(frozen=True)
class MusicPlan:
    track: MusicTrack
    beat_phase: float
    segment_durations: tuple[float, ...]


TRACK_PROFILES = {
    "healing_story": ("healing", 76.0),
    "knowledge_clean": ("knowledge", 92.0),
    "business_growth": ("business", 106.0),
    "viral_fast": ("viral", 124.0),
    "suspense_reveal": ("suspense", 132.0),
}

_selection_lock = threading.Lock()
_last_track_path: Path | None = None


def discover_music_tracks(directory: Path | None = None) -> list[MusicTrack]:
    directory = Path(directory or BGM_LIBRARY_DIR)
    if not directory.exists():
        return []

    tracks: list[MusicTrack] = []
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() not in {".mp3", ".wav", ".m4a", ".flac"}:
            continue
        stem = path.stem.lower()
        profile = next((value for key, value in TRACK_PROFILES.items() if stem.startswith(key)), None)
        if profile is None:
            bpm_match = re.search(r"(\d{2,3})\s*bpm", stem)
            bpm = float(bpm_match.group(1)) if bpm_match else 100.0
            profile = ("general", bpm, 4.0)
        mood, default_bpm = profile
        bpm_match = re.search(r"(\d{2,3})\s*bpm", stem)
        bpm = float(bpm_match.group(1)) if bpm_match else default_bpm
        tracks.append(MusicTrack(path=path, mood=mood, bpm=bpm))
    return tracks


def plan_random_music(
    segment_durations: list[float],
    directory: Path | None = None,
) -> MusicPlan | None:
    tracks = discover_music_tracks(directory)
    if not tracks:
        return None

    global _last_track_path
    with _selection_lock:
        choices = [track for track in tracks if track.path != _last_track_path] or tracks
        track = secrets.choice(choices)
        _last_track_path = track.path
    phase = analyze_beat_phase(track.path, track.bpm)
    durations = sync_durations_to_beats(segment_durations, track.bpm, phase)
    return MusicPlan(track=track, beat_phase=phase, segment_durations=tuple(durations))


def sync_durations_to_beats(
    durations: list[float],
    bpm: float,
    phase: float = 0.0,
    max_padding: float = 0.24,
) -> list[float]:
    if not durations or bpm <= 0:
        return list(durations)

    half_beat = 30.0 / bpm
    result: list[float] = []
    timeline = 0.0
    for index, duration in enumerate(durations):
        duration = max(0.05, float(duration))
        if index == len(durations) - 1:
            result.append(duration)
            break
        natural_end = timeline + duration
        beat_index = math.ceil((natural_end - phase) / half_beat)
        next_beat = phase + beat_index * half_beat
        padding = max(0.0, next_beat - natural_end)
        adjusted = duration + padding if padding <= max_padding else duration
        result.append(adjusted)
        timeline += adjusted
    return result


@lru_cache(maxsize=16)
def _cached_beat_phase(path_text: str, modified_ns: int, bpm: float) -> float:
    try:
        from moviepy import AudioFileClip
    except ImportError:
        from moviepy.editor import AudioFileClip

    clip = AudioFileClip(path_text)
    try:
        sample_rate = 8000
        duration = min(float(clip.duration), 45.0)
        if duration <= 0.5:
            return 0.0
        samples = clip.to_soundarray(fps=sample_rate)
    finally:
        clip.close()

    if samples.ndim > 1:
        samples = samples.mean(axis=1)
    samples = np.asarray(samples, dtype=np.float32)
    hop = 256
    usable = (len(samples) // hop) * hop
    if usable < hop * 8:
        return 0.0
    frames = samples[:usable].reshape(-1, hop)
    energy = np.sqrt(np.mean(frames * frames, axis=1) + 1e-9)
    novelty = np.maximum(0.0, np.diff(energy, prepend=energy[0]))
    novelty = np.convolve(novelty, np.ones(3, dtype=np.float32) / 3.0, mode="same")

    beat = 60.0 / bpm
    frame_time = hop / sample_rate
    offsets = np.linspace(0.0, beat, 80, endpoint=False)
    best_offset = 0.0
    best_score = -1.0
    for offset in offsets:
        times = np.arange(offset, duration, beat)
        indices = np.clip(np.rint(times / frame_time).astype(int), 0, len(novelty) - 1)
        score = float(novelty[indices].sum())
        if score > best_score:
            best_score = score
            best_offset = float(offset)
    return best_offset


def analyze_beat_phase(path: Path, bpm: float) -> float:
    try:
        modified_ns = path.stat().st_mtime_ns
        return _cached_beat_phase(str(path.resolve()), modified_ns, bpm)
    except (OSError, ValueError):
        return 0.0

