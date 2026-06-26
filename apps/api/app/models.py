import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

def uuid4_str() -> str: return str(uuid.uuid4())
def utcnow() -> datetime: return datetime.now(timezone.utc)
def default_canvas() -> dict:
    return {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "segment_duration": 2.0,
        "font_size": 108,
        "font_path": "",
        "heartbeat_interval_ms": 700,
        "caption_position_y": 0.5,
        "background_color": "#0e1116",
    }

class SegmentStatus(str, enum.Enum):
    draft = "draft"; audio_ready = "audio_ready"; ready = "ready"; error = "error"
class AssetKind(str, enum.Enum):
    image = "image"; reference_audio = "reference_audio"; narration = "narration"; bgm = "bgm"; video = "video"
class JobType(str, enum.Enum):
    tts_segment = "tts_segment"; tts_all = "tts_all"; preview = "preview"; render = "render"
class JobStatus(str, enum.Enum):
    queued = "queued"; running = "running"; succeeded = "succeeded"; failed = "failed"; cancelled = "cancelled"

class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    name: Mapped[str] = mapped_column(String(120), default="未命名项目")
    canvas: Mapped[dict] = mapped_column(JSON, default=default_canvas)
    template_id: Mapped[str] = mapped_column(String(64), default="centered-bold")
    tts_settings: Mapped[dict] = mapped_column(JSON, default=dict)
    bgm_settings: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    segments: Mapped[list["Segment"]] = relationship(back_populates="project", cascade="all, delete-orphan", order_by="Segment.order")
    jobs: Mapped[list["Job"]] = relationship(back_populates="project", cascade="all, delete-orphan")

class Segment(Base):
    __tablename__ = "segments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    order: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    marks: Mapped[list] = mapped_column(JSON, default=list)
    text_color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    background_asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)
    background_motion: Mapped[str | None] = mapped_column(String(32), nullable=True)
    background_position_x: Mapped[float] = mapped_column(Float, default=0.5)
    background_position_y: Mapped[float] = mapped_column(Float, default=0.5)
    tts_audio_asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)
    audio_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[SegmentStatus] = mapped_column(Enum(SegmentStatus), default=SegmentStatus.draft)
    project: Mapped[Project] = relationship(back_populates="segments")

class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    kind: Mapped[AssetKind] = mapped_column(Enum(AssetKind))
    original_name: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(1024), unique=True)
    mime_type: Mapped[str] = mapped_column(String(128))
    size: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    target_segment_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    result_asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)
    type: Mapped[JobType] = mapped_column(Enum(JobType))
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.queued, index=True)
    progress: Mapped[float] = mapped_column(Float, default=0)
    stage: Mapped[str] = mapped_column(String(128), default="等待处理")
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    project: Mapped[Project] = relationship(back_populates="jobs")
