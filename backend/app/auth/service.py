"""认证相关数据库操作。"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db.models import User, UserSession
from ..models.auth_schemas import UserRegisterRequest
from .exceptions import EmailAlreadyRegisteredError
from .passwords import hash_password, verify_password
from .sessions import (
    create_session_expiry,
    generate_session_token,
    hash_session_token,
)


# 用户不存在时也执行一次密码验证，
# 减小通过响应时间判断邮箱是否存在的风险。
_dummy_password_hash = hash_password(
    "not-a-real-user-password",
)


def register_user(
    db: Session,
    request: UserRegisterRequest,
) -> User:
    """注册用户并写入数据库。"""

    email = str(request.email)

    existing_user_id = db.scalar(
        select(User.id).where(
            User.email == email,
        )
    )

    if existing_user_id is not None:
        raise EmailAlreadyRegisteredError()

    user = User(
        email=email,
        password_hash=hash_password(
            request.password.get_secret_value(),
        ),
        display_name=request.display_name,
    )

    db.add(user)

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()

        # 数据库唯一约束负责处理并发注册。
        raise EmailAlreadyRegisteredError() from error

    db.refresh(user)

    return user


def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> User | None:
    """验证邮箱和密码。"""

    normalized_email = email.strip().casefold()

    user = db.scalar(
        select(User).where(
            User.email == normalized_email,
        )
    )

    password_hash = (
        user.password_hash
        if user is not None
        else _dummy_password_hash
    )

    password_matches = verify_password(
        password,
        password_hash,
    )

    if (
        user is None
        or not password_matches
        or not user.is_active
    ):
        return None

    return user


def create_user_session(
    db: Session,
    user: User,
) -> tuple[UserSession, str]:
    """创建会话，返回数据库记录及原始令牌。"""

    settings = get_settings()

    raw_token = generate_session_token()

    user_session = UserSession(
        user_id=user.id,
        token_hash=hash_session_token(
            raw_token,
        ),
        expires_at=create_session_expiry(
            settings.session_lifetime_days,
        ),
    )

    db.add(user_session)
    db.commit()
    db.refresh(user_session)

    return user_session, raw_token


def get_user_by_session_token(
    db: Session,
    raw_token: str,
) -> User | None:
    """通过尚未过期、尚未撤销的会话查询用户。"""

    if not raw_token:
        return None

    now = datetime.now(timezone.utc)
    token_hash = hash_session_token(raw_token)

    statement = (
        select(User)
        .join(
            UserSession,
            UserSession.user_id == User.id,
        )
        .where(
            UserSession.token_hash == token_hash,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
            User.is_active.is_(True),
        )
    )

    user = db.scalar(statement)
    if user is not None:
        user_session = db.scalar(
            select(UserSession).where(UserSession.token_hash == token_hash)
        )
        if user_session is not None and (
            user_session.last_seen_at is None
            or (now - user_session.last_seen_at).total_seconds() >= 300
        ):
            user_session.last_seen_at = now
            db.commit()
    return user


def revoke_user_session(
    db: Session,
    raw_token: str,
) -> bool:
    """撤销指定会话。"""

    if not raw_token:
        return False

    user_session = db.scalar(
        select(UserSession).where(
            UserSession.token_hash
            == hash_session_token(raw_token),
        )
    )

    if (
        user_session is None
        or user_session.revoked_at is not None
    ):
        return False

    user_session.revoked_at = datetime.now(
        timezone.utc,
    )

    db.commit()

    return True
