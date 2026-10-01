from contextvars import ContextVar
import json
import logging

_request_id: ContextVar[str] = ContextVar(
    "request_id",
    default="-",
)
logger = logging.getLogger("trip_planner")

def set_request_id(request_id: str):
    """设置当前请求ID并返回重置令牌。"""
    return _request_id.set(request_id)

def reset_request_id(token) -> None:
    """恢复之前的请求ID"""
    _request_id.reset(token)

def get_request_id() -> str:
    """获取当前请求ID"""
    return _request_id.get()

def log(message: str) -> None:
    """输出不包含用户请求正文的结构化日志。"""
    logger.info(
        json.dumps(
            {"request_id": get_request_id(), "message": message},
            ensure_ascii=False,
        )
    )
