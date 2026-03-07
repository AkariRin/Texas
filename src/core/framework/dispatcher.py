"""EventDispatcher —— 统一事件分发（类似 Spring DispatcherServlet）。"""

from __future__ import annotations

from typing import Any

import structlog

from src.core.framework.context import Context, FinishException
from src.core.framework.interceptor import HandlerInterceptor
from src.core.framework.mapping import CompositeHandlerMapping, HandlerMethod
from src.core.protocol.api import BotAPI
from src.core.protocol.models.base import OneBotEvent

logger = structlog.get_logger()


class EventDispatcher:
    """接收已解析的事件，通过映射解析处理器，并运行拦截器链。"""

    def __init__(
        self,
        mapping: CompositeHandlerMapping,
        interceptors: list[HandlerInterceptor] | None = None,
    ) -> None:
        self.mapping = mapping
        self.interceptors = interceptors or []

    async def dispatch(self, event: OneBotEvent, bot: BotAPI) -> None:
        ctx = Context(event=event, bot=bot)
        result: Any = None
        exc: Exception | None = None

        try:
            # 1. 前置拦截器
            for interceptor in self.interceptors:
                if not await interceptor.pre_handle(ctx):
                    logger.debug(
                        "Interceptor blocked event",
                        interceptor=type(interceptor).__name__,
                        event_type="dispatcher.interceptor_blocked",
                    )
                    return

            # 2. 解析匹配的处理器
            handlers: list[HandlerMethod] = self.mapping.resolve(event)

            if not handlers:
                logger.debug(
                    "No handler matched",
                    post_type=event.post_type,
                    event_type="dispatcher.no_match",
                )
                return

            # 3. 按优先级执行处理器
            for handler in handlers:
                ctx.handler_method = handler

                # 对于正则匹配，将匹配结果设置到上下文
                regex_match = handler.metadata.get("_last_match")
                if regex_match:
                    ctx.set_regex_match(regex_match)

                try:
                    result = await handler.method(handler.controller, ctx)
                    if result is True:
                        break  # 处理器发出停止传播信号
                except FinishException:
                    break

            # 4. 后置拦截器（逆序执行）
            for interceptor in reversed(self.interceptors):
                await interceptor.post_handle(ctx, result)

        except FinishException:
            pass  # 正常流程控制
        except Exception as e:
            exc = e
            logger.error(
                "Error during event dispatch",
                error=str(e),
                event_type="dispatcher.error",
                exc_info=True,
            )
        finally:
            # 5. 完成后拦截器（始终执行，逆序）
            for interceptor in reversed(self.interceptors):
                try:
                    await interceptor.after_completion(ctx, exc=exc)
                except Exception as cleanup_exc:
                    logger.error(
                        "Error in interceptor after_completion",
                        interceptor=type(interceptor).__name__,
                        error=str(cleanup_exc),
                        event_type="dispatcher.cleanup_error",
                    )

