"""每日打卡 Celery 任务 —— 由 RedBeat 每天零点触发，通过 Redis RPC 调用主进程执行打卡。"""

from __future__ import annotations

import structlog

from src.core.rpc.bridge import get_rpc_bridge
from src.core.tasks.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(name="src.core.tasks.daily_checkin.trigger_daily_checkin")
def trigger_daily_checkin() -> dict[str, object]:
    """每日打卡触发任务。

    通过 Redis RPC 调用主进程注册的 request_checkin handler，
    由主进程借助已有的 WebSocket 连接执行实际打卡流程。
    """
    bridge = get_rpc_bridge()
    resp = bridge.call("request_checkin", {"source": "scheduled"}, timeout=10.0)

    if resp.success:
        logger.info(
            "每日打卡 RPC 调用成功",
            response_data=resp.data,
            event_type="checkin.rpc_ok",
        )
        data = resp.data
        return data if isinstance(data, dict) else {}

    logger.error(
        "每日打卡 RPC 调用失败",
        error=resp.error,
        event_type="checkin.rpc_error",
    )
    raise RuntimeError(f"打卡 RPC 失败: {resp.error}")
