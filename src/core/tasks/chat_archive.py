"""聊天记录归档 Celery 任务 —— 冷数据导出为 Parquet 并上传至 S3。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from src.core.tasks.celery_app import celery_app
from src.core.tasks.utils import run_async

if TYPE_CHECKING:
    import celery

logger = structlog.get_logger()


def _build_services() -> tuple[Any, Any]:
    """延迟构建归档服务所需的引擎和 session factory。"""
    from src.core.config import get_settings
    from src.core.db.engine import create_engine, create_session_factory
    from src.core.services.archive_exporter import ChatArchiveSettings
    from src.core.services.archive_s3 import S3Settings
    from src.core.services.chat import ChatDatabaseSettings
    from src.core.services.chat_archive import ArchiveService

    chat_cfg = ChatDatabaseSettings()
    archive_cfg = ChatArchiveSettings()
    s3_cfg = S3Settings()
    main_cfg = get_settings()

    chat_engine = create_engine(
        chat_cfg.CHAT_DATABASE_URL,
        pool_size=chat_cfg.CHAT_DB_POOL_SIZE,
        max_overflow=chat_cfg.CHAT_DB_MAX_OVERFLOW,
    )
    chat_sf = create_session_factory(chat_engine)
    main_engine = create_engine(
        main_cfg.DATABASE_URL,
        pool_size=main_cfg.DB_POOL_SIZE,
        max_overflow=main_cfg.DB_MAX_OVERFLOW,
    )
    main_sf = create_session_factory(main_engine)
    service = ArchiveService(chat_sf, main_sf, archive_cfg, s3_cfg)
    return service, archive_cfg


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
def archive_chat_history(
    self: celery.Task[Any, Any],
    partition_name: str | None = None,
) -> dict[str, Any]:
    """归档指定分区或自动发现超过 12 个月的分区。

    归档流程：
    1. 发现待归档分区（>= 12 个月前的月分区）
    2. 状态标记为 exporting
    3. 流式读取分区数据 → 每 5000 行攒成 Row Group → 写入 Parquet 文件（内置 Zstd 压缩）
    4. 上传到 S3，校验 SHA256
    5. DETACH 分区 → DROP TABLE
    6. 更新归档元数据表状态为 completed
    """
    try:
        service, _ = _build_services()
        result: dict[str, Any] = run_async(service.archive(partition_name))
        return result
    except Exception as exc:
        logger.exception(
            "归档任务失败",
            partition=partition_name,
            event_type="task.archive_failed",
        )
        raise self.retry(exc=exc) from exc


@celery_app.task
def ensure_chat_partitions() -> dict[str, str]:
    """确保当月和下月的分区存在。由定时任务每月 25 号调用。"""
    try:
        service, _ = _build_services()
        result: dict[str, str] = run_async(service.ensure_partitions())
        return result
    except Exception:
        logger.exception(
            "分区预创建失败",
            event_type="task.partition_ensure_failed",
        )
        return {"status": "error", "message": "分区预创建失败"}
