"""任务队列 API 端点 —— 查询定时任务与消息队列状态。"""

from __future__ import annotations

import asyncio
import base64
import json
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import APIRouter, Query
from starlette.responses import StreamingResponse

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from celery.app.control import Inspect

from src.core.tasks.celery_app import celery_app
from src.core.utils.response import fail, ok

logger = structlog.get_logger()

router = APIRouter(prefix="/queue", tags=["queue"])

# ── 任务函数路径 → 中文显示名称 ──
TASK_DISPLAY_NAMES: dict[str, str] = {
    "src.core.tasks.chat_archive.archive_chat_history": "聊天记录归档",
    "src.core.tasks.chat_archive.ensure_chat_partitions": "分区预创建",
    "src.core.tasks.daily_checkin.trigger_daily_checkin": "每日打卡",
}


def _display_name(task_path: str) -> str:
    """将任务函数路径翻译为中文显示名称，无匹配时返回原始值。"""
    return TASK_DISPLAY_NAMES.get(task_path, task_path)


# ── 可复用的同步数据收集函数 ──


def _build_scheduled_tasks() -> list[dict[str, Any]]:
    """收集已注册的 Celery Beat 定时任务。"""
    from src.core.tasks.scheduled import celery_app as scheduled_app

    beat_schedule: dict[str, Any] = getattr(scheduled_app.conf, "beat_schedule", {}) or {}
    tasks: list[dict[str, Any]] = []
    for _name, config in beat_schedule.items():
        schedule = config.get("schedule")
        schedule_display = (
            f"每 {int(schedule)} 秒" if isinstance(schedule, (int, float)) else str(schedule)
        )
        options = config.get("options", {})
        tasks.append(
            {
                "name": _display_name(config.get("task", "")),
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
    return tasks


def _build_inspect_data() -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]
]:
    """收集活跃任务、预留任务、Worker 信息（单次 inspect 连接）。"""
    active_tasks: list[dict[str, Any]] = []
    reserved_tasks: list[dict[str, Any]] = []
    workers: list[dict[str, Any]] = []

    try:
        inspect: Inspect = celery_app.control.inspect(timeout=3.0)

        for worker_name, tasks in (inspect.active() or {}).items():
            for task in tasks:
                active_tasks.append(
                    {
                        "worker": worker_name,
                        "id": task.get("id"),
                        "name": _display_name(task.get("name", "")),
                        "args": task.get("args"),
                        "kwargs": task.get("kwargs"),
                        "started": task.get("time_start"),
                        "acknowledged": task.get("acknowledged"),
                    }
                )

        for worker_name, tasks in (inspect.reserved() or {}).items():
            for task in tasks:
                reserved_tasks.append(
                    {
                        "worker": worker_name,
                        "id": task.get("id"),
                        "name": _display_name(task.get("name", "")),
                        "args": task.get("args"),
                        "kwargs": task.get("kwargs"),
                        "acknowledged": task.get("acknowledged"),
                    }
                )

        for worker_name, info in (inspect.stats() or {}).items():
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
    except Exception as exc:
        logger.warning("Celery inspect 失败", error=str(exc), event_type="queue.inspect_error")

    return active_tasks, reserved_tasks, workers


def _build_queue_length() -> dict[str, Any]:
    """获取 Redis Broker 队列长度。"""
    try:
        with celery_app.connection_or_acquire() as conn:
            channel = conn.default_channel
            return {"queue": "celery", "length": channel.client.llen("celery")}
    except Exception as exc:
        logger.warning("获取队列长度失败", error=str(exc), event_type="queue.broker_error")
        return {"queue": "celery", "length": None}


def _parse_pending_tasks(max_count: int = 200) -> list[dict[str, Any]]:
    """从 Redis Broker 队列中读取等待中的任务消息（不消费，只读取）。"""
    pending: list[dict[str, Any]] = []
    try:
        with celery_app.connection_or_acquire() as conn:
            channel = conn.default_channel
            raw_messages = channel.client.lrange("celery", 0, max_count - 1)

            for raw in raw_messages:
                try:
                    msg = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
                    headers = msg.get("headers") or {}
                    body_raw = msg.get("body")
                    body: dict[str, Any] = {}
                    if body_raw:
                        try:
                            body = json.loads(base64.b64decode(body_raw))
                        except ValueError, TypeError:
                            # body_raw 非 base64 编码，尝试直接解析
                            try:
                                body = json.loads(body_raw) if isinstance(body_raw, str) else {}
                            except json.JSONDecodeError:
                                body = {}

                    task_id = headers.get("id") or msg.get("properties", {}).get(
                        "correlation_id", ""
                    )
                    task_name = headers.get("task") or ""
                    task_args = (
                        body[0]
                        if isinstance(body, (list, tuple)) and len(body) > 0
                        else headers.get("argsrepr")
                    )
                    task_kwargs = (
                        body[1]
                        if isinstance(body, (list, tuple)) and len(body) > 1
                        else headers.get("kwargsrepr")
                    )

                    pending.append(
                        {
                            "id": task_id,
                            "name": _display_name(task_name),
                            "args": str(task_args) if task_args else None,
                            "kwargs": str(task_kwargs) if task_kwargs else None,
                        }
                    )
                except Exception as exc:
                    logger.debug(
                        "跳过格式异常的队列消息",
                        error=str(exc),
                        event_type="queue.malformed_message",
                    )
                    continue
    except Exception as exc:
        logger.warning("获取等待任务失败", error=str(exc), event_type="queue.broker_error")

    return pending


