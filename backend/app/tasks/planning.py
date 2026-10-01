"""行程生成和修订Celery任务。"""

from datetime import datetime, timezone
from uuid import UUID

from billiard.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select, update

from ..agents.trip_planner_agent import create_trip_planner
from ..config import get_settings
from ..db.models import PlanningJob, Trip, TripRevision
from ..db.session import SessionLocal
from ..exceptions import ExternalServiceError, TripPlanningError
from ..models.planning_schemas import TripEditOperation
from ..models.schemas import Attraction, TripPlan, TripRequest
from ..services.amap_service import get_amap_service
from .celery_app import celery_app


class RevisionValidationError(Exception):
    """用户可以安全看到的行程修订校验错误。"""


settings = get_settings()


def _acquire_job(job_id: UUID, kind: str) -> str:
    """原子取得任务执行权，避免重复投递造成重复版本。"""

    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        result = db.execute(
            update(PlanningJob)
            .where(
                PlanningJob.id == job_id,
                PlanningJob.kind == kind,
                PlanningJob.status == "queued",
            )
            .values(
                status="running",
                stage="starting",
                progress_message="后台任务正在启动",
                started_at=now,
                heartbeat_at=now,
                attempts=PlanningJob.attempts + 1,
            )
        )
        db.commit()
        if result.rowcount == 1:
            return "acquired"
        job = db.get(PlanningJob, job_id)
        if job is None:
            return "missing"
        return job.status


def _update_progress(
    job_id: UUID,
    stage: str,
    current: int,
    total: int,
    message: str,
) -> None:
    with SessionLocal() as db:
        job = db.get(PlanningJob, job_id)
        if job is None:
            return
        if job.status != "running":
            return
        job.stage = stage
        job.progress_current = current
        job.progress_total = total
        job.progress_message = message
        job.heartbeat_at = datetime.now(timezone.utc)
        if job.started_at is None:
            job.started_at = datetime.now(timezone.utc)
        db.commit()


def _mark_failed(job_id: UUID, error: Exception) -> None:
    with SessionLocal() as db:
        job = db.get(PlanningJob, job_id)
        if job is None:
            return
        if job.status == "succeeded":
            return
        job.status = "failed"
        job.error_code = type(error).__name__.upper()
        job.error_message = (
            str(error)
            if isinstance(error, (TripPlanningError, RevisionValidationError))
            else "任务执行失败，请稍后重试"
        )
        job.progress_message = f"失败阶段：{job.stage}"
        job.finished_at = datetime.now(timezone.utc)
        trip = db.get(Trip, job.trip_id)
        if trip is not None and trip.current_version == 0:
            trip.status = "failed"
        db.commit()


def _queue_retry(job_id: UUID, message: str) -> None:
    with SessionLocal() as db:
        job = db.get(PlanningJob, job_id)
        if job is None or job.status != "running":
            return
        job.status = "queued"
        job.stage = "retrying"
        job.progress_message = message
        job.heartbeat_at = datetime.now(timezone.utc)
        db.commit()


@celery_app.task(
    bind=True,
    name="planning.generate_trip",
    max_retries=2,
    soft_time_limit=settings.celery_soft_time_limit_seconds,
    time_limit=settings.celery_time_limit_seconds,
)
def generate_trip_job(self, job_id: str) -> dict:
    parsed_job_id = UUID(job_id)
    acquisition = _acquire_job(parsed_job_id, "generate_trip")
    if acquisition != "acquired":
        return {"status": acquisition}
    try:
        with SessionLocal() as db:
            job = db.get(PlanningJob, parsed_job_id)
            if job is None:
                return {"status": "missing"}
            request = TripRequest.model_validate(job.request_payload)

        planner = create_trip_planner()
        plan = planner.plan_trip(
            request,
            progress_callback=lambda stage, current, total, message: _update_progress(
                parsed_job_id, stage, current, total, message
            ),
        )
        _update_progress(parsed_job_id, "saving_revision", 10, 10, "正在保存行程版本")

        with SessionLocal() as db:
            job = db.get(PlanningJob, parsed_job_id)
            trip = db.get(Trip, job.trip_id) if job else None
            if job is None or trip is None:
                return {"status": "missing"}
            if job.status != "running":
                return {"status": job.status}
            if trip.current_version != 0:
                return {"status": "already-published"}
            revision = TripRevision(
                trip_id=trip.id,
                version=1,
                request_snapshot=job.request_payload,
                preference_snapshot=job.preference_snapshot,
                plan=plan.model_dump(mode="json"),
            )
            db.add(revision)
            trip.current_version = 1
            trip.status = "ready"
            job.status = "succeeded"
            job.stage = "completed"
            job.progress_current = 10
            job.progress_total = 10
            job.progress_message = "行程生成完成"
            job.result_version = 1
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            return {"status": "succeeded", "trip_id": str(trip.id), "version": 1}
    except ExternalServiceError as error:
        if self.request.retries < self.max_retries:
            _queue_retry(parsed_job_id, "外部服务暂不可用，正在重试")
            raise self.retry(exc=error, countdown=5 * (2 ** self.request.retries))
        _mark_failed(parsed_job_id, error)
        raise
    except SoftTimeLimitExceeded as error:
        _mark_failed(parsed_job_id, RevisionValidationError("任务执行超时"))
        raise error
    except Exception as error:
        _mark_failed(parsed_job_id, error)
        raise


