from __future__ import annotations

import hashlib
import shutil
import sys
import wave
from io import BytesIO
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import ROOT, settings
from app.models import Asset, AssetKind, Job, JobStatus, JobType, Project, Segment, SegmentStatus

MEDIA_CORE_SRC = Path(__file__).resolve().parents[4] / "packages" / "media_core" / "src"
if str(MEDIA_CORE_SRC) not in sys.path:
    sys.path.insert(0, str(MEDIA_CORE_SRC))

from media_core.legacy_config import ANCIENT_FONT, ANCIENT_FALLBACK_FONT, ANCIENT_REFERENCE_TEXT, ANCIENT_VOICE, VideoConfig
from media_core.omnivoice_bridge import (
    DEFAULT_OMNIVOICE_DIR,
    OmniVoiceGenerationCancelled,
    OmniVoiceOptions,
    default_omnivoice_python,
    generate_omnivoice_audio,
    omnivoice_python_error_message,
    resolve_omnivoice_python,
    resolve_omnivoice_dir,
)
from media_core.font_utils import find_chinese_font
from media_core.renderer import CaptionRenderer, TextToken
from media_core.tts_bridge import (
    DEFAULT_TTS_MODEL_DIR,
    TTSGenerationCancelled,
    TTSOptions,
    generate_tts_audio,
    qwen_python_error_message,
    qwen_python_for_model,
    resolve_qwen_model_dir,
)
from media_core.video_builder import build_video_from_token_segments, caption_transition_for_key


TEMPLATE_MAP = {
    "scrolling-queue": "queue",
    "centered-bold": "center",
    "ancient-style": "ancient",
    "senior-emotion": "senior_emotion",
    "queue": "queue",
    "center": "center",
    "ancient": "ancient",
}
VOICE_PRESET_DIR = ROOT / "storage" / "resources" / "voice"
VOICE_PRESET_REFERENCE_TEXT = "你相信吗,一个不会乐器,不会唱歌,甚至五音不全的人今天也能在一分钟内,制作出自己的原创歌曲 "


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_job(db: Session, project_id: str, job_type: JobType, target_segment_id: str | None = None) -> Job:
    project = db.get(Project, project_id)
    if project is None:
        raise ValueError("项目不存在")
    if target_segment_id and not any(segment.id == target_segment_id for segment in project.segments):
        raise ValueError("片段不存在")
    validate_job_request(project, job_type, target_segment_id)
    job = Job(project_id=project_id, target_segment_id=target_segment_id, type=job_type, status=JobStatus.queued, progress=0, stage="等待后台 Worker")
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def retry_job(db: Session, job_id: str) -> Job:
    original = db.get(Job, job_id)
    if original is None:
        raise ValueError("任务不存在")
    return create_job(db, original.project_id, original.type, original.target_segment_id)


def mark_job(db: Session, job: Job, status: JobStatus | None = None, progress: float | None = None, stage: str | None = None) -> None:
    if status is not None:
        job.status = status
    if progress is not None:
        job.progress = progress
    if stage is not None:
        job.stage = stage
    if status == JobStatus.running and job.started_at is None:
        job.started_at = utcnow()
    if status in {JobStatus.succeeded, JobStatus.failed, JobStatus.cancelled}:
        job.finished_at = utcnow()
    db.commit()


def ensure_not_cancelled(db: Session, job: Job) -> None:
    db.refresh(job)
    if job.status == JobStatus.cancelled:
        raise CancelledJobError("任务已取消")


def is_cancel_requested(db: Session, job: Job) -> bool:
    db.refresh(job)
    return job.status == JobStatus.cancelled


class CancelledJobError(RuntimeError):
    pass


class JobValidationError(ValueError):
    pass


