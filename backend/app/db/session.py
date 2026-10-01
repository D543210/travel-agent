"""数据库引擎和会话管理"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session,sessionmaker

from ..config import get_settings

settings = get_settings()

if not settings.database_url:
    raise RuntimeError("DATABASE_URL未配置")

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
)

def get_db() -> Generator[Session,None,None]:
    with SessionLocal() as db:
        yield db