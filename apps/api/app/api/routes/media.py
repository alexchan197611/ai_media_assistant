from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.config import ROOT
from app.models import Asset, AssetKind, JobType, Project
from app.schemas import AssetRead, JobRead, ModelStatus, MusicTrackRead, VoicePresetRead
from app.services.media_jobs import JobValidationError, create_job, model_status, render_project_preview_gif, render_project_preview_png
from media_core.music_library import discover_music_tracks, select_random_music

router = APIRouter(tags=["media"])
VOICE_DIR = ROOT / "storage" / "resources" / "voice"
VOICE_REFERENCE_TEXT = "你相信吗,一个不会乐器,不会唱歌,甚至五音不全的人今天也能在一分钟内,制作出自己的原创歌曲 "
VOICE_PRESET_ORDER = [
    "男性沧桑旁白",
    "男性沉稳",
    "男性纪录片解说",
    "男性老夫子",
    "女性干练",
    "女性缓慢鸡汤",
    "女性温和主妇",
    "女性温暖",
]


@router.get("/models/status", response_model=ModelStatus)
def get_model_status():
    return model_status()


def music_track_payload(track) -> dict:
    return {
        "id": track.path.name,
        "name": track.path.stem,
        "path": str(track.path),
        "mood": track.mood,
        "bpm": track.bpm,
    }


@router.get("/bgm/tracks", response_model=list[MusicTrackRead])
def list_bgm_tracks():
    return [music_track_payload(track) for track in discover_music_tracks()]


@router.get("/bgm/random", response_model=MusicTrackRead)
def random_bgm_track():
    track = select_random_music()
    if track is None:
        raise HTTPException(status_code=404, detail="未找到本地 BGM 音乐库")
    return music_track_payload(track)


@router.get("/voice/presets", response_model=list[VoicePresetRead])
def list_voice_presets():
    if not VOICE_DIR.exists():
        return []
    by_name = {
        path.stem: {
            "id": path.stem,
            "name": path.stem,
            "path": str(path),
            "reference_text": VOICE_REFERENCE_TEXT,
        }
        for path in VOICE_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in {".wav", ".mp3", ".m4a", ".flac"}
    }
    ordered = [by_name[name] for name in VOICE_PRESET_ORDER if name in by_name]
    remaining = [item for name, item in sorted(by_name.items()) if name not in VOICE_PRESET_ORDER]
    return ordered + remaining


@router.post("/projects/{project_id}/tts/all", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED)
def enqueue_tts(project_id: str, db: Session = Depends(get_db)):
    try:
        return create_job(db, project_id, JobType.tts_all)
    except JobValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/projects/{project_id}/tts/segments/{segment_id}", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED)
def enqueue_segment_tts(project_id: str, segment_id: str, db: Session = Depends(get_db)):
    try:
        return create_job(db, project_id, JobType.tts_segment, target_segment_id=segment_id)
    except JobValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/projects/{project_id}/render", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED)
def enqueue_render(project_id: str, db: Session = Depends(get_db)):
    try:
        return create_job(db, project_id, JobType.render)
    except JobValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/projects/{project_id}/outputs", response_model=list[AssetRead])
def list_outputs(project_id: str, db: Session = Depends(get_db)):
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return db.scalars(
        select(Asset)
        .where(Asset.project_id == project_id, Asset.kind == AssetKind.video)
        .order_by(Asset.created_at.desc())
    ).all()


@router.get("/projects/{project_id}/preview.png")
def project_preview(project_id: str, segment_id: str | None = None, db: Session = Depends(get_db)):
    project = db.scalar(
        select(Project)
        .options(selectinload(Project.segments))
        .where(Project.id == project_id)
    )
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return Response(render_project_preview_png(db, project, segment_id), media_type="image/png")


@router.get("/projects/{project_id}/preview.gif")
def project_preview_gif(project_id: str, segment_id: str | None = None, db: Session = Depends(get_db)):
    project = db.scalar(
        select(Project)
        .options(selectinload(Project.segments))
        .where(Project.id == project_id)
    )
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return Response(render_project_preview_gif(db, project, segment_id), media_type="image/gif")
