"""使用 pydantic-settings 进行配置管理。"""

from __future__ import annotations

import sys
from functools import lru_cache
from typing import Literal

import structlog
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = structlog.get_logger()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # NapCat WebSocket（反向 WS：NapCat -> Texas）
    NAPCAT_ACCESS_TOKEN: SecretStr = SecretStr("")
    NAPCAT_MESSAGE_POST_FORMAT: Literal["array", "string"] = "array"
    NAPCAT_REPORT_SELF_MESSAGE: bool = False
    NAPCAT_HEART_INTERVAL: int = Field(default=30000, ge=1000)
    NAPCAT_RECONNECT_INTERVAL: int = Field(default=5000, ge=1000)

    # NapCat 资源
    IMAGE_URL_TTL: int = Field(default=7200, ge=1)
    ENABLE_RKEY_REFRESH: bool = True

    # PostgreSQL
    DATABASE_URL: str = "postgresql+asyncpg://texas:texas@localhost:5432/texas"
    DB_POOL_SIZE: int = Field(default=10, ge=1)
    DB_MAX_OVERFLOW: int = Field(default=20, ge=0)

    # Redis - Celery Broker
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"

    # Redis - Celery Beat（RedBeat 调度器存储）
    CELERY_REDBEAT_URL: str = "redis://localhost:6379/2"

    # Redis - 缓存
    CACHE_REDIS_URL: str = "redis://localhost:6379/1"
    CACHE_DEFAULT_TTL: int = Field(default=300, ge=1)

    # Prometheus
    METRICS_ENABLED: bool = True

    # 日志
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_FORMAT: Literal["json", "console"] = "json"

    # 处理器扫描
    HANDLER_SCAN_PACKAGES: list[str] = ["src.handlers"]

    # 前端
    FRONTEND_DIST_DIR: str = "frontend/dist"

    # 服务器
    HOST: str = "0.0.0.0"
    PORT: int = Field(default=8000, ge=1, le=65535)

    # ── 用户管理 (Personnel) ──
    PERSONNEL_SYNC_INTERVAL: int = Field(default=300, ge=10)
    PERSONNEL_SYNC_INITIAL_DELAY: int = Field(default=3, ge=0)
    PERSONNEL_SYNC_BATCH_SIZE: int = Field(default=500, ge=1)
    PERSONNEL_SYNC_API_DELAY: float = Field(default=0.5, ge=0.0)
    PERSONNEL_SYNC_LOCK_TTL: int = Field(default=600, ge=10)

    # ── 聊天记录数据库 ──
    CHAT_DATABASE_URL: str = "postgresql+asyncpg://texas:texas@localhost:5432/chat_history"
    CHAT_DB_POOL_SIZE: int = Field(default=5, ge=1)
    CHAT_DB_MAX_OVERFLOW: int = Field(default=10, ge=0)

    # ── S3 归档 ──
    S3_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: SecretStr = SecretStr("")
    S3_REGION: str = "us-east-1"
    S3_ARCHIVE_BUCKET: str = "texas-chat-archive"
    S3_ARCHIVE_PREFIX: str = "v1"

    # ── 聊天归档策略 ──
    CHAT_ARCHIVE_RETENTION_MONTHS: int = Field(default=12, ge=1)
    CHAT_ARCHIVE_BATCH_SIZE: int = Field(default=5000, ge=100)
    CHAT_ARCHIVE_COMPRESSION: Literal["zstd", "gzip", "none"] = "zstd"

    # 运行环境：development | production
    ENV: Literal["development", "production"] = "development"

    @field_validator("DATABASE_URL", "CHAT_DATABASE_URL")
    @classmethod
    def validate_pg_url(cls, v: str) -> str:
        if not v.startswith("postgresql"):
            raise ValueError(f"数据库 URL 必须以 'postgresql' 开头，当前值: {v!r}")
        return v

    @field_validator("CELERY_BROKER_URL", "CELERY_REDBEAT_URL", "CACHE_REDIS_URL")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        if not v.startswith(("redis://", "rediss://")):
            raise ValueError(f"Redis URL 必须以 'redis://' 或 'rediss://' 开头，当前值: {v!r}")
        return v

    @property
    def is_production(self) -> bool:
        """是否处于生产环境。"""
        return self.ENV == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """返回全局唯一的 Settings 实例（线程安全，延迟创建）。"""
    return Settings()


def validate_settings(settings: Settings) -> None:
    """验证关键配置项。若 NAPCAT_ACCESS_TOKEN 为空则退出。"""
    if not settings.NAPCAT_ACCESS_TOKEN.get_secret_value():
        logger.critical(
            "NAPCAT_ACCESS_TOKEN 为空！存在严重安全风险，拒绝启动。",
            event_type="security.token_missing",
        )
        sys.exit(1)
