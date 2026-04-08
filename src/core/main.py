"""FastAPI 应用入口 —— 组装并启动 Texas 框架。

开发环境运行: python -m src.core.main
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from prometheus_client import generate_latest
from starlette.requests import Request  # noqa: TC002
from starlette.responses import Response

from src.api.router import api_router
from src.core.config import get_settings
from src.core.exception import register_exception_handlers
from src.core.logging.setup import _bootstrap_root_logging
from src.core.version import get_description, get_version

# 尽早初始化根 logger，确保 structlog 管道就绪
_bootstrap_root_logging()
from src.core.lifespan import lifespan  # noqa: E402
from src.core.ws.server import ws_router  # noqa: E402

if TYPE_CHECKING:
    from starlette.types import Receive, Scope, Send

# ── 应用配置（只读，安全用作模块级常量） ──
settings = get_settings()

# ── 创建 FastAPI 应用 ──

app = FastAPI(
    title="Texas",
    version=get_version(),
    description=get_description(),
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

register_exception_handlers(app)

# 1. 管理 API (/api)
app.include_router(api_router, prefix="/api")

# 2. NapCat WebSocket 端点 (/ws)
app.include_router(ws_router, prefix="/ws")


# 3. 系统端点
@app.get("/health")
async def health_check(request: Request) -> dict[str, Any]:
    """就绪检查。"""
    return {
        "status": "healthy",
        "ws_connected": request.app.state.conn_mgr.connected,
    }


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus 指标端点。"""
    return Response(content=generate_latest(), media_type="text/plain; charset=utf-8")


# 4. 挂载前端静态文件（必须放最后，以避免覆盖 API 路由）


class _SPAStaticFiles(StaticFiles):
    """静态文件服务子类：忽略非 HTTP 请求（如 WebSocket），避免 AssertionError。"""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            # 正确拒绝 WebSocket 连接，防止 StaticFiles 的 assert 崩溃
            if scope["type"] == "websocket":
                await receive()  # websocket.connect
                await send({"type": "websocket.close", "code": 1000})
            return
        await super().__call__(scope, receive, send)


frontend_dist = Path(settings.FRONTEND_DIST_DIR)
if frontend_dist.exists():
    app.mount("/", _SPAStaticFiles(directory=frontend_dist, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.core.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        reload_dirs=["src"],
    )
