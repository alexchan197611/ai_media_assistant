from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Asset, AssetKind, Project
from app.services.background_matcher import BackgroundResource, choose_best_resource
from app.services.media_jobs import font_path_for_project, make_video_config
from pathlib import Path

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=__import__("sqlalchemy").pool.StaticPool)
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
Base.metadata.create_all(engine)
app.dependency_overrides[get_db] = lambda: TestingSession()
client = TestClient(app)

def test_project_crud_preserves_segment_uuid():
    segment_id = "9a01f4f5-279e-4662-b0ac-78b68d251dc2"
    created = client.post("/api/projects", json={"name": "测试项目", "segments": [{"id": segment_id, "order": 0, "text": "第一句"}]})
    assert created.status_code == 201
    project_id = created.json()["id"]
    assert created.json()["segments"][0]["id"] == segment_id
    updated = client.patch(f"/api/projects/{project_id}", json={"name": "新名称", "segments": [{"id": segment_id, "order": 0, "text": "修改后的句子"}]})
    assert updated.status_code == 200
    assert updated.json()["segments"][0]["text"] == "修改后的句子"
    assert client.get("/api/projects").json()[0]["name"] == "新名称"
    assert client.delete(f"/api/projects/{project_id}").status_code == 204
    assert client.get(f"/api/projects/{project_id}").status_code == 404

def test_project_canvas_defaults_include_render_controls():
    created = client.post("/api/projects", json={"name": "画布参数项目", "segments": []})
    assert created.status_code == 201
    canvas = created.json()["canvas"]
    assert canvas["width"] == 1080
    assert canvas["height"] == 1920
    assert canvas["fps"] == 30
    assert canvas["segment_duration"] == 2.0
    assert canvas["font_size"] == 108
    assert canvas["font_path"] == ""
    assert canvas["heartbeat_interval_ms"] == 700
    assert canvas["caption_position_y"] == 0.5

def test_video_config_uses_project_canvas_render_controls():
    project = Project(
        canvas={
            "width": 720,
            "height": 1280,
            "fps": 24,
            "segment_duration": 3.5,
            "font_size": 96,
            "heartbeat_interval_ms": 450,
            "background_color": "#112233",
        },
        bgm_settings={},
        template_id="centered-bold",
    )
    config = make_video_config(project)
    assert config.width == 720
    assert config.height == 1280
    assert config.fps == 24
    assert config.segment_duration == 3.5
    assert config.font_size == 96
    assert config.heartbeat_interval_ms == 700
    assert config.background_color == (17, 34, 51)

def test_senior_emotion_template_defaults_caption_lower():
    project = Project(canvas={"background_color": "#000000"}, bgm_settings={}, template_id="senior-emotion")
    config = make_video_config(project)
    assert config.caption_template == "senior_emotion"
    assert config.caption_position_y == 0.66

def test_project_font_path_is_optional_canvas_setting():
    empty = Project(canvas={"font_path": ""})
    custom = Project(canvas={"font_path": "C:/Windows/Fonts/msyh.ttc"})
    assert font_path_for_project(empty) is None
    assert font_path_for_project(custom) == "C:/Windows/Fonts/msyh.ttc"

def test_duplicate_segment_ids_are_rejected():
    segment = {"id": "9a01f4f5-279e-4662-b0ac-78b68d251dc2", "order": 0, "text": "内容"}
    response = client.patch("/api/projects/missing", json={"segments": [segment, segment]})
    assert response.status_code == 422

