"""框架扩展点 Protocol 接口定义 —— 框架核心与业务层之间的契约。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from src.core.framework.context import Context


@runtime_checkable
class FeatureChecker(Protocol):
    """统一权限检查（功能级 + 角色级），在 handler 循环中逐 handler 调用。"""

    async def check(self, ctx: Context) -> bool: ...
