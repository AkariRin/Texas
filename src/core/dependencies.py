"""集中定义 FastAPI Depends 依赖提供者函数。

所有 API 路由通过 ``Depends(get_xxx)`` 获取服务实例，
实例在 ``lifespan()`` 中创建并存入 ``app.state``。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
    from src.services.personnel_sync import SyncCoordinator


# ── FastAPI 路由层 Depends 函数 ──


def get_conn_mgr(request: Request) -> ConnectionManager:
    """获取 WebSocket 连接管理器。"""
    return request.app.state.conn_mgr  # type: ignore[no-any-return]


def get_bot_api(request: Request) -> BotAPI:
    """获取 OneBot API 客户端。"""
    return request.app.state.bot_api  # type: ignore[no-any-return]


def get_llm_service(request: Request) -> LLMService:
    """获取 LLM 服务。"""
    return request.app.state.llm_service  # type: ignore[no-any-return]


def get_chat_service(request: Request) -> ChatHistoryService:
    """获取聊天记录服务。"""
    return request.app.state.chat_service  # type: ignore[no-any-return]


def get_archive_service(request: Request) -> ArchiveService:
    """获取归档服务。"""
    return request.app.state.archive_service  # type: ignore[no-any-return]


def get_personnel_service(request: Request) -> PersonnelService:
    """获取用户管理服务。"""
    return request.app.state.personnel_service  # type: ignore[no-any-return]


def get_cache_client(request: Request) -> CacheClient:
    """获取 Redis 缓存客户端。"""
    return request.app.state.cache_client  # type: ignore[no-any-return]


def get_permission_service(request: Request) -> FeaturePermissionService:
    """获取功能级权限服务。"""
    return request.app.state.permission_service  # type: ignore[no-any-return]


def get_scanner(request: Request) -> ComponentScanner:
    """获取组件扫描器实例。"""
    return request.app.state.scanner  # type: ignore[no-any-return]


def get_scanner_controllers(request: Request) -> list[dict[str, Any]]:
    """获取已注册控制器元数据列表。"""
    scanner: ComponentScanner = request.app.state.scanner
    return scanner.controllers


def get_sync_coordinator(request: Request) -> SyncCoordinator:
    """获取用户数据同步协调器。"""
    return request.app.state.sync_coordinator  # type: ignore[no-any-return]


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
        state = websocket.app.state
        self.conn_mgr: ConnectionManager = state.conn_mgr
        self.bot_api: BotAPI = state.bot_api
        self.heartbeat: HeartbeatMonitor = state.heartbeat
        self.access_token: str = state.access_token
        self.event_dispatch_callback: Callable[[object], Coroutine[Any, Any, None]] | None = (
            state.event_dispatch_callback
        )
        self.sync_coordinator: SyncCoordinator = state.sync_coordinator