def fail_job(db: Session, job: Job, exc: Exception) -> None:
    if isinstance(exc, CancelledJobError):
        job.status = JobStatus.cancelled
        job.stage = "用户已取消"
        job.finished_at = utcnow()
        db.commit()
        return
    job.status = JobStatus.failed
    job.progress = min(float(job.progress or 0), 99)
    job.stage = "任务失败"
    job.error_code = exc.__class__.__name__
    job.error_message = str(exc)
    job.finished_at = utcnow()
    db.commit()


def load_project_for_job(db: Session, project_id: str) -> Project:
    project = db.scalar(
        select(Project)
        .options(selectinload(Project.segments))
        .where(Project.id == project_id)
    )
    if project is None:
        raise ValueError("项目不存在")
    return project


def validate_job_request(project: Project, job_type: JobType, target_segment_id: str | None = None) -> None:
    segments = [segment for segment in project.segments if segment.text.strip()]
    if target_segment_id:
        segments = [segment for segment in segments if segment.id == target_segment_id]
    if not segments:
        raise JobValidationError("项目没有可处理的文案片段")

    validate_canvas_settings(project)
    if job_type == JobType.render:
        validate_bgm_settings(project)

    tts_enabled = bool(project.tts_settings.get("enabled", True))
    needs_tts = job_type in {JobType.tts_all, JobType.tts_segment} or (
        job_type == JobType.render and tts_enabled and any(not segment.tts_audio_asset_id for segment in segments)
    )
    if needs_tts:
        validate_tts_settings(project)


def validate_canvas_settings(project: Project) -> None:
    canvas = project.canvas or {}
    font_path = str(canvas.get("font_path") or "").strip()
    if font_path and not Path(font_path).exists():
        raise JobValidationError(f"字体文件不存在：{font_path}")
    try:
        make_video_config(project)
    except (TypeError, ValueError) as exc:
        raise JobValidationError(f"画布参数无效：{exc}") from exc


def validate_bgm_settings(project: Project) -> None:
    bgm_path = str((project.bgm_settings or {}).get("path") or "").strip()
    if bgm_path and not Path(bgm_path).exists():
        raise JobValidationError(f"BGM 文件不存在：{bgm_path}")


def validate_tts_settings(project: Project) -> None:
    tts = project.tts_settings or {}
    engine = str(tts.get("engine") or "OmniVoice")
    if engine == "Qwen3-TTS":
        validate_qwen_settings(tts)
    elif engine == "OmniVoice":
        validate_omnivoice_settings(project, tts)
    else:
        raise JobValidationError(f"不支持的 TTS 引擎：{engine}")


def validate_qwen_settings(tts: dict) -> None:
    explicit_model_dir = str(tts.get("qwen_model_dir") or "").strip()
    model_dir = Path(explicit_model_dir) if explicit_model_dir else resolve_qwen_model_dir(DEFAULT_TTS_MODEL_DIR)
    python_exe = qwen_python_for_model(model_dir)
    if not model_dir.exists():
        raise JobValidationError(f"Qwen3-TTS 模型目录不存在：{model_dir}")
    if not python_exe.exists():
        raise JobValidationError(qwen_python_error_message(model_dir, python_exe))
    if explicit_model_dir and resolve_qwen_model_dir(model_dir) != model_dir:
        raise JobValidationError(f"Qwen3-TTS 模型目录不完整：{model_dir}")

    preset_audio = require_voice_preset_path(tts)
    mode = "voice_clone" if preset_audio else str(tts.get("qwen_mode") or "preset")
    if mode == "voice_design" and not str(tts.get("qwen_instruct") or "").strip():
        raise JobValidationError("Qwen3-TTS 语音设计模式需要填写声音、情绪或语速描述")
    if mode == "voice_clone":
        ref_audio = str(preset_audio or tts.get("qwen_ref_audio") or "").strip()
        if not ref_audio or not Path(ref_audio).exists():
            raise JobValidationError(f"Qwen3-TTS 参考音频不存在：{ref_audio or '未设置'}")
        ref_text = VOICE_PRESET_REFERENCE_TEXT if preset_audio else str(tts.get("qwen_ref_text") or "").strip()
        if not bool(tts.get("qwen_use_xvector_only", False)) and not ref_text:
            raise JobValidationError("Qwen3-TTS 语音克隆需要填写参考文本，或启用仅使用 x-vector")