def test_project_duplicate_copies_editing_state_without_generated_audio():
    segment_id = "bc495821-0cf2-4e92-ab9d-46f57b110998"
    created = client.post(
        "/api/projects",
        json={
            "name": "待复制项目",
            "segments": [
                {
                    "id": segment_id,
                    "order": 0,
                    "text": "复制这一句",
                    "marks": [{"start": 0, "end": 2, "text": "复制", "kind": "highlight"}],
                    "text_color": "#f8fafc",
                    "background_asset_id": None,
                    "background_motion": "slow_zoom_in",
                    "background_position_x": 0.25,
                    "background_position_y": 0.7,
                    "tts_audio_asset_id": "f2eea078-5601-49d1-8bdc-bb8528cbd534",
                    "audio_duration_ms": 1200,
                    "status": "audio_ready",
                }
            ],
        },
    )
    project_id = created.json()["id"]
    copied = client.post(f"/api/projects/{project_id}/duplicate")
    assert copied.status_code == 201
    payload = copied.json()
    assert payload["id"] != project_id
    assert payload["name"] == "待复制项目 副本"
    assert payload["segments"][0]["id"] != segment_id
    assert payload["segments"][0]["text"] == "复制这一句"
    assert payload["segments"][0]["marks"][0]["text"] == "复制"
    assert payload["segments"][0]["background_motion"] == "slow_zoom_in"
    assert payload["segments"][0]["background_position_x"] == 0.25
    assert payload["segments"][0]["background_position_y"] == 0.7
    assert payload["segments"][0]["tts_audio_asset_id"] is None
    assert payload["segments"][0]["audio_duration_ms"] is None
    assert payload["segments"][0]["status"] == "draft"

def test_senior_emotion_template_auto_matches_unique_backgrounds():
    segments = [
        {"id": "6caa9c2e-1a10-4adf-bb6e-0476d3c5ff01", "order": 0, "text": "父母老了，最怕的不是没钱，而是没人陪"},
        {"id": "6caa9c2e-1a10-4adf-bb6e-0476d3c5ff02", "order": 1, "text": "每天走一走，身体才会越来越轻松"},
        {"id": "6caa9c2e-1a10-4adf-bb6e-0476d3c5ff03", "order": 2, "text": "子女常回家看看，就是最好的养生"},
    ]
    created = client.post("/api/projects", json={"name": "情感模板项目", "segments": segments})
    project_id = created.json()["id"]
    updated = client.patch(
        f"/api/projects/{project_id}",
        json={"template_id": "senior-emotion", "segments": segments},
    )
    assert updated.status_code == 200
    payload = updated.json()
    assert payload["template_id"] == "senior-emotion"
    background_ids = [segment["background_asset_id"] for segment in payload["segments"]]
    assert all(background_ids)
    assert len(background_ids) == len(set(background_ids))

    with TestingSession() as db:
        assets = [db.get(Asset, asset_id) for asset_id in background_ids]
    assert all(asset is not None and asset.kind == AssetKind.image for asset in assets)
    assert any("broll" in asset.original_name or "elder" in asset.original_name for asset in assets)

def test_emotion_background_matching_varies_by_project_seed():
    resources = [
        BackgroundResource(
            id=f"resource-{index}",
            file=f"resource-{index}.png",
            path=Path(f"resource-{index}.png"),
            title_zh="家人陪伴",
            scene="family",
            emotions=("warm",),
            keywords_zh=("家", "陪伴"),
            keywords_en=(),
            match_text_types=(),
        )
        for index in range(1, 5)
    ]
    first = choose_best_resource("家人常回家陪伴", resources, set(), "project-a", "segment-1")
    repeated = choose_best_resource("家人常回家陪伴", resources, set(), "project-a", "segment-1")
    another_project = choose_best_resource("家人常回家陪伴", resources, set(), "project-d", "segment-1")

    assert first == repeated
    assert first.id != another_project.id

def test_emotion_background_matching_respects_current_project_used_images():
    resources = [
        BackgroundResource(
            id=f"resource-{index}",
            file=f"resource-{index}.png",
            path=Path(f"resource-{index}.png"),
            title_zh="家人陪伴",
            scene="family",
            emotions=("warm",),
            keywords_zh=("家", "陪伴"),
            keywords_en=(),
            match_text_types=(),
        )
        for index in range(1, 4)
    ]
    first = choose_best_resource("家人常回家陪伴", resources, set(), "project-a", "segment-1")
    second = choose_best_resource("家人常回家陪伴", resources, {first.id}, "project-a", "segment-2")

    assert first.id != second.id

