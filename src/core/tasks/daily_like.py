"""每日点赞 Celery 任务 —— 由 RedBeat 每天零点触发，通过 Redis RPC 调用主进程执行点赞。"""

from __future__ import annotations

import structlog

from src.core.rpc.bridge import get_rpc_bridge
from src.core.tasks.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(name="src.core.tasks.daily_like.trigger_daily_like")
def trigger_daily_like() -> dict[str, object]:
    """每日点赞触发任务。

    通过 Redis RPC 调用主进程注册的 request_like handler，
    由主进程借助已有的 WebSocket 连接执行实际点赞流程。
    """
    bridge = get_rpc_bridge()
    resp = bridge.call("request_like", {}, timeout=60.0)

    if resp.success:
        logger.info(
            "每日点赞 RPC 调用成功",
            response_data=resp.data,
            event_type="like.rpc_ok",
        )
        data = resp.data
        return data if isinstance(data, dict) else {}

    logger.error(
        "每日点赞 RPC 调用失败",
        error=resp.error,
        event_type="like.rpc_error",
    )
    raise RuntimeError(f"点赞 RPC 失败: {resp.error}")
