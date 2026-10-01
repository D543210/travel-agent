"""Redis优先、进程内退化的固定窗口限流。"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import defaultdict

from fastapi import HTTPException, Request, status
from redis import Redis
from redis.exceptions import RedisError

from ..config import get_settings


settings = get_settings()
_redis = Redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=0.25,
    socket_timeout=0.25,
)
_local_lock = threading.Lock()
_local_windows: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))


def client_identifier(request: Request) -> str:
    """使用实际连接地址，不信任客户端自行提交的转发头。"""

    return request.client.host if request.client else "unknown"


def _key(scope: str, identifier: str, window_seconds: int) -> str:
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:24]
    window = int(time.time()) // window_seconds
    return f"trip-planner:rate:{scope}:{digest}:{window}"


def _local_increment(key: str, window_seconds: int) -> int:
    now = int(time.time())
    with _local_lock:
        count, expires_at = _local_windows[key]
        if expires_at <= now:
            count, expires_at = 0, now + window_seconds
        count += 1
        _local_windows[key] = (count, expires_at)
        if len(_local_windows) > 10_000:
            expired = [name for name, (_, expiry) in _local_windows.items() if expiry <= now]
            for name in expired:
                _local_windows.pop(name, None)
        return count


def enforce_rate_limit(
    request: Request,
    *,
    scope: str,
    limit: int,
    window_seconds: int,
    identifier: str | None = None,
) -> None:
    """超过固定窗口配额时返回429。"""

    identity = identifier or client_identifier(request)
    key = _key(scope, identity, window_seconds)
    try:
        count = int(
            _redis.eval(
                "local n=redis.call('INCR',KEYS[1]); "
                "if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]); end; "
                "return n",
                1,
                key,
                window_seconds,
            )
        )
    except RedisError:
        count = _local_increment(key, window_seconds)

    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "RATE_LIMITED",
                "message": "请求过于频繁，请稍后再试",
            },
            headers={"Retry-After": str(window_seconds)},
        )