def validate_omnivoice_settings(project: Project, tts: dict) -> None:
    explicit_project_dir = str(tts.get("omnivoice_project_dir") or "").strip()
    project_dir = Path(explicit_project_dir) if explicit_project_dir else resolve_omnivoice_dir(DEFAULT_OMNIVOICE_DIR)
    python_exe = resolve_omnivoice_python(project_dir, str(tts.get("omnivoice_python") or "").strip() or None)
    if not project_dir.exists():
        raise JobValidationError(f"OmniVoice 项目目录不存在：{project_dir}")
    if not (project_dir / "omnivoice").exists():
        raise JobValidationError(f"OmniVoice 项目目录不完整：{project_dir}")
    if not python_exe.exists():
        raise JobValidationError(omnivoice_python_error_message(project_dir, python_exe))

    try:
        speed = float(tts.get("omnivoice_speed", 1.0))
        num_step = int(tts.get("omnivoice_num_step", 16))
    except (TypeError, ValueError) as exc:
        raise JobValidationError("OmniVoice 语速和步数必须是数字") from exc
    if speed < 0.5 or speed > 2.0:
        raise JobValidationError("OmniVoice 语速建议设置在 0.5 到 2.0 之间")
    if num_step < 4 or num_step > 64:
        raise JobValidationError("OmniVoice 步数建议设置在 4 到 64 之间")

    preset_audio = require_voice_preset_path(tts)
    mode = "clone" if preset_audio else str(tts.get("omnivoice_mode") or "auto")
    if project.template_id in {"ancient-style", "ancient"} and not tts.get("omnivoice_ref_audio") and ANCIENT_VOICE.exists():
        return
    if mode == "clone":
        ref_audio = str(preset_audio or tts.get("omnivoice_ref_audio") or "").strip()
        if not ref_audio or not Path(ref_audio).exists():
            raise JobValidationError(f"OmniVoice 参考音频不存在：{ref_audio or '未设置'}")
    if mode == "design" and not str(tts.get("omnivoice_instruct") or "").strip():
        raise JobValidationError("OmniVoice 语音设计模式需要填写语音描述")


def run_tts_job(db: Session, job: Job) -> None:
    project = load_project_for_job(db, job.project_id)
    segments = [segment for segment in project.segments if segment.text.strip()]
    if job.type == JobType.tts_segment:
        segments = [segment for segment in segments if segment.id == job.target_segment_id]
    if not segments:
        raise ValueError("项目没有可生成语音的文案")

    ensure_not_cancelled(db, job)
    mark_job(db, job, JobStatus.running, 8, "正在准备 TTS")
    try:
        audio_paths = generate_project_tts(project, segments, cancel_check=lambda: is_cancel_requested(db, job))
    except (TTSGenerationCancelled, OmniVoiceGenerationCancelled) as exc:
        raise CancelledJobError(str(exc)) from exc
    ensure_not_cancelled(db, job)
    mark_job(db, job, JobStatus.running, 75, "正在保存语音结果")
    assets = attach_narration_assets(db, project, segments, audio_paths)
    if assets:
        job.result_asset_id = assets[0].id
        db.commit()
    mark_job(db, job, JobStatus.succeeded, 100, "TTS 已完成")


