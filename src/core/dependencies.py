"""集中定义 FastAPI Depends 依赖提供者函数。

所有 API 路由通过 ``Depends(get_xxx)`` 获取服务实例，
实例在 ``lifespan()`` 中创建并存入 ``app.state``。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from fastapi import Request, WebSocket  # noqa: TC002

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from src.core.cache.client import CacheClient
    from src.core.framework.scanner import ComponentScanner
    from src.core.protocol.api import BotAPI
    from src.core.ws.connection import ConnectionManager
    from src.core.ws.heartbeat import HeartbeatMonitor
    from src.services.chat import ChatHistoryService
    from src.services.chat_archive import ArchiveService
    from src.services.llm import LLMService
    from src.services.permission import FeaturePermissionService
    from src.services.personnel import PersonnelService
    from src.services.personnel_query import PersonnelQueryService
    from src.services.personnel_sync import SyncCoordinator


@dataclass
class AppState:
    """app.state 的类型化视图，消除 Depends 函数中的 type: ignore。"""

    permission_service: FeaturePermissionService
    conn_mgr: ConnectionManager
    bot_api: BotAPI
    heartbeat: HeartbeatMonitor
    access_token: str
    cache_client: CacheClient
    scanner: ComponentScanner
    llm_service: LLMService
    chat_service: ChatHistoryService
    archive_service: ArchiveService
    personnel_service: PersonnelService
    personnel_query_service: PersonnelQueryService
    sync_coordinator: SyncCoordinator
    event_dispatch_callback: Callable[[Any], Coroutine[Any, Any, None]] | None


def _state(request: Request) -> AppState:
    return cast("AppState", request.app.state)


# ── FastAPI 路由层 Depends 函数 ──


def get_conn_mgr(request: Request) -> ConnectionManager:
    """获取 WebSocket 连接管理器。"""
    return _state(request).conn_mgr


def get_bot_api(request: Request) -> BotAPI:
    """获取 OneBot API 客户端。"""
    return _state(request).bot_api


def get_llm_service(request: Request) -> LLMService:
    """获取 LLM 服务。"""
    return _state(request).llm_service


def get_chat_service(request: Request) -> ChatHistoryService:
    """获取聊天记录服务。"""
    return _state(request).chat_service


def get_archive_service(request: Request) -> ArchiveService:
    """获取归档服务。"""
    return _state(request).archive_service


def get_personnel_service(request: Request) -> PersonnelService:
    """获取用户管理写操作服务（upsert、事件、管理员管理）。"""
    return _state(request).personnel_service


def get_personnel_query_service(request: Request) -> PersonnelQueryService:
    """获取用户管理只读查询服务（列表、详情）。"""
    return _state(request).personnel_query_service


def get_cache_client(request: Request) -> CacheClient:
    """获取 Redis 缓存客户端。"""
    return _state(request).cache_client


def get_permission_service(request: Request) -> FeaturePermissionService:
    """获取功能级权限服务。"""
    return _state(request).permission_service


def get_scanner(request: Request) -> ComponentScanner:
    """获取组件扫描器实例。"""
    return _state(request).scanner


def get_scanner_controllers(request: Request) -> list[dict[str, Any]]:
    """获取已注册控制器元数据列表。"""
    return _state(request).scanner.controllers


def get_sync_coordinator(request: Request) -> SyncCoordinator:
    """获取用户数据同步协调器。"""
    return _state(request).sync_coordinator


# ── WebSocket 端点辅助函数 ──


class WsDeps:
    """从 WebSocket 的 app.state 中提取 WS 依赖的辅助类。"""

    __slots__ = (
        "conn_mgr",
        "bot_api",
        "heartbeat",
        "access_token",
        "event_dispatch_callback",
        "sync_coordinator",
    )

    def __init__(self, websocket: WebSocket) -> None:
        state = cast("AppState", websocket.app.state)
        self.conn_mgr: ConnectionManager = state.conn_mgr
        self.bot_api: BotAPI = state.bot_api
        self.heartbeat: HeartbeatMonitor = state.heartbeat
        self.access_token: str = state.access_token
        self.event_dispatch_callback: Callable[[Any], Coroutine[Any, Any, None]] | None = (
            state.event_dispatch_callback
        )
        self.sync_coordinator: SyncCoordinator = state.sync_coordinator
