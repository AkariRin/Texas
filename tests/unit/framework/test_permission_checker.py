"""FeaturePermissionChecker 单元测试 —— 覆盖全部权限检查路径。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from src.core.framework.decorators import Permission
from src.core.framework.mapping import HandlerMethod
from src.core.permission.checker import FeaturePermissionChecker
from tests.conftest import make_group_message_event, make_private_message_event

# ── 辅助工厂 ─────────────────────────────────────────────────────────────────


def _make_handler_method(
    component_name: str = "test_feature",
    method_name: str = "handle",
    permission: Permission = Permission.ANYONE,
) -> HandlerMethod:
    """构造测试用 HandlerMethod。"""
    return HandlerMethod(
        component=MagicMock(),
        method=MagicMock(),
        permission=permission,
        component_name=component_name,
        method_name=method_name,
    )


def _make_checker(
    *,
    is_group_enabled: bool = True,
    is_group_feature_enabled: bool = True,
    is_private_feature_allowed: bool = True,
    admin_set: set[int] | None = None,
    perm_registry_is_system: bool = False,
    include_perm_registry: bool = True,
) -> FeaturePermissionChecker:
    """构造权限检查器，所有依赖均为 Mock。"""
    permission_service = MagicMock()
    permission_service.is_group_enabled = AsyncMock(return_value=is_group_enabled)
    permission_service.is_group_feature_enabled = AsyncMock(return_value=is_group_feature_enabled)
    permission_service.is_private_feature_allowed = AsyncMock(
        return_value=is_private_feature_allowed
    )

    personnel_service = MagicMock()
    personnel_service.get_admin_qq_set = AsyncMock(return_value=admin_set or set())

    perm_registry = None
    if include_perm_registry:
        perm_registry = MagicMock()
        perm_registry.is_system = MagicMock(return_value=perm_registry_is_system)

    return FeaturePermissionChecker(
        permission_service=permission_service,
        personnel_service=personnel_service,
        perm_registry=perm_registry,
    )


def _make_group_ctx(
    user_id: int = 10001,
    group_id: int = 100,
    role: str = "member",
    permission: Permission = Permission.ANYONE,
) -> MagicMock:
    """构造群聊上下文（基于真实 Context 对象）。"""
    from src.core.framework.context import Context

    event = make_group_message_event(user_id=user_id, group_id=group_id, role=role)
    ctx = Context(event=event, bot=MagicMock(), services={})
    ctx.handler_method = _make_handler_method(permission=permission)
    return ctx  # type: ignore[return-value]


def _make_private_ctx(
    user_id: int = 10001,
    permission: Permission = Permission.ANYONE,
) -> MagicMock:
    """构造私聊上下文（基于真实 Context 对象）。"""
    from src.core.framework.context import Context

    event = make_private_message_event(user_id=user_id)
    ctx = Context(event=event, bot=MagicMock(), services={})
    ctx.handler_method = _make_handler_method(permission=permission)
    return ctx  # type: ignore[return-value]


# ── 测试类 ────────────────────────────────────────────────────────────────────


class TestPermissionCheckerFastPaths:
    """快速路径测试：handler_method 为 None 和系统级功能直通。"""

    async def test_handler_method_none_returns_true(self) -> None:
        """handler_method 为 None 时直接返回 True，不查询任何服务。"""
        from src.core.framework.context import Context

        event = make_group_message_event()
        ctx = Context(event=event, bot=MagicMock(), services={})
        # ctx.handler_method 默认为 None

        checker = _make_checker()
        result = await checker.check(ctx)

        assert result is True
        # 系统级功能不应被查询
        checker._perm_registry.is_system.assert_not_called()  # type: ignore[union-attr]
        # 不应查询管理员列表
        checker._personnel_service.get_admin_qq_set.assert_not_called()

    async def test_system_feature_bypasses_all_checks(self) -> None:
        """perm_registry.is_system 返回 True 时直接放行，不查询数据库。"""
        ctx = _make_group_ctx()
        checker = _make_checker(perm_registry_is_system=True)

        result = await checker.check(ctx)

        assert result is True
        # 管理员列表不应被查询
        checker._personnel_service.get_admin_qq_set.assert_not_called()

    async def test_non_system_feature_proceeds_to_next_check(self) -> None:
        """非系统功能正常进入后续检查，不被 is_system 快速放行。"""
        ctx = _make_group_ctx()
        # 非系统功能，群总开关开启，功能启用，ANYONE 权限
        checker = _make_checker(perm_registry_is_system=False)

        result = await checker.check(ctx)

        assert result is True
        # is_system 已被调用
        checker._perm_registry.is_system.assert_called_once()  # type: ignore[union-attr]
        # 管理员列表也被查询
        checker._personnel_service.get_admin_qq_set.assert_awaited_once()

    async def test_no_perm_registry_still_works(self) -> None:
        """未注入 PermissionRegistry 时，跳过系统功能检查，继续后续流程。"""
        ctx = _make_group_ctx()
        checker = _make_checker(include_perm_registry=False)

        result = await checker.check(ctx)

        # 群聊、总开关开启、功能启用、ANYONE 权限 → 放行
        assert result is True


class TestPermissionCheckerAdminBypass:
    """超级管理员绕过测试。"""

    async def test_admin_bypasses_permission(self) -> None:
        """ctx.user_id 在 admin_set 中时，无论 required 是什么都放行。"""
        user_id = 10001
        ctx = _make_group_ctx(user_id=user_id, permission=Permission.ADMIN)
        # 功能被 is_group_feature_enabled 关闭，但管理员应绕过
        checker = _make_checker(
            admin_set={user_id},
            is_group_feature_enabled=False,
        )

        result = await checker.check(ctx)

        assert result is True

    async def test_non_admin_not_bypassed(self) -> None:
        """ctx.user_id 不在 admin_set 中时，不触发管理员绕过。"""
        user_id = 10001
        ctx = _make_group_ctx(user_id=user_id, permission=Permission.ADMIN)
        checker = _make_checker(admin_set={99999})  # 不同用户

        result = await checker.check(ctx)

        # 需要 ADMIN 权限但非管理员 → False
        assert result is False

    async def test_admin_bypasses_disabled_feature(self) -> None:
        """超级管理员绕过功能禁用限制。"""
        user_id = 10001
        ctx = _make_group_ctx(user_id=user_id, permission=Permission.ANYONE)
        checker = _make_checker(
            admin_set={user_id},
            is_group_enabled=False,  # 总开关关闭
        )

        result = await checker.check(ctx)

        assert result is True


class TestPermissionCheckerAdminRequired:
    """ADMIN 权限要求测试。"""

    async def test_non_admin_user_denied_when_admin_required(self) -> None:
        """required == Permission.ADMIN 且非管理员用户 → 拒绝。"""
        user_id = 10001
        ctx = _make_group_ctx(user_id=user_id, permission=Permission.ADMIN)
        checker = _make_checker(admin_set=set())  # 空集合，没有管理员

        result = await checker.check(ctx)

        assert result is False


class TestPermissionCheckerGroupChecks:
    """群聊权限检查路径测试。"""

    async def test_group_bot_disabled_returns_false(self) -> None:
        """群 bot 总开关关闭时拒绝所有请求。"""
        ctx = _make_group_ctx()
        checker = _make_checker(is_group_enabled=False)

        result = await checker.check(ctx)

        assert result is False

    async def test_group_feature_disabled_returns_false(self) -> None:
        """群功能被禁用时拒绝请求。"""
        ctx = _make_group_ctx()
        checker = _make_checker(is_group_feature_enabled=False)

        result = await checker.check(ctx)

        assert result is False

    async def test_member_denied_for_group_admin_permission(self) -> None:
        """普通 member 无法通过 GROUP_ADMIN 权限要求。"""
        ctx = _make_group_ctx(role="member", permission=Permission.GROUP_ADMIN)
        checker = _make_checker()

        result = await checker.check(ctx)

        assert result is False

    async def test_admin_passes_group_admin_permission(self) -> None:
        """群管理员（role=admin）可以通过 GROUP_ADMIN 权限要求。"""
        ctx = _make_group_ctx(role="admin", permission=Permission.GROUP_ADMIN)
        checker = _make_checker()

        result = await checker.check(ctx)

        assert result is True

    async def test_owner_passes_group_owner_permission(self) -> None:
        """群主（role=owner）可以通过 GROUP_OWNER 权限要求。"""
        ctx = _make_group_ctx(role="owner", permission=Permission.GROUP_OWNER)
        checker = _make_checker()

        result = await checker.check(ctx)

        assert result is True

    async def test_member_denied_for_group_owner_permission(self) -> None:
        """普通 member 无法通过 GROUP_OWNER 权限要求。"""
        ctx = _make_group_ctx(role="member", permission=Permission.GROUP_OWNER)
        checker = _make_checker()

        result = await checker.check(ctx)

        assert result is False

    async def test_member_passes_anyone_permission(self) -> None:
        """ANYONE 权限放行所有群成员（包括 member 角色）。"""
        ctx = _make_group_ctx(role="member", permission=Permission.ANYONE)
        checker = _make_checker()

        result = await checker.check(ctx)

        assert result is True

    async def test_member_passes_group_member_permission(self) -> None:
        """GROUP_MEMBER 与 ANYONE 等价，放行所有群成员。"""
        ctx = _make_group_ctx(role="member", permission=Permission.GROUP_MEMBER)
        checker = _make_checker()

        result = await checker.check(ctx)

        assert result is True

    async def test_owner_also_passes_group_admin_permission(self) -> None:
        """群主（role=owner）同样可以通过 GROUP_ADMIN 权限要求（高权限兼容低要求）。"""
        ctx = _make_group_ctx(role="owner", permission=Permission.GROUP_ADMIN)
        checker = _make_checker()

        result = await checker.check(ctx)

        assert result is True


class TestPermissionCheckerPrivateChecks:
    """私聊权限检查路径测试。"""

    async def test_private_feature_allowed_returns_true(self) -> None:
        """私聊功能允许时返回 True。"""
        ctx = _make_private_ctx()
        checker = _make_checker(is_private_feature_allowed=True)

        result = await checker.check(ctx)

        assert result is True

    async def test_private_feature_not_allowed_returns_false(self) -> None:
        """私聊功能不允许时返回 False。"""
        ctx = _make_private_ctx()
        checker = _make_checker(is_private_feature_allowed=False)

        result = await checker.check(ctx)

        assert result is False

    async def test_private_check_calls_service_with_correct_args(self) -> None:
        """私聊检查时使用正确的 ctrl_feature 和 method_feature 参数调用 service。"""
        user_id = 20001
        ctx = _make_private_ctx(user_id=user_id)
        hm = _make_handler_method(component_name="my_feature", method_name="my_method")
        ctx.handler_method = hm

        checker = _make_checker(is_private_feature_allowed=True)
        await checker.check(ctx)

        checker._service.is_private_feature_allowed.assert_awaited_once_with(
            "my_feature", "my_feature.my_method", user_id
        )
