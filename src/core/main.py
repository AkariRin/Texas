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

from src.api.router import api_router
from src.core.config import get_settings, validate_settings
from src.core.db.engine import create_engine, create_session_factory
from src.core.db.migration import run_all_startup_migrations
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
from src.core.ws.server import ws_router  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable, Coroutine

    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

    from src.core.cache.client import CacheClient
    from src.core.config import Settings
    from src.services.chat import ChatHistoryService
    from src.services.chat_archive import ArchiveService
    from src.services.llm import LLMService
    from src.services.permission import FeaturePermissionService
    from src.services.personnel import PersonnelService
    from src.services.personnel_sync import SyncCoordinator

logger = structlog.get_logger()

# ── 全局实例（模块级单例） ──
settings = get_settings()
conn_mgr = ConnectionManager()
heartbeat = HeartbeatMonitor(interval_ms=settings.NAPCAT_HEART_INTERVAL)
bot_api = BotAPI(connection_manager=conn_mgr)

# ── 构建 HandlerMapping 链 ──
composite_mapping = CompositeHandlerMapping(
    [
        CommandHandlerMapping(),
        RegexHandlerMapping(),
        KeywordHandlerMapping(),
        StartsWithHandlerMapping(),
        EndsWithHandlerMapping(),
        FullMatchHandlerMapping(),
        EventTypeHandlerMapping(),
    ]
)

# ── 核心调度器 & 扫描器 ──
dispatcher = EventDispatcher(
    mapping=composite_mapping,
    interceptors=[LoggingInterceptor(), MetricsInterceptor()],
)
scanner = ComponentScanner(mapping=composite_mapping)


# ─────────────────────── 模块启动函数 ───────────────────────


async def _startup_database(
    settings: Settings,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """主库引擎创建，返回 (engine, session_factory)。迁移由 run_all_startup_migrations 统一执行。"""
    import src.core.db  # noqa: F401 — 触发迁移目标注册

    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
    )
    session_factory = create_session_factory(engine)
    return engine, session_factory


