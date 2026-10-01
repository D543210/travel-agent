import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.auth.exceptions import (
    EmailAlreadyRegisteredError,
)
from app.auth.service import (
    authenticate_user,
    create_user_session,
    get_user_by_session_token,
    register_user,
    revoke_user_session,
)
from app.auth.sessions import hash_session_token
from app.db.base import Base
from app.db.models import UserSession
from app.models.auth_schemas import (
    UserRegisterRequest,
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
    )

    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    engine.dispose()


def make_register_request():
    return UserRegisterRequest(
        email="user@example.com",
        password="correct-password",
        display_name="旅行者",
    )


def test_register_user_hashes_password(
    db_session: Session,
):
    request = make_register_request()

    user = register_user(
        db_session,
        request,
    )

    assert user.email == "user@example.com"
    assert user.display_name == "旅行者"
    assert user.password_hash != "correct-password"
    assert user.password_hash.startswith("$argon2")


def test_duplicate_email_is_rejected(
    db_session: Session,
):
    request = make_register_request()

    register_user(db_session, request)

    with pytest.raises(
        EmailAlreadyRegisteredError,
    ):
        register_user(db_session, request)


def test_authenticate_user(
    db_session: Session,
):
    request = make_register_request()
    registered_user = register_user(
        db_session,
        request,
    )

    authenticated_user = authenticate_user(
        db_session,
        " USER@EXAMPLE.COM ",
        "correct-password",
    )

    assert authenticated_user is not None
    assert authenticated_user.id == registered_user.id

    assert (
        authenticate_user(
            db_session,
            "user@example.com",
            "wrong-password",
        )
        is None
    )

    assert (
        authenticate_user(
            db_session,
            "missing@example.com",
            "correct-password",
        )
        is None
    )


def test_session_creation_lookup_and_revocation(
    db_session: Session,
):
    user = register_user(
        db_session,
        make_register_request(),
    )

    user_session, raw_token = create_user_session(
        db_session,
        user,
    )

    stored_session = db_session.scalar(
        select(UserSession)
    )

    assert stored_session is not None
    assert stored_session.id == user_session.id
    assert (
        stored_session.token_hash
        == hash_session_token(raw_token)
    )
    assert stored_session.token_hash != raw_token

    current_user = get_user_by_session_token(
        db_session,
        raw_token,
    )

    assert current_user is not None
    assert current_user.id == user.id

    assert revoke_user_session(
        db_session,
        raw_token,
    )

    assert (
        get_user_by_session_token(
            db_session,
            raw_token,
        )
        is None
    )