# ── REST 端点 ──


@router.get("/scheduled-tasks")
async def get_scheduled_tasks() -> dict[str, Any]:
    """获取已注册的 Celery Beat 定时任务列表。"""
    return ok(_build_scheduled_tasks())


@router.get("/active-tasks")
async def get_active_tasks() -> dict[str, Any]:
    """获取当前正在执行的任务。"""
    try:
        loop = asyncio.get_running_loop()
        active, _, _ = await loop.run_in_executor(None, _build_inspect_data)
        return ok(active)
    except Exception as exc:
        logger.warning("获取活跃任务失败", error=str(exc), event_type="queue.inspect_error")
        return fail("无法连接 Worker", data=[])


@router.get("/reserved-tasks")
async def get_reserved_tasks() -> dict[str, Any]:
    """获取已预取但尚未开始执行的队列消息（reserved）。"""
    try:
        loop = asyncio.get_running_loop()
        _, reserved, _ = await loop.run_in_executor(None, _build_inspect_data)
        return ok(reserved)
    except Exception as exc:
        logger.warning("获取预留任务失败", error=str(exc), event_type="queue.inspect_error")
        return fail("无法连接 Worker", data=[])


@router.get("/workers")
async def get_workers() -> dict[str, Any]:
    """获取在线 Worker 节点信息。"""
    try:
        loop = asyncio.get_running_loop()
        _, _, workers = await loop.run_in_executor(None, _build_inspect_data)
        return ok(workers)
    except Exception as exc:
        logger.warning("获取 Worker 信息失败", error=str(exc), event_type="queue.inspect_error")
        return fail("无法连接 Worker", data=[])


@router.get("/queue-length")
async def get_queue_length() -> dict[str, Any]:
    """获取 Redis Broker 中各队列的消息数量。"""
    loop = asyncio.get_running_loop()
    try:
        data = await loop.run_in_executor(None, _build_queue_length)
        return ok(data)
    except Exception as exc:
        logger.warning("获取队列长度失败", error=str(exc), event_type="queue.broker_error")
        return fail("无法获取队列长度", data={"queue": "celery", "length": None})


@router.get("/pending-tasks")
async def get_pending_tasks() -> dict[str, Any]:
    """获取 Redis Broker 队列中等待被消费的任务。"""
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, _parse_pending_tasks)
        return ok(result)
    except Exception as exc:
        logger.warning("获取等待任务失败", error=str(exc), event_type="queue.broker_error")
        return fail("无法读取队列", data=[])


# ── SSE 实时推送 ──


def _collect_all() -> dict[str, Any]:
    """同步收集全部队列状态数据（在线程池中运行）。"""
    active_tasks, reserved_tasks, workers = _build_inspect_data()
    return {
        "scheduledTasks": _build_scheduled_tasks(),
        "activeTasks": active_tasks,
        "reservedTasks": reserved_tasks,
        "pendingTasks": _parse_pending_tasks(),
        "workers": workers,
        "queueLength": _build_queue_length(),
    }


async def _sse_event_stream(interval: float) -> AsyncGenerator[str]:
    """按固定间隔推送全部队列状态的 SSE 事件流。"""
    loop = asyncio.get_running_loop()
    try:
        while True:
            try:
                data = await loop.run_in_executor(None, _collect_all)
                payload = json.dumps(data, ensure_ascii=False)
                yield f"data: {payload}\n\n"
            except Exception as exc:
                error_payload = json.dumps({"error": str(exc)}, ensure_ascii=False)
                yield f"data: {error_payload}\n\n"
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        return


@router.get("/stream")
async def stream_queue_status(
    interval: float = Query(5.0, ge=1.0, le=60.0, description="推送间隔（秒）"),
) -> StreamingResponse:
    """SSE 端点 —— 实时推送队列状态数据。"""
    return StreamingResponse(
        _sse_event_stream(interval),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
