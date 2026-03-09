"""任务队列 API 端点 —— 查询定时任务与消息队列状态。"""

from __future__ import annotations

from typing import Any

import structlog
from celery.app.control import Inspect
from fastapi import APIRouter

from src.core.tasks.celery_app import celery_app

logger = structlog.get_logger()

router = APIRouter(prefix="/queue", tags=["queue"])


@router.get("/scheduled-tasks")
async def get_scheduled_tasks() -> dict[str, Any]:
    """获取已注册的 Celery Beat 定时任务列表。"""
    # 从 celery_app.conf.beat_schedule 导入（含运行时注册的任务）
    from src.core.tasks.scheduled import celery_app as scheduled_app

    beat_schedule: dict[str, Any] = getattr(scheduled_app.conf, "beat_schedule", {}) or {}

    tasks: list[dict[str, Any]] = []
    for name, config in beat_schedule.items():
        schedule = config.get("schedule")
        # schedule 可能是 int/float（秒）或 crontab 等
        if isinstance(schedule, (int, float)):
            schedule_display = f"每 {int(schedule)} 秒"
        else:
            schedule_display = str(schedule)

        options = config.get("options", {})
        tasks.append(
            {
                "name": name,
                "task": config.get("task", ""),
                "schedule": schedule_display,
                "schedule_raw": schedule if isinstance(schedule, (int, float)) else None,
                "args": config.get("args"),
                "kwargs": config.get("kwargs"),
                "options": {
                    "expires": options.get("expires"),
                    "queue": options.get("queue"),
                },
                "enabled": config.get("enabled", True),
            }
        )

    return {"code": 0, "data": tasks, "message": "ok"}


@router.get("/active-tasks")
async def get_active_tasks() -> dict[str, Any]:
    """获取当前正在执行的任务。"""
    try:
        inspect: Inspect = celery_app.control.inspect(timeout=3.0)
        active = inspect.active() or {}

        result: list[dict[str, Any]] = []
        for worker_name, tasks in active.items():
            for task in tasks:
                result.append(
                    {
                        "worker": worker_name,
                        "id": task.get("id"),
                        "name": task.get("name"),
                        "args": task.get("args"),
                        "kwargs": task.get("kwargs"),
                        "started": task.get("time_start"),
                        "acknowledged": task.get("acknowledged"),
                    }
                )

        return {"code": 0, "data": result, "message": "ok"}
    except Exception as exc:
        logger.warning("获取活跃任务失败", error=str(exc), event_type="queue.inspect_error")
        return {"code": -1, "data": [], "message": f"无法连接 Worker: {exc}"}


@router.get("/reserved-tasks")
async def get_reserved_tasks() -> dict[str, Any]:
    """获取已预取但尚未开始执行的队列消息（reserved）。"""
    try:
        inspect: Inspect = celery_app.control.inspect(timeout=3.0)
        reserved = inspect.reserved() or {}

        result: list[dict[str, Any]] = []
        for worker_name, tasks in reserved.items():
            for task in tasks:
                result.append(
                    {
                        "worker": worker_name,
                        "id": task.get("id"),
                        "name": task.get("name"),
                        "args": task.get("args"),
                        "kwargs": task.get("kwargs"),
                        "acknowledged": task.get("acknowledged"),
                    }
                )

        return {"code": 0, "data": result, "message": "ok"}
    except Exception as exc:
        logger.warning("获取预留任务失败", error=str(exc), event_type="queue.inspect_error")
        return {"code": -1, "data": [], "message": f"无法连接 Worker: {exc}"}


@router.get("/workers")
async def get_workers() -> dict[str, Any]:
    """获取在线 Worker 节点信息。"""
    try:
        inspect: Inspect = celery_app.control.inspect(timeout=3.0)
        stats = inspect.stats() or {}

        workers: list[dict[str, Any]] = []
        for worker_name, info in stats.items():
            workers.append(
                {
                    "name": worker_name,
                    "concurrency": info.get("pool", {}).get("max-concurrency"),
                    "broker": info.get("broker", {}).get("transport"),
                    "prefetch_count": info.get("prefetch_count"),
                    "pid": info.get("pid"),
                    "uptime": info.get("clock"),
                }
            )

        return {"code": 0, "data": workers, "message": "ok"}
    except Exception as exc:
        logger.warning("获取 Worker 信息失败", error=str(exc), event_type="queue.inspect_error")
        return {"code": -1, "data": [], "message": f"无法连接 Worker: {exc}"}


@router.get("/queue-length")
async def get_queue_length() -> dict[str, Any]:
    """获取 Redis Broker 中各队列的消息数量。"""
    try:
        # 使用 celery 内置方法获取队列长度
        with celery_app.connection_or_acquire() as conn:
            channel = conn.default_channel
            # 默认队列名为 celery
            queue_name = "celery"
            queue_length = channel.client.llen(queue_name)

        return {
            "code": 0,
            "data": {"queue": queue_name, "length": queue_length},
            "message": "ok",
        }
    except Exception as exc:
        logger.warning("获取队列长度失败", error=str(exc), event_type="queue.broker_error")
        return {"code": -1, "data": {"queue": "celery", "length": None}, "message": str(exc)}

