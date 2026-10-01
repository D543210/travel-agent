"""认证服务异常。"""


class AuthServiceError(Exception):
    """认证服务基础异常。"""


class EmailAlreadyRegisteredError(AuthServiceError):
    """邮箱已经注册。"""