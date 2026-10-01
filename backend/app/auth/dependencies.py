"""FastAPI认证依赖。"""

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db.models import User
from ..db.session import get_db
from .service import get_user_by_session_token


settings = get_settings()


def get_current_user(
    db: Annotated[
        Session,
        Depends(get_db),
    ],
    raw_token: Annotated[
        str | None,
        Cookie(
            alias=settings.session_cookie_name,
        ),
    ] = None,
) -> User:
    """取得当前登录用户，否则返回401。"""

    if raw_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "NOT_AUTHENTICATED",
                "message": "请先登录",
            },
        )

    user = get_user_by_session_token(
        db,
        raw_token,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_SESSION",
                "message": "登录状态已失效，请重新登录",
            },
        )

    return user