def test_media_jobs_can_be_enqueued():
    segment_id = "9a01f4f5-279e-4662-b0ac-78b68d251dc2"
    created = client.post("/api/projects", json={"name": "任务项目", "segments": [{"id": segment_id, "order": 0, "text": "单句任务"}]})
    project_id = created.json()["id"]
    tts = client.post(f"/api/projects/{project_id}/tts/all")
    assert tts.status_code == 202
    assert tts.json()["type"] == "tts_all"
    assert tts.json()["status"] == "queued"
    segment_tts = client.post(f"/api/projects/{project_id}/tts/segments/{segment_id}")
    assert segment_tts.status_code == 202
    assert segment_tts.json()["type"] == "tts_segment"
    assert segment_tts.json()["target_segment_id"] == segment_id
    render = client.post(f"/api/projects/{project_id}/render")
    assert render.status_code == 202
    assert render.json()["type"] == "render"
    jobs = client.get(f"/api/jobs?project_id={project_id}")
    assert jobs.status_code == 200
    assert len(jobs.json()) == 3
    cancelled = client.post(f"/api/jobs/{segment_tts.json()['id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    retried = client.post(f"/api/jobs/{segment_tts.json()['id']}/retry")
    assert retried.status_code == 200
    assert retried.json()["type"] == "tts_segment"
    assert retried.json()["target_segment_id"] == segment_id
    assert retried.json()["status"] == "queued"

def test_enqueue_render_rejects_invalid_font_path_before_queueing():
    segment_id = "1a090eb1-1402-40f4-9c80-9341524fb9e3"
    created = client.post(
        "/api/projects",
        json={"name": "字体错误项目", "segments": [{"id": segment_id, "order": 0, "text": "字体校验"}]},
    )
    project_id = created.json()["id"]
    updated = client.patch(
        f"/api/projects/{project_id}",
        json={"canvas": {**created.json()["canvas"], "font_path": "D:/not/exist/font.ttf"}},
    )
    assert updated.status_code == 200
    response = client.post(f"/api/projects/{project_id}/render")
    assert response.status_code == 400
    assert "字体文件不存在" in response.json()["detail"]

def test_enqueue_tts_rejects_qwen_clone_without_reference_audio():
    segment_id = "7fbba03d-f79f-4d51-ab83-1653ad962342"
    created = client.post(
        "/api/projects",
        json={"name": "Qwen 参数错误项目", "segments": [{"id": segment_id, "order": 0, "text": "声音克隆"}]},
    )
    project_id = created.json()["id"]
    updated = client.patch(
        f"/api/projects/{project_id}",
        json={"tts_settings": {"engine": "Qwen3-TTS", "qwen_mode": "voice_clone", "qwen_ref_audio": "", "qwen_ref_text": "测试"}},
    )
    assert updated.status_code == 200
    response = client.post(f"/api/projects/{project_id}/tts/all")
    assert response.status_code == 400
    assert "Qwen3-TTS 参考音频不存在" in response.json()["detail"]

def test_render_can_be_enqueued_with_tts_disabled_even_if_tts_settings_are_invalid():
    segment_id = "3efbd322-6d3b-4853-996d-81ffccdfecb5"
    created = client.post(
        "/api/projects",
        json={"name": "关闭 TTS 渲染", "segments": [{"id": segment_id, "order": 0, "text": "只渲染字幕"}]},
    )
    project_id = created.json()["id"]
    updated = client.patch(
        f"/api/projects/{project_id}",
        json={"tts_settings": {"enabled": False, "engine": "Qwen3-TTS", "qwen_mode": "voice_clone", "qwen_ref_audio": ""}},
    )
    assert updated.status_code == 200
    response = client.post(f"/api/projects/{project_id}/render")
    assert response.status_code == 202
    assert response.json()["type"] == "render"

def test_model_status_shape():
    response = client.get("/api/models/status")
    assert response.status_code == 200
    payload = response.json()
    assert "qwen_model_dir" in payload
    assert "qwen_python" in payload
    assert "omnivoice_project_dir" in payload
    assert isinstance(payload["qwen_available"], bool)
    assert isinstance(payload["ffmpeg_available"], bool)
    assert "ancient_voice_path" in payload
    assert "ancient_reference_text" in payload

def test_worker_status_shape():
    response = client.get("/api/jobs/worker/status")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["online"], bool)
    assert "heartbeat_file" in payload

