"""功能级权限检查器 —— 在 handler 循环中对每个 handler 执行完整权限检查（功能级 + 角色级）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from src.core.framework.decorators import Permission

if TYPE_CHECKING:
    from src.core.framework.context import Context
    from src.core.registries.permission_registry import PermissionRegistry
    from src.core.services.permission import FeaturePermissionService
    from src.core.services.personnel import PersonnelService

logger = structlog.get_logger()


class FeaturePermissionChecker:
    """统一权限检查器：功能级权限 + 角色级权限，单次 check() 完成全部校验。

    检查顺序：
    1. 系统级功能（system=True）零 IO 直接通过
    2. 超级管理员绕过所有权限（单次 IO，合并原分发器中的重复查询）
    3. ADMIN 权限要求：非管理员直接拒绝
    4. 群聊 → 群 bot 总开关 → 功能启用检查 → 角色检查（无 IO）
    5. 私聊 → 功能允许检查
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

        ctrl_feature: str = handler.component_name
        method_feature: str = f"{handler.component_name}.{handler.method_name}"
        required: Permission = handler.permission

        # 零 IO 快速路径：系统级功能（PermissionRegistry 内存快照）始终允许
        if self._perm_registry is not None and self._perm_registry.is_system(ctrl_feature):
            return True
        if self._perm_registry is None:
            logger.warning(
                "PermissionRegistry 未注入，跳过系统功能快速路径",
                event_type="permission.registry_missing",
            )

        # 超级管理员绕过所有权限（统一单次 IO 查询，消除原分发器中的重复查询）
        admin_set = await self._personnel_service.get_admin_qq_set()
        if ctx.user_id in admin_set:
            return True

        # ADMIN 权限：非管理员直接拒绝
        if required == Permission.ADMIN:
            logger.debug(
                "角色权限拒绝：需要 ADMIN",
                user_id=ctx.user_id,
                event_type="permission.role_denied",
            )
            return False

        # 功能级权限检查（含角色检查）
        if ctx.is_group:
            return await self._check_group(ctx, ctrl_feature, method_feature, required)
        return await self._check_private(ctx, ctrl_feature, method_feature)

    async def _check_group(
        self,
        ctx: Context,
        ctrl_feature: str,
        method_feature: str,
        required: Permission,
    ) -> bool:
        """群聊权限检查：总开关 → 功能启用 → 角色。"""
        group_id = ctx.group_id
        if group_id is None:
            return True

        if not await self._service.is_group_enabled(group_id):
            logger.debug(
                "群 bot 总开关关闭",
                group_id=group_id,
                user_id=ctx.user_id,
                event_type="permission.group_disabled",
            )
            return False

        if not await self._service.is_group_feature_enabled(group_id, ctrl_feature, method_feature):
            logger.debug(
                "功能权限拒绝",
                controller=ctrl_feature,
                method=method_feature,
                user_id=ctx.user_id,
                group_id=group_id,
                event_type="permission.feature_denied",
            )
            return False

        return self._check_group_role(ctx, required)

    async def _check_private(self, ctx: Context, ctrl_feature: str, method_feature: str) -> bool:
        """私聊权限检查（以 controller 级为粒度）。"""
        allowed = await self._service.is_private_feature_allowed(
            ctrl_feature, method_feature, ctx.user_id
        )
        if not allowed:
            logger.debug(
                "功能权限拒绝",
                controller=ctrl_feature,
                method=method_feature,
                user_id=ctx.user_id,
                event_type="permission.feature_denied",
            )
        return allowed

    def _check_group_role(self, ctx: Context, required: Permission) -> bool:
        """群聊角色级权限检查（无 IO，同步方法，勿加 await）。"""
        if required in (Permission.ANYONE, Permission.GROUP_MEMBER):
            # ctx.is_group=True 时发送者已隐含为群成员，两者等价放行
            return True
        sender = getattr(ctx.event, "sender", None)
        role: str = getattr(sender, "role", "member") if sender else "member"
        if required == Permission.GROUP_OWNER:
            if role != "owner":
                logger.debug(
                    "角色权限拒绝：需要 GROUP_OWNER",
                    user_id=ctx.user_id,
                    event_type="permission.role_denied",
                )
                return False
            return True
        if required == Permission.GROUP_ADMIN:
            if role not in ("admin", "owner"):
                logger.debug(
                    "角色权限拒绝：需要 GROUP_ADMIN",
                    user_id=ctx.user_id,
                    event_type="permission.role_denied",
                )
                return False
            return True
        # 未知 Permission 值，保守拒绝以防权限枚举扩展时静默漏洞
        logger.warning(
            "未知权限等级，保守拒绝",
            required=int(required),
            user_id=ctx.user_id,
            event_type="permission.unknown_level",
        )
        return False
