"""Celery Worker 共享工具函数。"""

from __future__ import annotations

import asyncio
import threading
from typing import Any

# 为 Celery Worker 维护一个持久的事件循环，避免 asyncio.run() 每次
# 创建/销毁循环导致 async 数据库引擎连接池失效。
_worker_loop: asyncio.AbstractEventLoop | None = None
_loop_lock = threading.Lock()


def _get_worker_loop() -> asyncio.AbstractEventLoop:
    """获取或创建 Worker 专用的持久事件循环（线程安全）。"""
    global _worker_loop
    with _loop_lock:
        if _worker_loop is None or _worker_loop.is_closed():
            _worker_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_worker_loop)
        return _worker_loop


def run_async(coro: Any) -> Any:
    """在 Celery 同步 Worker 中安全运行异步协程。

    使用持久事件循环（run_until_complete），确保 async 数据库引擎的
    连接池始终绑定在同一个存活的循环上，不会因循环关闭而失效。

    - 无运行中的事件循环 → 使用持久 Worker 循环执行
    - 已有运行中的事件循环 → 在独立线程中使用持久循环执行（极端情况防御）
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        worker_loop = _get_worker_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(worker_loop.run_until_complete, coro).result()
    return _get_worker_loop().run_until_complete(coro)