def run_render_job(db: Session, job: Job) -> None:
    project = load_project_for_job(db, job.project_id)
    segments = [segment for segment in project.segments if segment.text.strip()]
    if not segments:
        raise ValueError("项目没有可渲染的文案")

    ensure_not_cancelled(db, job)
    tts_enabled = bool(project.tts_settings.get("enabled", True))
    if tts_enabled and any(not segment.tts_audio_asset_id for segment in segments):
        mark_job(db, job, JobStatus.running, 12, "正在生成缺失配音")
        try:
            audio_paths = generate_project_tts(project, segments, cancel_check=lambda: is_cancel_requested(db, job))
        except (TTSGenerationCancelled, OmniVoiceGenerationCancelled) as exc:
            raise CancelledJobError(str(exc)) from exc
        ensure_not_cancelled(db, job)
        attach_narration_assets(db, project, segments, audio_paths)
        project = load_project_for_job(db, job.project_id)
        segments = [segment for segment in project.segments if segment.text.strip()]

    mark_job(db, job, JobStatus.running, 34, "正在准备字幕、配图和音乐")
    mark_job(db, job, JobStatus.running, 42, "正在渲染视频帧与音频")
    output_path = render_project_video(
        db,
        project,
        segments,
        log_callback=lambda message: mark_job(db, job, JobStatus.running, 45, message),
    )
    ensure_not_cancelled(db, job)
    asset = create_file_asset(db, AssetKind.video, output_path, "video/mp4", duration_ms=None, project_id=project.id)
    job.result_asset_id = asset.id
    db.commit()
    mark_job(db, job, JobStatus.succeeded, 100, f"视频已生成：{Path(asset.storage_path).name}")


def generate_project_tts(project: Project, segments: list[Segment], cancel_check=None) -> list[Path]:
    settings.tts_cache_dir.mkdir(parents=True, exist_ok=True)
    output_dir = settings.tts_cache_dir / str(project.id)
    engine = project.tts_settings.get("engine", "OmniVoice")
    texts = [segment.text.strip() for segment in segments]
    if engine == "Qwen3-TTS":
        preset_audio = require_voice_preset_path(project.tts_settings)
        options = TTSOptions(
            model_dir=Path(project.tts_settings.get("qwen_model_dir") or DEFAULT_TTS_MODEL_DIR),
            mode="voice_clone" if preset_audio else project.tts_settings.get("qwen_mode", "preset"),
            speaker=project.tts_settings.get("qwen_speaker", "Vivian"),
            language=project.tts_settings.get("qwen_language", "Chinese"),
            model_size=project.tts_settings.get("qwen_model_size", "1.7B"),
            instruct=project.tts_settings.get("qwen_instruct", ""),
            ref_audio=preset_audio or _optional_path(project.tts_settings.get("qwen_ref_audio")),
            ref_text=VOICE_PRESET_REFERENCE_TEXT if preset_audio else project.tts_settings.get("qwen_ref_text", ""),
            use_xvector_only=bool(project.tts_settings.get("qwen_use_xvector_only", False)),
        )
        return generate_tts_audio(texts, output_dir, options, cancel_check=cancel_check)

    project_dir = Path(project.tts_settings.get("omnivoice_project_dir") or DEFAULT_OMNIVOICE_DIR)
    preset_audio = require_voice_preset_path(project.tts_settings)
    if preset_audio:
        ref_audio = preset_audio
        ref_text = VOICE_PRESET_REFERENCE_TEXT
        mode = "clone"
    elif project.template_id in {"ancient-style", "ancient"} and not project.tts_settings.get("omnivoice_ref_audio"):
        ref_audio = ANCIENT_VOICE if ANCIENT_VOICE.exists() else None
        ref_text = ANCIENT_REFERENCE_TEXT
        mode = "clone" if ref_audio else project.tts_settings.get("omnivoice_mode", "auto")
    else:
        ref_audio = _optional_path(project.tts_settings.get("omnivoice_ref_audio"))
        ref_text = project.tts_settings.get("omnivoice_ref_text", "")
        mode = project.tts_settings.get("omnivoice_mode", "auto")
    options = OmniVoiceOptions(
        project_dir=project_dir,
        python_exe=resolve_omnivoice_python(project_dir, project.tts_settings.get("omnivoice_python")),
        mode=mode,
        ref_audio=ref_audio,
        ref_text=ref_text,
        instruct=project.tts_settings.get("omnivoice_instruct", "female, natural, clear"),
        speed=float(project.tts_settings.get("omnivoice_speed", 1.0)),
        num_step=int(project.tts_settings.get("omnivoice_num_step", 16)),
    )
    return generate_omnivoice_audio(texts, output_dir, options, cancel_check=cancel_check)


