"""NapCat 反向 WebSocket 连接的 WebSocket 服务端端点。"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from src.core.protocol.event import parse_event
from src.core.protocol.models.events import HeartbeatEvent

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from src.core.protocol.api import BotAPI
    from src.core.ws.connection import ConnectionManager
    from src.core.ws.heartbeat import HeartbeatMonitor

logger = structlog.get_logger()

ws_router = APIRouter()

# 这些将在应用启动时通过 set_ws_dependencies() 设置
_conn_mgr: ConnectionManager | None = None
_bot_api: BotAPI | None = None
_heartbeat: HeartbeatMonitor | None = None
_access_token: str = ""


def set_ws_dependencies(
    conn_mgr: ConnectionManager,
    bot_api: BotAPI,
    heartbeat: HeartbeatMonitor,
    access_token: str,
) -> None:
    global _conn_mgr, _bot_api, _heartbeat, _access_token
    _conn_mgr = conn_mgr
    _bot_api = bot_api
    _heartbeat = heartbeat
    _access_token = access_token


def _check_token(token_param: str | None, headers: dict[str, str]) -> bool:
    """从 URL 参数或 Authorization 请求头中验证访问令牌。"""
    if token_param and token_param == _access_token:
        return True
    auth = headers.get("authorization", "")
    return bool(auth.startswith("Bearer ") and auth[7:] == _access_token)


@ws_router.websocket("/onebot")
async def onebot_ws_endpoint(
    ws: WebSocket,
    access_token: str | None = Query(default=None),
) -> None:
    """NapCat 反向 WebSocket 端点。NapCat 以客户端身份连接至此。"""
    assert _conn_mgr is not None
    assert _bot_api is not None
    assert _heartbeat is not None

    # 令牌鉴权
    headers = {k.decode(): v.decode() for k, v in ws.scope.get("headers", [])}
    if not _check_token(access_token, headers):
        logger.critical(
            "WebSocket connection rejected: invalid access token",
            event_type="ws.auth_failed",
        )
        await ws.close(code=4001, reason="Unauthorized")
        return

    conn_id = uuid.uuid4().hex[:12]
    await _conn_mgr.accept(ws, conn_id)
    _heartbeat.start()

    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON from NapCat", raw=raw[:200], event_type="ws.bad_json")
                continue

            # 检查是否为 API 响应（含有 echo 字段且与挂起的调用匹配）
            if _bot_api.handle_response(data):
                continue

            # 解析为事件
            event = parse_event(data)

            # 处理心跳事件
            if isinstance(event, HeartbeatEvent):
                status = event.status.model_dump() if event.status else None
                _heartbeat.record_heartbeat(status)
                continue

            # 分发至框架（在应用初始化期间连接）
            await _dispatch_event(event)

    except WebSocketDisconnect:
        logger.info("NapCat disconnected", conn_id=conn_id, event_type="ws.disconnected")
    except Exception as exc:
        logger.error("WebSocket error", error=str(exc), conn_id=conn_id, event_type="ws.error")
    finally:
        _conn_mgr.disconnect(conn_id)
        if _conn_mgr.connection_count == 0:
            _heartbeat.stop()


# 事件分发回调 —— 在框架初始化后由 app.py 设置

_event_dispatch_callback: Callable[[object], Awaitable[None]] | None = None


def set_event_dispatcher(callback: Callable[[object], Awaitable[None]]) -> None:
    global _event_dispatch_callback
    _event_dispatch_callback = callback


async def _dispatch_event(event: object) -> None:
    callback = _event_dispatch_callback
    if callback is not None:
        await callback(event)
    else:
        logger.debug("No event dispatcher set, ignoring event", event_type="ws.no_dispatcher")
