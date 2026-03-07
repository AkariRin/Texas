"""用于 HTTP 请求指标收集的 FastAPI 中间件。"""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class MetricsMiddleware(BaseHTTPMiddleware):
    """收集基本 HTTP 请求指标（第 5 阶段的占位实现）。"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        # duration = time.monotonic() - start
        # TODO: 按 path、method、status 记录 prometheus 直方图
        return response

