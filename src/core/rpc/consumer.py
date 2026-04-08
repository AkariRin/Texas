"""主进程端 RPC 消费者 —— 从 Redis 队列取请求，委托已注册 handler 执行，响应写回 Redis。"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Awaitable, Callable
from typing import Any

import redis.asyncio as aioredis
import structlog

from src.core.monitoring.metrics import (
    rpc_handler_exec_seconds,
    rpc_inflight,
    rpc_registered_handlers,
)
from src.core.rpc.keys import rpc_request_queue, rpc_response_channel

from .models import RPCRequest, RPCResponse

logger = structlog.get_logger()

# 自定义 action handler 类型：接收 params dict，返回任意可序列化结果
ActionHandler = Callable[[dict[str, Any]], Awaitable[Any]]

# 并发 handler 数量上限（背压保护）
_DEFAULT_MAX_CONCURRENCY = 64


class RPCConsumer:
    """在主进程事件循环中运行的通用 RPC 请求消费者。

    使用 BLPOP 阻塞式从 Redis List 取请求，
    调用已注册的 handler 执行，
    结果通过 PUBLISH 返回给 Worker 端的 Pub/Sub 订阅者。

    特性：
    - start() 幂等，多次调用安全
    - 停机时等待所有 in-flight handler 完成
    - 每个请求受 RPCRequest.timeout 约束
    - 并发 handler 数量受 max_concurrency 限制（背压）
    """

    def __init__(self, redis_url: str, *, max_concurrency: int = _DEFAULT_MAX_CONCURRENCY) -> None:
        self._redis = aioredis.from_url(redis_url, decode_responses=True)  # type: ignore[no-untyped-call]
        self._handlers: dict[str, ActionHandler] = {}
        self._task: asyncio.Task[None] | None = None
        self._inflight: set[asyncio.Task[None]] = set()
        self._semaphore = asyncio.Semaphore(max_concurrency)

    def register_handler(self, action: str, handler: ActionHandler) -> None:
        """注册 action handler。

        若 action 已有 handler，打印 WARNING 后覆盖。
        """
        if action in self._handlers:
            logger.warning(
                "RPC handler 重复注册，将覆盖原有 handler",
                action=action,
                event_type="rpc.handler_overwritten",
            )
        self._handlers[action] = handler
        rpc_registered_handlers.set(len(self._handlers))
        logger.debug(
            "RPC handler 已注册",
            action=action,
            event_type="rpc.handler_registered",
        )

    async def start(self) -> None:
        """启动消费循环（作为后台 asyncio Task）。幂等，重复调用无副作用。"""
        if self._task and not self._task.done():
            logger.debug(
                "RPC 消费者已在运行，跳过重复启动",
                event_type="rpc.consumer_already_running",
            )
            return
        self._task = asyncio.create_task(self._consume_loop(), name="rpc-consumer")
        logger.info("RPC 消费者已启动", event_type="rpc.consumer_started")

    async def stop(self) -> None:
        """停止消费循环，等待所有 in-flight 请求完成后关闭 Redis 连接。"""
        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

        # 等待所有 in-flight handler 完成，避免停机时丢失响应
        if self._inflight:
            logger.info(
                "等待 in-flight RPC 请求完成",
                count=len(self._inflight),
                event_type="rpc.consumer_draining",
            )
            await asyncio.gather(*self._inflight, return_exceptions=True)

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
                task = asyncio.create_task(self._handle_request(raw))
                self._inflight.add(task)
                task.add_done_callback(self._inflight.discard)
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

        # 绑定 request_id 到日志上下文，让 handler 内所有日志自动携带追踪 ID
        bound_logger = logger.bind(request_id=req.request_id, action=req.action)

        # 背压保护：超过最大并发时阻塞等待
        async with self._semaphore:
            rpc_inflight.inc()
            try:
                rpc_resp = await self._execute(req, bound_logger)
            finally:
                rpc_inflight.dec()

        resp_channel = rpc_response_channel(req.request_id)
        try:
            await self._redis.publish(resp_channel, rpc_resp.model_dump_json())
        except Exception:
            bound_logger.exception(
                "RPC 响应发布失败",
                event_type="rpc.publish_error",
            )

    async def _execute(self, req: RPCRequest, bound_logger: Any) -> RPCResponse:
        """执行 RPC 请求：查找已注册 handler，未注册则返回错误。受 req.timeout 约束。"""
        if req.action not in self._handlers:
            bound_logger.warning(
                "RPC 未注册的 action",
                event_type="rpc.unregistered_action",
            )
            return RPCResponse(
                request_id=req.request_id,
                success=False,
                error=f"未注册的 action: {req.action}",
            )

        handler = self._handlers[req.action]
        t0 = time.monotonic()
        try:
            result = await asyncio.wait_for(handler(req.params), timeout=req.timeout)
            elapsed = time.monotonic() - t0
            rpc_handler_exec_seconds.labels(action=req.action).observe(elapsed)
            data: dict[str, object] = result if isinstance(result, dict) else {"result": result}
            return RPCResponse(
                request_id=req.request_id,
                success=True,
                data=data,
            )
        except TimeoutError:
            elapsed = time.monotonic() - t0
            rpc_handler_exec_seconds.labels(action=req.action).observe(elapsed)
            bound_logger.warning(
                "RPC handler 执行超时",
                timeout=req.timeout,
                elapsed=elapsed,
                event_type="rpc.handler_timeout",
            )
            return RPCResponse(
                request_id=req.request_id,
                success=False,
                error=f"handler 执行超时（>{req.timeout}s）",
            )
        except Exception as exc:
            elapsed = time.monotonic() - t0
            rpc_handler_exec_seconds.labels(action=req.action).observe(elapsed)
            bound_logger.warning(
                "RPC 请求执行失败",
                error=str(exc),
                event_type="rpc.exec_error",
            )
            return RPCResponse(
                request_id=req.request_id,
                success=False,
                error=str(exc),
            )
