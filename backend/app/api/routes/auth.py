"""用户注册、登录及会话API。"""

from typing import Annotated

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy.orm import Session

from ...auth.cookies import (
    delete_session_cookie,
    set_session_cookie,
)
from ...auth.dependencies import get_current_user
from ...auth.exceptions import (
    EmailAlreadyRegisteredError,
)
from ...auth.service import (
    authenticate_user,
    create_user_session,
    register_user,
    revoke_user_session,
)
from ...config import get_settings
from ...db.models import User
from ...db.session import get_db
from ...models.auth_schemas import (
    AuthResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from ...security.rate_limit import client_identifier, enforce_rate_limit


router = APIRouter(
    prefix="/auth",
    tags=["用户认证"],
)

settings = get_settings()


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    request: UserRegisterRequest,
    http_request: Request,
    db: Annotated[
        Session,
        Depends(get_db),
    ],
):
    """注册用户。"""

    enforce_rate_limit(
        http_request,
        scope="auth-register",
        identifier=client_identifier(http_request),
        limit=settings.auth_rate_limit_per_10_minutes,
        window_seconds=600,
    )
    try:
        user = register_user(
            db,
            request,
        )
    except EmailAlreadyRegisteredError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "EMAIL_ALREADY_REGISTERED",
                "message": "该邮箱已经注册",
            },
        )

    return AuthResponse(
        message="注册成功，请登录",
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/login",
    response_model=AuthResponse,
)
def login(
    request: UserLoginRequest,
    http_request: Request,
    response: Response,
    db: Annotated[
        Session,
        Depends(get_db),
    ],
):
    """登录并创建服务端会话。"""

    enforce_rate_limit(
        http_request,
        scope="auth-login",
        identifier=client_identifier(http_request),
        limit=settings.auth_rate_limit_per_10_minutes,
        window_seconds=600,
    )
    user = authenticate_user(
        db,
        str(request.email),
        request.password.get_secret_value(),
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_CREDENTIALS",
                "message": "邮箱或密码错误",
            },
        )

    _, raw_token = create_user_session(
        db,
        user,
    )

    set_session_cookie(
        response,
        raw_token,
    )

    return AuthResponse(
        message="登录成功",
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
def logout(
    response: Response,
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
) -> None:
    """撤销当前会话并删除Cookie。"""

    if raw_token is not None:
        revoke_user_session(
            db,
            raw_token,
        )

    delete_session_cookie(response)


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_me(
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
):
    """返回当前登录用户。"""

    return UserResponse.model_validate(
        current_user,
    )
