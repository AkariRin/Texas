"""WebSocket 连接管理器 —— 跟踪活跃的 NapCat 连接。"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from starlette.websockets import WebSocket

logger = structlog.get_logger()


class ConnectionManager:
    """管理一个或多个 NapCat 反向 WebSocket 连接。"""

    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}

    @property
    def connected(self) -> bool:
        return len(self._connections) > 0

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def accept(self, ws: WebSocket, conn_id: str) -> None:
        await ws.accept()
        self._connections[conn_id] = ws
        logger.info(
            "NapCat WebSocket connected",
            conn_id=conn_id,
            total=len(self._connections),
            event_type="ws.connected",
        )

    def disconnect(self, conn_id: str) -> None:
        self._connections.pop(conn_id, None)
        logger.info(
            "NapCat WebSocket disconnected",
            conn_id=conn_id,
            total=len(self._connections),
            event_type="ws.disconnected",
        )

    async def send(self, data: dict[str, Any], conn_id: str | None = None) -> None:
        """向指定连接发送 JSON，若未指定则发送至第一个可用连接。"""
        text = json.dumps(data, ensure_ascii=False)
        if conn_id and conn_id in self._connections:
            await self._connections[conn_id].send_text(text)
            return
        # 发送至第一个可用连接
        for ws in self._connections.values():
            await ws.send_text(text)
            return
        logger.warning("No active WS connections to send to", event_type="ws.no_connection")

    def get_connections(self) -> list[str]:
        return list(self._connections.keys())
