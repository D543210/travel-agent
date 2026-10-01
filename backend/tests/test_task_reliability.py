from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import PlanningJob, Trip, User
from app.tasks import maintenance, planning


def make_session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
    )


def seed_job(session_factory, *, status="queued", old=False):
    with session_factory() as db:
        user = User(email="worker@example.com", password_hash="unused", display_name="Worker")
        db.add(user)
        db.flush()
        trip = Trip(user_id=user.id, title="测试行程", status="planning")
        db.add(trip)
        db.flush()
        timestamp = datetime.now(timezone.utc) - timedelta(hours=2) if old else None
        job = PlanningJob(
            user_id=user.id,
            trip_id=trip.id,
            kind="generate_trip",
            status=status,
            request_payload={},
            preference_snapshot={},
            created_at=timestamp or datetime.now(timezone.utc),
            heartbeat_at=timestamp,
        )
        db.add(job)
        db.commit()
        return job.id, trip.id


def test_job_acquisition_is_idempotent(monkeypatch):
    engine, session_factory = make_session_factory()
    job_id, _ = seed_job(session_factory)
    monkeypatch.setattr(planning, "SessionLocal", session_factory)

    assert planning._acquire_job(job_id, "generate_trip") == "acquired"
    assert planning._acquire_job(job_id, "generate_trip") == "running"

    with session_factory() as db:
        job = db.get(PlanningJob, job_id)
        assert job.attempts == 1
    engine.dispose()


def test_stale_job_is_failed_without_publishing_trip(monkeypatch):
    engine, session_factory = make_session_factory()
    job_id, trip_id = seed_job(session_factory, status="running", old=True)
    monkeypatch.setattr(maintenance, "SessionLocal", session_factory)

    result = maintenance.recover_stale_jobs.run()
    assert result["recovered"] == 1
    with session_factory() as db:
        assert db.get(PlanningJob, job_id).status == "failed"
        assert db.get(Trip, trip_id).status == "failed"
        assert db.get(Trip, trip_id).current_version == 0
    engine.dispose()
