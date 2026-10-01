"""登录会话令牌工具。"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone


SESSION_TOKEN_BYTES = 32


def generate_session_token() -> str:
    """生成不可预测的随机会话令牌。"""

    return secrets.token_urlsafe(
        SESSION_TOKEN_BYTES,
    )


def hash_session_token(token: str) -> str:
    """计算会话令牌的SHA-256摘要。"""

    return hashlib.sha256(
        token.encode("utf-8"),
    ).hexdigest()


def create_session_expiry(
    lifetime_days: int = 7,
) -> datetime:
    """计算带时区的会话过期时间。"""

    return datetime.now(timezone.utc) + timedelta(
        days=lifetime_days,
    )