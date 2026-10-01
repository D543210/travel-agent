"""认证Cookie配置。"""

from fastapi import Response

from ..config import get_settings


def set_session_cookie(
    response: Response,
    raw_token: str,
) -> None:
    """把原始会话令牌写入HttpOnly Cookie。"""

    settings = get_settings()

    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        max_age=(
            settings.session_lifetime_days
            * 24
            * 60
            * 60
        ),
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )


def delete_session_cookie(
    response: Response,
) -> None:
    """要求浏览器删除会话Cookie。"""

    settings = get_settings()

    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )