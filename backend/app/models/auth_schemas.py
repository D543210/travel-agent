"""认证API使用的请求和响应模型。"""

from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
)


class UserRegisterRequest(BaseModel):
    """用户注册请求。"""

    email: EmailStr
    password: SecretStr = Field(
        ...,
        min_length=8,
        max_length=128,
    )
    display_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return str(value).strip().casefold()

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(
        cls,
        value: str,
    ) -> str:
        value = value.strip()

        if not value:
            raise ValueError("显示名称不能为空")

        return value


class UserLoginRequest(BaseModel):
    """用户登录请求。"""

    email: EmailStr
    password: SecretStr = Field(
        ...,
        min_length=8,
        max_length=128,
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return str(value).strip().casefold()


class UserResponse(BaseModel):
    """可以安全返回给前端的用户信息。"""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    email: EmailStr
    display_name: str
    is_active: bool
    created_at: datetime


class AuthResponse(BaseModel):
    """登录或注册成功响应。"""

    message: str
    user: UserResponse