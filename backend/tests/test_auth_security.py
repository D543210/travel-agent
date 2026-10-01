from app.auth.passwords import (
    hash_password,
    verify_password,
)
from app.auth.sessions import (
    generate_session_token,
    hash_session_token,
)
from app.models.auth_schemas import (
    UserRegisterRequest,
)


def test_password_hash_and_verification():
    password = "correct-password"
    password_hash = hash_password(password)

    assert password_hash != password
    assert password_hash.startswith("$argon2")
    assert verify_password(password, password_hash)
    assert not verify_password(
        "wrong-password",
        password_hash,
    )


def test_password_hash_uses_random_salt():
    password = "correct-password"

    first_hash = hash_password(password)
    second_hash = hash_password(password)

    assert first_hash != second_hash


def test_session_tokens_are_random_and_hashable():
    first_token = generate_session_token()
    second_token = generate_session_token()

    assert first_token != second_token

    digest = hash_session_token(first_token)

    assert len(digest) == 64
    assert digest == hash_session_token(first_token)
    assert digest != first_token


def test_registration_normalizes_public_fields():
    request = UserRegisterRequest(
        email=" User@Example.COM ",
        password="correct-password",
        display_name=" 旅行者 ",
    )

    assert str(request.email) == "user@example.com"
    assert request.display_name == "旅行者"
    assert (
        request.password.get_secret_value()
        == "correct-password"
    )
    assert "correct-password" not in repr(request)