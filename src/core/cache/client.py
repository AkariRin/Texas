"""Redis 缓存客户端封装。"""

from __future__ import annotations

import inspect
import json
from typing import TYPE_CHECKING, Any, TypeVar

import redis.asyncio as aioredis

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")


class CacheClient:
    """支持常用操作的异步 Redis 缓存客户端。"""

    def __init__(self, url: str, default_ttl: int = 300) -> None:
        self._redis = aioredis.from_url(url, decode_responses=True)  # type: ignore[no-untyped-call]
        self._default_ttl = default_ttl

    async def close(self) -> None:
        await self._redis.aclose()

    async def get(self, key: str) -> Any | None:
        val = await self._redis.get(key)
        if val is None:
            return None
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        ttl = ttl if ttl is not None else self._default_ttl
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        await self._redis.set(key, value, ex=ttl if ttl else None)

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    async def exists(self, key: str) -> bool:
        return bool(await self._redis.exists(key))

    async def incr(self, key: str) -> int:
        return int(await self._redis.incr(key))

    async def expire(self, key: str, ttl: int) -> None:
        await self._redis.expire(key, ttl)

    async def get_or_set(self, key: str, factory: Callable[[], Any], ttl: int | None = None) -> Any:
        """从缓存中获取值；若未命中，则调用 factory，缓存结果并返回。

        factory 可以是同步函数或 async 函数。
        """
        val = await self.get(key)
        if val is not None:
            return val
        val = factory()
        if inspect.isawaitable(val):
            val = await val
        await self.set(key, val, ttl)
        return val

    async def delete_by_pattern(self, pattern: str) -> None:
        """按 glob 模式批量删除匹配的键（使用 SCAN 迭代，避免 KEYS 阻塞）。"""
        cursor = 0
        while True:
            cursor, keys = await self._redis.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                await self._redis.delete(*keys)
            if cursor == 0:
                break
