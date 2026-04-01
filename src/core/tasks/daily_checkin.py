"""每日打卡 Celery 任务 —— 由 RedBeat 每天零点触发，回调主进程执行打卡。"""

from __future__ import annotations

import structlog

from src.core.config import get_settings
from src.core.tasks.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(name="src.core.tasks.daily_checkin.trigger_daily_checkin")
def trigger_daily_checkin() -> dict[str, object]:
    """每日打卡触发任务。

    通过 HTTP 回调主进程内部端点，由主进程借助已有的 WebSocket 连接执行实际打卡。
    主进程地址由 ``INTERNAL_API_BASE_URL`` 配置项指定（默认 http://localhost:8000）。
    """
    import httpx

    settings = get_settings()
    url = f"{settings.INTERNAL_API_BASE_URL}/api/checkin/trigger"
    token = settings.NAPCAT_ACCESS_TOKEN.get_secret_value()

    try:
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,  # 降低超时避免 Celery Worker 长时间阻塞
        )
        resp.raise_for_status()
        data: dict[str, object] = resp.json()
        logger.info(
            "每日打卡 Beat 回调成功",
            status_code=resp.status_code,
            response=data,
            event_type="checkin.beat_callback_ok",
        )
        return data
    except Exception as exc:
        logger.error(
            "每日打卡 Beat 回调失败",
            url=url,
            error=str(exc),
            event_type="checkin.beat_callback_error",
        )
        raise
