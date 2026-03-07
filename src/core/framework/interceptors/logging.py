"""LoggingInterceptor —— 记录事件处理详情。"""

from __future__ import annotations

import time
from typing import Any

import structlog

from src.core.framework.context import Context
from src.core.framework.interceptor import HandlerInterceptor

logger = structlog.get_logger()

_CTX_KEY_START_TIME = "_logging_start_time"


class LoggingInterceptor(HandlerInterceptor):
    async def pre_handle(self, ctx: Context) -> bool:
        ctx.set_attribute(_CTX_KEY_START_TIME, time.monotonic())
        logger.debug(
            "Processing event",
            post_type=ctx.event.post_type,
            user_id=ctx.user_id,
            group_id=ctx.group_id,
            event_type="interceptor.logging.pre",
        )
        return True

    async def after_completion(self, ctx: Context, exc: Exception | None = None) -> None:
        start = ctx.get_attribute(_CTX_KEY_START_TIME)
        duration_ms = round((time.monotonic() - start) * 1000, 2) if start else 0

        handler_name = ""
        if ctx.handler_method:
            handler_name = f"{ctx.handler_method.controller_name}.{ctx.handler_method.method_name}"

        if exc:
            logger.error(
                "Event processing failed",
                handler=handler_name,
                duration_ms=duration_ms,
                error=str(exc),
                event_type="interceptor.logging.error",
            )
        else:
            logger.info(
                "Event processed",
                handler=handler_name,
                duration_ms=duration_ms,
                post_type=ctx.event.post_type,
                event_type="interceptor.logging.done",
            )

