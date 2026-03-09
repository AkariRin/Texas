"""FastAPI 应用入口 —— 组装并启动 Texas 框架。

开发环境运行: python -m src.core.main
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from prometheus_client import generate_latest
from starlette.responses import Response

from src.api.bot import set_bot_providers
from src.api.handlers import set_scanner_provider
from src.api.router import api_router
from src.core.config import Settings, validate_settings
from src.core.db.engine import create_engine as create_db_engine
from src.core.db.migration import run_startup_db_check
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
from src.core.logging.setup import _bootstrap_root_logging, setup_logging

# 尽早初始化根 logger，确保 structlog 管道就绪（uvicorn 保留其自身日志格式）
_bootstrap_root_logging()
from src.core.monitoring.metrics import handlers_registered  # noqa: E402
from src.core.protocol.api import BotAPI  # noqa: E402
from src.core.ws.connection import ConnectionManager  # noqa: E402
from src.core.ws.heartbeat import HeartbeatMonitor  # noqa: E402
from src.core.ws.server import (  # noqa: E402
    set_event_dispatcher,
    set_personnel_sync_callback,
    set_ws_dependencies,
    ws_router,
)

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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """应用生命周期：启动与关闭逻辑。"""

    # ── 启动 ──
    setup_logging(log_level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
    validate_settings(settings)

    # 安装日志 SSE 广播 handler
    from src.api.logs import install_log_broadcast

    install_log_broadcast()

    logger.info(
        "Texas 正在启动",
        version="0.1.0",
        event_type="app.starting",
    )

    # 数据库连接检查 & Alembic 迁移管理
    engine = create_db_engine(settings)
    await run_startup_db_check(engine, settings)

    # ── 人事管理模块初始化 ──
    from src.core.cache.client import CacheClient
    from src.core.db.engine import create_session_factory
    from src.core.monitoring.metrics import personnel_api_errors
    from src.core.personnel.api import set_personnel_api_deps
    from src.core.personnel.handler import set_personnel_service
    from src.core.personnel.service import PersonnelService

    session_factory = create_session_factory(engine)
    cache_client = CacheClient(
        url=settings.CACHE_REDIS_URL,
        default_ttl=settings.CACHE_DEFAULT_TTL,
    )
    personnel_service = PersonnelService(
        session_factory=session_factory,
        cache=cache_client,
        settings=settings,
    )

    # 注入人事管理服务到增量事件处理器
    set_personnel_service(personnel_service)

    # 扫描并注册处理器（包含 src.core.personnel 中的 PersonnelEventHandler）
    scan_packages = list(settings.HANDLER_SCAN_PACKAGES)
    if "src.core.personnel" not in scan_packages:
        scan_packages.append("src.core.personnel")
    scanner.scan(scan_packages)
    handlers_registered.set(composite_mapping.registered_count)

    logger.info(
        "处理器扫描完成",
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
    set_scanner_provider(lambda: scanner.controllers)
    set_bot_providers(conn_mgr, bot_api)

    # ── 人事管理：数据采集编排（主进程采集 + Celery 写入） ──
    async def _do_personnel_sync() -> None:
        """全量同步人事数据（主进程采集，Celery 写入）。"""
        await asyncio.sleep(settings.PERSONNEL_SYNC_INITIAL_DELAY)

        if not conn_mgr.connected:
            logger.warning("连接已断开，取消人事同步", event_type="personnel.sync_aborted")
            return

        logger.info("开始人事数据同步", event_type="personnel.sync_start")

        try:
            # 1. 获取好友列表
            friends_resp = await bot_api.get_friend_list()
            friends_data = friends_resp.data if friends_resp.ok else None

            # 2. 获取群列表
            groups_resp = await bot_api.get_group_list()
            groups_data = groups_resp.data if groups_resp.ok else None

            # 3. 逐群获取成员列表
            members_data: dict[int, list[Any]] = {}
            if groups_data and isinstance(groups_data, list):
                for group in groups_data:
                    if not conn_mgr.connected:
                        logger.warning("同步中途连接断开", event_type="personnel.sync_interrupted")
                        break

                    group_id = group.get("group_id") if isinstance(group, dict) else None
                    if not group_id:
                        continue

                    try:
                        member_resp = await bot_api.get_group_member_list(int(group_id))
                        if member_resp.ok and isinstance(member_resp.data, list):
                            members_data[int(group_id)] = member_resp.data
                    except Exception as exc:
                        personnel_api_errors.labels(action="get_group_member_list").inc()
                        logger.warning(
                            "获取群成员列表失败",
                            group_id=group_id,
                            error=str(exc),
                            event_type="personnel.api_error",
                        )

                    await asyncio.sleep(settings.PERSONNEL_SYNC_API_DELAY)

            # 4. 提交 Celery 写入任务
            from src.core.tasks.personnel import persist_personnel_data

            # 将 members_data 的 key 转为字符串以兼容 JSON 序列化
            members_serializable = {str(k): v for k, v in members_data.items()}
            persist_personnel_data.delay(
                friends=friends_data,
                groups=groups_data,
                members=members_serializable,
            )

            logger.info(
                "人事数据采集完成，已提交 Celery 写入任务",
                friends_count=len(friends_data) if friends_data else 0,
                groups_count=len(groups_data) if groups_data else 0,
                members_groups=len(members_data),
                event_type="personnel.sync_submitted",
            )

        except Exception as exc:
            logger.error(
                "人事数据同步失败",
                error=str(exc),
                event_type="personnel.sync_error",
            )

    # 注入同步回调到 WS 服务端和人事管理 API
    set_personnel_sync_callback(_do_personnel_sync)
    set_personnel_api_deps(personnel_service, _do_personnel_sync)

    # 以 debug 等级逐行打印所有已加载的路由
    all_routes = list(app.routes)
    logger.debug(f"已加载 {len(all_routes)} 个后端路由", event_type="app.routes_loaded")
    for route in all_routes:
        path = getattr(route, "path", "")
        methods = sorted(getattr(route, "methods", None) or [])
        name = getattr(route, "name", "")
        methods_str = ",".join(methods) if methods else "-"
        logger.debug(f":: {methods_str:<12} {path}  ({name})", event_type="app.route")

    logger.info(
        "Texas 已启动，等待 NapCat 连接",
        host=settings.HOST,
        port=settings.PORT,
        event_type="app.started",
    )

    yield

    # ── 关闭 ──
    await cache_client.close()
    await engine.dispose()
    heartbeat.stop()
    logger.info("Texas 已停止", event_type="app.stopped")


# ── 创建 FastAPI 应用 ──

_docs_url = None if settings.is_production else "/docs"
_redoc_url = None if settings.is_production else "/redoc"
_openapi_url = None if settings.is_production else "/openapi.json"

app = FastAPI(
    title="Texas",
    version="0.1.0",
    description="基于 NapCat / OneBot 11 的 QQ 机器人框架",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
)

# 1. 管理 API (/api/v1)
app.include_router(api_router, prefix="/api")

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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.core.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        reload_dirs=["src"],
    )