def attach_narration_assets(db: Session, project: Project, segments: list[Segment], paths: list[Path]) -> list[Asset]:
    assets: list[Asset] = []
    for segment, path in zip(segments, paths, strict=False):
        asset = create_file_asset(db, AssetKind.narration, path, "audio/wav", duration_ms=wav_duration_ms(path), project_id=project.id)
        assets.append(asset)
        segment.tts_audio_asset_id = asset.id
        segment.audio_duration_ms = asset.duration_ms
        segment.status = SegmentStatus.audio_ready
    project.updated_at = utcnow()
    db.commit()
    return assets


def render_project_video(db: Session, project: Project, segments: list[Segment], log_callback=None) -> Path:
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = settings.output_dir / f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{project.id[:8]}.mp4"
    config = make_video_config(project)
    token_segments = [tokens_for_segment(segment) for segment in segments]
    narration_paths = [asset_path_for(db, segment.tts_audio_asset_id) for segment in segments]
    background_paths = [asset_path_for(db, segment.background_asset_id) for segment in segments]
    background_motions = [segment.background_motion for segment in segments]
    background_positions = [None for _ in segments]
    bgm_path = _optional_path(project.bgm_settings.get("path"))
    build_video_from_token_segments(
        token_segments,
        output_path,
        config,
        bgm_path=bgm_path,
        font_path=font_path_for_project(project),
        narration_paths=narration_paths,
        background_paths=background_paths,
        background_motions=background_motions,
        background_positions=background_positions,
        caption_transition_keys=[segment.id for segment in segments],
        random_bgm=bool(project.bgm_settings.get("random", False)),
        beat_sync=False,
        bgm_bpm=None,
        log_callback=log_callback,
    )
    return output_path


def render_project_preview_png(db: Session, project: Project, segment_id: str | None = None) -> bytes:
    segments = [segment for segment in project.segments if segment.text.strip()]
    if not segments:
        return blank_preview_png(project)

    active_index = 0
    if segment_id:
        active_index = next((index for index, segment in enumerate(segments) if segment.id == segment_id), 0)

    config = make_video_config(project, preview=True)
    duration = max((segments[active_index].audio_duration_ms or 2000) / 1000.0, config.segment_duration)
    t = min(max(config.intro_duration + 0.18, 0.25), max(0.25, duration - config.outro_duration - 0.05))
    image = render_preview_frame(db, project, segments, active_index, t, duration)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def render_project_preview_gif(db: Session, project: Project, segment_id: str | None = None) -> bytes:
    segments = [segment for segment in project.segments if segment.text.strip()]
    if not segments:
        config = make_video_config(project, preview=True)
        image = Image.new("RGB", (config.width, config.height), config.background_color)
        output = BytesIO()
        image.save(output, format="GIF")
        return output.getvalue()

    active_index = 0
    if segment_id:
        active_index = next((index for index, segment in enumerate(segments) if segment.id == segment_id), 0)

    config = make_video_config(project, preview=True)
    duration = max((segments[active_index].audio_duration_ms or 2000) / 1000.0, config.segment_duration)
    frame_count = 12
    frame_duration_ms = 120
    times = [min(duration - 0.001, (duration * index) / max(1, frame_count - 1)) for index in range(frame_count)]
    frames = [render_preview_frame(db, project, segments, active_index, t, duration).convert("P", palette=Image.Palette.ADAPTIVE) for t in times]
    output = BytesIO()
    frames[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=frame_duration_ms,
        loop=0,
        optimize=True,
    )
    return output.getvalue()


