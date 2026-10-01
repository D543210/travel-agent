"""FastAPI主应用"""

from contextlib import asynccontextmanager
import logging
from uuid import uuid4
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from ..config import get_settings, validate_config, print_config
from .routes import auth, planning, preferences, trip, poi, map as map_routes
from ..logging_context import (
    reset_request_id,
    set_request_id,
)
from ..db.session import SessionLocal

# 获取配置
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """验证启动配置，并在应用关闭时输出统一日志。"""

    print("\n" + "=" * 60)
    print(f"🚀 {settings.app_name} v{settings.app_version}")
    print("=" * 60)
    print_config()
    try:
        validate_config()
        print("\n✅ 配置验证通过")
    except ValueError as error:
        print(f"\n❌ 配置验证失败:\n{error}")
        print("\n请检查.env文件并确保所有必要的配置项都已设置")
        raise

    print("\n" + "=" * 60)
    print("📚 API文档: http://localhost:8000/docs")
    print("📖 ReDoc文档: http://localhost:8000/redoc")
    print("=" * 60 + "\n")
    yield
    print("\n" + "=" * 60)
    print("👋 应用正在关闭...")
    print("=" * 60 + "\n")

# 创建FastAPI应用
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="基于HelloAgents框架的智能旅行规划助手API",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def origin_guard_middleware(request: Request, call_next):
    """拒绝浏览器从未授权Origin发起的状态修改请求。"""

    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        if origin and origin not in settings.get_cors_origins_list():
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": {"code": "ORIGIN_NOT_ALLOWED", "message": "请求来源不受信任"}},
            )
    return await call_next(request)

@app.middleware("http")
async def request_id_middleware(
    request: Request,
    call_next,
):
    """为每次HTTP请求设置独立的请求ID"""
    request_id = (
        request.headers.get("X-Request-ID")
        or uuid4().hex[:12]
    )

    token = set_request_id(request_id)

    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        reset_request_id(token)

# 注册路由
app.include_router(auth.router, prefix="/api")
app.include_router(preferences.router, prefix="/api")
app.include_router(planning.router, prefix="/api")
app.include_router(trip.router, prefix="/api")
app.include_router(poi.router, prefix="/api")
app.include_router(map_routes.router, prefix="/api")

@app.get("/")
async def root():
    """根路径"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health")
def health():
    """检查API、PostgreSQL、Redis和Worker心跳。"""

    dependencies: dict[str, str] = {}
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        dependencies["postgresql"] = "healthy"
    except Exception:
        dependencies["postgresql"] = "unavailable"

    try:
        redis_client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
        redis_client.ping()
        dependencies["redis"] = "healthy"
        dependencies["worker"] = (
            "healthy"
            if redis_client.get("trip-planner:worker-heartbeat")
            else "unavailable"
        )
    except RedisError:
        dependencies["redis"] = "unavailable"
        dependencies["worker"] = "unavailable"

    healthy = all(value == "healthy" for value in dependencies.values())
    payload = {
        "status": "healthy" if healthy else "degraded",
        "service": settings.app_name,
        "version": settings.app_version,
        "dependencies": dependencies,
    }
    if not healthy:
        return JSONResponse(status_code=503, content=payload)
    return payload


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
