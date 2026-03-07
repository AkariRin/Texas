"""NapCat 连接的心跳监控。"""

from __future__ import annotations

import asyncio
import time

import structlog

logger = structlog.get_logger()


class HeartbeatMonitor:
    """监控来自 NapCat 的心跳事件。

    若在超时时间（2 倍间隔）内未收到心跳，则触发警告。
    """

    def __init__(self, interval_ms: int = 30000) -> None:
        self._interval_ms = interval_ms
        self._last_heartbeat: float = 0.0
        self._task: asyncio.Task[None] | None = None
        self._running = False

    @property
    def last_heartbeat(self) -> float:
        return self._last_heartbeat

    def record_heartbeat(self, status: dict[str, object] | None = None) -> None:
        self._last_heartbeat = time.time()
        logger.debug(
            "Heartbeat received",
            status=status,
            event_type="ws.heartbeat",
        )

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._last_heartbeat = time.time()
        self._task = asyncio.create_task(self._monitor_loop())

    def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()

    async def _monitor_loop(self) -> None:
        timeout_s = (self._interval_ms * 2) / 1000.0
        while self._running:
            await asyncio.sleep(timeout_s)
            if not self._running:
                break
            elapsed = time.time() - self._last_heartbeat
            if elapsed > timeout_s:
                logger.warning(
                    "Heartbeat timeout — no heartbeat received",
                    elapsed_s=round(elapsed, 1),
                    timeout_s=timeout_s,
                    event_type="ws.heartbeat_timeout",
                )