def render_preview_frame(db: Session, project: Project, segments: list[Segment], active_index: int, t: float, duration: float) -> Image.Image:
    config = make_video_config(project, preview=True)
    renderer = CaptionRenderer(config, find_chinese_font(font_path_for_project(project)), [])
    background = load_preview_background(db, segments[active_index])
    motion = segments[active_index].background_motion or "zoom_in"
    position = (segments[active_index].background_position_x, segments[active_index].background_position_y)
    template = TEMPLATE_MAP.get(project.template_id, "center")
    if template == "queue":
        token_segments = tuple(tuple(tokens_for_segment(segment)) for segment in segments)
        frame = renderer.frame_queue(token_segments, active_index, t, duration, background=background, background_motion=motion, background_position=position)
    elif template == "ancient":
        frame = renderer.frame_ancient(tuple(tokens_for_segment(segments[active_index])), t, duration, background=background, background_motion=motion, background_position=position)
    else:
        active_segment = segments[active_index]
        frame = renderer.frame_tokens(
            tuple(tokens_for_segment(active_segment)),
            t,
            duration,
            transition=caption_transition_for_key(active_segment.id, config),
            background=background,
            background_motion=motion,
            background_position=position,
        )
    return Image.fromarray(frame)


def make_video_config(project: Project, preview: bool = False) -> VideoConfig:
    canvas = project.canvas or {}
    width = int(canvas.get("width", 1080))
    height = int(canvas.get("height", 1920))
    scale = 0.5 if preview else 1.0
    bg = hex_to_rgb(canvas.get("background_color", "#000000"))
    return VideoConfig(
        width=max(1, int(width * scale)),
        height=max(1, int(height * scale)),
        fps=max(1, min(120, int(canvas.get("fps", 30)))),
        segment_duration=max(0.2, min(60.0, float(canvas.get("segment_duration", VideoConfig.segment_duration)))),
        background_color=bg,
        font_size=max(12, int(max(20, min(260, int(canvas.get("font_size", 108)))) * scale)),
        line_spacing=max(4, int(VideoConfig.line_spacing * scale)),
        intro_duration=float(canvas.get("intro_duration", VideoConfig.intro_duration)),
        outro_duration=float(canvas.get("outro_duration", VideoConfig.outro_duration)),
        heartbeat_interval_ms=700,
        caption_position_y=max(0.05, min(0.95, float(canvas.get("caption_position_y", 0.66 if project.template_id == "senior-emotion" else 0.5)))),
        caption_template=TEMPLATE_MAP.get(project.template_id, "center"),
        bgm_volume=float(project.bgm_settings.get("volume", 0.30)),
    )


def font_path_for_project(project: Project) -> str | None:
    canvas = project.canvas or {}
    value = str(canvas.get("font_path") or "").strip()
    return value or None


def tokens_for_segment(segment: Segment) -> list[TextToken]:
    text = segment.text
    marks = sorted(segment.marks or [], key=lambda item: int(item.get("start", 0)))
    tokens: list[TextToken] = []
    cursor = 0
    color = rgba_from_project_color(segment.text_color)
    for mark in marks:
        start = max(cursor, int(mark.get("start", 0)))
        end = min(len(text), int(mark.get("end", start)))
        if start > cursor:
            tokens.append(TextToken(text[cursor:start], False, color))
        if end > start:
            tokens.append(TextToken(text[start:end], True, color))
        cursor = max(cursor, end)
    if cursor < len(text):
        tokens.append(TextToken(text[cursor:], False, color))
    return tokens or [TextToken(text, False, color)]


