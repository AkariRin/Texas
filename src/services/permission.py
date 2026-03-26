"""功能级权限服务 —— 管理功能注册、启用状态、群/私聊权限。"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.models.permission import Feature, GroupFeaturePermission, PrivateFeaturePermission
from src.models.personnel import Group

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from src.core.cache.client import CacheClient

logger = structlog.get_logger()

# 缓存 TTL（秒）
_CACHE_TTL = 60
_KEY_GROUP = "perm:group:{group_id}:{feature}"
_KEY_PRIVATE = "perm:private:{feature}:{qq}"


class FeaturePermissionService:
    """功能级权限服务。"""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        cache: CacheClient,
        metadata_provider: dict[str, Any] | None = None,
    ) -> None:
        self._factory = session_factory
        self._cache = cache
        # 内存元数据：由 ComponentScanner.feature_metadata 注入，不经 DB 存储
        self._metadata: dict[str, Any] = metadata_provider or {}

    # ─────────────────────── 功能同步 ───────────────────────

    async def sync_features(self, controllers: list[dict[str, Any]]) -> None:
        """启动时将扫描到的 controller/method 同步到功能注册表。

        规则：
        - 已存在记录：仅更新 display_name / description / is_active，不覆盖 enabled / private_mode。
        - 不存在记录：插入新记录，使用装饰器声明的 default_enabled。
        - 代码中已删除的功能：标记 is_active=False，保留历史配置。
        """
        async with self._factory() as session:
            # 收集代码中所有活跃功能名
            active_names: set[str] = set()
            upserts: list[dict[str, Any]] = []

            for ctrl in controllers:
                ctrl_name: str = ctrl["name"]
                ctrl_enabled: bool = ctrl.get("default_enabled", False)
                active_names.add(ctrl_name)

                upserts.append(
                    {
                        "name": ctrl_name,
                        "parent": None,
                        "display_name": ctrl.get("display_name") or ctrl_name,
                        "description": ctrl.get("description", ""),
                        "default_enabled": ctrl_enabled,
                        "is_active": True,
                    }
                )

                for method in ctrl.get("methods", []):
                    method_name: str = f"{ctrl_name}.{method['method']}"
                    # method 级 default_enabled：None 表示跟随 controller
                    method_enabled_raw = method.get("default_enabled")
                    method_enabled = (
                        ctrl_enabled if method_enabled_raw is None else method_enabled_raw
                    )
                    active_names.add(method_name)

                    upserts.append(
                        {
                            "name": method_name,
                            "parent": ctrl_name,
                            "display_name": method.get("display_name") or method["method"],
                            "description": method.get("description", ""),
                            "default_enabled": method_enabled,
                            "is_active": True,
                        }
                    )

            # 批量 upsert（仅更新展示信息，不覆盖管理员配置）
            if upserts:
                batch_values = [{**item, "enabled": item["default_enabled"]} for item in upserts]
                stmt = pg_insert(Feature).values(batch_values)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["name"],
                    set_={
                        "display_name": stmt.excluded.display_name,
                        "description": stmt.excluded.description,
                        "default_enabled": stmt.excluded.default_enabled,
                        "is_active": True,
                        # enabled / private_mode 不覆盖（保留管理员配置）
                    },
                )
                await session.execute(stmt)

            # 将已删除的功能标记为不活跃
            await session.execute(
                update(Feature)
                .where(Feature.name.not_in(list(active_names)))
                .values(is_active=False)
            )

            await session.commit()

        logger.info(
            "功能注册表同步完成",
            total=len(upserts),
            event_type="permission.sync_complete",
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
        cache_key = _KEY_GROUP.format(group_id=group_id, feature=feature_name)
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return bool(cached)

        result = await self._query_group_feature(group_id, feature_name)
        await self._cache.set(cache_key, result, ttl=_CACHE_TTL)
        return result

    async def _query_group_feature(self, group_id: int, feature_name: str) -> bool:
        """从数据库查询群聊功能状态。"""
        async with self._factory() as session:
            # 先查群显式设置
            row = await session.execute(
                select(GroupFeaturePermission.enabled).where(
                    GroupFeaturePermission.group_id == group_id,
                    GroupFeaturePermission.feature_name == feature_name,
                )
            )
            explicit = row.scalar_one_or_none()
            if explicit is not None:
                return bool(explicit)

            # 无显式设置 → 读 Feature.enabled（全局开关 * default_enabled 的叠加结果）
            feat_row = await session.execute(
                select(Feature.enabled).where(Feature.name == feature_name)
            )
            enabled = feat_row.scalar_one_or_none()
            return bool(enabled) if enabled is not None else True

    async def is_private_feature_allowed(
        self,
        ctrl_feature: str,
        method_feature: str,  # noqa: ARG002 — 私聊以 controller 级为粒度
        user_qq: int,
    ) -> bool:
        """私聊权限查询（以 controller 级为粒度）。"""
        cache_key = _KEY_PRIVATE.format(feature=ctrl_feature, qq=user_qq)
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return bool(cached)

        result = await self._query_private_feature(ctrl_feature, user_qq)
        await self._cache.set(cache_key, result, ttl=_CACHE_TTL)
        return result

    async def _query_private_feature(self, feature_name: str, user_qq: int) -> bool:
        """从数据库查询私聊功能状态。"""
        async with self._factory() as session:
            feat_row = await session.execute(
                select(Feature.enabled, Feature.private_mode).where(Feature.name == feature_name)
            )
            row = feat_row.one_or_none()
            if row is None:
                return True
            enabled, private_mode = row

            if not enabled:
                return False

            # 检查用户是否在列表中
            user_in_list = await session.execute(
                select(PrivateFeaturePermission.id).where(
                    PrivateFeaturePermission.feature_name == feature_name,
                    PrivateFeaturePermission.user_qq == user_qq,
                )
            )
            in_list = user_in_list.scalar_one_or_none() is not None

            if private_mode == "whitelist":
                return in_list  # 白名单：仅列表中的用户可用
            else:
                return not in_list  # 黑名单：列表中的用户被屏蔽

    # ─────────────────────── 管理 API ───────────────────────

    async def list_features(self) -> list[dict[str, Any]]:
        """列出所有活跃功能（树状结构：controller → methods）。"""
        async with self._factory() as session:
            rows = await session.execute(
                select(Feature).where(Feature.is_active.is_(True)).order_by(Feature.name)
            )
            features = rows.scalars().all()

        tree: list[dict[str, Any]] = []
        children_map: dict[str, list[dict[str, Any]]] = {}

        for f in features:
            meta = self._metadata.get(f.name, {})
            item = {
                "name": f.name,
                "parent": f.parent,
                "display_name": f.display_name,
                "description": f.description,
                "default_enabled": f.default_enabled,
                "enabled": f.enabled,
                "private_mode": f.private_mode,
                "is_active": f.is_active,
                # 内存元数据注解字段
                "admin": meta.get("admin", False),
                "message_scope": meta.get("message_scope", "all"),
                "mapping_type": meta.get("mapping_type", ""),
                "tags": meta.get("tags", []),
                "children": [],
            }
            if f.parent is None:
                tree.append(item)
            else:
                children_map.setdefault(f.parent, []).append(item)

        # 组装树
        for ctrl_item in tree:
            ctrl_item["children"] = children_map.get(ctrl_item["name"], [])

        return tree

    async def update_feature(
        self,
        name: str,
        enabled: bool | None = None,
        private_mode: str | None = None,
    ) -> dict[str, Any] | None:
        """更新功能全局设置，返回更新后的记录。"""
        updates: dict[str, Any] = {}
        if enabled is not None:
            updates["enabled"] = enabled
        if private_mode is not None:
            updates["private_mode"] = private_mode

        if not updates:
            return None

        async with self._factory() as session:
            stmt = (
                update(Feature)
                .where(Feature.name == name)
                .values(**updates)
                .returning(Feature.name, Feature.enabled, Feature.private_mode)
            )
            result = await session.execute(stmt)
            row = result.first()
            await session.commit()
            if row is None:
                return None
            return {"name": row.name, "enabled": row.enabled, "private_mode": row.private_mode}

    async def get_group_permissions(self, group_id: int) -> list[dict[str, Any]]:
        """获取某群所有功能的权限状态（含未显式设置的功能，controller + method 两级）。"""
        async with self._factory() as session:
            # 所有活跃功能（含 controller + method 两级）
            feat_rows = await session.execute(
                select(Feature).where(Feature.is_active.is_(True)).order_by(Feature.name)
            )
            features = feat_rows.scalars().all()

            # 该群的显式设置
            perm_rows = await session.execute(
                select(GroupFeaturePermission).where(GroupFeaturePermission.group_id == group_id)
            )
            perms = {p.feature_name: p.enabled for p in perm_rows.scalars().all()}

        result = []
        for f in features:
            result.append(
                {
                    "feature_name": f.name,
                    "display_name": f.display_name,
                    "enabled": perms.get(f.name, f.enabled),
                    "is_explicit": f.name in perms,
                    "parent": f.parent,
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

        # 清缓存
        await self._cache.delete(_KEY_GROUP.format(group_id=group_id, feature=feature_name))

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

        # 批量清缓存
        await asyncio.gather(
            *[
                self._cache.delete(
                    _KEY_GROUP.format(group_id=group_id, feature=item["feature_name"])
                )
                for item in features
            ]
        )

    async def get_private_users(self, feature_name: str) -> list[int]:
        """获取私聊黑/白名单用户列表。"""
        async with self._factory() as session:
            rows = await session.execute(
                select(PrivateFeaturePermission.user_qq).where(
                    PrivateFeaturePermission.feature_name == feature_name
                )
            )
            return [r for (r,) in rows.all()]

    async def add_private_user(self, feature_name: str, user_qq: int) -> None:
        """添加用户到黑/白名单。"""
        async with self._factory() as session:
            stmt = pg_insert(PrivateFeaturePermission).values(
                id=uuid.uuid4(),
                feature_name=feature_name,
                user_qq=user_qq,
            )
            stmt = stmt.on_conflict_do_nothing(constraint="uq_private_feature_user")
            await session.execute(stmt)
            await session.commit()

        await self._cache.delete(_KEY_PRIVATE.format(feature=feature_name, qq=user_qq))

    async def remove_private_user(self, feature_name: str, user_qq: int) -> None:
        """从黑/白名单移除用户。"""
        async with self._factory() as session:
            await session.execute(
                delete(PrivateFeaturePermission).where(
                    PrivateFeaturePermission.feature_name == feature_name,
                    PrivateFeaturePermission.user_qq == user_qq,
                )
            )
            await session.commit()

        await self._cache.delete(_KEY_PRIVATE.format(feature=feature_name, qq=user_qq))

    async def get_permission_matrix(self) -> dict[str, Any]:
        """获取完整权限矩阵（所有活跃群 × 所有活跃功能，含 controller + method 两级）。"""
        async with self._factory() as session:
            # 所有活跃功能（含 controller 和 method 两级）
            feat_rows = await session.execute(
                select(Feature).where(Feature.is_active.is_(True)).order_by(Feature.name)
            )
            all_features = feat_rows.scalars().all()

            # 所有群
            group_rows = await session.execute(
                select(Group.group_id, Group.group_name).where(Group.is_active.is_(True))
            )
            groups = group_rows.all()

            # 所有显式权限设置
            perm_rows = await session.execute(select(GroupFeaturePermission))
            perms: dict[tuple[int, str], bool] = {
                (p.group_id, p.feature_name): p.enabled for p in perm_rows.scalars().all()
            }

        # 构建树形 features 结构
        ctrl_features: list[Feature] = [f for f in all_features if f.parent is None]
        method_features_map: dict[str, list[Feature]] = {}
        for f in all_features:
            if f.parent is not None:
                method_features_map.setdefault(f.parent, []).append(f)

        features_tree = []
        for ctrl in ctrl_features:
            ctrl_meta = self._metadata.get(ctrl.name, {})
            children = []
            for method in method_features_map.get(ctrl.name, []):
                method_meta = self._metadata.get(method.name, {})
                children.append(
                    {
                        "name": method.name,
                        "display_name": method.display_name,
                        "description": method.description,
                        "enabled": method.enabled,
                        "admin": method_meta.get("admin", False),
                        "message_scope": method_meta.get("message_scope", "all"),
                        "mapping_type": method_meta.get("mapping_type", ""),
                    }
                )
            features_tree.append(
                {
                    "name": ctrl.name,
                    "display_name": ctrl.display_name,
                    "description": ctrl.description,
                    "enabled": ctrl.enabled,
                    "admin": ctrl_meta.get("admin", False),
                    "tags": ctrl_meta.get("tags", []),
                    "children": children,
                }
            )

        # 构建每个群的权限 map（包含所有 feature name）
        all_feature_names = [f.name for f in all_features]
        feature_default_map = {f.name: f.enabled for f in all_features}

        return {
            "features": features_tree,
            "groups": [
                {
                    "group_id": g.group_id,
                    "group_name": g.group_name,
                    "permissions": {
                        name: perms.get((g.group_id, name), feature_default_map[name])
                        for name in all_feature_names
                    },
                }
                for g in groups
            ],
        }
