"""用于 HTTP 请求指标收集的 FastAPI 中间件。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response


class MetricsMiddleware(BaseHTTPMiddleware):
    """收集基本 HTTP 请求指标（第 5 阶段的占位实现）。"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        return await call_next(request)
