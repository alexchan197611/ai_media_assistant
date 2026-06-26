import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, get_db
from app.models import Job, JobStatus
from app.schemas import JobRead, WorkerStatus
from app.services.media_jobs import JobValidationError, retry_job
from app.services.worker_status import read_worker_status

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobRead])
def list_jobs(project_id: str | None = None, db: Session = Depends(get_db)):
    statement = select(Job).order_by(Job.created_at.desc()).limit(50)
    if project_id:
        statement = select(Job).where(Job.project_id == project_id).order_by(Job.created_at.desc()).limit(50)
    return db.scalars(statement).all()


@router.get("/events/stream")
async def events(project_id: str | None = None):
    async def stream():
        previous = ""
        while True:
            with SessionLocal() as db:
                statement = select(Job).order_by(Job.created_at.desc()).limit(20)
                if project_id:
                    statement = select(Job).where(Job.project_id == project_id).order_by(Job.created_at.desc()).limit(20)
                jobs = db.scalars(statement).all()
                payload = json.dumps(
                    [
                        {
                            "id": job.id,
                            "project_id": job.project_id,
                            "target_segment_id": job.target_segment_id,
                            "result_asset_id": job.result_asset_id,
                            "type": job.type.value,
                            "status": job.status.value,
                            "progress": job.progress,
                            "stage": job.stage,
                            "error_message": job.error_message,
                        }
                        for job in jobs
                    ],
                    ensure_ascii=False,
                )
            if payload != previous:
                yield f"event: jobs\ndata: {payload}\n\n"
                previous = payload
            else:
                yield "event: heartbeat\ndata: {}\n\n"
            await asyncio.sleep(1.5)

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/worker/status", response_model=WorkerStatus)
def worker_status():
    return read_worker_status()


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job


@router.post("/{job_id}/cancel", response_model=JobRead)
def cancel_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job.status in {JobStatus.queued, JobStatus.running}:
        job.status = JobStatus.cancelled
        job.finished_at = datetime.now(timezone.utc)
        job.stage = "用户已取消"
        db.commit()
        db.refresh(job)
    return job


@router.post("/{job_id}/retry", response_model=JobRead)
def retry(job_id: str, db: Session = Depends(get_db)):
    try:
        return retry_job(db, job_id)
    except JobValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
