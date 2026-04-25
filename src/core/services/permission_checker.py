"""功能级权限检查器 —— 在 handler 循环中对每个 handler 执行权限检查。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from src.core.framework.context import Context
    from src.core.registries.permission_registry import PermissionRegistry
    from src.core.services.permission import FeaturePermissionService
    from src.core.services.personnel import PersonnelService

logger = structlog.get_logger()


class FeaturePermissionChecker:
    """功能级权限检查。每条消息每个 handler 调用一次。

    检查顺序：
    1. 系统级功能（system=True）零 IO 直接通过（PermissionRegistry 内存快照优先）
    2. ADMIN 超级管理员直接通过（绕过所有功能权限，需 IO）
    3. 群聊 → 先检查群 bot 总开关，再检查两级功能权限
    4. 私聊 → 以 controller 级为粒度的黑/白名单
    """

    def __init__(
        self,
        permission_service: FeaturePermissionService,
        personnel_service: PersonnelService,
        perm_registry: PermissionRegistry | None = None,
    ) -> None:
        self._service = permission_service
        self._personnel_service = personnel_service
        self._perm_registry = perm_registry

    async def check(self, ctx: Context) -> bool:
        """返回 True 表示允许执行该 handler。"""
        handler = ctx.handler_method
        if handler is None:
            return True

        ctrl_feature: str = handler.controller_name
        method_feature: str = f"{handler.controller_name}.{handler.method_name}"

        # 零 IO 快速路径：系统级功能（PermissionRegistry 内存快照）始终允许
        if self._perm_registry is not None and self._perm_registry.is_system(ctrl_feature):
            return True

        # perm_registry 未设置时退化为读 handler 元数据（仍为内存操作）
        if self._perm_registry is None:
            handler_meta = getattr(handler, "metadata", {}) or {}
            if handler_meta.get("system"):
                return True

        # ADMIN 超级管理员绕过所有功能权限检查（IO）
        admin_set = await self._personnel_service.get_admin_qq_set()
        if ctx.user_id in admin_set:
            return True

        if ctx.is_group:
            group_id = ctx.group_id
            if group_id is None:
                return True
            # 先检查群 bot 总开关
            if not await self._service.is_group_enabled(group_id):
                logger.debug(
                    "群 bot 总开关关闭",
                    group_id=group_id,
                    user_id=ctx.user_id,
                    event_type="permission.group_disabled",
                )
                return False
            allowed = await self._service.is_group_feature_enabled(
                group_id, ctrl_feature, method_feature
            )
        else:
            allowed = await self._service.is_private_feature_allowed(
                ctrl_feature, method_feature, ctx.user_id
            )

        if not allowed:
            logger.debug(
                "功能权限拒绝",
                controller=ctrl_feature,
                method=method_feature,
                user_id=ctx.user_id,
                group_id=ctx.group_id,
                event_type="permission.feature_denied",
            )

        return allowed
