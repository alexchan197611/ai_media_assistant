from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ROOT
from app.models import Asset, AssetKind, Project, Segment

EMOTION_TEMPLATE_ID = "senior-emotion"
RESOURCE_DIRS = [
    ROOT / "storage" / "resources" / "bg_B-Roll_Senior_Emotions",
    ROOT / "storage" / "resources" / "bg_elder_person",
]

SCENE_HINTS: dict[str, list[str]] = {
    "loneliness": ["孤独", "独居", "空巢", "没人", "一个人", "冷清", "等待", "想念", "思念"],
    "waiting": ["等待", "等你", "回家", "盼", "归来", "车站", "公交", "火车"],
    "memory": ["回忆", "以前", "过去", "从前", "岁月", "照片", "相册", "旧", "怀念", "家书"],
    "companionship": ["陪伴", "老伴", "牵手", "一起", "相伴", "夫妻", "爱情", "身边"],
    "health": ["健康", "养生", "散步", "运动", "锻炼", "身体", "茶", "饮食", "吃饭"],
    "family": ["家人", "子女", "孩子", "孙子", "孙女", "团圆", "亲情", "孝顺", "母亲", "父亲"],
    "home": ["家", "老家", "院子", "家门", "乡村", "做饭", "烟火气", "饭"],
    "hope": ["希望", "春天", "明天", "新生", "阳光", "平安", "祝福", "幸福"],
    "reflection": ["人生", "晚年", "变老", "时间", "路", "归途", "一生", "不易"],
    "prayer": ["祈福", "平安", "寺庙", "信仰", "保佑", "祝愿"],
}


@dataclass(frozen=True)
class BackgroundResource:
    id: str
    file: str
    path: Path
    title_zh: str
    scene: str
    emotions: tuple[str, ...]
    keywords_zh: tuple[str, ...]
    keywords_en: tuple[str, ...]
    match_text_types: tuple[str, ...]


def apply_emotion_backgrounds(db: Session, project: Project) -> None:
    resources = load_background_resources()
    if not resources:
        return
    global_resource_paths = {str(resource.path) for resource in resources}
    used_asset_ids = {
        segment.background_asset_id
        for segment in project.segments
        if segment.background_asset_id and not _is_replaceable_asset(db, segment.background_asset_id, global_resource_paths)
    }
    used_resource_ids: set[str] = set()
    for segment in sorted(project.segments, key=lambda item: item.order):
        if not segment.text.strip():
            continue
        if segment.background_asset_id and not _is_replaceable_asset(db, segment.background_asset_id, global_resource_paths):
            continue
        resource = choose_best_resource(segment.text, resources, used_resource_ids)
        used_resource_ids.add(resource.id)
        asset = ensure_resource_asset(db, resource)
        if asset.id in used_asset_ids:
            continue
        used_asset_ids.add(asset.id)
        segment.background_asset_id = asset.id
        segment.background_motion = None
        segment.background_position_x = 0.35 + ((_stable_int(segment.id + resource.id) % 31) / 100)
        segment.background_position_y = 0.35 + ((_stable_int(resource.id + segment.id) % 31) / 100)


def load_background_resources() -> list[BackgroundResource]:
    resources: list[BackgroundResource] = []
    for resource_dir in RESOURCE_DIRS:
        index_path = resource_dir / "index.json"
        if not index_path.exists():
            continue
        payload = json.loads(index_path.read_text(encoding="utf-8"))
        for item in payload.get("assets", []):
            path = resource_dir / item["file"]
            if not path.exists():
                continue
            resources.append(
                BackgroundResource(
                    id=str(item["id"]),
                    file=str(item["file"]),
                    path=path,
                    title_zh=str(item.get("title_zh", "")),
                    scene=str(item.get("scene", "")),
                    emotions=tuple(map(str, item.get("emotions", []))),
                    keywords_zh=tuple(map(str, item.get("keywords_zh", []))),
                    keywords_en=tuple(map(str, item.get("keywords_en", []))),
                    match_text_types=tuple(map(str, item.get("match_text_types", []))),
                )
            )
    return resources


def choose_best_resource(text: str, resources: list[BackgroundResource], used_resource_ids: set[str]) -> BackgroundResource:
    available = [resource for resource in resources if resource.id not in used_resource_ids] or resources
    normalized = normalize_text(text)
    best = max(available, key=lambda resource: (score_resource(normalized, resource), -available.index(resource)))
    return best


def score_resource(text: str, resource: BackgroundResource) -> int:
    score = 0
    for keyword in [*resource.keywords_zh, *resource.keywords_en, *resource.match_text_types, resource.title_zh, resource.scene, *resource.emotions]:
        normalized_keyword = normalize_text(keyword)
        if not normalized_keyword:
            continue
        if normalized_keyword in text:
            score += 12 + len(normalized_keyword)
        elif any(token and token in text for token in re.split(r"[_\s-]+", normalized_keyword)):
            score += 3
    semantic_blob = " ".join([resource.scene, *resource.emotions, *resource.match_text_types])
    for hint, words in SCENE_HINTS.items():
        if hint in semantic_blob and any(word in text for word in words):
            score += 10
    return score


def ensure_resource_asset(db: Session, resource: BackgroundResource) -> Asset:
    storage_path = str(resource.path)
    existing = db.scalar(select(Asset).where(Asset.storage_path == storage_path))
    if existing:
        return existing
    data = resource.path.read_bytes()
    asset = Asset(
        project_id=None,
        kind=AssetKind.image,
        original_name=resource.file,
        storage_path=storage_path,
        mime_type=mime_type_for(resource.path),
        size=len(data),
        duration_ms=None,
        sha256=hashlib.sha256(data).hexdigest(),
    )
    db.add(asset)
    db.flush()
    return asset


def _is_replaceable_asset(db: Session, asset_id: str, global_resource_paths: set[str]) -> bool:
    asset = db.get(Asset, asset_id)
    return asset is None or asset.storage_path in global_resource_paths


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", value.lower())


def mime_type_for(path: Path) -> str:
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(path.suffix.lower(), "application/octet-stream")


def _stable_int(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:8], 16)
