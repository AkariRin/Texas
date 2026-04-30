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
    scan_packages = (
        settings.HANDLER_SCAN_PACKAGES
        + settings.SERVICE_SCAN_PACKAGES
        + settings.TASK_SCAN_PACKAGES
    )
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
    chat_service: Any,
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

    from src.core.logging.broadcast import install_log_broadcast

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

    # 统一执行主库迁移（聊天库迁移由平台组件初始化块负责）
    await run_all_startup_migrations({"main": engine}, settings)

    # ── RPC 消费者（待 checkin 模块注册 handler 后再 start）──
    from src.core.rpc.consumer import RPCConsumer

    rpc_consumer = RPCConsumer(redis_url=settings.PERSISTENT_REDIS_URL)

    # 框架扫描（含 src.services，触发 @startup / @shutdown 装饰器注册）
    _startup_framework(settings, scanner=scanner, composite_mapping=composite_mapping)
    scanner.register_sessions(session_manager)

    # ── 平台组件直接初始化（替代 @startup 动态注册）──

    # 1. LLM（仅依赖 session_factory 和 cache_client）
    from src.core.llm.main import LLMService as _LLMService

    llm_svc = _LLMService(session_factory=session_factory, cache=cache_client)

    # 2. 人员管理
    from src.core.personnel.events import PersonnelEventService as _PersonnelEventService
    from src.core.personnel.events import register_event_handlers as _register_event_handlers
    from src.core.personnel.main import PersonnelService as _PersonnelService
    from src.core.personnel.query import PersonnelQueryService as _PersonnelQueryService
    from src.core.personnel.sync import PersonnelSyncSettings as _PersonnelSyncSettings
    from src.core.personnel.sync import SyncCoordinator as _SyncCoordinator

    _sync_settings = _PersonnelSyncSettings()
    personnel_svc = _PersonnelService(
        session_factory=session_factory,
        cache=cache_client,
        persistent=persistent_client,
        settings=_sync_settings,
    )
    personnel_event_svc = _PersonnelEventService(
        session_factory=session_factory,
        cache=cache_client,
    )
    personnel_query_svc = _PersonnelQueryService(
        session_factory=session_factory,
        cache=cache_client,
    )
    sync_coordinator = _SyncCoordinator(
        bot_api=bot_api,
        conn_mgr=conn_mgr,
        personnel_service=personnel_svc,
        settings=_sync_settings,
    )
    sync_coordinator.start_scheduler()
    _register_event_handlers(composite_mapping, personnel_event_svc)

    # 3. 权限（依赖 scanner.feature_registry 和 personnel_service，须在扫描后初始化）
    from src.core.permission.checker import FeaturePermissionChecker as _FeaturePermissionChecker
    from src.core.permission.main import FeaturePermissionService as _FeaturePermissionService
    from src.core.registries.permission_registry import PermissionRegistry as _PermissionRegistry

    permission_svc = _FeaturePermissionService(
        session_factory=session_factory,
        cache=cache_client,
        registry=scanner.feature_registry,
    )
    await permission_svc.sync_permissions()
    _perm_registry = _PermissionRegistry.from_feature_registry(scanner.feature_registry)
    feature_checker = _FeaturePermissionChecker(
        permission_service=permission_svc,
        personnel_service=personnel_svc,
        perm_registry=_perm_registry,
    )
    personnel_event_svc.configure_permission_service(permission_svc)
    dispatcher._feature_checker = feature_checker

    # 4. 聊天记录（独立 chat DB engine）
    from src.core.chat.archive import ArchiveService as _ArchiveService
    from src.core.chat.exporter import ChatArchiveSettings as _ChatArchiveSettings
    from src.core.chat.main import ChatDatabaseSettings as _ChatDatabaseSettings
    from src.core.chat.main import ChatHistoryService as _ChatHistoryService
    from src.core.chat.s3 import S3Settings as _S3Settings

    _chat_cfg = _ChatDatabaseSettings()
    chat_engine = create_engine(
        _chat_cfg.CHAT_DATABASE_URL,
        pool_size=_chat_cfg.CHAT_DB_POOL_SIZE,
        max_overflow=_chat_cfg.CHAT_DB_MAX_OVERFLOW,
    )
    await run_all_startup_migrations({"chat": chat_engine}, settings)
    chat_session_factory = create_session_factory(chat_engine)
    chat_svc = _ChatHistoryService(session_factory=chat_session_factory)
    archive_svc = _ArchiveService(
        chat_session_factory=chat_session_factory,
        main_session_factory=session_factory,
        archive_settings=_ChatArchiveSettings(),
        s3_settings=_S3Settings(),
    )
    try:
        await archive_svc.ensure_partitions()
        logger.info("聊天分区已就绪", event_type="chat.partitions_ensured")
    except Exception:
        logger.exception("启动时分区预创建失败", event_type="chat.partition_ensure_error")

    # ── 生命周期编排器（统一管理所有业务模块）──
    from src.core.lifecycle.orchestrator import LifecycleOrchestrator

    orchestrator = LifecycleOrchestrator()
    await orchestrator.startup(
        {
            "conn_mgr": conn_mgr,
            "bot_api": bot_api,
            "session_factory": session_factory,
            "cache_client": cache_client,
            "persistent_client": persistent_client,
            "scanner": scanner,
            "dispatcher": dispatcher,
            "session_manager": session_manager,
            "rpc_consumer": rpc_consumer,
            # 平台组件（供业务 @startup requires 引用）
            "permission_service": permission_svc,
            "feature_checker": feature_checker,
            "personnel_service": personnel_svc,
            "personnel_event_service": personnel_event_svc,
            "personnel_query_service": personnel_query_svc,
            "chat_service": chat_svc,
            "archive_service": archive_svc,
            "llm_service": llm_svc,
            "sync_coordinator": sync_coordinator,
        },
        startup_entries=scanner.startup_entries,
    )
    _infra_keys: frozenset[str] = frozenset(
        {
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
            # 平台组件（由 lifespan 直接写入 app.state，不经由 orchestrator.populate_app_state）
            "permission_service",
            "feature_checker",
            "personnel_service",
            "personnel_event_service",
            "personnel_query_service",
            "chat_service",
            "archive_service",
            "llm_service",
            "sync_coordinator",
        }
    )
    orchestrator.populate_app_state(app.state, exclude=_infra_keys)
    orchestrator.populate_dispatcher(dispatcher)
    service_registry = orchestrator.build_registry()
    app.state.service_registry = service_registry

    # 注册基础设施服务到 Dispatcher（业务服务已由 populate_dispatcher 处理）
    from src.core.cache.client import CacheClient as _CacheClientClass

    dispatcher.services[_CacheClientClass] = cache_client
    dispatcher.services[SessionManager] = session_manager

    # 启动 RPC 消费者（checkin 模块已注册 handler）
    await rpc_consumer.start()

    # 构建事件分发回调
    _chat_svc = chat_svc
    event_dispatch_callback = _build_event_dispatch_callback(_chat_svc, dispatcher, bot_api)

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
    # 平台组件服务
    app.state.permission_service = permission_svc
    app.state.feature_checker = feature_checker
    app.state.personnel_service = personnel_svc
    app.state.personnel_event_service = personnel_event_svc
    app.state.personnel_query_service = personnel_query_svc
    app.state.chat_service = chat_svc
    app.state.archive_service = archive_svc
    app.state.llm_service = llm_svc
    app.state.sync_coordinator = sync_coordinator
    app.state.chat_engine = chat_engine

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
    # 平台组件关闭（按初始化逆序）
    sync_coordinator.stop_scheduler()
    await llm_svc.close()
    await chat_engine.dispose()
    await orchestrator.shutdown(shutdown_entries=scanner.shutdown_entries)
    await rpc_consumer.stop()
    await session_manager.close()
    await cache_client.close()
    await persistent_client.close()
    await engine.dispose()
    heartbeat.stop()
    logger.info("Texas 已停止", event_type="app.stopped")
