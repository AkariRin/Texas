"""用户管理写操作服务 —— relation 计算、批量 upsert、全量同步持久化、管理员管理。

只读查询（列表、详情）已迁移至 PersonnelQueryService（personnel_query.py）。
增量事件处理（好友/群成员变更）已迁移至 PersonnelEventService（personnel_events.py）。
本类专注于批量写入操作，遵循单一职责原则。
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

import structlog
from sqlalchemy import case, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.core.cache.key_registry import cache_key, glob_for
from src.core.monitoring.metrics import (
    personnel_admins_total,
    personnel_friends_total,
    personnel_groups_total,
    personnel_memberships_total,
    personnel_sync_duration,
    personnel_sync_last_success_ts,
    personnel_sync_total,
    personnel_users_total,
)
from src.core.utils import SHANGHAI_TZ
from src.models.enums import GroupRole, UserRelation
from src.models.personnel import Group, GroupMembership, User

if TYPE_CHECKING:
    from sqlalchemy.engine import CursorResult
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from src.core.cache.client import CacheClient
    from src.core.config import Settings

logger = structlog.get_logger()

# ── 本模块的 Redis 缓存键定义 ──
personnel_sync_status_key = cache_key(
    "personnel.sync_status",
    "texas:personnel:sync_status",
    description="最近一次同步状态。",
)
personnel_sync_lock_key = cache_key(
    "personnel.sync_lock",
    "texas:lock:personnel_sync",
    description="同步任务分布式锁。",
)
user_relation_key = cache_key(
    "personnel.user_relation",
    "texas:personnel:user:{qq}:relation",
    description="用户关系等级缓存。",
)
admin_set_key = cache_key(
    "personnel.admin_set",
    "texas:personnel:admins",
    description="超级管理员 QQ 号集合（Redis Set）。",
)


def compute_relation(
    current_relation: UserRelation, is_in_friend_list: bool, has_active_membership: bool
) -> UserRelation:
    """根据同步数据计算关系等级。

    当前 relation 为 admin 时直接返回，不做任何变更。
    """
    if current_relation == UserRelation.admin:
        return UserRelation.admin
    if is_in_friend_list:
        return UserRelation.friend
    if has_active_membership:
        return UserRelation.group_member
    return UserRelation.stranger


class PersonnelService:
    """用户管理核心服务 —— 封装 upsert、同步编排、缓存管理。"""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        cache: CacheClient,
        persistent: CacheClient,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._cache = cache  # 易失缓存：用户关系、管理员集合（可丢失，TTL 短）
        self._persistent = persistent  # 持久存储：同步状态、分布式锁（不可丢失）
        self._settings = settings

    # ── 批量 upsert 操作 ──

    async def upsert_users(
        self,
        session: AsyncSession,
        users_data: list[dict[str, Any]],
        relation: UserRelation = UserRelation.stranger,
    ) -> int:
        """批量 upsert 用户，返回受影响行数。

        若用户当前 relation 为 admin，则跳过 relation 更新。
        """
        if not users_data:
            return 0

        batch_size = self._settings.PERSONNEL_SYNC_BATCH_SIZE
        total = 0

        for i in range(0, len(users_data), batch_size):
            batch = users_data[i : i + batch_size]
            values = []
            for u in batch:
                values.append(
                    {
                        "qq": int(u.get("user_id", u.get("qq", 0))),
                        "nickname": str(u.get("nickname", u.get("nick", ""))),
                        "relation": relation,
                        "last_synced": datetime.now(SHANGHAI_TZ),
                    }
                )

            stmt = pg_insert(User).values(values)
            # 若当前 relation 为 admin 则不更新 relation
            stmt = stmt.on_conflict_do_update(
                index_elements=["qq"],
                set_={
                    "nickname": stmt.excluded.nickname,
                    "last_synced": stmt.excluded.last_synced,
                    "relation": case(
                        (User.__table__.c.relation == UserRelation.admin, UserRelation.admin),
                        else_=stmt.excluded.relation,
                    ),
                },
            )
            cursor_result = cast("CursorResult[Any]", await session.execute(stmt))
            total += cursor_result.rowcount

        return total

    async def upsert_groups(
        self,
        session: AsyncSession,
        groups_data: list[dict[str, Any]],
    ) -> int:
        """批量 upsert 群聊。"""
        if not groups_data:
            return 0

        batch_size = self._settings.PERSONNEL_SYNC_BATCH_SIZE
        total = 0

        for i in range(0, len(groups_data), batch_size):
            batch = groups_data[i : i + batch_size]
            values = []
            for g in batch:
                values.append(
                    {
                        "group_id": int(g.get("group_id", 0)),
                        "group_name": str(g.get("group_name", "")),
                        "member_count": int(g.get("member_count", 0)),
                        "max_member_count": int(g.get("max_member_count", 0)),
                        "is_active": True,
                        "last_synced": datetime.now(SHANGHAI_TZ),
                    }
                )

            stmt = pg_insert(Group).values(values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["group_id"],
                set_={
                    "group_name": stmt.excluded.group_name,
                    "member_count": stmt.excluded.member_count,
                    "max_member_count": stmt.excluded.max_member_count,
                    "is_active": stmt.excluded.is_active,
                    "last_synced": stmt.excluded.last_synced,
                },
            )
            cursor_result = cast("CursorResult[Any]", await session.execute(stmt))
            total += cursor_result.rowcount

        return total

    async def upsert_memberships(
        self,
        session: AsyncSession,
        group_id: int,
        members_data: list[dict[str, Any]],
    ) -> int:
        """批量 upsert 群成员关系，并确保用户存在。"""
        if not members_data:
            return 0

        batch_size = self._settings.PERSONNEL_SYNC_BATCH_SIZE
        total = 0

        for i in range(0, len(members_data), batch_size):
            batch = members_data[i : i + batch_size]

            # 先确保用户存在
            user_values = []
            for m in batch:
                user_values.append(
                    {
                        "qq": int(m.get("user_id", 0)),
                        "nickname": str(m.get("nickname", "")),
                        "relation": UserRelation.group_member,
                        "last_synced": datetime.now(SHANGHAI_TZ),
                    }
                )

            user_stmt = pg_insert(User).values(user_values)
            user_stmt = user_stmt.on_conflict_do_update(
                index_elements=["qq"],
                set_={
                    "nickname": user_stmt.excluded.nickname,
                    "last_synced": user_stmt.excluded.last_synced,
                    "relation": case(
                        (User.__table__.c.relation == UserRelation.admin, UserRelation.admin),
                        (User.__table__.c.relation == UserRelation.friend, UserRelation.friend),
                        else_=user_stmt.excluded.relation,
                    ),
                },
            )
            await session.execute(user_stmt)

            # upsert 成员关系
            membership_values = []
            for m in batch:
                membership_values.append(
                    {
                        "user_id": int(m.get("user_id", 0)),
                        "group_id": group_id,
                        "card": str(m.get("card", "")),
                        "role": GroupRole(m.get("role", "member")),
                        "join_time": int(m.get("join_time", 0)),
                        "last_active_time": int(m.get("last_sent_time", 0)),
                        "title": str(m.get("title", "")),
                        "title_expire_time": int(m.get("title_expire_time", 0)),
                        "level": str(m.get("level", "")),
                        "is_active": True,
                    }
                )

            mem_stmt = pg_insert(GroupMembership).values(membership_values)
            mem_stmt = mem_stmt.on_conflict_do_update(
                constraint="uq_user_group",
                set_={
                    "card": mem_stmt.excluded.card,
                    "role": mem_stmt.excluded.role,
                    "join_time": mem_stmt.excluded.join_time,
                    "last_active_time": mem_stmt.excluded.last_active_time,
                    "title": mem_stmt.excluded.title,
                    "title_expire_time": mem_stmt.excluded.title_expire_time,
                    "level": mem_stmt.excluded.level,
                    "is_active": mem_stmt.excluded.is_active,
                },
            )
            cursor_result = cast("CursorResult[Any]", await session.execute(mem_stmt))
            total += cursor_result.rowcount

        return total

    # ── 失效数据清理 ──

    async def deactivate_stale_groups(
        self, session: AsyncSession, active_group_ids: set[int]
    ) -> None:
        """将不在最新群列表中的群标记为 is_active=False。"""
        if not active_group_ids:
            await session.execute(update(Group).values(is_active=False))
            return

        await session.execute(
            update(Group)
            .where(Group.group_id.notin_(active_group_ids), Group.is_active.is_(True))
            .values(is_active=False)
        )

    async def deactivate_stale_memberships(
        self, session: AsyncSession, group_id: int, active_user_ids: set[int]
    ) -> None:
        """将不在最新成员列表中的成员关系标记为 is_active=False。"""
        if not active_user_ids:
            await session.execute(
                update(GroupMembership)
                .where(GroupMembership.group_id == group_id, GroupMembership.is_active.is_(True))
                .values(is_active=False)
            )
            return

        await session.execute(
            update(GroupMembership)
            .where(
                GroupMembership.group_id == group_id,
                GroupMembership.user_id.notin_(active_user_ids),
                GroupMembership.is_active.is_(True),
            )
            .values(is_active=False)
        )

    async def recalculate_relations(self, session: AsyncSession, friend_qq_set: set[int]) -> None:
        """重算所有非 admin 用户的 relation 字段（批量查询替代 N+1）。"""
        # 查询所有非 admin 用户
        result = await session.execute(select(User).where(User.relation != UserRelation.admin))
        users = result.scalars().all()

        if not users:
            return

        # 一次性查出所有有活跃群成员关系的用户 ID 集合，避免 N+1
        user_ids = [u.qq for u in users]
        mem_result = await session.execute(
            select(GroupMembership.user_id.distinct()).where(
                GroupMembership.user_id.in_(user_ids),
                GroupMembership.is_active.is_(True),
            )
        )
        active_member_ids: set[int] = {row[0] for row in mem_result.all()}

        for user in users:
            has_active_membership = user.qq in active_member_ids
            is_friend = user.qq in friend_qq_set

            new_relation = compute_relation(user.relation, is_friend, has_active_membership)
            if user.relation != new_relation:
                user.relation = new_relation

    # ── 全量同步持久化（供 Celery 任务调用） ──

    async def persist_sync_data(
        self,
        friends: list[dict[str, Any]] | None,
        groups: list[dict[str, Any]] | None,
        members: dict[int, list[dict[str, Any]]] | None,
    ) -> dict[str, int]:
        """将采集到的用户数据批量持久化到数据库。

        Returns:
            {"users_synced": int, "groups_synced": int, "memberships_synced": int}
        """
        start_time = time.monotonic()
        users_synced = 0
        groups_synced = 0
        memberships_synced = 0

        async with self._session_factory() as session, session.begin():
            # 1. 同步好友
            friend_qq_set: set[int] = set()
            if friends:
                users_synced += await self.upsert_users(
                    session, friends, relation=UserRelation.friend
                )
                for f in friends:
                    qq = int(f.get("user_id", f.get("qq", 0)))
                    if qq:
                        friend_qq_set.add(qq)

            # 2. 同步群聊
            active_group_ids: set[int] = set()
            if groups:
                groups_synced = await self.upsert_groups(session, groups)
                for g in groups:
                    gid = int(g.get("group_id", 0))
                    if gid:
                        active_group_ids.add(gid)

            # 3. 同步群成员
            if members:
                for gid, member_list in members.items():
                    gid = int(gid)
                    memberships_synced += await self.upsert_memberships(session, gid, member_list)
                    # 清理该群中的失效成员
                    active_user_ids = {
                        int(m.get("user_id", 0)) for m in member_list if m.get("user_id")
                    }
                    await self.deactivate_stale_memberships(session, gid, active_user_ids)

            # 4. 清理失效群
            if groups is not None:
                await self.deactivate_stale_groups(session, active_group_ids)

            # 5. 重算关系等级
            await self.recalculate_relations(session, friend_qq_set)

        duration = time.monotonic() - start_time

        # 更新 Prometheus 指标
        personnel_sync_total.labels(status="success").inc()
        personnel_sync_duration.observe(duration)
        personnel_sync_last_success_ts.set(time.time())

        # 更新 Gauge 指标
        await self._update_gauge_metrics()

        # 写入 Redis 同步状态
        status_data = {
            "last_sync_time": datetime.now(SHANGHAI_TZ).isoformat(),
            "duration_seconds": round(duration, 3),
            "status": "success",
            "users_synced": users_synced,
            "groups_synced": groups_synced,
            "memberships_synced": memberships_synced,
        }
        await self._persistent.set(personnel_sync_status_key(), status_data, ttl=0)

        # 清除用户关系缓存（全量同步后失效）
        await self._invalidate_all_relation_cache()

        logger.info(
            "用户数据同步完成",
            users_synced=users_synced,
            groups_synced=groups_synced,
            memberships_synced=memberships_synced,
            duration=round(duration, 3),
            event_type="personnel.sync_complete",
        )

        return {
            "users_synced": users_synced,
            "groups_synced": groups_synced,
            "memberships_synced": memberships_synced,
        }

    # ── 超级管理员管理 ──

    async def set_admin(self, qq: int) -> bool:
        """设置超级管理员。返回是否成功。"""
        async with self._session_factory() as session, session.begin():
            user = await session.get(User, qq)
            if not user:
                return False
            user.relation = UserRelation.admin

        await self._cache.delete(user_relation_key(qq))
        await self._cache.delete(admin_set_key())
        logger.info("超级管理员已设置", qq=qq, event_type="personnel.admin_set")
        return True

    async def remove_admin(self, qq: int) -> bool:
        """移除超级管理员，根据当前状态自动降级。返回是否成功。"""
        async with self._session_factory() as session, session.begin():
            user = await session.get(User, qq)
            if not user or user.relation != UserRelation.admin:
                return False

            # 检查是否有活跃群关系
            mem_result = await session.execute(
                select(GroupMembership.id)
                .where(
                    GroupMembership.user_id == qq,
                    GroupMembership.is_active.is_(True),
                )
                .limit(1)
            )
            has_membership = mem_result.scalar_one_or_none() is not None

            # 好友状态在下次同步时会自动修正
            user.relation = UserRelation.group_member if has_membership else UserRelation.stranger

        await self._cache.delete(user_relation_key(qq))
        await self._cache.delete(admin_set_key())
        logger.info(
            "超级管理员已移除",
            qq=qq,
            new_relation=user.relation,
            event_type="personnel.admin_removed",
        )
        return True

    async def get_admins(self) -> list[dict[str, Any]]:
        """获取所有超级管理员列表。"""
        async with self._session_factory() as session:
            result = await session.execute(select(User).where(User.relation == UserRelation.admin))
            admins = result.scalars().all()
            return [
                {
                    "qq": r.qq,
                    "nickname": r.nickname,
                    "relation": r.relation,
                    "last_synced": r.last_synced.isoformat() if r.last_synced else None,
                }
                for r in admins
            ]

    async def get_admin_qq_set(self) -> set[int]:
        """获取所有超级管理员的 QQ 号集合（带 Redis 缓存）。"""
        cache_key = admin_set_key()
        cached = await self._cache.get(cache_key)
        if cached and isinstance(cached, list):
            return set(cached)

        async with self._session_factory() as session:
            result = await session.execute(
                select(User.qq).where(User.relation == UserRelation.admin)
            )
            qq_list = [row[0] for row in result.all()]

        await self._cache.set(cache_key, qq_list, ttl=300)
        return set(qq_list)

    async def get_sync_status(self) -> dict[str, Any]:
        """获取最近一次同步状态。"""
        data = await self._persistent.get(personnel_sync_status_key())
        if data and isinstance(data, dict):
            return cast("dict[str, Any]", data)
        return {
            "last_sync_time": None,
            "duration_seconds": None,
            "status": "never",
            "users_synced": 0,
            "groups_synced": 0,
            "memberships_synced": 0,
        }

    # ── 用户关系缓存 ──

    async def get_user_relation(self, qq: int) -> str:
        """获取用户关系等级（带缓存）。"""
        cache_key = user_relation_key(qq)
        cached = await self._cache.get(cache_key)
        if cached and isinstance(cached, str):
            return str(cached)

        async with self._session_factory() as session:
            user = await session.get(User, qq)
            relation: str = str(user.relation) if user else UserRelation.stranger

        await self._cache.set(cache_key, relation, ttl=300)
        return relation

    # ── 内部辅助 ──

    async def _update_gauge_metrics(self) -> None:
        """更新 Gauge 类型的 Prometheus 指标（使用 COUNT(*) 替代内存计数）。"""
        try:
            async with self._session_factory() as session:
                # 用户总数
                personnel_users_total.set(
                    (await session.execute(select(func.count()).select_from(User))).scalar() or 0
                )
                # 好友总数
                personnel_friends_total.set(
                    (
                        await session.execute(
                            select(func.count())
                            .select_from(User)
                            .where(User.relation == UserRelation.friend)
                        )
                    ).scalar()
                    or 0
                )
                # 超级管理员总数
                personnel_admins_total.set(
                    (
                        await session.execute(
                            select(func.count())
                            .select_from(User)
                            .where(User.relation == UserRelation.admin)
                        )
                    ).scalar()
                    or 0
                )
                # 活跃群总数
                personnel_groups_total.set(
                    (
                        await session.execute(
                            select(func.count()).select_from(Group).where(Group.is_active.is_(True))
                        )
                    ).scalar()
                    or 0
                )
                # 活跃成员关系总数
                personnel_memberships_total.set(
                    (
                        await session.execute(
                            select(func.count())
                            .select_from(GroupMembership)
                            .where(GroupMembership.is_active.is_(True))
                        )
                    ).scalar()
                    or 0
                )
        except Exception as exc:
            logger.warning(
                "更新 Gauge 指标失败", error=str(exc), event_type="personnel.metrics_error"
            )

    async def _invalidate_all_relation_cache(self) -> None:
        """清除所有用户关系缓存（全量同步后）。"""
        try:
            await self._cache.delete_by_pattern(glob_for(user_relation_key))
            # 同时清除超级管理员集合缓存
            await self._cache.delete(admin_set_key())
        except Exception as exc:
            logger.warning(
                "清除关系缓存失败", error=str(exc), event_type="personnel.cache_invalidate_error"
            )


# ── 生命周期注册 ──

from src.core.lifecycle import shutdown, startup  # noqa: E402


@startup(
    name="personnel",
    provides=[
        "personnel_service",
        "personnel_event_service",
        "personnel_query_service",
        "sync_coordinator",
    ],
    requires=[
        "session_factory",
        "cache_client",
        "persistent_client",
        "settings",
        "bot_api",
        "conn_mgr",
    ],
    dispatcher_services=["personnel_service", "personnel_event_service"],
)
async def _lifecycle_start(deps: dict[str, Any]) -> dict[str, Any]:
    """用户管理模块启动。"""
    from src.services.personnel_events import PersonnelEventService
    from src.services.personnel_query import PersonnelQueryService
    from src.services.personnel_sync import SyncCoordinator

    ps = PersonnelService(
        session_factory=deps["session_factory"],
        cache=deps["cache_client"],
        persistent=deps["persistent_client"],
        settings=deps["settings"],
    )
    pe = PersonnelEventService(
        session_factory=deps["session_factory"],
        cache=deps["cache_client"],
    )
    pq = PersonnelQueryService(
        session_factory=deps["session_factory"],
        cache=deps["cache_client"],
    )
    sc = SyncCoordinator(
        bot_api=deps["bot_api"],
        conn_mgr=deps["conn_mgr"],
        personnel_service=ps,
        settings=deps["settings"],
    )
    sc.start_scheduler()
    return {
        "personnel_service": ps,
        "personnel_event_service": pe,
        "personnel_query_service": pq,
        "sync_coordinator": sc,
    }


@shutdown(name="personnel")
async def _lifecycle_stop(services: dict[str, Any]) -> None:
    """用户管理模块关闭（停止同步调度器）。"""
    services["sync_coordinator"].stop_scheduler()
