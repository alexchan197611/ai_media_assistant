from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models import Asset, AssetKind
from app.schemas import AssetRead

router = APIRouter(prefix="/assets", tags=["assets"])

ALLOWED_EXTENSIONS = {
    AssetKind.image: {".png", ".jpg", ".jpeg", ".webp"},
    AssetKind.reference_audio: {".wav", ".mp3", ".m4a", ".flac"},
    AssetKind.bgm: {".wav", ".mp3", ".m4a", ".flac"},
}

MIME_BY_EXTENSION = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".flac": "audio/flac",
}


@router.post("", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
async def upload_asset(kind: AssetKind, project_id: str | None = None, file: UploadFile = File(...), db: Session = Depends(get_db)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS[kind]:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS[kind]))
        raise HTTPException(status_code=400, detail=f"不支持的文件格式，允许：{allowed}")

    asset_id = str(uuid4())
    target_dir = settings.upload_dir / kind.value
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{asset_id}{suffix}"
    digest = hashlib.sha256()
    size = 0

    with target_path.open("wb") as handle:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
            handle.write(chunk)

    if size == 0:
        target_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="上传文件为空")

    asset = Asset(
        id=asset_id,
        project_id=project_id,
        kind=kind,
        original_name=file.filename or target_path.name,
        storage_path=str(target_path),
        mime_type=file.content_type or MIME_BY_EXTENSION.get(suffix, "application/octet-stream"),
        size=size,
        duration_ms=None,
        sha256=digest.hexdigest(),
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@router.get("/{asset_id}", response_model=AssetRead)
def get_asset(asset_id: str, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="素材不存在")
    return asset


@router.get("/{asset_id}/content")
def get_asset_content(asset_id: str, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="素材不存在")
    path = Path(asset.storage_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="素材文件不存在")
    return FileResponse(path, media_type=asset.mime_type, filename=asset.original_name)
