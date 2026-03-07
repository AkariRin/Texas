"""Redis 缓存客户端封装。"""

from __future__ import annotations

import json
from typing import Any, Callable, TypeVar

import redis.asyncio as aioredis

T = TypeVar("T")


class CacheClient:
    """支持常用操作的异步 Redis 缓存客户端。"""

    def __init__(self, url: str, default_ttl: int = 300) -> None:
        self._redis = aioredis.from_url(url, decode_responses=True)
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
        ttl = ttl or self._default_ttl
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        await self._redis.set(key, value, ex=ttl)

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    async def exists(self, key: str) -> bool:
        return bool(await self._redis.exists(key))

    async def incr(self, key: str) -> int:
        return await self._redis.incr(key)

    async def expire(self, key: str, ttl: int) -> None:
        await self._redis.expire(key, ttl)

    async def get_or_set(
        self, key: str, factory: Callable[[], Any], ttl: int | None = None
    ) -> Any:
        """从缓存中获取值；若未命中，则调用 factory，缓存结果并返回。"""
        val = await self.get(key)
        if val is not None:
            return val
        val = factory() if not callable(factory) else factory()
        await self.set(key, val, ttl)
        return val

