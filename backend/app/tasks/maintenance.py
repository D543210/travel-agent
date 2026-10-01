"""后台任务和会话的周期性维护。"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, or_, select

from ..config import get_settings
from ..db.models import PlanningJob, Trip, UserSession
from ..db.session import SessionLocal
from .celery_app import celery_app


settings = get_settings()


@celery_app.task(name="maintenance.recover_stale_jobs")
def recover_stale_jobs() -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=settings.planning_job_stale_minutes
    )
    recovered = 0
    with SessionLocal() as db:
        jobs = list(
            db.scalars(
                select(PlanningJob).where(
                    PlanningJob.status.in_(("queued", "running")),
                    or_(
                        PlanningJob.heartbeat_at < cutoff,
                        (
                            PlanningJob.heartbeat_at.is_(None)
                            & (PlanningJob.created_at < cutoff)
                        ),
                    ),
                )
            ).all()
        )
        for job in jobs:
            job.status = "failed"
            job.error_code = "JOB_STALE"
            job.error_message = "任务长时间没有心跳，已停止；请重新提交"
            job.progress_message = "任务执行超时"
            job.finished_at = datetime.now(timezone.utc)
            trip = db.get(Trip, job.trip_id)
            if trip is not None and trip.current_version == 0:
                trip.status = "failed"
            recovered += 1
        db.commit()
    return {"recovered": recovered}


@celery_app.task(name="maintenance.cleanup_expired_data")
def cleanup_expired_data() -> dict:
    now = datetime.now(timezone.utc)
    job_cutoff = now - timedelta(days=settings.planning_job_retention_days)
    with SessionLocal() as db:
        expired_sessions = db.execute(
            delete(UserSession).where(UserSession.expires_at < now)
        ).rowcount
        old_jobs = db.execute(
            delete(PlanningJob).where(
                PlanningJob.status.in_(("succeeded", "failed")),
                PlanningJob.finished_at < job_cutoff,
            )
        ).rowcount
        db.commit()
    return {
        "expired_sessions": expired_sessions or 0,
        "old_jobs": old_jobs or 0,
    }
