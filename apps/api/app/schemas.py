from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator

class SegmentBase(BaseModel):
    id: UUID
    order: int = Field(ge=0)
    text: str = Field(min_length=1)
    marks: list[dict] = Field(default_factory=list)
    text_color: str | None = None
    background_asset_id: UUID | None = None
    background_motion: str | None = None
    background_position_x: float = Field(default=0.5, ge=0.0, le=1.0)
    background_position_y: float = Field(default=0.5, ge=0.0, le=1.0)
    tts_audio_asset_id: UUID | None = None
    audio_duration_ms: int | None = None
    status: str = "draft"

class ProjectCreate(BaseModel):
    name: str = Field(default="未命名项目", min_length=1, max_length=120)
    segments: list[SegmentBase] = Field(default_factory=list)

class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    canvas: dict | None = None
    template_id: str | None = None
    tts_settings: dict | None = None
    bgm_settings: dict | None = None
    segments: list[SegmentBase] | None = None

    @model_validator(mode="after")
    def unique_segment_ids(self):
        if self.segments is not None and len({s.id for s in self.segments}) != len(self.segments):
            raise ValueError("segment ids must be unique")
        return self

class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; name: str; canvas: dict; template_id: str; tts_settings: dict; bgm_settings: dict
    created_at: datetime; updated_at: datetime; segments: list[SegmentBase]

class ProjectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; name: str; template_id: str; created_at: datetime; updated_at: datetime

class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    target_segment_id: UUID | None = None
    result_asset_id: UUID | None = None
    type: str
    status: str
    progress: float
    stage: str
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

class WorkerStatus(BaseModel):
    online: bool
    pid: int | None = None
    current_job_id: UUID | None = None
    updated_at: datetime | None = None
    stale_seconds: float | None = None
    heartbeat_file: str

class ModelStatus(BaseModel):
    qwen_available: bool
    qwen_model_dir: str
    qwen_python: str
    omnivoice_available: bool
    omnivoice_project_dir: str
    omnivoice_python: str
    ffmpeg_available: bool
    ffmpeg_path: str
    ancient_voice_available: bool
    ancient_voice_path: str
    ancient_font_available: bool
    ancient_font_path: str
    ancient_reference_text: str

class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID | None = None
    kind: str
    original_name: str
    storage_path: str
    mime_type: str
    size: int
    duration_ms: int | None = None
    sha256: str
    created_at: datetime

class MusicTrackRead(BaseModel):
    id: str
    name: str
    path: str
    mood: str
    bpm: float

class VoicePresetRead(BaseModel):
    id: str
    name: str
    path: str
    reference_text: str
