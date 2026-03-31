"""Session 鉴权 ASGI 中间件 —— 保护所有 /api/ 路由（白名单除外）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from src.core.utils.response import fail

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

logger = structlog.get_logger()

# 无需鉴权的路径（精确匹配）
_WHITELIST: frozenset[str] = frozenset(
    [
        "/health",
        "/metrics",
        "/api/auth/login",
        "/api/auth/logout",
        "/api/auth/totp/verify",
        "/api/auth/webauthn/login/begin",
        "/api/auth/webauthn/login/finish",
    ]
)


def _is_whitelisted(path: str) -> bool:
    """判断请求路径是否在白名单（精确匹配或 /ws 前缀匹配）。"""
    if path in _WHITELIST:
        return True
    # /ws 开头的 WebSocket 路由
    return bool(path.startswith("/ws"))


class SessionAuthMiddleware(BaseHTTPMiddleware):
    """验证 session_id cookie，未通过则返回 401。

    白名单路径直接放行，其余路径必须携带有效 Session。
    Session 存储于 Redis，由 AuthService 管理。
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        if _is_whitelisted(path):
            return await call_next(request)

        # 从 cookie 读取 session_id
        session_id = request.cookies.get("session_id")
        if not session_id:
            return JSONResponse(
                status_code=401,
                content=fail("未登录或 Session 已过期", code=401),
            )

        # 验证 Session（AuthService 已挂载到 app.state）
        auth_service = getattr(request.app.state, "auth_service", None)
        if auth_service is None:
            logger.error("AuthService 未初始化", event_type="auth.middleware_error")
            return JSONResponse(status_code=500, content=fail("服务器内部错误"))

        if not await auth_service.validate_session(session_id):
            return JSONResponse(
                status_code=401,
                content=fail("Session 无效或已过期，请重新登录", code=401),
            )

        return await call_next(request)
