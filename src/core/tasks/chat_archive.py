"""聊天记录归档 Celery 任务 —— 冷数据导出为 Parquet 并上传至 S3。"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from src.core.tasks.celery_app import celery_app

logger = structlog.get_logger()


def _run_async(coro: Any) -> Any:
    """在 Celery 同步 Worker 中运行异步协程。"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def _build_services() -> tuple[Any, Any]:
    """延迟构建归档服务所需的引擎和 session factory。"""
    from src.core.chat.archive_service import ArchiveService
    from src.core.chat.engine import create_chat_engine, create_chat_session_factory
    from src.core.config import Settings
    from src.core.db.engine import create_engine, create_session_factory

    settings = Settings()
    chat_engine = create_chat_engine(settings)
    chat_sf = create_chat_session_factory(chat_engine)
    main_engine = create_engine(settings)
    main_sf = create_session_factory(main_engine)
    service = ArchiveService(chat_sf, main_sf, settings)
    return service, settings


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
def archive_chat_history(self: Any, partition_name: str | None = None) -> dict[str, Any]:
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
        result: dict[str, Any] = _run_async(service.archive(partition_name))
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
        result: dict[str, str] = _run_async(service.ensure_partitions())
        return result
    except Exception:
        logger.exception(
            "分区预创建失败",
            event_type="task.partition_ensure_failed",
        )
        return {"status": "error", "message": "分区预创建失败"}
