"""Worker 端通用 RPC 桥接器 —— 通过 Redis 桥接主进程的 RPC Consumer。

Celery Worker 运行在同步上下文，本模块使用同步 redis 客户端，
向 Worker 暴露简洁的跨进程调用接口，返回通用 RPCResponse。
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import redis
import structlog

from src.core.config import get_settings
from src.core.rpc.keys import rpc_request_queue, rpc_response_channel

from .models import RPCRequest, RPCResponse

logger = structlog.get_logger()

# RPC 超时裕量（秒）：覆盖网络延迟 + 主进程调度耗时
_TIMEOUT_MARGIN = 5.0
# Pub/Sub 轮询粒度（秒）：降低至 0.1s 减少无谓等待
_POLL_INTERVAL = 0.1


class RPCBridge:
    """Worker 端的通用跨进程 RPC 桥接器。

    通过 Redis List（请求队列）+ Pub/Sub（响应通道）实现 RPC，
    返回通用 RPCResponse，不依赖任何协议特定模型。
    """

    def __init__(self, redis_url: str | None = None) -> None:
        url = redis_url or get_settings().PERSISTENT_REDIS_URL
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
        try:
            pubsub.subscribe(resp_channel)
        except redis.RedisError as exc:
            pubsub.close()
            logger.error(
                "RPC 订阅响应通道失败",
                action=action,
                request_id=request_id,
                error=str(exc),
                event_type="rpc.bridge_subscribe_error",
            )
            return RPCResponse(
                request_id=request_id,
                success=False,
                error="rpc_connection_error",
            )

        t0 = time.monotonic()
        try:
            try:
                # 先订阅、再入队，防止竞态窗口
                self._redis.rpush(rpc_request_queue(), req.model_dump_json())
            except redis.RedisError as exc:
                logger.error(
                    "RPC 请求入队失败",
                    action=action,
                    request_id=request_id,
                    error=str(exc),
                    event_type="rpc.bridge_enqueue_error",
                )
                return RPCResponse(
                    request_id=request_id,
                    success=False,
                    error="rpc_connection_error",
                )

            # 等待响应，超时阈值包含裕量
            deadline = timeout + _TIMEOUT_MARGIN
            while True:
                elapsed = time.monotonic() - t0
                remaining = deadline - elapsed
                if remaining <= 0:
                    break
                msg = pubsub.get_message(
                    timeout=min(remaining, _POLL_INTERVAL),
                    ignore_subscribe_messages=True,
                )
                if msg and msg["type"] == "message":
                    return RPCResponse.model_validate_json(msg["data"])

            logger.warning(
                "RPC 调用超时",
                action=action,
                request_id=request_id,
                elapsed=time.monotonic() - t0,
                event_type="rpc.bridge_timeout",
            )
            return RPCResponse(
                request_id=request_id,
                success=False,
                error="rpc_timeout",
            )
        finally:
            pubsub.unsubscribe(resp_channel)
            pubsub.close()

    def close(self) -> None:
        """关闭底层 Redis 连接池。测试隔离或进程退出时调用。"""
        self._redis.close()


# ── 模块级 lazy singleton（Celery Worker 进程内复用 Redis 连接）──

_bridge: RPCBridge | None = None


def get_rpc_bridge() -> RPCBridge:
    """获取全局 RPCBridge 单例。

    在 Celery Worker 进程中首次调用时创建实例，后续复用同一连接。
    """
    global _bridge
    if _bridge is None:
        _bridge = RPCBridge()
    return _bridge


def reset_rpc_bridge() -> None:
    """重置全局 RPCBridge 单例并关闭 Redis 连接。

    主要供测试使用，确保用例间连接隔离。
    """
    global _bridge
    if _bridge is not None:
        _bridge.close()
        _bridge = None
