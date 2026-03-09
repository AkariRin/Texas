"""日志 SSE 端点 —— 实时推送应用日志到前端。"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from fastapi import APIRouter, Query
from starlette.responses import StreamingResponse

router = APIRouter()

# ANSI 转义序列正则（覆盖 CSI 序列与 OSC 序列）
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\x1b][^\x07]*\x07|\x1b[()][AB012]")

# ── 广播机制：每个 SSE 客户端对应一个 asyncio.Queue ──
_subscribers: set[asyncio.Queue[str]] = set()


def _strip_ansi(text: str) -> str:
    """移除字符串中所有 ANSI 转义序列。"""
    return _ANSI_RE.sub("", text)


class _BroadcastHandler(logging.Handler):
    """将日志记录广播到所有 SSE 订阅者。"""

    def emit(self, record: logging.LogRecord) -> None:
        if not _subscribers:
            return

        # 获取干净的消息文本（去除 ANSI 转义码）
        raw_message = _strip_ansi(record.getMessage()).strip()

        entry = {
            "timestamp": self.format_time(record),
            "level": record.levelname,
            "logger": record.name,
            "message": raw_message,
        }

        # 附加 structlog 绑定字段（如 event_type）
        if hasattr(record, "positional_fields"):
            entry.update(record.positional_fields)  # type: ignore[arg-type]

        line = json.dumps(entry, ensure_ascii=False)
        dead: list[asyncio.Queue[str]] = []
        for q in _subscribers:
            try:
                q.put_nowait(line)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            _subscribers.discard(q)

    @staticmethod
    def format_time(record: logging.LogRecord) -> str:
        from datetime import datetime, timezone

        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(record.msecs):03d}Z"


# ── 安装 handler（模块加载时注册到根 logger） ──
_handler = _BroadcastHandler()
_handler.setLevel(logging.DEBUG)


def install_log_broadcast() -> None:
    """将广播 handler 注入根 logger，应在 setup_logging 之后调用。"""
    root = logging.getLogger()
    if _handler not in root.handlers:
        root.addHandler(_handler)


# ── SSE 端点 ──


async def _event_stream(level: int) -> Any:
    """生成 SSE 数据流。"""
    q: asyncio.Queue[str] = asyncio.Queue(maxsize=512)
    _subscribers.add(q)
    try:
        yield "event: connected\ndata: {}\n\n"
        while True:
            line = await q.get()
            # 按级别过滤
            try:
                parsed = json.loads(line)
                log_level = logging.getLevelName(parsed.get("level", "INFO"))
                if isinstance(log_level, int) and log_level < level:
                    continue
            except Exception:
                pass
            yield f"data: {line}\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        _subscribers.discard(q)


@router.get("/logs")
async def stream_logs(
    level: str = Query("DEBUG", description="最低日志级别过滤: DEBUG / INFO / WARNING / ERROR"),
) -> StreamingResponse:
    """SSE 端点 —— 实时推送应用日志。"""
    numeric_level = getattr(logging, level.upper(), logging.DEBUG)
    return StreamingResponse(
        _event_stream(numeric_level),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

