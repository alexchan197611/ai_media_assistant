from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


HEARTBEAT_PATH = Path(os.environ.get("AMA_WORKER_HEARTBEAT_FILE", "D:/Codex/cache/tmp/ai_media_assistant_worker.json"))
STALE_SECONDS = 8.0


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def write_worker_heartbeat(pid: int, current_job_id: str | None = None) -> None:
    HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pid": pid,
        "current_job_id": current_job_id,
        "updated_at": utcnow().isoformat(),
    }
    tmp_path = HEARTBEAT_PATH.with_name(f"{HEARTBEAT_PATH.stem}.{pid}.{uuid4().hex}.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    for attempt in range(5):
        try:
            tmp_path.replace(HEARTBEAT_PATH)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.05)


def read_worker_status() -> dict:
    if not HEARTBEAT_PATH.exists():
        return {
            "online": False,
            "pid": None,
            "current_job_id": None,
            "updated_at": None,
            "stale_seconds": None,
            "heartbeat_file": str(HEARTBEAT_PATH),
        }
    try:
        payload = json.loads(HEARTBEAT_PATH.read_text(encoding="utf-8"))
        updated_at = datetime.fromisoformat(payload["updated_at"])
    except (OSError, KeyError, ValueError, json.JSONDecodeError):
        return {
            "online": False,
            "pid": None,
            "current_job_id": None,
            "updated_at": None,
            "stale_seconds": None,
            "heartbeat_file": str(HEARTBEAT_PATH),
        }

    stale_seconds = max(0.0, (utcnow() - updated_at).total_seconds())
    return {
        "online": stale_seconds <= STALE_SECONDS,
        "pid": payload.get("pid"),
        "current_job_id": payload.get("current_job_id"),
        "updated_at": updated_at,
        "stale_seconds": stale_seconds,
        "heartbeat_file": str(HEARTBEAT_PATH),
    }
