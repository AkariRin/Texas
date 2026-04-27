"""日志广播器 —— 将日志事件推送到所有 SSE 订阅者（框架基础设施层）。"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime

from src.core.utils import SHANGHAI_TZ

# ANSI 转义序列正则（覆盖 CSI 序列与 OSC 序列）
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\x1b][^\x07]*\x07|\x1b[()][AB012]")

# 广播机制：每个 SSE 客户端对应一个 asyncio.Queue
subscribers: set[asyncio.Queue[str]] = set()
subscribers_lock: asyncio.Lock = asyncio.Lock()


def _strip_ansi(text: str) -> str:
    """移除字符串中所有 ANSI 转义序列。"""
    return _ANSI_RE.sub("", text)


class BroadcastHandler(logging.Handler):
    """将日志记录广播到所有 SSE 订阅者。"""

    def emit(self, record: logging.LogRecord) -> None:
        if not subscribers:
            return

        raw_message = _strip_ansi(record.getMessage()).strip()
        entry = {
            "timestamp": self._format_time(record),
            "level": record.levelname,
            "logger": record.name,
            "message": raw_message,
        }

        if hasattr(record, "positional_fields"):
            entry.update(record.positional_fields)

        line = json.dumps(entry, ensure_ascii=False)
        snapshot = list(subscribers)
        dead: list[asyncio.Queue[str]] = []
        for q in snapshot:
            try:
                q.put_nowait(line)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            subscribers.discard(q)

    @staticmethod
    def _format_time(record: logging.LogRecord) -> str:
        dt = datetime.fromtimestamp(record.created, tz=SHANGHAI_TZ)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(record.msecs):03d}+08:00"


_handler = BroadcastHandler()
_handler.setLevel(logging.DEBUG)


def install_log_broadcast() -> None:
    """将广播 handler 注入根 logger，应在 setup_logging 之后调用。"""
    root = logging.getLogger()
    if _handler not in root.handlers:
        root.addHandler(_handler)
