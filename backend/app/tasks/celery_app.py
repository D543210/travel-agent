"""Celery应用配置。"""

from celery import Celery
from celery.signals import heartbeat_sent, worker_ready
from redis import Redis
from redis.exceptions import RedisError

from ..config import get_settings


settings = get_settings()

celery_app = Celery(
    "trip_planner",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.planning", "app.tasks.maintenance"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=settings.celery_soft_time_limit_seconds,
    task_time_limit=settings.celery_time_limit_seconds,
    beat_schedule={
        "recover-stale-planning-jobs": {
            "task": "maintenance.recover_stale_jobs",
            "schedule": 60.0,
        },
        "cleanup-expired-data": {
            "task": "maintenance.cleanup_expired_data",
            "schedule": 86400.0,
        },
    },
)


def _write_worker_heartbeat() -> None:
    try:
        Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        ).setex("trip-planner:worker-heartbeat", 90, "1")
    except RedisError:
        pass


@worker_ready.connect
def on_worker_ready(**_kwargs) -> None:
    _write_worker_heartbeat()


@heartbeat_sent.connect
def on_worker_heartbeat(**_kwargs) -> None:
    _write_worker_heartbeat()
