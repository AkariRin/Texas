"""Worker 端通用 RPC 代理 —— 通过 Redis 桥接主进程的 RPC Consumer。

Celery Worker 运行在同步上下文，本模块使用同步 redis 客户端，
向 Worker 暴露简洁的跨进程调用接口，返回通用 RPCResponse。
"""

from __future__ import annotations

import uuid
from typing import Any

import redis
import structlog

from src.core.cache.keys import rpc_request_queue, rpc_response_channel
from src.core.config import get_settings

from .models import RPCRequest, RPCResponse

logger = structlog.get_logger()

# RPC 超时裕量（秒）：覆盖网络延迟 + 主进程调度耗时
_TIMEOUT_MARGIN = 5.0


class RPCProxy:
    """Worker 端的通用跨进程 RPC 代理。

    通过 Redis List（请求队列）+ Pub/Sub（响应通道）实现 RPC，
    返回通用 RPCResponse，不依赖任何协议特定模型。
    """

    def __init__(self, redis_url: str | None = None) -> None:
        url = redis_url or get_settings().CACHE_REDIS_URL
        self._redis = redis.from_url(url, decode_responses=True)  # type: ignore[no-untyped-call]

    def call(
        self,
        action: str,
        params: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> RPCResponse:
        """通过 Redis RPC 调用主进程注册的 handler。

        先订阅响应通道再入队请求，避免响应先于订阅到达导致丢失。
        等待时间为 timeout + _TIMEOUT_MARGIN。
        """
        request_id = uuid.uuid4().hex
        req = RPCRequest(
            request_id=request_id,
            action=action,
            params=params or {},
            timeout=timeout,
        )

        resp_channel = rpc_response_channel(request_id)
        pubsub = self._redis.pubsub()
        pubsub.subscribe(resp_channel)

        try:
            # 先订阅、再入队，防止竞态窗口
            self._redis.rpush(rpc_request_queue(), req.model_dump_json())

            # 等待响应，超时阈值包含裕量
            deadline = timeout + _TIMEOUT_MARGIN
            while deadline > 0:
                msg = pubsub.get_message(timeout=min(deadline, 1.0), ignore_subscribe_messages=True)
                if msg and msg["type"] == "message":
                    return RPCResponse.model_validate_json(msg["data"])
                deadline -= 1.0

            logger.warning(
                "RPC 调用超时",
                action=action,
                request_id=request_id,
                event_type="rpc.proxy_timeout",
            )
            return RPCResponse(
                request_id=request_id,
                success=False,
                error="rpc_timeout",
            )
        finally:
            pubsub.unsubscribe(resp_channel)
            pubsub.close()


# ── 模块级 lazy singleton（Celery Worker 进程内复用 Redis 连接）──

_proxy: RPCProxy | None = None


def get_rpc_proxy() -> RPCProxy:
    """获取全局 RPCProxy 单例。

    在 Celery Worker 进程中首次调用时创建实例，后续复用同一连接。
    """
    global _proxy
    if _proxy is None:
        _proxy = RPCProxy()
    return _proxy
