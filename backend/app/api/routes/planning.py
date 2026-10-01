"""异步行程规划、进度与版本API。"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from ...auth.dependencies import get_current_user
from ...db.models import PlanningJob, Trip, User
from ...db.session import get_db
from ...models.planning_schemas import (
    JobCreatedResponse,
    PlanningJobResponse,
    TripDetailResponse,
    TripSummaryResponse,
    TripPlanningJobRequest,
    TripRevisionJobRequest,
)
from ...models.schemas import TripPlan
from ...services.planning_service import (
    TripNotFoundError,
    TripVersionConflictError,
    TooManyActiveJobsError,
    archive_owned_trip,
    create_generation_job,
    create_revision_job,
    get_owned_job,
    get_owned_trip,
    job_response,
    list_owned_jobs,
    list_owned_trips,
    restore_owned_trip,
)
from ...config import get_settings
from ...security.rate_limit import enforce_rate_limit
from ...tasks.planning import generate_trip_job, revise_trip_job


router = APIRouter(tags=["异步行程规划"])
settings = get_settings()


def _enqueue(db: Session, job: PlanningJob) -> None:
    task = generate_trip_job if job.kind == "generate_trip" else revise_trip_job
    try:
        result = task.delay(str(job.id))
        job.celery_task_id = result.id
        db.commit()
    except Exception as error:
        job.status = "failed"
        job.error_code = "QUEUE_UNAVAILABLE"
        job.error_message = "后台任务队列暂时不可用"
        trip = db.get(Trip, job.trip_id)
        if trip is not None and trip.current_version == 0:
            trip.status = "failed"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "QUEUE_UNAVAILABLE",
                "message": "后台任务队列暂时不可用",
            },
        ) from error


@router.post(
    "/trips/plan",
    response_model=JobCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_trip_plan(
    request: TripPlanningJobRequest,
    http_request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    enforce_rate_limit(
        http_request,
        scope="trip-plan",
        identifier=str(current_user.id),
        limit=settings.trip_plan_rate_limit_per_hour,
        window_seconds=3600,
    )
    try:
        job = create_generation_job(db, current_user.id, request)
    except TooManyActiveJobsError:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "TOO_MANY_ACTIVE_JOBS", "message": "已有较多任务正在处理中"},
        )
    _enqueue(db, job)
    return JobCreatedResponse(job_id=job.id, trip_id=job.trip_id)


@router.get("/jobs/{job_id}", response_model=PlanningJobResponse)
def read_job(
    job_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    job = get_owned_job(db, current_user.id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "JOB_NOT_FOUND"})
    return job_response(job)


@router.get("/jobs", response_model=list[PlanningJobResponse])
def read_jobs(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    active_only: bool = Query(True),
):
    return [job_response(job) for job in list_owned_jobs(db, current_user.id, active_only)]


@router.get("/trips", response_model=list[TripSummaryResponse])
def read_trips(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    include_archived: bool = Query(False),
):
    return [
        TripSummaryResponse(
            trip_id=trip.id,
            title=trip.title,
            status=trip.status,
            current_version=trip.current_version,
            created_at=trip.created_at,
            updated_at=trip.updated_at,
            archived_at=trip.archived_at,
        )
        for trip in list_owned_trips(db, current_user.id, include_archived)
    ]


@router.get("/trips/{trip_id}", response_model=TripDetailResponse)
def read_trip(
    trip_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    trip, revision = get_owned_trip(db, current_user.id, trip_id)
    if trip is None or revision is None:
        raise HTTPException(status_code=404, detail={"code": "TRIP_NOT_FOUND"})
    return TripDetailResponse(
        trip_id=trip.id,
        version=revision.version,
        status=trip.status,
        plan=TripPlan.model_validate(revision.plan),
    )


@router.post(
    "/trips/{trip_id}/revisions",
    response_model=JobCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def revise_trip(
    trip_id: UUID,
    request: TripRevisionJobRequest,
    http_request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    enforce_rate_limit(
        http_request,
        scope="trip-revision",
        identifier=str(current_user.id),
        limit=settings.trip_plan_rate_limit_per_hour * 2,
        window_seconds=3600,
    )
    try:
        job = create_revision_job(db, current_user.id, trip_id, request)
    except TripNotFoundError:
        raise HTTPException(status_code=404, detail={"code": "TRIP_NOT_FOUND"})
    except TripVersionConflictError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "TRIP_VERSION_CONFLICT",
                "message": "行程已更新，请刷新后重试",
            },
        )
    except TooManyActiveJobsError:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "TOO_MANY_ACTIVE_JOBS", "message": "已有较多任务正在处理中"},
        )
    _enqueue(db, job)
    return JobCreatedResponse(job_id=job.id, trip_id=job.trip_id)


@router.delete("/trips/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_trip(
    trip_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    if not archive_owned_trip(db, current_user.id, trip_id):
        raise HTTPException(status_code=404, detail={"code": "TRIP_NOT_FOUND"})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/trips/{trip_id}/restore", status_code=status.HTTP_204_NO_CONTENT)
def restore_trip(
    trip_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    if not restore_owned_trip(db, current_user.id, trip_id):
        raise HTTPException(status_code=404, detail={"code": "TRIP_NOT_FOUND"})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
