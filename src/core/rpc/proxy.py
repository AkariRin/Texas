"""Worker 端 BotAPI 代理 —— 通过 Redis RPC 桥接主进程的 BotAPI。

Celery Worker 运行在同步上下文，本模块使用同步 redis 客户端，
提供与 BotAPI 接口一致的调用方式。
"""

from __future__ import annotations

import uuid
from typing import Any

import redis
import structlog

from src.core.cache.keys import rpc_request_queue, rpc_response_channel
from src.core.config import get_settings
from src.core.protocol.models.api import APIResponse

from .models import RPCRequest, RPCResponse

logger = structlog.get_logger()

# RPC 超时裕量（秒）：覆盖网络延迟 + 主进程调度耗时
_TIMEOUT_MARGIN = 5.0


class BotAPIProxy:
    """Worker 端的 BotAPI 跨进程代理。

    通过 Redis List（请求队列）+ Pub/Sub（响应通道）实现 RPC，
    向 Worker 暴露与 BotAPI 一致的调用接口。
    """

    def __init__(self, redis_url: str | None = None) -> None:
        url = redis_url or get_settings().CACHE_REDIS_URL
        self._redis = redis.from_url(url, decode_responses=True)  # type: ignore[no-untyped-call]

    def call(
        self,
        action: str,
        params: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> APIResponse:
        """通过 Redis RPC 调用主进程的 BotAPI，对标 BotAPI._call()。

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
                # get_message 最多阻塞 1 秒，循环检测 deadline
                msg = pubsub.get_message(timeout=min(deadline, 1.0), ignore_subscribe_messages=True)
                if msg and msg["type"] == "message":
                    rpc_resp = RPCResponse.model_validate_json(msg["data"])
                    if rpc_resp.success and rpc_resp.data is not None:
                        return APIResponse.model_validate(rpc_resp.data)
                    return APIResponse(
                        status="failed",
                        retcode=-1,
                        message=rpc_resp.error or "rpc_error",
                        echo=request_id,
                    )
                deadline -= 1.0

            logger.warning(
                "RPC 调用超时",
                action=action,
                request_id=request_id,
                event_type="rpc.proxy_timeout",
            )
            return APIResponse(
                status="failed",
                retcode=-1,
                message="rpc_timeout",
                echo=request_id,
            )
        finally:
            pubsub.unsubscribe(resp_channel)
            pubsub.close()

    # ── 便捷方法（高频 OneBot action 包装）──

    def send_group_msg(self, group_id: int, message: str) -> APIResponse:
        """发送群消息。"""
        return self.call("send_group_msg", {"group_id": group_id, "message": message})

    def send_private_msg(self, user_id: int, message: str) -> APIResponse:
        """发送私聊消息。"""
        return self.call("send_private_msg", {"user_id": user_id, "message": message})

    def send_group_sign(self, group_id: int) -> APIResponse:
        """群打卡（发送群签到）。"""
        return self.call("send_group_sign", {"group_id": group_id})


# ── 模块级 lazy singleton（Celery Worker 进程内复用 Redis 连接）──

_proxy: BotAPIProxy | None = None


def get_bot_api_proxy() -> BotAPIProxy:
    """获取全局 BotAPIProxy 单例。

    在 Celery Worker 进程中首次调用时创建实例，后续复用同一连接。
    """
    global _proxy
    if _proxy is None:
        _proxy = BotAPIProxy()
    return _proxy
