"""应用生命周期 —— 基础设施创建、框架扫描、业务模块编排。

从 main.py 提取，职责：
  - 创建所有基础设施实例（DB 引擎、Redis、WS 管理器等）
  - 执行数据库迁移
  - 驱动 ComponentScanner 扫描处理器与服务
  - 通过 LifecycleOrchestrator 按拓扑序启动/关闭业务模块
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import structlog

from src.core.config import get_settings, validate_settings
from src.core.db.engine import create_engine, create_session_factory
from src.core.db.migration import run_all_startup_migrations
from src.core.framework.dispatcher import EventDispatcher
from src.core.framework.interceptors.logging import LoggingInterceptor
from src.core.framework.interceptors.session import SessionInterceptor
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
from src.core.framework.session.manager import SessionManager
from src.core.logging.setup import setup_logging
from src.core.monitoring.metrics import handlers_registered
from src.core.protocol.api import BotAPI
from src.core.version import get_version
from src.core.ws.connection import ConnectionManager
from src.core.ws.heartbeat import HeartbeatMonitor

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable, Coroutine

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

    from src.core.config import Settings
    from src.services.chat import ChatHistoryService

logger = structlog.get_logger()

# 模块级配置（缓存单例，与 main.py 共享同一实例）
settings = get_settings()


# ─────────────────────── 内部辅助函数 ───────────────────────


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


def _startup_framework(
    settings: Settings,
    *,
    scanner: ComponentScanner,
    composite_mapping: CompositeHandlerMapping,
) -> None:
    """扫描处理器与独立功能组件。"""
    # 扫描 handler 包 + 服务层 + 任务层（收集 @feature 装饰的独立功能）
    scan_packages = list(settings.HANDLER_SCAN_PACKAGES) + ["src.services", "src.tasks"]
    scanner.scan(scan_packages)
    handlers_registered.set(composite_mapping.registered_count)

    logger.info(
        "处理器扫描完成",
        total_handlers=composite_mapping.registered_count,
        controllers=len(scanner.controllers),
        standalone_features=len(scanner.standalone_features),
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


# ─────────────────────── Lifespan ───────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """应用生命周期：启动与关闭逻辑。"""

    # ── 启动 ──
    setup_logging(log_level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
    validate_settings(settings)

    from src.api.logs import install_log_broadcast

    install_log_broadcast()

    logger.info("Texas 正在启动", version=get_version(), event_type="app.starting")

    # ── 基础设施实例（集中在 lifespan 内创建，通过 app.state 统一暴露） ──
    conn_mgr = ConnectionManager()
    heartbeat = HeartbeatMonitor(interval_ms=settings.NAPCAT_HEART_INTERVAL)
    bot_api = BotAPI(connection_manager=conn_mgr)

    from src.core.cache.client import CacheClient

    engine, session_factory = await _startup_database(settings)
    cache_client = CacheClient(url=settings.CACHE_REDIS_URL, default_ttl=settings.CACHE_DEFAULT_TTL)
    persistent_client = CacheClient(url=settings.PERSISTENT_REDIS_URL, default_ttl=0)

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
    session_manager = SessionManager(cache=persistent_client)
    dispatcher = EventDispatcher(
        mapping=composite_mapping,
        interceptors=[
            LoggingInterceptor(),
            SessionInterceptor(session_manager=session_manager),
        ],
    )
    scanner = ComponentScanner(mapping=composite_mapping)

    import src.core.db.migrations.chat  # noqa: F401 — 触发聊天库迁移目标注册

    chat_engine = create_engine(
        settings.CHAT_DATABASE_URL,
        pool_size=settings.CHAT_DB_POOL_SIZE,
        max_overflow=settings.CHAT_DB_MAX_OVERFLOW,
    )

    # 统一执行所有数据库迁移（连接检查 + schema 创建 + upgrade head）
    await run_all_startup_migrations({"main": engine, "chat": chat_engine}, settings)

    # ── RPC 消费者（待 checkin 模块注册 handler 后再 start）──
    from src.core.rpc.consumer import RPCConsumer

    rpc_consumer = RPCConsumer(redis_url=settings.PERSISTENT_REDIS_URL)

    # 框架扫描（含 src.services，触发 @startup / @shutdown 装饰器注册）
    _startup_framework(settings, scanner=scanner, composite_mapping=composite_mapping)
    scanner.register_sessions(session_manager)

    # ── 生命周期编排器（统一管理所有业务模块）──
    from src.core.lifecycle.orchestrator import LifecycleOrchestrator

    orchestrator = LifecycleOrchestrator()
    await orchestrator.startup(
        {
            "settings": settings,
            "conn_mgr": conn_mgr,
            "bot_api": bot_api,
            "session_factory": session_factory,
            "chat_engine": chat_engine,
            "cache_client": cache_client,
            "persistent_client": persistent_client,
            "scanner": scanner,
            "dispatcher": dispatcher,
            "session_manager": session_manager,
            "rpc_consumer": rpc_consumer,
        },
        startup_entries=scanner.startup_entries,
    )
    _infra_keys: frozenset[str] = frozenset(
        {
            "settings",
            "conn_mgr",
            "bot_api",
            "session_factory",
            "chat_engine",
            "cache_client",
            "persistent_client",
            "scanner",
            "dispatcher",
            "session_manager",
            "rpc_consumer",
        }
    )
    orchestrator.populate_app_state(app.state, exclude=_infra_keys)
    orchestrator.populate_dispatcher(dispatcher)

    # 注册基础设施服务到 Dispatcher（业务服务已由 populate_dispatcher 处理）
    from src.core.cache.client import CacheClient as _CacheClientClass

    dispatcher.services[_CacheClientClass] = cache_client
    dispatcher.services[SessionManager] = session_manager

    # 启动 RPC 消费者（checkin 模块已注册 handler）
    await rpc_consumer.start()

    # 构建事件分发回调（chat_service 由 orchestrator 提供）
    event_dispatch_callback = _build_event_dispatch_callback(
        orchestrator.services["chat_service"], dispatcher, bot_api
    )

    # ── app.state（基础设施，业务服务已由 orchestrator.populate_app_state 写入）──
    app.state.conn_mgr = conn_mgr
    app.state.bot_api = bot_api
    app.state.heartbeat = heartbeat
    app.state.access_token = settings.NAPCAT_ACCESS_TOKEN.get_secret_value()
    app.state.cache_client = cache_client
    app.state.persistent_client = persistent_client
    app.state.scanner = scanner
    app.state.session_manager = session_manager
    app.state.rpc_consumer = rpc_consumer
    app.state.event_dispatch_callback = event_dispatch_callback

    logger.debug("已加载后端路由", count=len(app.routes), event_type="app.routes_loaded")
    if settings.LOG_LEVEL.upper() == "DEBUG":
        for route in app.routes:
            path = getattr(route, "path", "")
            methods = sorted(getattr(route, "methods", None) or [])
            name = getattr(route, "name", "")
            logger.debug(
                "路由详情",
                methods=",".join(methods) if methods else "-",
                path=path,
                name=name,
                event_type="app.route",
            )

    logger.info(
        "Texas 已启动，等待 NapCat 连接",
        host=settings.HOST,
        port=settings.PORT,
        event_type="app.started",
    )

    yield

    # ── 关闭 ──
    await orchestrator.shutdown(shutdown_entries=scanner.shutdown_entries)
    await rpc_consumer.stop()
    await session_manager.close()
    await cache_client.close()
    await persistent_client.close()
    await chat_engine.dispose()
    await engine.dispose()
    heartbeat.stop()
    logger.info("Texas 已停止", event_type="app.stopped")
