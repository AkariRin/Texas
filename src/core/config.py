"""使用 pydantic-settings 进行配置管理。"""

from __future__ import annotations

import sys
from functools import lru_cache
from typing import Literal, Self
from urllib.parse import urlparse, urlunparse

import structlog
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = structlog.get_logger()


def _normalize_redis_url(url: str) -> str:
    """规范化 Redis URL，强制使用 DB /0，忽略 URL 中填写的库索引。

    允许运维人员在环境变量中省略 /0 后缀（如 redis://host:6379），
    系统内部统一补齐，确保所有连接指向 DB 0（Redis Cluster 兼容要求）。
    """
    parsed = urlparse(url)
    return urlunparse(parsed._replace(path="/0"))


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
    NAPCAT_HEART_INTERVAL: int = Field(default=30000, ge=1000)  # 心跳间隔（ms），默认 30s
    NAPCAT_RECONNECT_INTERVAL: int = Field(default=5000, ge=1000)  # 断线重连间隔（ms），默认 5s

    # NapCat 资源
    IMAGE_URL_TTL: int = Field(default=7200, ge=1)  # 图片 URL 缓存时间（秒），默认 2h
    ENABLE_RKEY_REFRESH: bool = True

    # PostgreSQL
    DATABASE_URL: str = "postgresql+asyncpg://texas:texas@localhost:5432/texas"
    DB_POOL_SIZE: int = Field(default=10, ge=1)  # 连接池基础连接数
    # 连接池最大溢出连接数（总上限 = pool_size + max_overflow）
    DB_MAX_OVERFLOW: int = Field(default=20, ge=0)

    # Redis - Celery Broker（与应用数据共用同一 DB，通过 texas:queue 队列名区分）
    CELERY_BROKER_URL: str = "redis://localhost:6379"

    # Redis - Celery Beat（RedBeat 调度器存储，键前缀 texas:beat:）
    CELERY_REDBEAT_URL: str = "redis://localhost:6379"

    # 内部服务回调地址（供 Celery Worker 回调主进程）
    INTERNAL_API_BASE_URL: str = "http://localhost:8000"

    # Redis - 缓存（易失，可丢失，无持久化；键前缀 texas:perm:* / texas:personnel:*）
    CACHE_REDIS_URL: str = "redis://localhost:6379"
    CACHE_DEFAULT_TTL: int = Field(default=300, ge=1)  # 缓存默认 TTL（秒），默认 5min

    # Redis - 持久化存储（会话、RPC、分布式锁、打卡去重、同步状态；键前缀 texas:*）
    # 留空时自动回退到 CACHE_REDIS_URL（单实例兼容模式）
    PERSISTENT_REDIS_URL: str = ""

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
    PERSONNEL_SYNC_INTERVAL: int = Field(default=300, ge=10)  # 定时同步间隔（秒），默认 5min
    # 首次同步启动延迟（秒），等待 WS 稳定
    PERSONNEL_SYNC_INITIAL_DELAY: int = Field(default=3, ge=0)
    PERSONNEL_SYNC_BATCH_SIZE: int = Field(default=500, ge=1)  # 批量写入每批条数
    # 逐群拉成员时的 API 间隔（秒），避免限速
    PERSONNEL_SYNC_API_DELAY: float = Field(default=0.5, ge=0.0)
    # 同步分布式锁 TTL（秒），默认 10min
    PERSONNEL_SYNC_LOCK_TTL: int = Field(default=600, ge=10)

    # ── 聊天记录数据库 ──
    CHAT_DATABASE_URL: str = "postgresql+asyncpg://texas:texas@localhost:5432/chat_history"
    # 聊天库连接池（写入频率低于主库，池大小相应缩小）
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
    # 热数据保留月数，超期分区移至 S3
    CHAT_ARCHIVE_RETENTION_MONTHS: int = Field(default=12, ge=1)
    # 导出 Parquet 时每批行数（行组大小）
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
        """校验 Redis URL 格式并强制规范化到 DB /0。"""
        if not v.startswith(("redis://", "rediss://")):
            raise ValueError(f"Redis URL 必须以 'redis://' 或 'rediss://' 开头，当前值: {v!r}")
        return _normalize_redis_url(v)

    @model_validator(mode="after")
    def _default_persistent_redis(self) -> Self:
        """未显式配置 PERSISTENT_REDIS_URL 时回退到 CACHE_REDIS_URL（单实例兼容模式）。"""
        if not self.PERSISTENT_REDIS_URL:
            self.PERSISTENT_REDIS_URL = self.CACHE_REDIS_URL
        elif not self.PERSISTENT_REDIS_URL.startswith(("redis://", "rediss://")):
            raise ValueError(
                f"PERSISTENT_REDIS_URL 必须以 'redis://' 或 'rediss://' 开头，"
                f"当前值: {self.PERSISTENT_REDIS_URL!r}"
            )
        else:
            self.PERSISTENT_REDIS_URL = _normalize_redis_url(self.PERSISTENT_REDIS_URL)
        return self

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
