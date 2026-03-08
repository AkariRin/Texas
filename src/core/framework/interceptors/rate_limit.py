"""频率限制拦截器 —— Redis 滑动窗口。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from src.core.framework.interceptor import HandlerInterceptor

if TYPE_CHECKING:
    from src.core.cache.client import CacheClient
    from src.core.framework.context import Context

logger = structlog.get_logger()


class RateLimitInterceptor(HandlerInterceptor):
    """使用 Redis 的滑动窗口频率限制器（可选）。

    若未提供缓存客户端，则禁用频率限制。
    """

    def __init__(
        self,
        cache_client: CacheClient | None = None,
        max_requests: int = 10,
        window_seconds: int = 60,
    ) -> None:
        self._cache = cache_client
        self._max_requests = max_requests
        self._window = window_seconds

    async def pre_handle(self, ctx: Context) -> bool:
        if self._cache is None:
            return True  # 无缓存 = 不限速

        user_id = ctx.user_id
        if user_id == 0:
            return True

        key = f"texas:ratelimit:{user_id}"

        try:
            count = await self._cache.incr(key)
            if count == 1:
                await self._cache.expire(key, self._window)

            if count > self._max_requests:
                logger.info(
                    "Rate limit exceeded",
                    user_id=user_id,
                    count=count,
                    event_type="interceptor.rate_limit.exceeded",
                )
                await ctx.reply("Rate limit exceeded. Please slow down.")
                return False
        except Exception as exc:
            logger.warning(
                "Rate limit check failed",
                error=str(exc),
                event_type="interceptor.rate_limit.error",
            )

        return True
