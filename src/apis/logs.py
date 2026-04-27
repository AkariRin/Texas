"""日志 SSE 端点 —— 实时推送应用日志到前端。"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Query

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
from starlette.responses import StreamingResponse

from src.core.logging.broadcast import subscribers as _subscribers
from src.core.logging.broadcast import subscribers_lock as _subscribers_lock

router = APIRouter()


# ── SSE 端点 ──


async def _event_stream(level: int) -> AsyncGenerator[str]:
    """生成 SSE 数据流。"""
    q: asyncio.Queue[str] = asyncio.Queue(maxsize=512)
    async with _subscribers_lock:
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
            except json.JSONDecodeError, KeyError, TypeError:
                pass  # 非 JSON 格式日志行，跳过级别过滤，直接透传
            yield f"data: {line}\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        async with _subscribers_lock:
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
