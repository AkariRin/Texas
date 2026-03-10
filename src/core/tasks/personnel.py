"""人事数据持久化 Celery 任务。"""

from __future__ import annotations

import asyncio
from typing import Any, cast

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.cache.client import CacheClient
from src.core.config import Settings
from src.core.monitoring.metrics import personnel_sync_total
from src.core.personnel.service import PersonnelService
from src.core.tasks.celery_app import celery_app

logger = structlog.get_logger()

# 为 Celery Worker 创建独立的数据库引擎和缓存客户端
_settings = Settings()
_engine = create_async_engine(
    _settings.DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)
_session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
_cache = CacheClient(url=_settings.CACHE_REDIS_URL, default_ttl=_settings.CACHE_DEFAULT_TTL)
_service = PersonnelService(
    session_factory=_session_factory,
    cache=_cache,
    settings=_settings,
)


def _run_async(coro: Any) -> Any:
    """在 Celery 同步 Worker 中运行异步协程。"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # 不应该发生，但以防万一
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def persist_personnel_data(
    self: Any,
    friends: list[dict[str, Any]] | None = None,
    groups: list[dict[str, Any]] | None = None,
    members: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, int]:
    """将采集到的人事数据批量持久化到数据库。

    Args:
        friends: get_friend_list 返回的好友列表
        groups: get_group_list 返回的群列表
        members: {group_id: [member_info, ...]} 每个群的成员列表
                 注意：JSON 序列化后 key 变为字符串

    Returns:
        同步结果统计 {"users_synced": int, "groups_synced": int, "memberships_synced": int}
    """
    try:
        # JSON 序列化后 members 的 key 是字符串，需转回 int
        members_int: dict[int, list[dict[str, Any]]] | None = None
        if members:
            members_int = {int(k): v for k, v in members.items()}

        result: dict[str, int] = cast(
            "dict[str, int]",
            _run_async(
                _service.persist_sync_data(
                    friends=friends,
                    groups=groups,
                    members=members_int,
                )
            ),
        )
        return result

    except Exception as exc:
        personnel_sync_total.labels(status="failure").inc()
        logger.error(
            "人事数据持久化失败",
            error=str(exc),
            retry=self.request.retries,
            event_type="personnel.persist_error",
        )
        raise self.retry(exc=exc) from exc


@celery_app.task
def schedule_personnel_sync() -> dict[str, str]:
    """定时任务：通知主进程发起数据采集。

    通过 HTTP 请求 POST /api/internal/personnel/trigger-sync 触发。
    """
    import httpx

    try:
        url = f"http://localhost:{_settings.PORT}/api/internal/personnel/trigger-sync"
        with httpx.Client(timeout=10) as client:
            resp = client.post(url)
            resp.raise_for_status()
        logger.info("定时同步已触发", event_type="personnel.schedule_triggered")
        return {"status": "triggered"}
    except Exception as exc:
        logger.error(
            "定时同步触发失败", error=str(exc), event_type="personnel.schedule_trigger_error"
        )
        return {"status": "error", "error": str(exc)}
