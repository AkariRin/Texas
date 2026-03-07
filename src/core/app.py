"""FastAPI 应用入口 —— 组装并启动 Texas 框架。"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from prometheus_client import generate_latest
from starlette.responses import Response

from src.api.handlers import set_scanner_provider
from src.api.router import api_router
from src.api.status import set_status_provider
from src.core.config import Settings, validate_settings
from src.core.framework.dispatcher import EventDispatcher
from src.core.framework.interceptors.logging import LoggingInterceptor
from src.core.framework.interceptors.metrics import MetricsInterceptor
from src.core.framework.mapping import (
    CommandHandlerMapping,
    CompositeHandlerMapping,
    EndsWithHandlerMapping,
    EventTypeHandlerMapping,
    FullMatchHandlerMapping,
    KeywordHandlerMapping,
    RegexHandlerMapping,
    StartsWithHandlerMapping,
)
from src.core.framework.scanner import ComponentScanner
from src.core.logging.setup import setup_logging
from src.core.monitoring.metrics import handlers_registered
from src.core.protocol.api import BotAPI
from src.core.ws.connection import ConnectionManager
from src.core.ws.heartbeat import HeartbeatMonitor
from src.core.ws.server import set_event_dispatcher, set_ws_dependencies, ws_router

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = structlog.get_logger()

# ── 全局实例（模块级单例） ──
settings = Settings()
conn_mgr = ConnectionManager()
heartbeat = HeartbeatMonitor(interval_ms=settings.NAPCAT_HEART_INTERVAL)
bot_api = BotAPI(connection_manager=conn_mgr)

# ── 构建 HandlerMapping 链 ──
command_mapping = CommandHandlerMapping()
regex_mapping = RegexHandlerMapping()
keyword_mapping = KeywordHandlerMapping()
startswith_mapping = StartsWithHandlerMapping()
endswith_mapping = EndsWithHandlerMapping()
fullmatch_mapping = FullMatchHandlerMapping()
event_type_mapping = EventTypeHandlerMapping()

composite_mapping = CompositeHandlerMapping(
    [
        command_mapping,
        regex_mapping,
        keyword_mapping,
        startswith_mapping,
        endswith_mapping,
        fullmatch_mapping,
        event_type_mapping,
    ]
)

# ── 拦截器 ──
interceptors = [
    LoggingInterceptor(),
    MetricsInterceptor(),
]

# ── 核心调度器 ──
dispatcher = EventDispatcher(mapping=composite_mapping, interceptors=interceptors)

# ── 组件扫描器 ──
scanner = ComponentScanner(mapping=composite_mapping)

_start_time: float = 0.0


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """应用生命周期：启动与关闭逻辑。"""
    global _start_time

    # ── 启动 ──
    setup_logging(log_level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
    validate_settings(settings)

    logger.info(
        "Starting Texas Bot Framework",
        version="0.1.0",
        event_type="app.starting",
    )

    # 扫描并注册处理器
    scanner.scan(settings.HANDLER_SCAN_PACKAGES)
    handlers_registered.set(composite_mapping.registered_count)

    logger.info(
        "Handler scanning complete",
        total_handlers=composite_mapping.registered_count,
        controllers=len(scanner.controllers),
        event_type="app.scan_complete",
    )

    # 注入 WebSocket 依赖
    set_ws_dependencies(conn_mgr, bot_api, heartbeat, settings.NAPCAT_ACCESS_TOKEN)

    # 将事件调度器绑定到 WS 服务端
    async def _dispatch(event: Any) -> None:
        await dispatcher.dispatch(event, bot_api)

    set_event_dispatcher(_dispatch)

    # 注入管理 API 提供者
    set_status_provider(
        lambda: {
            "code": 0,
            "data": {
                "status": "running",
                "ws_connected": conn_mgr.connected,
                "ws_connections": conn_mgr.connection_count,
                "handlers_registered": composite_mapping.registered_count,
                "controllers": len(scanner.controllers),
                "uptime_seconds": round(time.time() - _start_time, 1),
            },
            "message": "ok",
        }
    )
    set_scanner_provider(lambda: scanner.controllers)

    _start_time = time.time()

    logger.info(
        "Texas Bot Framework started — waiting for NapCat connections on /ws/onebot",
        host=settings.HOST,
        port=settings.PORT,
        event_type="app.started",
    )

    yield

    # ── 关闭 ──
    heartbeat.stop()
    logger.info("Texas Bot Framework stopped", event_type="app.stopped")


# ── 创建 FastAPI 应用 ──

app = FastAPI(
    title="Texas Bot Framework",
    version="0.1.0",
    description="基于 NapCat / OneBot 11 的 QQ 机器人框架",
    lifespan=lifespan,
)

# 1. 管理 API (/api/v1)
app.include_router(api_router, prefix="/api/v1")

# 2. NapCat WebSocket 端点 (/ws)
app.include_router(ws_router, prefix="/ws")


# 3. 系统端点
@app.get("/health")
async def health_check() -> dict[str, Any]:
    """就绪检查。"""
    return {
        "status": "healthy",
        "ws_connected": conn_mgr.connected,
    }


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus 指标端点。"""
    return Response(content=generate_latest(), media_type="text/plain; charset=utf-8")


# 4. 挂载前端静态文件（必须放最后，以避免覆盖 API 路由）
frontend_dist = Path(settings.FRONTEND_DIST_DIR)
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
