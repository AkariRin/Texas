"""使用 pydantic-settings 进行配置管理。"""

from __future__ import annotations

import sys
from functools import lru_cache

import structlog
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = structlog.get_logger()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # NapCat WebSocket（反向 WS：NapCat -> Texas）
    NAPCAT_ACCESS_TOKEN: str = ""
    NAPCAT_MESSAGE_POST_FORMAT: str = "array"
    NAPCAT_REPORT_SELF_MESSAGE: bool = False
    NAPCAT_HEART_INTERVAL: int = 30000
    NAPCAT_RECONNECT_INTERVAL: int = 5000

    # NapCat 资源
    IMAGE_URL_TTL: int = 7200
    ENABLE_RKEY_REFRESH: bool = True

    # PostgreSQL
    DATABASE_URL: str = "postgresql+asyncpg://texas:texas@localhost:5432/texas"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # Redis - Celery Broker
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"

    # Redis - Celery Beat（RedBeat 调度器存储）
    CELERY_REDBEAT_URL: str = "redis://localhost:6379/2"

    # Redis - 缓存
    CACHE_REDIS_URL: str = "redis://localhost:6379/1"
    CACHE_DEFAULT_TTL: int = 300

    # Prometheus
    METRICS_ENABLED: bool = True

    # 日志
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json | console

    # 处理器扫描
    HANDLER_SCAN_PACKAGES: list[str] = ["src.handlers"]

    # 前端
    FRONTEND_DIST_DIR: str = "frontend/dist"

    # 服务器
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ── 用户管理 (Personnel) ──
    PERSONNEL_SYNC_INTERVAL: int = 300  # 定期同步间隔（秒），默认 5 分钟
    PERSONNEL_SYNC_INITIAL_DELAY: int = 3  # 连接建立后首次同步延迟（秒）
    PERSONNEL_SYNC_BATCH_SIZE: int = 500  # 批量写入每批大小
    PERSONNEL_SYNC_API_DELAY: float = 0.5  # 每个群 API 调用之间的延迟（秒），防止 NapCat 限流
    PERSONNEL_SYNC_LOCK_TTL: int = 600  # 同步锁超时时间（秒）

    # ── 聊天记录数据库 ──
    CHAT_DATABASE_URL: str = "postgresql+asyncpg://texas:texas@localhost:5432/chat_history"
    CHAT_DB_POOL_SIZE: int = 5
    CHAT_DB_MAX_OVERFLOW: int = 10

    # ── S3 归档 ──
    S3_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    S3_REGION: str = "us-east-1"
    S3_ARCHIVE_BUCKET: str = "texas-chat-archive"
    S3_ARCHIVE_PREFIX: str = "v1"

    # ── 聊天归档策略 ──
    CHAT_ARCHIVE_RETENTION_MONTHS: int = 12
    CHAT_ARCHIVE_BATCH_SIZE: int = 5000
    CHAT_ARCHIVE_COMPRESSION: str = "zstd"

    # 运行环境：development | production
    ENV: str = "development"

    @property
    def is_production(self) -> bool:
        """是否处于生产环境。"""
        return self.ENV.lower() == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """返回全局唯一的 Settings 实例（线程安全，延迟创建）。"""
    return Settings()


def validate_settings(settings: Settings) -> None:
    """验证关键配置项。若 NAPCAT_ACCESS_TOKEN 为空则退出。"""
    if not settings.NAPCAT_ACCESS_TOKEN:
        logger.critical(
            "NAPCAT_ACCESS_TOKEN 为空！存在严重安全风险，拒绝启动。",
            event_type="security.token_missing",
        )
        sys.exit(1)
