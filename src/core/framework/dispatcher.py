"""EventDispatcher —— 统一事件分发（类似 Spring DispatcherServlet）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from src.core.framework.context import Context, FinishError

if TYPE_CHECKING:
    from src.core.framework.interceptor import HandlerInterceptor
    from src.core.framework.mapping import CompositeHandlerMapping, ResolvedHandler
    from src.core.framework.ports import FeatureChecker
    from src.core.protocol.api import BotAPI
    from src.core.protocol.models.base import OneBotEvent

logger = structlog.get_logger()


class EventDispatcher:
    """接收已解析的事件，通过映射解析处理器，并运行拦截器链。

    权限检查（功能级 + 角色级）统一委托给 feature_checker，
    分发器不实现任何权限规则。
    """

    def __init__(
        self,
        mapping: CompositeHandlerMapping,
        interceptors: list[HandlerInterceptor] | None = None,
        services: dict[type, Any] | None = None,
        feature_checker: FeatureChecker | None = None,
    ) -> None:
        self.mapping = mapping
        self.interceptors = interceptors or []
        self.services: dict[type, Any] = {} if services is None else services
        self._feature_checker = feature_checker

    async def dispatch(self, event: OneBotEvent, bot: BotAPI) -> None:
        ctx = Context(event=event, bot=bot, services=self.services)
        result: Any = None
        exc: Exception | None = None

        try:
            # 1. 前置拦截器
            for interceptor in self.interceptors:
                if not await interceptor.pre_handle(ctx):
                    logger.debug(
                        "拦截器已阻断事件",
                        interceptor=type(interceptor).__name__,
                        event_type="dispatcher.interceptor_blocked",
                    )
                    return

            # 2. 解析匹配的处理器
            resolved_handlers: list[ResolvedHandler] = self.mapping.resolve(event)

            if not resolved_handlers:
                logger.debug(
                    "未找到匹配的处理器",
                    post_type=event.post_type,
                    event_type="dispatcher.no_match",
                )
                return

            # 3. 按优先级执行处理器
            for resolved in resolved_handlers:
                handler = resolved.handler
                ctx.handler_method = handler

                if resolved.regex_match is not None:
                    ctx.set_regex_match(resolved.regex_match)

                # 统一权限检查（功能级 + 角色级，由 feature_checker 统一处理）
                if self._feature_checker is not None and not await self._feature_checker.check(ctx):
                    continue

                try:
                    result = await handler.method(ctx)
                    if result is True:
                        break
                except FinishError:
                    break

            # 4. 后置拦截器（逆序执行）
            for interceptor in reversed(self.interceptors):
                await interceptor.post_handle(ctx, result)

        except FinishError:
            pass
        except Exception as e:
            exc = e
            logger.error(
                "事件分发过程中发生错误",
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
                        "拦截器 after_completion 中发生错误",
                        interceptor=type(interceptor).__name__,
                        error=str(cleanup_exc),
                        event_type="dispatcher.cleanup_error",
                    )
