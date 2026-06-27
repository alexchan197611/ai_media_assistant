"""Local background worker for TTS and render jobs."""
import time
import sys
import os
import threading
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "packages" / "media_core" / "src"))

from app.db.session import SessionLocal
from app.models import Job, JobStatus, JobType
from app.services.media_jobs import fail_job, mark_job, run_render_job, run_tts_job
from app.services.worker_status import read_worker_status, write_worker_heartbeat

_current_job_id: str | None = None
_current_job_lock = threading.Lock()
_lock_handle = None
WORKER_LOCK_PATH = ROOT / "storage" / "projects" / "ai_media_assistant_worker.lock"


def set_current_job(job_id: str | None) -> None:
    global _current_job_id
    with _current_job_lock:
        _current_job_id = job_id


def get_current_job() -> str | None:
    with _current_job_lock:
        return _current_job_id


def heartbeat_loop() -> None:
    while True:
        write_worker_heartbeat(os.getpid(), get_current_job())
        time.sleep(2)


def acquire_worker_lock() -> bool:
    global _lock_handle
    WORKER_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    _lock_handle = WORKER_LOCK_PATH.open("a+b")
    _lock_handle.seek(0)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(_lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(_lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        print("另一个 AI Media Assistant Worker 已在运行，本进程保持旁路等待。")
        return False
    return True


def passive_wait_for_existing_worker() -> None:
    while True:
        status = read_worker_status()
        if not status.get("online"):
            raise SystemExit("未检测到在线 Worker，请重新启动。")
        time.sleep(5)


def recover_running_jobs() -> int:
    with SessionLocal() as db:
        jobs = db.scalars(select(Job).where(Job.status == JobStatus.running)).all()
        for job in jobs:
            job.status = JobStatus.failed
            job.progress = min(float(job.progress or 0), 99)
            job.stage = "Worker 上次退出，任务已标记为可重试"
            job.error_code = "WorkerRestarted"
            job.error_message = "后台 Worker 启动时发现该任务遗留在运行中，请点击重试。"
        if jobs:
            db.commit()
        return len(jobs)

def poll_once() -> bool:
    with SessionLocal() as db:
        job = db.scalar(select(Job).where(Job.status == JobStatus.queued).order_by(Job.created_at).limit(1))
        write_worker_heartbeat(os.getpid(), job.id if job else None)
        if not job:
            return False
        set_current_job(job.id)
        mark_job(db, job, JobStatus.running, 1, "Worker 已接收任务")
        try:
            if job.type in {JobType.tts_all, JobType.tts_segment}:
                run_tts_job(db, job)
            elif job.type == JobType.render:
                run_render_job(db, job)
            else:
                raise NotImplementedError(f"暂不支持的任务类型：{job.type.value}")
        except Exception as exc:
            fail_job(db, job, exc)
        finally:
            write_worker_heartbeat(os.getpid(), get_current_job())
            set_current_job(None)
        return True

def main():
    if not acquire_worker_lock():
        passive_wait_for_existing_worker()
        return
    print("AI Media Assistant worker listening on the local SQLite queue")
    recovered = recover_running_jobs()
    if recovered:
        print(f"Recovered {recovered} stale running job(s).")
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    write_worker_heartbeat(os.getpid())
    while True:
        poll_once()
        write_worker_heartbeat(os.getpid())
        time.sleep(1)

if __name__ == "__main__": main()
