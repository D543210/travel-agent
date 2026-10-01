import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.db.base import Base
from app.db.session import get_db


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
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

    app.dependency_overrides[get_db] = (
        override_get_db
    )

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    engine.dispose()


def registration_payload():
    return {
        "email": "user@example.com",
        "password": "correct-password",
        "display_name": "旅行者",
    }


def test_register_login_me_and_logout(
    client: TestClient,
):
    register_response = client.post(
        "/api/auth/register",
        json=registration_payload(),
    )

    assert register_response.status_code == 201
    assert (
        register_response.json()["user"]["email"]
        == "user@example.com"
    )
    assert "password_hash" not in (
        register_response.text
    )

    wrong_login_response = client.post(
        "/api/auth/login",
        json={
            "email": "user@example.com",
            "password": "wrong-password",
        },
    )

    assert wrong_login_response.status_code == 401

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": "user@example.com",
            "password": "correct-password",
        },
    )

    assert login_response.status_code == 200

    set_cookie = login_response.headers.get(
        "set-cookie",
        "",
    ).lower()

    assert "trip_session=" in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie

    me_response = client.get(
        "/api/auth/me",
    )

    assert me_response.status_code == 200
    assert (
        me_response.json()["email"]
        == "user@example.com"
    )

    logout_response = client.post(
        "/api/auth/logout",
    )

    assert logout_response.status_code == 204

    after_logout_response = client.get(
        "/api/auth/me",
    )

    assert after_logout_response.status_code == 401


def test_duplicate_registration_returns_409(
    client: TestClient,
):
    first_response = client.post(
        "/api/auth/register",
        json=registration_payload(),
    )

    second_response = client.post(
        "/api/auth/register",
        json=registration_payload(),
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_trip_plan_requires_auth(
    client: TestClient,
):
    response = client.post(
        "/api/trip/plan",
        json={
            "city": "北京",
            "start_date": "2026-10-01",
            "end_date": "2026-10-01",
            "travel_days": 1,
            "transportation": "公共交通",
            "accommodation": "经济型酒店",
            "preferences": ["历史文化"],
            "free_text_input": "",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == (
        "NOT_AUTHENTICATED"
    )


def test_external_service_endpoints_require_auth(client: TestClient):
    response = client.get("/api/poi/search", params={"keywords": "故宫", "city": "北京"})
    assert response.status_code == 401


def test_untrusted_origin_is_rejected(client: TestClient):
    response = client.post(
        "/api/auth/login",
        headers={"Origin": "https://evil.example"},
        json={"email": "user@example.com", "password": "correct-password"},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ORIGIN_NOT_ALLOWED"
