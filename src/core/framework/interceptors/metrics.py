"""MetricsInterceptor —— 收集事件处理的 Prometheus 指标。"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from src.core.framework.interceptor import HandlerInterceptor

if TYPE_CHECKING:
    from src.core.framework.context import Context

_CTX_KEY_START_TIME = "_metrics_start_time"

# Prometheus 指标将从 monitoring 模块导入。
# 当前为占位实现，将在第 5 阶段连接。
_event_counter = None
_event_histogram = None
_error_counter = None


class MetricsInterceptor(HandlerInterceptor):
    async def pre_handle(self, ctx: Context) -> bool:
        ctx.set_attribute(_CTX_KEY_START_TIME, time.monotonic())
        return True

    async def post_handle(self, ctx: Context, result: Any) -> None:
        if _event_counter is not None:
            handler = ""
            if ctx.handler_method:
                handler = f"{ctx.handler_method.controller_name}.{ctx.handler_method.method_name}"
            _event_counter.labels(
                event_type=ctx.event.post_type,
                handler=handler,
            ).inc()

    async def after_completion(self, ctx: Context, exc: Exception | None = None) -> None:
        start = ctx.get_attribute(_CTX_KEY_START_TIME)
        if start and _event_histogram is not None:
            duration = time.monotonic() - start
            _event_histogram.observe(duration)

        if exc and _error_counter is not None:
            _error_counter.inc()
