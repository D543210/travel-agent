"""行程、版本与任务的持久化服务。"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import PlanningJob, Trip, TripRevision, UserPreference
from ..models.planning_schemas import (
    PlanningJobResponse,
    TripPlanningJobRequest,
    TripRevisionJobRequest,
)
from .preference_service import preference_snapshot


class TripNotFoundError(Exception):
    pass


class TripVersionConflictError(Exception):
    pass


class TooManyActiveJobsError(Exception):
    pass


def _ensure_job_capacity(db: Session, user_id) -> None:
    from ..config import get_settings

    active_count = db.scalar(
        select(func.count(PlanningJob.id)).where(
            PlanningJob.user_id == user_id,
            PlanningJob.status.in_(("queued", "running")),
        )
    ) or 0
    if active_count >= get_settings().max_active_jobs_per_user:
        raise TooManyActiveJobsError()


def _merged_request_payload(
    request: TripPlanningJobRequest,
    preference: UserPreference | None,
) -> tuple[dict, dict]:
    payload = request.model_dump(exclude={"use_saved_preferences"})
    snapshot = preference_snapshot(preference) if request.use_saved_preferences else {}
    if not snapshot:
        return payload, snapshot

    payload["preferences"] = list(
        dict.fromkeys(
            [*payload.get("preferences", []), *snapshot.get("attraction_types", [])]
        )
    )[:20]
    if snapshot.get("transportation_preference"):
        payload["transportation"] = snapshot["transportation_preference"]
    if snapshot.get("accommodation_preference"):
        payload["accommodation"] = snapshot["accommodation_preference"]
    dietary = snapshot.get("dietary_restrictions") or []
    preference_notes: list[str] = []
    if dietary:
        preference_notes.append("饮食限制：" + "、".join(dietary))
    if snapshot.get("travel_pace"):
        preference_notes.append("旅行节奏：" + snapshot["travel_pace"])
    if preference_notes:
        payload["free_text_input"] = "；".join(
            item
            for item in [
                payload.get("free_text_input", "").strip(),
                *preference_notes,
            ]
            if item
        )[:1000]
    return payload, snapshot


def create_generation_job(
    db: Session,
    user_id,
    request: TripPlanningJobRequest,
) -> PlanningJob:
    _ensure_job_capacity(db, user_id)
    preference = db.scalar(
        select(UserPreference).where(UserPreference.user_id == user_id)
    )
    payload, snapshot = _merged_request_payload(request, preference)
    trip = Trip(
        user_id=user_id,
        title=f"{payload['city']}{payload['travel_days']}日行程",
        status="planning",
    )
    db.add(trip)
    db.flush()
    job = PlanningJob(
        user_id=user_id,
        trip_id=trip.id,
        kind="generate_trip",
        request_payload=payload,
        preference_snapshot=snapshot,
        progress_total=10,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def create_revision_job(
    db: Session,
    user_id,
    trip_id: UUID,
    request: TripRevisionJobRequest,
) -> PlanningJob:
    _ensure_job_capacity(db, user_id)
    trip = db.scalar(
        select(Trip).where(Trip.id == trip_id, Trip.user_id == user_id)
    )
    if trip is None:
        raise TripNotFoundError()
    if trip.current_version != request.expected_version:
        raise TripVersionConflictError()
    job = PlanningJob(
        user_id=user_id,
        trip_id=trip.id,
        kind="revise_trip",
        request_payload=request.model_dump(mode="json"),
        preference_snapshot={},
        base_version=request.expected_version,
        progress_total=4,
        progress_message="行程修改已排队",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_owned_job(db: Session, user_id, job_id: UUID) -> PlanningJob | None:
    return db.scalar(
        select(PlanningJob).where(
            PlanningJob.id == job_id,
            PlanningJob.user_id == user_id,
        )
    )


def get_owned_trip(db: Session, user_id, trip_id: UUID):
    trip = db.scalar(
        select(Trip).where(Trip.id == trip_id, Trip.user_id == user_id)
    )
    if trip is None or trip.current_version < 1:
        return None, None
    revision = db.scalar(
        select(TripRevision).where(
            TripRevision.trip_id == trip.id,
            TripRevision.version == trip.current_version,
        )
    )
    return trip, revision


def list_owned_trips(db: Session, user_id, include_archived: bool = False) -> list[Trip]:
    statement = select(Trip).where(Trip.user_id == user_id)
    if not include_archived:
        statement = statement.where(Trip.archived_at.is_(None))
    return list(db.scalars(statement.order_by(Trip.updated_at.desc())).all())


def archive_owned_trip(db: Session, user_id, trip_id: UUID) -> bool:
    trip = db.scalar(select(Trip).where(Trip.id == trip_id, Trip.user_id == user_id))
    if trip is None:
        return False
    trip.archived_at = datetime.now(timezone.utc)
    db.commit()
    return True


def restore_owned_trip(db: Session, user_id, trip_id: UUID) -> bool:
    trip = db.scalar(select(Trip).where(Trip.id == trip_id, Trip.user_id == user_id))
    if trip is None:
        return False
    trip.archived_at = None
    db.commit()
    return True


def list_owned_jobs(db: Session, user_id, active_only: bool = True) -> list[PlanningJob]:
    statement = select(PlanningJob).where(PlanningJob.user_id == user_id)
    if active_only:
        statement = statement.where(PlanningJob.status.in_(("queued", "running")))
    return list(db.scalars(statement.order_by(PlanningJob.created_at.desc()).limit(100)).all())


def job_response(job: PlanningJob) -> PlanningJobResponse:
    if job.status == "succeeded":
        percent = 100
    elif job.progress_total > 0:
        percent = min(99, int(job.progress_current * 100 / job.progress_total))
    else:
        percent = 0
    return PlanningJobResponse(
        job_id=job.id,
        trip_id=job.trip_id,
        kind=job.kind,
        status=job.status,
        stage=job.stage,
        progress_current=job.progress_current,
        progress_total=job.progress_total,
        progress_percent=percent,
        progress_message=job.progress_message,
        attempts=job.attempts,
        result_version=job.result_version,
        error_code=job.error_code,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