def test_bgm_library_endpoints_are_available():
    tracks = client.get("/api/bgm/tracks")
    assert tracks.status_code == 200
    assert isinstance(tracks.json(), list)
    random_track = client.get("/api/bgm/random")
    assert random_track.status_code in {200, 404}
    if random_track.status_code == 200:
        assert {"id", "name", "path", "mood", "bpm"} <= set(random_track.json())

def test_asset_upload_and_content():
    response = client.post(
        "/api/assets?kind=image",
        files={"file": ("cover.png", b"\x89PNG\r\n\x1a\nsample", "image/png")},
    )
    assert response.status_code == 201
    asset = response.json()
    assert asset["kind"] == "image"
    assert asset["original_name"] == "cover.png"
    content = client.get(f"/api/assets/{asset['id']}/content")
    assert content.status_code == 200
    assert content.content == b"\x89PNG\r\n\x1a\nsample"

def test_project_outputs_list_video_assets():
    created = client.post("/api/projects", json={"name": "输出项目", "segments": []})
    project_id = created.json()["id"]
    with TestingSession() as db:
        asset = Asset(
            project_id=project_id,
            kind=AssetKind.video,
            original_name="202606240001.mp4",
            storage_path="D:/Codex/outputs/fake.mp4",
            mime_type="video/mp4",
            size=42,
            duration_ms=None,
            sha256="0" * 64,
        )
        db.add(asset)
        db.commit()
    response = client.get(f"/api/projects/{project_id}/outputs")
    assert response.status_code == 200
    assert response.json()[0]["original_name"] == "202606240001.mp4"

def test_project_preview_png_uses_renderer():
    segment_id = "0c74aa5d-412f-47c9-89d8-13b80bd3a325"
    created = client.post(
        "/api/projects",
        json={
            "name": "预览项目",
            "segments": [
                {
                    "id": segment_id,
                    "order": 0,
                    "text": "今天适合创作",
                    "marks": [{"start": 2, "end": 4, "text": "适合", "kind": "highlight"}],
                    "text_color": "#ffffff",
                }
            ],
        },
    )
    assert created.status_code == 201
    project_id = created.json()["id"]
    preview = client.get(f"/api/projects/{project_id}/preview.png?segment_id={segment_id}")
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/png"
    assert preview.content.startswith(b"\x89PNG\r\n\x1a\n")

def test_project_preview_gif_uses_renderer():
    segment_id = "1e468ed3-79dd-4cd0-8bda-85a8a869f427"
    created = client.post(
        "/api/projects",
        json={
            "name": "动效预览项目",
            "segments": [{"id": segment_id, "order": 0, "text": "动态预览"}],
        },
    )
    assert created.status_code == 201
    project_id = created.json()["id"]
    preview = client.get(f"/api/projects/{project_id}/preview.gif?segment_id={segment_id}")
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/gif"
    assert preview.content.startswith(b"GIF")

def test_built_web_brand_assets_are_served():
    response = client.get("/brand/favicon.ico")
    assert response.status_code in {200, 404}
    if response.status_code == 200:
        assert response.headers["content-type"] in {"image/vnd.microsoft.icon", "image/x-icon"}
