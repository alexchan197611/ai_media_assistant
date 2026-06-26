from copy import deepcopy
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.db.session import get_db
from app.models import Project, Segment
from app.schemas import ProjectCreate, ProjectRead, ProjectSummary, ProjectUpdate
from app.services.background_matcher import EMOTION_TEMPLATE_ID, apply_emotion_backgrounds

router = APIRouter(prefix="/projects", tags=["projects"])

def load_project(db: Session, project_id: str) -> Project:
    project = db.scalar(select(Project).options(selectinload(Project.segments)).where(Project.id == project_id))
    if not project: raise HTTPException(status_code=404, detail="项目不存在")
    return project

def apply_segments(project: Project, values) -> None:
    project.segments.clear()
    for item in sorted(values, key=lambda value: value.order):
        project.segments.append(Segment(**item.model_dump(mode="json")))

@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(name=payload.name)
    apply_segments(project, payload.segments)
    db.add(project); db.commit()
    return load_project(db, project.id)

@router.get("", response_model=list[ProjectSummary])
def list_projects(db: Session = Depends(get_db)):
    return db.scalars(select(Project).order_by(Project.updated_at.desc())).all()

@router.post("/{project_id}/duplicate", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def duplicate_project(project_id: str, db: Session = Depends(get_db)):
    source = load_project(db, project_id)
    project = Project(
        name=f"{source.name} 副本",
        canvas=deepcopy(source.canvas),
        template_id=source.template_id,
        tts_settings=deepcopy(source.tts_settings),
        bgm_settings=deepcopy(source.bgm_settings),
    )
    for segment in source.segments:
        project.segments.append(
            Segment(
                id=str(uuid4()),
                order=segment.order,
                text=segment.text,
                marks=deepcopy(segment.marks),
                text_color=segment.text_color,
                background_asset_id=segment.background_asset_id,
                background_motion=segment.background_motion,
                background_position_x=segment.background_position_x,
                background_position_y=segment.background_position_y,
                tts_audio_asset_id=None,
                audio_duration_ms=None,
                status="draft",
            )
        )
    db.add(project)
    db.commit()
    return load_project(db, project.id)

@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, db: Session = Depends(get_db)):
    return load_project(db, project_id)

@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(project_id: str, payload: ProjectUpdate, db: Session = Depends(get_db)):
    project = load_project(db, project_id)
    changes = payload.model_dump(exclude_unset=True, exclude={"segments"})
    for key, value in changes.items(): setattr(project, key, value)
    if "segments" in payload.model_fields_set: apply_segments(project, payload.segments or [])
    if project.template_id == EMOTION_TEMPLATE_ID:
        apply_emotion_backgrounds(db, project)
    db.commit()
    return load_project(db, project_id)

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, db: Session = Depends(get_db)):
    db.delete(load_project(db, project_id)); db.commit(); return Response(status_code=204)
