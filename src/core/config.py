"""使用 pydantic-settings 进行配置管理。"""

from __future__ import annotations

import sys

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

    # 运行环境：development | production
    ENV: str = "development"

    @property
    def is_production(self) -> bool:
        """是否处于生产环境。"""
        return self.ENV.lower() == "production"


def validate_settings(settings: Settings) -> None:
    """验证关键配置项。若 NAPCAT_ACCESS_TOKEN 为空则退出。"""
    if not settings.NAPCAT_ACCESS_TOKEN:
        logger.critical(
            "NAPCAT_ACCESS_TOKEN 为空！存在严重安全风险，拒绝启动。",
            event_type="security.token_missing",
        )
        sys.exit(1)
