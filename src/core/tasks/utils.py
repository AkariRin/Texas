"""Celery Worker 共享工具函数。"""

from __future__ import annotations

import asyncio
from typing import Any


def run_async(coro: Any) -> Any:
    """在 Celery 同步 Worker 中安全运行异步协程。

    - 无事件循环 → 直接 asyncio.run()
    - 已有事件循环 → 在独立线程中运行（极端情况防御）
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)

