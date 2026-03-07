"""HandlerInterceptor 接口 —— Spring 风格的前置/后置/完成后钩子。"""

from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.core.framework.context import Context


class HandlerInterceptor(ABC):
    """拦截器基础接口。

    执行顺序：
        pre_handle -> 处理器执行 -> post_handle -> after_completion
                                                    ^ （异常时也会执行）
    """

    async def pre_handle(self, ctx: Context) -> bool:
        """在处理器执行前调用。返回 False 则中止调用链。"""
        return True

    async def post_handle(self, ctx: Context, result: Any) -> None:
        """在处理器成功执行后调用。"""

    async def after_completion(self, ctx: Context, exc: Exception | None = None) -> None:
        """在完成后调用（无论成功或失败）。用于资源清理。"""

