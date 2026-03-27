"""协议层公共工具函数。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.protocol.models.events import MessageEvent

if TYPE_CHECKING:
    from src.core.protocol.models.base import OneBotEvent


def extract_plaintext(event: OneBotEvent) -> str:
    """从消息事件中提取纯文本内容。"""
    if not isinstance(event, MessageEvent):
        return ""
    msg = event.message
    if isinstance(msg, str):
        return msg
    parts: list[str] = []
    for seg in msg:
        if seg.type == "text":
            parts.append(str(seg.data.get("text", "")))
    return "".join(parts).strip()
