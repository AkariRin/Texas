"""功能级权限服务 —— 管理功能启用状态、群/私聊权限。

feature_registry 表已移除，功能元数据由内存不可变 FeatureRegistry 维护。
permission_group / permission_private 存储全量记录，无需回退逻辑。
group_id=0 哨兵行代表功能的全局默认启用状态。
"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.core.cache.key_registry import cache_key
from src.models.permission import GroupFeaturePermission, PrivateFeaturePermission
from src.models.personnel import Group

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from src.core.cache.client import CacheClient
    from src.core.framework.feature_registry import FeatureRegistry

logger = structlog.get_logger()

# 缓存 TTL（秒）
_CACHE_TTL = 60

# 缓存键定义（遵循 texas: 命名空间前缀规范）
_key_group = cache_key(
    "perm.group",
    "texas:perm:group:{group_id}:{feature}",
    ttl_hint=60,
    description="群功能权限缓存。",
)
_key_private = cache_key(
    "perm.private",
    "texas:perm:private:{feature}:{qq}",
    ttl_hint=60,
    description="私聊功能权限缓存。",
)
_key_group_enabled = cache_key(
    "perm.group_enabled",
    "texas:perm:group_enabled:{group_id}",
    ttl_hint=60,
    description="群 bot 总开关缓存。",
)

# group_id=0 哨兵值，代表功能全局默认启用状态
_GLOBAL_GROUP_ID = 0


class FeaturePermissionService:
    """功能级权限服务。"""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        cache: CacheClient,
        registry: FeatureRegistry,
    ) -> None:
        self._factory = session_factory
        self._cache = cache
        self._registry = registry

    @property
    def registry(self) -> FeatureRegistry:
        """只读访问内存功能注册表。"""
        return self._registry

    # ─────────────────────── 权限同步 ───────────────────────

    async def sync_permissions(self) -> None:
        """启动时同步全量权限记录。

        1. 为每个活跃功能确保 group_id=0 全局哨兵行存在（缺失则以 default_enabled 填充）。
        2. 为每个活跃群确保每个活跃功能都有对应权限行（缺失则以 default_enabled 填充）。
        3. 清理不再存在的功能对应的权限行。
        """
        active_feature_names = list(self._registry.non_system_names())
        if not active_feature_names:
            return

        async with self._factory() as session:
            # ── 获取所有活跃群 ID ──
            group_rows = await session.execute(
                select(Group.group_id).where(Group.is_active.is_(True))
            )
            active_group_ids: list[int] = [r for (r,) in group_rows.all()]

            # ── 查询已有 permission_group 行（含哨兵行） ──
            existing_rows = await session.execute(
                select(GroupFeaturePermission.group_id, GroupFeaturePermission.feature_name)
            )
            existing: set[tuple[int, str]] = {(r.group_id, r.feature_name) for r in existing_rows}

            # ── 计算缺失的记录 ──
            all_group_ids = [_GLOBAL_GROUP_ID, *active_group_ids]
            missing: list[dict[str, Any]] = []
            for gid in all_group_ids:
                for fname in active_feature_names:
                    if (gid, fname) not in existing:
                        meta = self._registry.get(fname)
                        default = meta.default_enabled if meta is not None else True
                        missing.append(
                            {
                                "id": uuid.uuid4(),
                                "group_id": gid,
                                "feature_name": fname,
                                "enabled": default,
                            }
                        )

            # ── 批量插入缺失记录 ──
            if missing:
                stmt = pg_insert(GroupFeaturePermission).values(missing)
                stmt = stmt.on_conflict_do_nothing(constraint="uq_group_feature")
                await session.execute(stmt)

            # ── 清理不再活跃的功能权限行 ──
            await session.execute(
                delete(GroupFeaturePermission).where(
                    GroupFeaturePermission.feature_name.not_in(active_feature_names)
                )
            )
            await session.execute(
                delete(PrivateFeaturePermission).where(
                    PrivateFeaturePermission.feature_name.not_in(active_feature_names)
                )
            )

            await session.commit()

        logger.info(
            "权限记录同步完成",
            total_features=len(active_feature_names),
            total_groups=len(active_group_ids),
            missing_inserted=len(missing),
            event_type="permission.sync_complete",
        )

    async def sync_group_permissions(self, group_id: int) -> None:
        """新群加入时，为该群批量插入全量功能权限记录。"""
        active_feature_names = list(self._registry.non_system_names())
        if not active_feature_names:
            return

        async with self._factory() as session:
            values = [
                {
                    "id": uuid.uuid4(),
                    "group_id": group_id,
                    "feature_name": fname,
                    "enabled": self._registry[fname].default_enabled
                    if fname in self._registry
                    else True,
                }
                for fname in active_feature_names
            ]
            stmt = pg_insert(GroupFeaturePermission).values(values)
            stmt = stmt.on_conflict_do_nothing(constraint="uq_group_feature")
            await session.execute(stmt)
            await session.commit()

        logger.info(
            "新群权限记录已初始化",
            group_id=group_id,
            feature_count=len(active_feature_names),
            event_type="permission.group_sync",
        )

    # ─────────────────────── 权限查询 ───────────────────────

    async def is_group_feature_enabled(
        self,
        group_id: int,
        ctrl_feature: str,
        method_feature: str,
    ) -> bool:
        """两级群聊权限查询（并发查缓存/DB，减少热路径延迟）。"""
        ctrl_enabled, method_enabled = await asyncio.gather(
            self._get_group_feature(group_id, ctrl_feature),
            self._get_group_feature(group_id, method_feature),
        )
        return ctrl_enabled and method_enabled

    async def _get_group_feature(self, group_id: int, feature_name: str) -> bool:
        """获取群聊某功能的启用状态（含缓存）。"""
        key = _key_group(group_id=group_id, feature=feature_name)
        cached = await self._cache.get(key)
        if cached is not None:
            return bool(cached)

        result = await self._query_group_feature(group_id, feature_name)
        await self._cache.set(key, result, ttl=_CACHE_TTL)
        return result

    async def _query_group_feature(self, group_id: int, feature_name: str) -> bool:
        """从数据库查询群聊功能状态（全量记录，无需回退到 Feature 表）。"""
        async with self._factory() as session:
            row = await session.execute(
                select(GroupFeaturePermission.enabled).where(
                    GroupFeaturePermission.group_id == group_id,
                    GroupFeaturePermission.feature_name == feature_name,
                )
            )
            enabled = row.scalar_one_or_none()
            if enabled is not None:
                return bool(enabled)

        # 极少发生（新功能上线但 sync 尚未完成）：回退到内存注册表默认值
        meta = self._registry.get(feature_name)
        return meta.default_enabled if meta is not None else True

    async def is_private_feature_allowed(
        self,
        ctrl_feature: str,
        method_feature: str,  # noqa: ARG002 — 私聊以 controller 级为粒度
        user_qq: int,
    ) -> bool:
        """私聊权限查询（以 controller 级为粒度）。"""
        key = _key_private(feature=ctrl_feature, qq=user_qq)
        cached = await self._cache.get(key)
        if cached is not None:
            return bool(cached)

        result = await self._query_private_feature(ctrl_feature, user_qq)
        await self._cache.set(key, result, ttl=_CACHE_TTL)
        return result

    async def _query_private_feature(self, feature_name: str, user_qq: int) -> bool:
        """从数据库查询私聊功能状态（优先查用户显式设置，再查全局默认）。"""
        async with self._factory() as session:
            # 优先查用户显式设置
            user_row = await session.execute(
                select(PrivateFeaturePermission.enabled).where(
                    PrivateFeaturePermission.feature_name == feature_name,
                    PrivateFeaturePermission.user_qq == user_qq,
                )
            )
            user_enabled = user_row.scalar_one_or_none()
            if user_enabled is not None:
                return bool(user_enabled)

            # 回退到全局默认（group_id=0 哨兵行）
            global_row = await session.execute(
                select(GroupFeaturePermission.enabled).where(
                    GroupFeaturePermission.group_id == _GLOBAL_GROUP_ID,
                    GroupFeaturePermission.feature_name == feature_name,
                )
            )
            global_enabled = global_row.scalar_one_or_none()
            if global_enabled is not None:
                return bool(global_enabled)

        # 最终回退：内存注册表默认值
        meta = self._registry.get(feature_name)
        return meta.default_enabled if meta is not None else True

    # ─────────────────────── 管理 API ───────────────────────

    async def list_features(self) -> list[dict[str, Any]]:
        """列出所有活跃功能（树状结构：controller → methods），过滤系统功能。

        功能元数据来自内存注册表，当前 enabled 状态来自 group_id=0 哨兵行。
        """
        async with self._factory() as session:
            global_rows = await session.execute(
                select(
                    GroupFeaturePermission.feature_name,
                    GroupFeaturePermission.enabled,
                ).where(GroupFeaturePermission.group_id == _GLOBAL_GROUP_ID)
            )
            global_enabled: dict[str, bool] = {r.feature_name: r.enabled for r in global_rows}

        return self._registry.non_system_tree(global_enabled)

    async def update_feature(
        self,
        name: str,
        enabled: bool | None = None,
    ) -> dict[str, Any] | None:
        """更新功能全局启用状态（写入 group_id=0 哨兵行），返回更新后的状态。"""
        if enabled is None:
            return None

        # 功能必须存在于注册表
        meta = self._registry.get(name)
        if meta is None:
            return None

        async with self._factory() as session:
            stmt = pg_insert(GroupFeaturePermission).values(
                id=uuid.uuid4(),
                group_id=_GLOBAL_GROUP_ID,
                feature_name=name,
                enabled=enabled,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_group_feature",
                set_={"enabled": enabled},
            )
            await session.execute(stmt)
            await session.commit()

        # 清全局缓存（group_id=0 哨兵行对应的缓存键）
        await self._cache.delete(_key_group(group_id=_GLOBAL_GROUP_ID, feature=name))

        return {"name": name, "enabled": enabled}

    async def is_group_enabled(self, group_id: int) -> bool:
        """查询群 bot 总开关（含缓存）。"""
        key = _key_group_enabled(group_id=group_id)
        cached = await self._cache.get(key)
        if cached is not None:
            return bool(cached)

        async with self._factory() as session:
            row = await session.execute(select(Group.bot_enabled).where(Group.group_id == group_id))
            enabled = row.scalar_one_or_none()
            result = bool(enabled) if enabled is not None else True

        await self._cache.set(key, result, ttl=_CACHE_TTL)
        return result

    async def set_group_enabled(self, group_id: int, enabled: bool) -> None:
        """设置群 bot 总开关。"""
        async with self._factory() as session:
            await session.execute(
                update(Group).where(Group.group_id == group_id).values(bot_enabled=enabled)
            )
            await session.commit()
        await self._cache.delete(_key_group_enabled(group_id=group_id))

    async def get_group_permissions(self, group_id: int) -> list[dict[str, Any]]:
        """获取某群所有功能的权限状态（全量记录，无需回退）。"""
        async with self._factory() as session:
            perm_rows = await session.execute(
                select(GroupFeaturePermission).where(GroupFeaturePermission.group_id == group_id)
            )
            perms: dict[str, bool] = {p.feature_name: p.enabled for p in perm_rows.scalars().all()}

        result = []
        for fname in sorted(self._registry.non_system_names()):
            meta = self._registry.get(fname)
            if meta is None:
                continue
            result.append(
                {
                    "feature_name": fname,
                    "display_name": meta.display_name,
                    "enabled": perms.get(fname, meta.default_enabled),
                    "parent": meta.parent,
                }
            )
        return result

    async def set_group_feature(self, group_id: int, feature_name: str, enabled: bool) -> None:
        """设置（或更新）群对某功能的启用状态。"""
        async with self._factory() as session:
            stmt = pg_insert(GroupFeaturePermission).values(
                id=uuid.uuid4(),
                group_id=group_id,
                feature_name=feature_name,
                enabled=enabled,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_group_feature",
                set_={"enabled": enabled},
            )
            await session.execute(stmt)
            await session.commit()

        await self._cache.delete(_key_group(group_id=group_id, feature=feature_name))

    async def batch_set_group_features(self, group_id: int, features: list[dict[str, Any]]) -> None:
        """批量设置群功能状态（单事务原子操作）。features: [{feature_name, enabled}]"""
        if not features:
            return

        async with self._factory() as session:
            values = [
                {
                    "id": uuid.uuid4(),
                    "group_id": group_id,
                    "feature_name": item["feature_name"],
                    "enabled": item["enabled"],
                }
                for item in features
            ]
            stmt = pg_insert(GroupFeaturePermission).values(values)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_group_feature",
                set_={"enabled": stmt.excluded.enabled},
            )
            await session.execute(stmt)
            await session.commit()

        await asyncio.gather(
            *[
                self._cache.delete(_key_group(group_id=group_id, feature=item["feature_name"]))
                for item in features
            ]
        )

    async def get_private_permissions(self, feature_name: str) -> list[dict[str, Any]]:
        """获取某功能的私聊用户权限列表（含显式 enabled 状态）。"""
        async with self._factory() as session:
            rows = await session.execute(
                select(
                    PrivateFeaturePermission.user_qq,
                    PrivateFeaturePermission.enabled,
                ).where(PrivateFeaturePermission.feature_name == feature_name)
            )
            return [{"user_qq": r.user_qq, "enabled": r.enabled} for r in rows.all()]

    async def set_private_permission(
        self,
        feature_name: str,
        user_qq: int,
        enabled: bool,
    ) -> None:
        """设置用户私聊权限（upsert）。"""
        async with self._factory() as session:
            stmt = pg_insert(PrivateFeaturePermission).values(
                id=uuid.uuid4(),
                feature_name=feature_name,
                user_qq=user_qq,
                enabled=enabled,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_private_feature_user",
                set_={"enabled": enabled},
            )
            await session.execute(stmt)
            await session.commit()

        await self._cache.delete(_key_private(feature=feature_name, qq=user_qq))

    async def remove_private_user(self, feature_name: str, user_qq: int) -> None:
        """删除用户私聊权限记录（恢复为全局默认）。"""
        async with self._factory() as session:
            await session.execute(
                delete(PrivateFeaturePermission).where(
                    PrivateFeaturePermission.feature_name == feature_name,
                    PrivateFeaturePermission.user_qq == user_qq,
                )
            )
            await session.commit()

        await self._cache.delete(_key_private(feature=feature_name, qq=user_qq))

    async def get_help_features_for_group(
        self,
        group_id: int,
        is_admin: bool,
    ) -> list[dict[str, Any]]:
        """批量查询群聊帮助功能列表（仅返回该群已启用的功能）。

        Args:
            group_id: 群号。
            is_admin: 请求者是否为超级管理员，为 False 时过滤 admin=True 的功能。

        Returns:
            controller 级功能列表，每项含 tag / display_name / description / admin / methods。
            methods 为通过权限检查的子命令列表，每项含 display_name / description / trigger。

        注意：此方法直接查 DB，绕过单条功能的缓存层（_get_group_feature）。
        帮助页一次性批量获取，单次查询比 N 次缓存命中更高效；权限变更后的缓存不一致
        对帮助页展示可接受（帮助卡不是安全边界，权限执行在 FeaturePermissionChecker）。
        群聊权限行由 sync_permissions 启动时预填充，无需回退到全局哨兵（group_id=0）；
        私聊则需三级合并（用户显式 → 全局哨兵 → registry 默认）。
        """
        # ── 单次批量查询权限记录（含 controller 和 method 两级） ──
        async with self._factory() as session:
            perm_rows = await session.execute(
                select(
                    GroupFeaturePermission.feature_name,
                    GroupFeaturePermission.enabled,
                ).where(GroupFeaturePermission.group_id == group_id)
            )
            perms: dict[str, bool] = {r.feature_name: r.enabled for r in perm_rows.all()}

        result: list[dict[str, Any]] = []
        _group_scopes = frozenset(("all", "group"))

        for fname in sorted(self._registry.non_system_names()):
            meta = self._registry.get(fname)
            if meta is None or meta.parent is not None:
                # 跳过 method 级条目，只处理 controller 级
                continue
            if meta.message_scope not in _group_scopes:
                continue
            if not is_admin and meta.admin:
                continue

            # controller 启用状态
            ctrl_enabled = perms.get(fname, meta.default_enabled)
            if not ctrl_enabled:
                continue

            # 收集通过权限检查的子命令
            methods: list[dict[str, Any]] = []
            for child_name in meta.children:
                child = self._registry.get(child_name)
                if child is None:
                    continue
                if not is_admin and child.admin:
                    continue
                if child.message_scope not in _group_scopes:
                    continue
                child_enabled = perms.get(child_name, child.default_enabled)
                if not child_enabled:
                    continue
                methods.append(
                    {
                        "display_name": child.display_name,
                        "description": child.description,
                        "trigger": child.trigger,
                    }
                )

            result.append(
                {
                    "tag": meta.tags[0] if meta.tags else "",
                    "display_name": meta.display_name,
                    "description": meta.description,
                    "admin": meta.admin,
                    "methods": methods,
                }
            )

        return result

    async def get_help_features_for_private(
        self,
        user_qq: int,
        is_admin: bool,
    ) -> list[dict[str, Any]]:
        """批量查询私聊帮助功能列表（仅返回该用户可使用的私聊功能）。

        Args:
            user_qq: 用户 QQ 号。
            is_admin: 请求者是否为超级管理员。

        Returns:
            格式与 get_help_features_for_group 相同，message_scope 过滤为 all/private。
        """
        # ── 顺序执行两次查询（AsyncSession 单连接不支持并发 execute） ──
        # 用户显式权限 + 全局哨兵行（group_id=0），两次 I/O 均 < 1ms，无需并发
        async with self._factory() as session:
            user_result = await session.execute(
                select(
                    PrivateFeaturePermission.feature_name,
                    PrivateFeaturePermission.enabled,
                ).where(PrivateFeaturePermission.user_qq == user_qq)
            )
            global_result = await session.execute(
                select(
                    GroupFeaturePermission.feature_name,
                    GroupFeaturePermission.enabled,
                ).where(GroupFeaturePermission.group_id == _GLOBAL_GROUP_ID)
            )
            user_perms: dict[str, bool] = {r.feature_name: r.enabled for r in user_result.all()}
            global_perms: dict[str, bool] = {r.feature_name: r.enabled for r in global_result.all()}

        def _is_enabled(feature_name: str, default: bool) -> bool:
            """合并优先级：用户显式 > 全局哨兵 > registry 默认。"""
            if feature_name in user_perms:
                return user_perms[feature_name]
            if feature_name in global_perms:
                return global_perms[feature_name]
            return default

        result: list[dict[str, Any]] = []
        _private_scopes = frozenset(("all", "private"))

        for fname in sorted(self._registry.non_system_names()):
            meta = self._registry.get(fname)
            if meta is None or meta.parent is not None:
                continue
            if meta.message_scope not in _private_scopes:
                continue
            if not is_admin and meta.admin:
                continue
            if not _is_enabled(fname, meta.default_enabled):
                continue

            methods: list[dict[str, Any]] = []
            for child_name in meta.children:
                child = self._registry.get(child_name)
                if child is None:
                    continue
                if not is_admin and child.admin:
                    continue
                if child.message_scope not in _private_scopes:
                    continue
                if not _is_enabled(child_name, child.default_enabled):
                    continue
                methods.append(
                    {
                        "display_name": child.display_name,
                        "description": child.description,
                        "trigger": child.trigger,
                    }
                )

            result.append(
                {
                    "tag": meta.tags[0] if meta.tags else "",
                    "display_name": meta.display_name,
                    "description": meta.description,
                    "admin": meta.admin,
                    "methods": methods,
                }
            )

        return result

    async def get_permission_matrix(self) -> dict[str, Any]:
        """获取完整权限矩阵（所有活跃群 × 所有活跃功能，过滤系统功能）。"""
        async with self._factory() as session:
            # 所有群
            group_rows = await session.execute(
                select(Group.group_id, Group.bot_enabled).where(Group.is_active.is_(True))
            )
            groups = group_rows.all()

            # 所有权限行（含哨兵行）
            perm_rows = await session.execute(select(GroupFeaturePermission))
            perms: dict[tuple[int, str], bool] = {
                (p.group_id, p.feature_name): p.enabled for p in perm_rows.scalars().all()
            }

        # 全局默认（group_id=0 哨兵行）
        global_enabled: dict[str, bool] = {
            fname: perms.get((_GLOBAL_GROUP_ID, fname), self._registry[fname].default_enabled)
            for fname in self._registry.non_system_names()
            if fname in self._registry
        }

        # features 树从注册表构建，enabled 来自全局哨兵行
        features_tree = self._registry.non_system_tree(global_enabled)

        # 所有非系统功能名称
        all_feature_names = list(self._registry.non_system_names())

        return {
            "features": features_tree,
            "groups": [
                {
                    "group_id": g.group_id,
                    "bot_enabled": g.bot_enabled,
                    "permissions": {
                        fname: perms.get((g.group_id, fname), global_enabled.get(fname, True))
                        for fname in all_feature_names
                    },
                }
                for g in groups
            ],
        }


# ── 生命周期注册 ──

from src.core.lifecycle import startup  # noqa: E402


@startup(
    name="permission",
    provides=["permission_service"],
    requires=["session_factory", "cache_client", "scanner", "dispatcher", "personnel_service"],
)
async def _lifecycle_start(deps: dict[str, Any]) -> dict[str, Any]:
    """权限系统启动：同步全量权限记录并注入 dispatcher。"""
    from src.core.framework.permission_checker import FeaturePermissionChecker

    scanner = deps["scanner"]
    permission_service = FeaturePermissionService(
        session_factory=deps["session_factory"],
        cache=deps["cache_client"],
        registry=scanner.feature_registry,
    )
    await permission_service.sync_permissions()
    checker = FeaturePermissionChecker(
        permission_service=permission_service,
        personnel_service=deps["personnel_service"],
    )
    dispatcher = deps["dispatcher"]
    dispatcher.feature_checker = checker
    dispatcher.personnel_service = deps["personnel_service"]
    logger.info("权限系统已就绪", event_type="permission.ready")
    return {"permission_service": permission_service}
