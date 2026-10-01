"""配置管理模块"""

import os
from pathlib import Path
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# 加载环境变量
# 首先尝试加载当前目录的.env
load_dotenv()

# 然后尝试加载HelloAgents的.env(如果存在)
helloagents_env = Path(__file__).parent.parent.parent.parent / "HelloAgents" / ".env"
if helloagents_env.exists():
    load_dotenv(helloagents_env, override=False)  # 不覆盖已有的环境变量


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    # 应用基本配置
    app_name: str = "HelloAgents智能旅行助手"
    app_version: str = "1.4.0"
    debug: bool = False
    app_environment: str = "development"

    # 服务器配置
    host: str = "0.0.0.0"
    port: int = 8000
    max_concurrent_trip_plans: int = Field(default=4, ge=1, le=100)
    daily_available_minutes: int = Field(default=720, ge=60, le=1440)
    daily_meal_buffer_minutes: int = Field(default=180, ge=0, le=480)

    # 数据库配置
    database_url: str = ""

    session_cookie_name: str = "trip_session"
    session_cookie_secure: bool = False

    # Celery/Redis配置
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    celery_soft_time_limit_seconds: int = Field(default=1140, ge=60, le=7200)
    celery_time_limit_seconds: int = Field(default=1200, ge=60, le=7200)
    planning_job_stale_minutes: int = Field(default=35, ge=5, le=1440)
    planning_job_retention_days: int = Field(default=30, ge=1, le=365)

    # API限流。Redis不可用时会退化为当前进程内限流。
    auth_rate_limit_per_10_minutes: int = Field(default=20, ge=1, le=1000)
    external_api_rate_limit_per_minute: int = Field(default=60, ge=1, le=5000)
    trip_plan_rate_limit_per_hour: int = Field(default=10, ge=1, le=1000)
    max_active_jobs_per_user: int = Field(default=3, ge=1, le=20)

    session_lifetime_days: int = Field(
        default=7,
        ge=1,
        le=90,
    )

    # CORS配置 - 使用字符串,在代码中分割
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"

    # 高德地图API配置
    amap_api_key: str = ""

    # Unsplash API配置
    unsplash_access_key: str = ""
    unsplash_secret_key: str = ""

    # LLM配置 (从环境变量读取,由HelloAgents管理)
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4"

    # 日志配置
    log_level: str = "INFO"

    def get_cors_origins_list(self) -> List[str]:
        """获取CORS origins列表"""
        return [origin.strip() for origin in self.cors_origins.split(',')]


# 创建全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例"""
    return settings


# 验证必要的配置
def validate_config():
    """验证配置是否完整"""
    errors = []
    warnings = []

    if not settings.database_url:
        errors.append("DATABASE_URL未配置")

    if not settings.amap_api_key:
        errors.append("AMAP_API_KEY未配置")

    if settings.app_environment.casefold() == "production":
        if not settings.session_cookie_secure:
            errors.append("生产环境必须设置SESSION_COOKIE_SECURE=true")
        if any("localhost" in origin or "127.0.0.1" in origin for origin in settings.get_cors_origins_list()):
            errors.append("生产环境CORS_ORIGINS不能包含本地开发地址")

    # HelloAgentsLLM会自动从LLM_API_KEY读取,不强制要求OPENAI_API_KEY
    llm_api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not llm_api_key:
        warnings.append("LLM_API_KEY或OPENAI_API_KEY未配置,LLM功能可能无法使用")

    if errors:
        error_msg = "配置错误:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ValueError(error_msg)

    if warnings:
        print("\n⚠️  配置警告:")
        for w in warnings:
            print(f"  - {w}")

    return True


# 打印配置信息(用于调试)
def print_config():
    """打印当前配置(隐藏敏感信息)"""
    print(f"应用名称: {settings.app_name}")
    print(f"版本: {settings.app_version}")
    print(f"服务器: {settings.host}:{settings.port}")
    print(f"高德地图API Key: {'已配置' if settings.amap_api_key else '未配置'}")

    # 检查LLM配置
    llm_api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    llm_base_url = os.getenv("LLM_BASE_URL") or settings.openai_base_url
    llm_model = os.getenv("LLM_MODEL_ID") or settings.openai_model

    print(f"LLM API Key: {'已配置' if llm_api_key else '未配置'}")
    print(f"LLM Base URL: {llm_base_url}")
    print(f"LLM Model: {llm_model}")
    print(f"日志级别: {settings.log_level}")