def create_file_asset(db: Session, kind: AssetKind, path: Path, mime_type: str, duration_ms: int | None, project_id: str | None = None) -> Asset:
    path = Path(path)
    digest = sha256_file(path)
    existing = db.scalar(select(Asset).where(Asset.storage_path == str(path)))
    if existing:
        existing.duration_ms = duration_ms
        if project_id and existing.project_id is None:
            existing.project_id = project_id
        db.commit()
        return existing
    asset = Asset(
        id=str(uuid4()),
        project_id=project_id,
        kind=kind,
        original_name=path.name,
        storage_path=str(path),
        mime_type=mime_type,
        size=path.stat().st_size,
        duration_ms=duration_ms,
        sha256=digest,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def model_status() -> dict:
    qwen_dir = resolve_qwen_model_dir(DEFAULT_TTS_MODEL_DIR)
    omni_dir = resolve_omnivoice_dir(DEFAULT_OMNIVOICE_DIR)
    omni_python = default_omnivoice_python(omni_dir)
    qwen_python = qwen_python_for_model(qwen_dir)
    ffmpeg_path = resolve_ffmpeg_path()
    ancient_font_path = ANCIENT_FONT if ANCIENT_FONT.exists() else ANCIENT_FALLBACK_FONT
    return {
        "qwen_available": qwen_dir.exists() and qwen_python.exists(),
        "qwen_model_dir": str(qwen_dir),
        "qwen_python": str(qwen_python),
        "omnivoice_available": omni_dir.exists() and (omni_dir / "omnivoice").exists() and omni_python.exists(),
        "omnivoice_project_dir": str(omni_dir),
        "omnivoice_python": str(omni_python),
        "ffmpeg_available": bool(ffmpeg_path),
        "ffmpeg_path": ffmpeg_path,
        "ancient_voice_available": ANCIENT_VOICE.exists(),
        "ancient_voice_path": str(ANCIENT_VOICE),
        "ancient_font_available": ancient_font_path.exists(),
        "ancient_font_path": str(ancient_font_path),
        "ancient_reference_text": ANCIENT_REFERENCE_TEXT,
    }


def resolve_ffmpeg_path() -> str:
    discovered = shutil.which("ffmpeg")
    if discovered:
        return discovered
    try:
        import imageio_ffmpeg

        path = imageio_ffmpeg.get_ffmpeg_exe()
        return str(path) if path else ""
    except Exception:
        return ""


def wav_duration_ms(path: Path) -> int | None:
    try:
        with wave.open(str(path), "rb") as wav:
            return int(wav.getnframes() / float(wav.getframerate()) * 1000)
    except (OSError, wave.Error, ZeroDivisionError):
        return None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = (value or "#000000").strip().lstrip("#")
    if len(value) != 6:
        return (0, 0, 0)
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def rgba_from_project_color(value: str | None) -> tuple[int, int, int, int] | None:
    if not value:
        return None
    red, green, blue = hex_to_rgb(value)
    return (red, green, blue, 255)


def _optional_path(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.exists() else None


def voice_preset_path(tts: dict) -> Path | None:
    preset_id = str(tts.get("voice_preset_id") or "").strip()
    if not preset_id:
        return None
    for suffix in (".wav", ".mp3", ".m4a", ".flac"):
        path = VOICE_PRESET_DIR / f"{preset_id}{suffix}"
        if path.exists():
            return path
    return None


def require_voice_preset_path(tts: dict) -> Path | None:
    preset_id = str(tts.get("voice_preset_id") or "").strip()
    path = voice_preset_path(tts)
    if preset_id and path is None:
        raise JobValidationError(f"预设语音不存在：{preset_id}")
    return path


def asset_path_for(db: Session, asset_id: str | None) -> Path | None:
    if not asset_id:
        return None
    asset = db.get(Asset, asset_id)
    if asset is None:
        return None
    path = Path(asset.storage_path)
    return path if path.exists() else None


def load_preview_background(db: Session, segment: Segment) -> Image.Image | None:
    path = asset_path_for(db, segment.background_asset_id)
    if path is None:
        return None
    try:
        with Image.open(path) as source:
            return source.convert("RGB").copy()
    except OSError:
        return None


def blank_preview_png(project: Project) -> bytes:
    config = make_video_config(project, preview=True)
    image = Image.new("RGB", (config.width, config.height), config.background_color)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
