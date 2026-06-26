from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import secrets
import threading

from .legacy_config import EXE_DIR, FROZEN, RESOURCE_ROOT


BGM_LIBRARY_DIR = (EXE_DIR / "assets" / "bgm_library") if FROZEN else RESOURCE_ROOT / "bgm_library"


@dataclass(frozen=True)
class MusicTrack:
    path: Path
    mood: str
    bpm: float


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
            profile = ("general", bpm)
        mood, default_bpm = profile
        bpm_match = re.search(r"(\d{2,3})\s*bpm", stem)
        bpm = float(bpm_match.group(1)) if bpm_match else default_bpm
        tracks.append(MusicTrack(path=path, mood=mood, bpm=bpm))
    return tracks


def select_random_music(directory: Path | None = None) -> MusicTrack | None:
    tracks = discover_music_tracks(directory)
    if not tracks:
        return None

    global _last_track_path
    with _selection_lock:
        choices = [track for track in tracks if track.path != _last_track_path] or tracks
        track = secrets.choice(choices)
        _last_track_path = track.path
    return track
