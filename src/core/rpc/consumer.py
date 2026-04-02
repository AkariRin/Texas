"""主进程端 RPC 消费者 —— 从 Redis 队列取请求，委托 BotAPI 执行，响应写回 Redis。"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

import redis.asyncio as aioredis
import structlog

from src.core.cache.keys import rpc_request_queue, rpc_response_channel

from .models import RPCRequest, RPCResponse

if TYPE_CHECKING:
    from src.core.protocol.api import BotAPI

logger = structlog.get_logger()

# 自定义 action handler 类型：接收 params dict，返回任意可序列化结果
ActionHandler = Callable[[dict[str, Any]], Awaitable[Any]]


class RPCConsumer:
    """在主进程事件循环中运行的 RPC 请求消费者。

    使用 BLPOP 阻塞式从 Redis List 取请求，
    调用 BotAPI._call() 或自定义 handler 执行，
    结果通过 PUBLISH 返回给 Worker 端的 Pub/Sub 订阅者。
    """

    def __init__(self, bot_api: BotAPI, redis_url: str) -> None:
        self._bot_api = bot_api
        self._redis = aioredis.from_url(redis_url, decode_responses=True)  # type: ignore[no-untyped-call]
        self._custom_handlers: dict[str, ActionHandler] = {}
        self._task: asyncio.Task[None] | None = None

    def register_handler(self, action: str, handler: ActionHandler) -> None:
        """注册自定义 action handler，优先于透传给 BotAPI._call()。

        用于高层业务操作（如 request_checkin），这些操作无法直接映射为
        单个 OneBot action，需要在主进程侧执行业务逻辑。
        """
        self._custom_handlers[action] = handler
        logger.debug(
            "RPC 自定义 handler 已注册",
            action=action,
            event_type="rpc.handler_registered",
        )

    async def start(self) -> None:
        """启动消费循环（作为后台 asyncio Task）。"""
        self._task = asyncio.create_task(self._consume_loop(), name="rpc-consumer")
        logger.info("RPC 消费者已启动", event_type="rpc.consumer_started")

    async def stop(self) -> None:
        """停止消费循环并关闭 Redis 连接。"""
        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        await self._redis.aclose()
        logger.info("RPC 消费者已停止", event_type="rpc.consumer_stopped")

    async def _consume_loop(self) -> None:
        """主消费循环：BLPOP → 并发处理 → PUBLISH 响应。"""
        queue_key = rpc_request_queue()
        while True:
            try:
                # BLPOP timeout=1 便于响应 CancelledError
                result = await self._redis.blpop([queue_key], timeout=1)
                if result is None:
                    continue
                _, raw = result  # (key, value)
                # 每个请求在独立 task 中处理，不阻塞队列消费
                asyncio.create_task(self._handle_request(raw))
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("RPC 消费循环异常", event_type="rpc.consume_error")
                await asyncio.sleep(1)  # 防止异常风暴

    async def _handle_request(self, raw: str) -> None:
        """解析并处理单个 RPC 请求，将结果 PUBLISH 到响应通道。"""
        try:
            req = RPCRequest.model_validate_json(raw)
        except Exception:
            logger.warning(
                "RPC 请求解析失败",
                raw=raw[:200],
                event_type="rpc.parse_error",
            )
            return

        rpc_resp = await self._execute(req)

        resp_channel = rpc_response_channel(req.request_id)
        try:
            await self._redis.publish(resp_channel, rpc_resp.model_dump_json())
        except Exception:
            logger.exception(
                "RPC 响应发布失败",
                request_id=req.request_id,
                event_type="rpc.publish_error",
            )

    async def _execute(self, req: RPCRequest) -> RPCResponse:
        """执行 RPC 请求：自定义 handler 优先，否则透传给 BotAPI._call()。"""
        try:
            if req.action in self._custom_handlers:
                handler = self._custom_handlers[req.action]
                result = await handler(req.params)
                # 自定义 handler 返回值包装为 APIResponse 兼容的结构，
                # 确保 Proxy 端 APIResponse.model_validate() 得到 status="ok"
                payload: dict[str, object] = (
                    result if isinstance(result, dict) else {"result": result}
                )
                return RPCResponse(
                    request_id=req.request_id,
                    success=True,
                    data={
                        "status": "ok",
                        "retcode": 0,
                        "data": payload,
                        "message": "",
                        "echo": req.request_id,
                    },
                )

            # 标准 OneBot action：透传给 BotAPI
            api_resp = await self._bot_api._call(req.action, req.params, timeout=req.timeout)
            return RPCResponse(
                request_id=req.request_id,
                success=True,
                data=api_resp.model_dump(),
            )
        except Exception as exc:
            logger.warning(
                "RPC 请求执行失败",
                action=req.action,
                error=str(exc),
                event_type="rpc.exec_error",
            )
            return RPCResponse(
                request_id=req.request_id,
                success=False,
                error=str(exc),
            )
