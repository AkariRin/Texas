"""框架扩展点 Protocol 接口定义 —— 框架核心与业务层之间的契约。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from src.core.framework.context import Context


@runtime_checkable
class AdminProvider(Protocol):
    """返回超级管理员 QQ 集合，用于框架角色权限检查。"""

    async def get_admin_qq_set(self) -> frozenset[int]: ...


@runtime_checkable
class FeatureChecker(Protocol):
    """功能级权限检查，在 handler 循环中逐 handler 调用。"""

    async def check(self, ctx: Context) -> bool: ...
