"""打卡 API 路由 —— 内部触发端点，供 Celery Beat 任务回调。"""

from __future__ import annotations

import secrets

import structlog
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from src.core.config import get_settings
from src.core.utils.response import fail, ok

logger = structlog.get_logger()

router = APIRouter(prefix="/checkin", tags=["checkin"])


def _verify_internal_token(request: Request) -> bool:
    """校验内部回调令牌（使用 NAPCAT_ACCESS_TOKEN 复用已有密钥）。"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return False
    token = auth_header.removeprefix("Bearer ")
    expected = get_settings().NAPCAT_ACCESS_TOKEN.get_secret_value()
    # 防止时序攻击
    return secrets.compare_digest(token, expected)


@router.post("/trigger")
async def trigger_checkin(request: Request) -> JSONResponse:
    """触发一轮每日打卡（内部端点，仅供 Celery Beat 回调）。

    使用 NAPCAT_ACCESS_TOKEN 做 Bearer 鉴权，防止外部滥用。
    """
    if not _verify_internal_token(request):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=fail("Unauthorized", data=None),
        )

    checkin_service = request.app.state.checkin_service
    task = checkin_service.request_checkin(source="scheduled")

    if task is None:
        logger.info("打卡任务已在执行，跳过本次 Beat 触发", event_type="checkin.beat_skipped")
        return JSONResponse(content=ok({"triggered": False, "reason": "already_running"}))

    logger.info("打卡任务已由 Beat 回调触发", event_type="checkin.beat_triggered")
    return JSONResponse(content=ok({"triggered": True}))