def _apply_operation(plan: TripPlan, operation: TripEditOperation) -> None:
    if operation.day_index >= len(plan.days):
        raise RevisionValidationError("行程天数不存在")
    day = plan.days[operation.day_index]
    if operation.attraction_index >= len(day.attractions):
        raise RevisionValidationError("景点下标不存在")

    if operation.type == "delete_attraction":
        if len(day.attractions) <= 2:
            raise RevisionValidationError("每天至少保留2个景点")
        day.attractions.pop(operation.attraction_index)
    elif operation.type == "move_attraction":
        assert operation.target_index is not None
        if operation.target_index >= len(day.attractions):
            raise RevisionValidationError("目标位置不存在")
        attraction = day.attractions.pop(operation.attraction_index)
        day.attractions.insert(operation.target_index, attraction)
    elif operation.type == "update_visit_duration":
        assert operation.visit_duration is not None
        day.attractions[operation.attraction_index].visit_duration = (
            operation.visit_duration
        )
    elif operation.type == "replace_attraction":
        assert operation.replacement_poi_id is not None
        try:
            poi = get_amap_service().get_poi_info(operation.replacement_poi_id)
        except Exception as error:
            raise ExternalServiceError("替换景点数据服务暂时不可用") from error
        old = day.attractions[operation.attraction_index]
        day.attractions[operation.attraction_index] = Attraction(
            poi_id=poi.id,
            name=poi.name,
            address=poi.address,
            location=poi.location,
            visit_duration=old.visit_duration,
            description="用户替换的真实POI",
            category=poi.type,
            ticket_price=None,
        )


@celery_app.task(
    bind=True,
    name="planning.revise_trip",
    max_retries=2,
    soft_time_limit=settings.celery_soft_time_limit_seconds,
    time_limit=settings.celery_time_limit_seconds,
)
def revise_trip_job(self, job_id: str) -> dict:
    parsed_job_id = UUID(job_id)
    acquisition = _acquire_job(parsed_job_id, "revise_trip")
    if acquisition != "acquired":
        return {"status": acquisition}
    try:
        _update_progress(parsed_job_id, "applying_changes", 1, 4, "正在应用行程修改")
        with SessionLocal() as db:
            job = db.get(PlanningJob, parsed_job_id)
            if job is None or job.base_version is None:
                return {"status": "missing"}
            base = db.scalar(
                select(TripRevision).where(
                    TripRevision.trip_id == job.trip_id,
                    TripRevision.version == job.base_version,
                )
            )
            if base is None:
                raise RevisionValidationError("原行程版本不存在")
            plan = TripPlan.model_validate(base.plan)
            request_snapshot = dict(base.request_snapshot)
            preference_snapshot = dict(base.preference_snapshot)
            operations = [
                TripEditOperation.model_validate(item)
                for item in job.request_payload["operations"]
            ]

        for operation in operations:
            _apply_operation(plan, operation)

        all_poi_ids = [
            attraction.poi_id
            for day in plan.days
            for attraction in day.attractions
        ]
        if len(all_poi_ids) != len(set(all_poi_ids)):
            raise RevisionValidationError("行程中不能重复安排同一景点")
        if any(not 2 <= len(day.attractions) <= 3 for day in plan.days):
            raise RevisionValidationError("每天必须保留2至3个景点")

        _update_progress(parsed_job_id, "recalculating_routes", 2, 4, "正在重算酒店往返路线")
        planner = create_trip_planner()
        amap_service = get_amap_service()
        warnings: list[str] = []
        for day in plan.days:
            warnings.extend(
                planner._populate_routes_and_validate_feasibility(
                    day=day,
                    city=plan.city,
                    requested_transportation=day.transportation,
                    amap_service=amap_service,
                    route_cache={},
                )
            )

        if warnings:
            raise RevisionValidationError(
                "路线数据不完整，无法验证修改后的时间可行性；旧版本已保留"
            )

        _update_progress(parsed_job_id, "recalculating_budget", 3, 4, "正在重算时间与预算")
        planner._normalize_and_validate_budget(plan)
        if any(
            attraction.ticket_price is None
            for day in plan.days
            for attraction in day.attractions
        ):
            warnings.append("部分替换景点门票价格未知，请出行前确认")
        plan.warnings = list(dict.fromkeys([*plan.warnings, *warnings]))
        plan.status = "degraded" if plan.warnings else "success"

        _update_progress(parsed_job_id, "saving_revision", 4, 4, "正在发布新版本")
        with SessionLocal() as db:
            job = db.get(PlanningJob, parsed_job_id)
            if job is None:
                return {"status": "missing"}
            if job.status != "running":
                return {"status": job.status}
            trip = db.scalar(
                select(Trip).where(Trip.id == job.trip_id).with_for_update()
            )
            if trip is None:
                return {"status": "missing"}
            if trip.current_version != job.base_version:
                raise RevisionValidationError("行程已被其他修改更新，请刷新后重试")
            new_version = trip.current_version + 1
            db.add(
                TripRevision(
                    trip_id=trip.id,
                    version=new_version,
                    parent_version=job.base_version,
                    request_snapshot=request_snapshot,
                    preference_snapshot=preference_snapshot,
                    plan=plan.model_dump(mode="json"),
                )
            )
            trip.current_version = new_version
            trip.status = "ready"
            job.status = "succeeded"
            job.stage = "completed"
            job.progress_message = "行程修改已发布"
            job.result_version = new_version
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            return {"status": "succeeded", "version": new_version}
    except ExternalServiceError as error:
        if self.request.retries < self.max_retries:
            _queue_retry(parsed_job_id, "外部服务暂不可用，正在重试")
            raise self.retry(exc=error, countdown=5 * (2 ** self.request.retries))
        _mark_failed(parsed_job_id, error)
        raise
    except SoftTimeLimitExceeded as error:
        _mark_failed(parsed_job_id, RevisionValidationError("任务执行超时，旧版本已保留"))
        raise error
    except Exception as error:
        _mark_failed(parsed_job_id, error)
        raise