async def _startup_chat(
    chat_engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> tuple[ChatHistoryService, ArchiveService]:
    """聊天库服务初始化（引擎由外部创建，迁移已由 run_all_startup_migrations 完成）。

    返回 (chat_service, archive_service)。
    """
    from src.services.chat import ChatHistoryService
    from src.services.chat_archive import ArchiveService

    chat_session_factory = create_session_factory(chat_engine)
    chat_service = ChatHistoryService(session_factory=chat_session_factory)
    archive_service = ArchiveService(
        chat_session_factory=chat_session_factory,
        main_session_factory=session_factory,
        settings=settings,
    )

    # 启动时确保当月和下月分区存在，防止因分区缺失导致写入失败
    try:
        await archive_service.ensure_partitions()
        logger.info("聊天分区已就绪", event_type="chat.partitions_ensured")
    except Exception:
        logger.exception("启动时分区预创建失败", event_type="chat.partition_ensure_error")

    return chat_service, archive_service


def _startup_personnel(
    session_factory: async_sessionmaker[AsyncSession],
    cache_client: CacheClient,
    settings: Settings,
) -> tuple[PersonnelService, SyncCoordinator]:
    """用户管理模块初始化，返回 (personnel_service, sync_coordinator)。"""
    from src.services.personnel import PersonnelService
    from src.services.personnel_sync import SyncCoordinator

    personnel_service = PersonnelService(
        session_factory=session_factory,
        cache=cache_client,
        settings=settings,
    )

    # 同步协调器（集中管理同步任务生命周期，杜绝重复触发）
    sync_coordinator = SyncCoordinator(
        bot_api=bot_api,
        conn_mgr=conn_mgr,
        personnel_service=personnel_service,
        settings=settings,
    )
    return personnel_service, sync_coordinator


def _startup_llm(
    session_factory: async_sessionmaker[AsyncSession],
    cache_client: CacheClient,
) -> LLMService:
    """LLM 模块初始化，返回 LLMService。"""
    from src.services.llm import LLMService
    from src.services.llm_completion import init_completion

    llm_service = LLMService(session_factory=session_factory, cache=cache_client)
    init_completion(llm_service)
    return llm_service


async def _startup_permission(
    session_factory: async_sessionmaker[AsyncSession],
    cache_client: CacheClient,
    personnel_svc: PersonnelService,
) -> FeaturePermissionService:
    """初始化权限系统：同步功能注册表并注入 dispatcher。"""
    from src.core.framework.permission_checker import FeaturePermissionChecker
    from src.services.permission import FeaturePermissionService

    permission_service = FeaturePermissionService(
        session_factory=session_factory,
        cache=cache_client,
    )
    await permission_service.sync_features(scanner.controllers)

    checker = FeaturePermissionChecker(
        permission_service=permission_service,
        personnel_service=personnel_svc,
    )
    dispatcher.feature_checker = checker
    dispatcher.personnel_service = personnel_svc

    logger.info(
        "权限系统已就绪",
        event_type="permission.ready",
    )
    return permission_service


def _startup_framework(settings: Settings) -> None:
    """扫描处理器。"""
    scan_packages = list(settings.HANDLER_SCAN_PACKAGES)
    scanner.scan(scan_packages)
    handlers_registered.set(composite_mapping.registered_count)

    logger.info(
        "处理器扫描完成",
        total_handlers=composite_mapping.registered_count,
        controllers=len(scanner.controllers),
        event_type="app.scan_complete",
    )


def _build_event_dispatch_callback(
    chat_service: ChatHistoryService,
    dispatcher_instance: EventDispatcher,
    bot_api_instance: BotAPI,
) -> Callable[[Any], Coroutine[Any, Any, None]]:
    """构建事件分发回调（含消息持久化）。"""
    from src.core.protocol.models.events import MessageEvent, MessageSentEvent

    async def _save_chat_message(event: Any) -> None:
        try:
            await chat_service.save_message(event)
        except Exception:
            logger.exception(
                "聊天记录持久化失败（非致命）",
                message_id=getattr(event, "message_id", None),
                event_type="chat.save_error",
            )

    async def _dispatch(event: Any) -> None:
        if isinstance(event, (MessageEvent, MessageSentEvent)):
            asyncio.create_task(_save_chat_message(event))
        await dispatcher_instance.dispatch(event, bot_api_instance)

    return _dispatch


def _register_services_to_dispatcher(
    dispatcher_instance: EventDispatcher,
    *,
    personnel_service: PersonnelService | None = None,
    llm_service: LLMService | None = None,
    cache_client: CacheClient | None = None,
) -> None:
    """将业务服务注册到 EventDispatcher 的服务注册表。

    供 Controller 通过 ctx.get_service() 获取。
    """
    from src.services.personnel import PersonnelService

    if personnel_service is not None:
        dispatcher_instance.services[PersonnelService] = personnel_service

    # 未来可在此处注册更多服务类型:
    # from src.core.llm.service import LLMService
    # if llm_service is not None:
    #     dispatcher_instance.services[LLMService] = llm_service


# ─────────────────────── Lifespan ───────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """应用生命周期：启动与关闭逻辑。"""

    # ── 启动 ──
    setup_logging(log_level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
    validate_settings(settings)

    from src.api.logs import install_log_broadcast

    install_log_broadcast()

    logger.info("Texas 正在启动", version="0.1.0", event_type="app.starting")

    # 基础设施 —— 引擎创建（触发迁移目标注册）
    from src.core.cache.client import CacheClient

    engine, session_factory = await _startup_database(settings)
    cache_client = CacheClient(url=settings.CACHE_REDIS_URL, default_ttl=settings.CACHE_DEFAULT_TTL)

    import src.core.db.chat_migrations  # noqa: F401 — 触发聊天库迁移目标注册

    chat_engine = create_engine(
        settings.CHAT_DATABASE_URL,
        pool_size=settings.CHAT_DB_POOL_SIZE,
        max_overflow=settings.CHAT_DB_MAX_OVERFLOW,
    )

    # 统一执行所有数据库迁移（连接检查 + schema 创建 + upgrade head）
    await run_all_startup_migrations({"main": engine, "chat": chat_engine}, settings)

    # 业务模块（依赖 schema 已就绪）
    personnel_service, sync_coordinator = _startup_personnel(
        session_factory, cache_client, settings
    )
    llm_service = _startup_llm(session_factory, cache_client)
    chat_service, archive_service = await _startup_chat(chat_engine, session_factory, settings)

    # 框架
    _startup_framework(settings)

    # 权限系统（功能同步 + checker 注入）
    permission_service = await _startup_permission(session_factory, cache_client, personnel_service)

    # 将服务注册到 Dispatcher（供 Controller 通过 ctx.get_service() 获取）
    _register_services_to_dispatcher(
        dispatcher,
        personnel_service=personnel_service,
        llm_service=llm_service,
        cache_client=cache_client,
    )

    # 构建事件分发回调
    event_dispatch_callback = _build_event_dispatch_callback(chat_service, dispatcher, bot_api)

    # ── 将所有实例存入 app.state（供 Depends / WsDeps 获取） ──
    app.state.permission_service = permission_service
    app.state.conn_mgr = conn_mgr
    app.state.bot_api = bot_api
    app.state.heartbeat = heartbeat
    app.state.access_token = settings.NAPCAT_ACCESS_TOKEN
    app.state.cache_client = cache_client
    app.state.scanner = scanner
    app.state.llm_service = llm_service
    app.state.chat_service = chat_service
    app.state.archive_service = archive_service
    app.state.personnel_service = personnel_service
    app.state.sync_coordinator = sync_coordinator
    app.state.event_dispatch_callback = event_dispatch_callback

    # 启动用户同步定时调度
    sync_coordinator.start_scheduler()

    # 路由调试
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
    sync_coordinator.stop_scheduler()
    await llm_service.close()
    await cache_client.close()
    await chat_engine.dispose()
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


class _SPAStaticFiles(StaticFiles):
    """静态文件服务子类：忽略非 HTTP 请求（如 WebSocket），避免 AssertionError。"""

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
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
