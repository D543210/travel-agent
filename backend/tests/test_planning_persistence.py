from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import Trip, TripRevision, User
from app.models.planning_schemas import (
    TripPlanningJobRequest,
    TripRevisionJobRequest,
    UserPreferenceUpdate,
)
from app.services.planning_service import (
    TripVersionConflictError,
    create_generation_job,
    create_revision_job,
    get_owned_job,
)
from app.services.preference_service import (
    delete_user_preference,
    get_user_preference,
    upsert_user_preference,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def user(db_session: Session):
    value = User(
        email="planner@example.com",
        password_hash="unused",
        display_name="Planner",
    )
    db_session.add(value)
    db_session.commit()
    db_session.refresh(value)
    return value


def request_payload(use_saved_preferences=True):
    return TripPlanningJobRequest(
        city="北京",
        start_date="2026-10-01",
        end_date="2026-10-01",
        travel_days=1,
        transportation="步行",
        accommodation="经济型酒店",
        preferences=["历史文化"],
        free_text_input="",
        use_saved_preferences=use_saved_preferences,
    )


def test_preferences_are_explicit_and_versioned(db_session, user):
    first = upsert_user_preference(
        db_session,
        user.id,
        UserPreferenceUpdate(
            attraction_types=["自然风光"],
            dietary_restrictions=["素食"],
            transportation_preference="公共交通",
        ),
    )
    assert first.version == 1

    second = upsert_user_preference(
        db_session,
        user.id,
        UserPreferenceUpdate(attraction_types=["艺术"]),
    )
    assert second.version == 2
    assert get_user_preference(db_session, user.id).attraction_types == ["艺术"]
    assert delete_user_preference(db_session, user.id)
    assert get_user_preference(db_session, user.id) is None


def test_generation_job_snapshots_used_preferences(db_session, user):
    upsert_user_preference(
        db_session,
        user.id,
        UserPreferenceUpdate(
            attraction_types=["自然风光"],
            dietary_restrictions=["素食"],
            transportation_preference="公共交通",
        ),
    )
    job = create_generation_job(db_session, user.id, request_payload())

    assert job.status == "queued"
    assert job.request_payload["preferences"] == ["历史文化", "自然风光"]
    assert job.request_payload["transportation"] == "公共交通"
    assert "素食" in job.request_payload["free_text_input"]
    assert job.preference_snapshot["version"] == 1
    assert get_owned_job(db_session, user.id, job.id).id == job.id
    assert get_owned_job(db_session, uuid4(), job.id) is None


def test_revision_job_uses_optimistic_version(db_session, user):
    trip = Trip(
        user_id=user.id,
        title="北京行程",
        status="ready",
        current_version=1,
    )
    db_session.add(trip)
    db_session.flush()
    db_session.add(
        TripRevision(
            trip_id=trip.id,
            version=1,
            request_snapshot={},
            preference_snapshot={},
            plan={},
        )
    )
    db_session.commit()

    request = TripRevisionJobRequest(
        expected_version=1,
        operations=[
            {
                "type": "update_visit_duration",
                "day_index": 0,
                "attraction_index": 0,
                "visit_duration": 120,
            }
        ],
    )
    job = create_revision_job(db_session, user.id, trip.id, request)
    assert job.base_version == 1

    request.expected_version = 2
    with pytest.raises(TripVersionConflictError):
        create_revision_job(db_session, user.id, trip.id, request)
