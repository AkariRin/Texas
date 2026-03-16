"""WebSocket 连接管理器 —— 跟踪唯一的 NapCat 连接（一对一架构）。"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from starlette.websockets import WebSocket

logger = structlog.get_logger()


class ConnectionManager:
    """管理唯一的 NapCat 反向 WebSocket 连接（一对一架构）。"""

    def __init__(self) -> None:
        self._ws: WebSocket | None = None

    @property
    def connected(self) -> bool:
        return self._ws is not None

    async def accept(self, ws: WebSocket) -> None:
        self._ws = ws  # 先占位，防止并发连接通过 connected 检查
        try:
            await ws.accept()
        except Exception:
            self._ws = None
            raise
        logger.info("NapCat WebSocket 已连接", event_type="ws.connected")

    def disconnect(self) -> None:
        self._ws = None
        logger.info("NapCat WebSocket 已断开", event_type="ws.disconnected")

    async def send(self, data: dict[str, Any]) -> None:
        """向当前连接发送 JSON 数据。"""
        if self._ws is None:
            logger.warning("当前无活跃的 WS 连接可供发送", event_type="ws.no_connection")
            return
        text = json.dumps(data, ensure_ascii=False)
        await self._ws.send_text(text)
