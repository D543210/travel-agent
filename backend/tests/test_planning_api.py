from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.db.base import Base
from app.db.session import get_db


@pytest.fixture
def planning_client(authenticated_user, monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
    )
    Base.metadata.create_all(engine)

    def override_get_db():
        with testing_session() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(
        "app.api.routes.planning.generate_trip_job.delay",
        lambda job_id: SimpleNamespace(id=f"celery-{job_id}"),
    )

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


def trip_request():
    return {
        "city": "北京",
        "start_date": "2026-10-01",
        "end_date": "2026-10-01",
        "travel_days": 1,
        "transportation": "公共交通",
        "accommodation": "经济型酒店",
        "preferences": ["历史文化"],
        "free_text_input": "",
        "use_saved_preferences": True,
    }


def test_preferences_and_async_job_api(planning_client: TestClient):
    preference = {
        "attraction_types": ["自然风光"],
        "dietary_restrictions": ["素食"],
        "travel_pace": "舒缓",
        "transportation_preference": "步行",
        "accommodation_preference": "民宿",
    }
    saved = planning_client.put("/api/preferences/me", json=preference)
    assert saved.status_code == 200
    assert saved.json()["version"] == 1

    created = planning_client.post("/api/trips/plan", json=trip_request())
    assert created.status_code == 202
    job_id = created.json()["job_id"]

    job = planning_client.get(f"/api/jobs/{job_id}")
    assert job.status_code == 200
    assert job.json()["status"] == "queued"
    assert job.json()["progress_percent"] == 0

    trips = planning_client.get("/api/trips")
    assert trips.status_code == 200
    assert trips.json()[0]["trip_id"] == created.json()["trip_id"]

    archived = planning_client.delete(f"/api/trips/{created.json()['trip_id']}")
    assert archived.status_code == 204
    assert planning_client.get("/api/trips").json() == []
    assert len(planning_client.get("/api/trips?include_archived=true").json()) == 1

    restored = planning_client.post(f"/api/trips/{created.json()['trip_id']}/restore")
    assert restored.status_code == 204
    assert len(planning_client.get("/api/trips").json()) == 1

    removed = planning_client.delete("/api/preferences/me")
    assert removed.status_code == 204
    assert planning_client.get("/api/preferences/me").json() is None


def test_job_is_not_visible_to_a_different_user(
    planning_client: TestClient,
    authenticated_user,
):
    created = planning_client.post("/api/trips/plan", json=trip_request())
    job_id = created.json()["job_id"]
    authenticated_user.id = uuid4()

    response = planning_client.get(f"/api/jobs/{job_id}")
    assert response.status_code == 404
