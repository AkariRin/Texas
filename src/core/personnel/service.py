"""人事管理业务逻辑 —— relation 计算、批量 upsert、数据采集编排。"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

import structlog
from sqlalchemy import case, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.core.cache.keys import (
    admin_set_key,
    personnel_sync_status_key,
    user_relation_key,
)
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
from src.core.personnel.models import Group, GroupMembership, User

if TYPE_CHECKING:
    from sqlalchemy.engine import CursorResult
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.core.cache.client import CacheClient
    from src.core.config import Settings

logger = structlog.get_logger()


# ── 关系等级优先级 ──
RELATION_PRIORITY = {
    "stranger": 0,
    "group_member": 1,
    "friend": 2,
    "admin": 3,
}


def compute_relation(
    current_relation: str, is_in_friend_list: bool, has_active_membership: bool
) -> str:
    """根据同步数据计算关系等级。

    当前 relation 为 admin 时直接返回，不做任何变更。
    """
    if current_relation == "admin":
        return "admin"
    if is_in_friend_list:
        return "friend"
    if has_active_membership:
        return "group_member"
    return "stranger"


class PersonnelService:
    """人事管理核心服务 —— 封装 upsert、同步编排、缓存管理。"""

    def __init__(
        self,
        session_factory: Any,
        cache: CacheClient,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._cache = cache
        self._settings = settings

    # ── 批量 upsert 操作 ──

    async def upsert_users(
        self,
        session: AsyncSession,
        users_data: list[dict[str, Any]],
        relation: str = "stranger",
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
                        "last_synced": datetime.now(UTC),
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
                        (User.__table__.c.relation == "admin", "admin"),
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
                        "last_synced": datetime.now(UTC),
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
                        "relation": "group_member",
                        "last_synced": datetime.now(UTC),
                    }
                )

            user_stmt = pg_insert(User).values(user_values)
            user_stmt = user_stmt.on_conflict_do_update(
                index_elements=["qq"],
                set_={
                    "nickname": user_stmt.excluded.nickname,
                    "last_synced": user_stmt.excluded.last_synced,
                    "relation": case(
                        (User.__table__.c.relation == "admin", "admin"),
                        (User.__table__.c.relation == "friend", "friend"),
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
                        "role": str(m.get("role", "member")),
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
        """重算所有非 admin 用户的 relation 字段。"""
        # 查询所有非 admin 用户
        result = await session.execute(select(User).where(User.relation != "admin"))
        users = result.scalars().all()

        for user in users:
            # 检查是否有活跃的群成员关系
            mem_result = await session.execute(
                select(GroupMembership.id)
                .where(
                    GroupMembership.user_id == user.qq,
                    GroupMembership.is_active.is_(True),
                )
                .limit(1)
            )
            has_active_membership = mem_result.scalar_one_or_none() is not None
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
        """将采集到的人事数据批量持久化到数据库。

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
                users_synced += await self.upsert_users(session, friends, relation="friend")
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
            "last_sync_time": datetime.now(UTC).isoformat(),
            "duration_seconds": round(duration, 3),
            "status": "success",
            "users_synced": users_synced,
            "groups_synced": groups_synced,
            "memberships_synced": memberships_synced,
        }
        await self._cache.set(personnel_sync_status_key(), status_data, ttl=0)

        # 清除用户关系缓存（全量同步后失效）
        await self._invalidate_all_relation_cache()

        logger.info(
            "人事数据同步完成",
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

    # ── 增量操作 ──

    async def on_friend_add(self, user_id: int) -> None:
        """好友添加：若非 admin 则升级为 friend。"""
        async with self._session_factory() as session, session.begin():
            stmt = pg_insert(User).values(
                qq=user_id,
                nickname="",
                relation="friend",
                last_synced=datetime.now(UTC),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["qq"],
                set_={
                    "last_synced": stmt.excluded.last_synced,
                    "relation": case(
                        (User.__table__.c.relation == "admin", "admin"),
                        else_="friend",
                    ),
                },
            )
            await session.execute(stmt)

        await self._cache.delete(user_relation_key(user_id))
        logger.info("好友添加已处理", user_id=user_id, event_type="personnel.friend_add")

    async def on_group_increase(self, group_id: int, user_id: int) -> None:
        """群成员增加：创建成员关系记录，若为 stranger 则升级为 group_member。"""
        async with self._session_factory() as session, session.begin():
            # upsert 用户
            user_stmt = pg_insert(User).values(
                qq=user_id,
                nickname="",
                relation="group_member",
                last_synced=datetime.now(UTC),
            )
            user_stmt = user_stmt.on_conflict_do_update(
                index_elements=["qq"],
                set_={
                    "last_synced": user_stmt.excluded.last_synced,
                    "relation": case(
                        (User.__table__.c.relation == "admin", "admin"),
                        (User.__table__.c.relation == "friend", "friend"),
                        else_="group_member",
                    ),
                },
            )
            await session.execute(user_stmt)

            # upsert 成员关系
            mem_stmt = pg_insert(GroupMembership).values(
                user_id=user_id,
                group_id=group_id,
                is_active=True,
            )
            mem_stmt = mem_stmt.on_conflict_do_update(
                constraint="uq_user_group",
                set_={"is_active": True},
            )
            await session.execute(mem_stmt)

        await self._cache.delete(user_relation_key(user_id))
        logger.info(
            "群成员增加已处理",
            group_id=group_id,
            user_id=user_id,
            event_type="personnel.group_increase",
        )

    async def on_group_decrease(self, group_id: int, user_id: int, sub_type: str) -> None:
        """群成员减少：标记成员关系为非活跃，重算 relation。"""
        async with self._session_factory() as session, session.begin():
            # 标记成员关系 is_active=False
            await session.execute(
                update(GroupMembership)
                .where(
                    GroupMembership.user_id == user_id,
                    GroupMembership.group_id == group_id,
                )
                .values(is_active=False)
            )

            # 若 kick_me，标记群为非活跃
            if sub_type == "kick_me":
                await session.execute(
                    update(Group).where(Group.group_id == group_id).values(is_active=False)
                )

            # 重算用户 relation
            user = await session.get(User, user_id)
            if user and user.relation != "admin":
                mem_result = await session.execute(
                    select(GroupMembership.id)
                    .where(
                        GroupMembership.user_id == user_id,
                        GroupMembership.is_active.is_(True),
                    )
                    .limit(1)
                )
                has_membership = mem_result.scalar_one_or_none() is not None
                is_friend = user.relation == "friend"
                user.relation = compute_relation(user.relation, is_friend, has_membership)

        await self._cache.delete(user_relation_key(user_id))
        logger.info(
            "群成员减少已处理",
            group_id=group_id,
            user_id=user_id,
            sub_type=sub_type,
            event_type="personnel.group_decrease",
        )

    async def on_group_admin_change(self, group_id: int, user_id: int, sub_type: str) -> None:
        """群管理员变动：更新成员关系的 role 字段。"""
        new_role = "admin" if sub_type == "set" else "member"
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(GroupMembership)
                .where(
                    GroupMembership.user_id == user_id,
                    GroupMembership.group_id == group_id,
                )
                .values(role=new_role)
            )

        logger.info(
            "群管理员变动已处理",
            group_id=group_id,
            user_id=user_id,
            new_role=new_role,
            event_type="personnel.group_admin_change",
        )

    async def on_group_card_change(self, group_id: int, user_id: int, card_new: str) -> None:
        """群名片变更：更新成员关系的 card 字段。"""
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(GroupMembership)
                .where(
                    GroupMembership.user_id == user_id,
                    GroupMembership.group_id == group_id,
                )
                .values(card=card_new)
            )

        logger.info(
            "群名片变更已处理",
            group_id=group_id,
            user_id=user_id,
            card_new=card_new,
            event_type="personnel.group_card_change",
        )

    # ── 管理员管理 ──

    async def set_admin(self, qq: int) -> bool:
        """设置管理员。返回是否成功。"""
        async with self._session_factory() as session, session.begin():
            user = await session.get(User, qq)
            if not user:
                return False
            user.relation = "admin"

        await self._cache.delete(user_relation_key(qq))
        await self._cache.delete(admin_set_key())
        logger.info("管理员已设置", qq=qq, event_type="personnel.admin_set")
        return True

    async def remove_admin(self, qq: int) -> bool:
        """移除管理员，根据当前状态自动降级。返回是否成功。"""
        async with self._session_factory() as session, session.begin():
            user = await session.get(User, qq)
            if not user or user.relation != "admin":
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

            # 检查是否为好友（无法精确判断，降级为 group_member 或 stranger）
            # 好友状态在下次同步时会自动修正
            user.relation = "group_member" if has_membership else "stranger"

        await self._cache.delete(user_relation_key(qq))
        await self._cache.delete(admin_set_key())
        logger.info(
            "管理员已移除",
            qq=qq,
            new_relation=user.relation,
            event_type="personnel.admin_removed",
        )
        return True

    async def get_admins(self) -> list[dict[str, Any]]:
        """获取所有管理员列表。"""
        async with self._session_factory() as session:
            result = await session.execute(select(User).where(User.relation == "admin"))
            admins = result.scalars().all()
            return [
                {
                    "qq": a.qq,
                    "nickname": a.nickname,
                    "relation": a.relation,
                    "last_synced": a.last_synced.isoformat() if a.last_synced else None,
                }
                for a in admins
            ]

    # ── 查询操作 ──

    async def get_user(self, qq: int) -> dict[str, Any] | None:
        """获取单个用户详情。"""
        async with self._session_factory() as session:
            user = await session.get(User, qq)
            if not user:
                return None

            # 计算活跃群聊数
            mem_result = await session.execute(
                select(GroupMembership).where(
                    GroupMembership.user_id == qq, GroupMembership.is_active.is_(True)
                )
            )
            memberships = mem_result.scalars().all()

            return {
                "qq": user.qq,
                "nickname": user.nickname,
                "relation": user.relation,
                "group_count": len(memberships),
                "last_synced": user.last_synced.isoformat() if user.last_synced else None,
            }

    async def list_users(
        self,
        page: int = 1,
        page_size: int = 20,
        relation: str | None = None,
        qq: int | None = None,
        nickname: str | None = None,
    ) -> dict[str, Any]:
        """分页查询用户列表。"""
        async with self._session_factory() as session:
            query = select(User)
            count_query = select(User.qq)

            if relation:
                query = query.where(User.relation == relation)
                count_query = count_query.where(User.relation == relation)
            if qq:
                query = query.where(User.qq == qq)
                count_query = count_query.where(User.qq == qq)
            if nickname:
                query = query.where(User.nickname.contains(nickname))
                count_query = count_query.where(User.nickname.contains(nickname))

            # 总数
            total_result = await session.execute(count_query)
            total = len(total_result.all())

            # 分页
            offset = (page - 1) * page_size
            query = query.offset(offset).limit(page_size).order_by(User.qq)
            result = await session.execute(query)
            users = result.scalars().all()

            items = []
            for u in users:
                mem_result = await session.execute(
                    select(GroupMembership.id).where(
                        GroupMembership.user_id == u.qq,
                        GroupMembership.is_active.is_(True),
                    )
                )
                group_count = len(mem_result.all())
                items.append(
                    {
                        "qq": u.qq,
                        "nickname": u.nickname,
                        "relation": u.relation,
                        "group_count": group_count,
                        "last_synced": u.last_synced.isoformat() if u.last_synced else None,
                    }
                )

            pages = (total + page_size - 1) // page_size if total > 0 else 0
            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "pages": pages,
            }

    async def get_user_groups(self, qq: int) -> list[dict[str, Any]]:
        """获取用户所属的所有群聊。"""
        async with self._session_factory() as session:
            result = await session.execute(
                select(GroupMembership, Group)
                .join(Group, GroupMembership.group_id == Group.group_id)
                .where(GroupMembership.user_id == qq, GroupMembership.is_active.is_(True))
            )
            rows = result.all()
            return [
                {
                    "group_id": group.group_id,
                    "group_name": group.group_name,
                    "member_count": group.member_count,
                    "max_member_count": group.max_member_count,
                    "is_active": group.is_active,
                    "last_synced": group.last_synced.isoformat() if group.last_synced else None,
                    "card": membership.card,
                    "role": membership.role,
                    "join_time": membership.join_time,
                }
                for membership, group in rows
            ]

    async def list_groups(
        self,
        page: int = 1,
        page_size: int = 20,
        group_name: str | None = None,
        is_active: bool | None = None,
    ) -> dict[str, Any]:
        """分页查询群列表。"""
        async with self._session_factory() as session:
            query = select(Group)
            count_query = select(Group.group_id)

            if group_name:
                query = query.where(Group.group_name.contains(group_name))
                count_query = count_query.where(Group.group_name.contains(group_name))
            if is_active is not None:
                query = query.where(Group.is_active == is_active)
                count_query = count_query.where(Group.is_active == is_active)

            total_result = await session.execute(count_query)
            total = len(total_result.all())

            offset = (page - 1) * page_size
            query = query.offset(offset).limit(page_size).order_by(Group.group_id)
            result = await session.execute(query)
            groups = result.scalars().all()

            items = [
                {
                    "group_id": g.group_id,
                    "group_name": g.group_name,
                    "member_count": g.member_count,
                    "max_member_count": g.max_member_count,
                    "is_active": g.is_active,
                    "last_synced": g.last_synced.isoformat() if g.last_synced else None,
                }
                for g in groups
            ]

            pages = (total + page_size - 1) // page_size if total > 0 else 0
            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "pages": pages,
            }

    async def get_group(self, group_id: int) -> dict[str, Any] | None:
        """获取单个群聊详情。"""
        async with self._session_factory() as session:
            group = await session.get(Group, group_id)
            if not group:
                return None
            return {
                "group_id": group.group_id,
                "group_name": group.group_name,
                "member_count": group.member_count,
                "max_member_count": group.max_member_count,
                "is_active": group.is_active,
                "last_synced": group.last_synced.isoformat() if group.last_synced else None,
            }

    async def list_group_members(
        self,
        group_id: int,
        page: int = 1,
        page_size: int = 20,
        role: str | None = None,
        nickname: str | None = None,
    ) -> dict[str, Any]:
        """分页获取群成员列表。"""
        async with self._session_factory() as session:
            query = (
                select(GroupMembership, User)
                .join(User, GroupMembership.user_id == User.qq)
                .where(GroupMembership.group_id == group_id, GroupMembership.is_active.is_(True))
            )
            count_query = (
                select(GroupMembership.id)
                .join(User, GroupMembership.user_id == User.qq)
                .where(GroupMembership.group_id == group_id, GroupMembership.is_active.is_(True))
            )

            if role:
                query = query.where(GroupMembership.role == role)
                count_query = count_query.where(GroupMembership.role == role)
            if nickname:
                query = query.where(User.nickname.contains(nickname))
                count_query = count_query.where(User.nickname.contains(nickname))

            total_result = await session.execute(count_query)
            total = len(total_result.all())

            offset = (page - 1) * page_size
            query = query.offset(offset).limit(page_size).order_by(GroupMembership.user_id)
            result = await session.execute(query)
            rows = result.all()

            items = [
                {
                    "qq": user.qq,
                    "nickname": user.nickname,
                    "card": membership.card,
                    "role": membership.role,
                    "relation": user.relation,
                    "join_time": membership.join_time,
                    "last_active_time": membership.last_active_time,
                    "title": membership.title,
                }
                for membership, user in rows
            ]

            pages = (total + page_size - 1) // page_size if total > 0 else 0
            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "pages": pages,
            }

    async def get_sync_status(self) -> dict[str, Any]:
        """获取最近一次同步状态。"""
        data = await self._cache.get(personnel_sync_status_key())
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
            relation: str = str(user.relation) if user else "stranger"

        await self._cache.set(cache_key, relation, ttl=300)
        return relation

    # ── 内部辅助 ──

    async def _update_gauge_metrics(self) -> None:
        """更新 Gauge 类型的 Prometheus 指标。"""
        try:
            async with self._session_factory() as session:
                # 用户总数
                result = await session.execute(select(User.qq))
                personnel_users_total.set(len(result.all()))

                # 好友总数
                result = await session.execute(select(User.qq).where(User.relation == "friend"))
                personnel_friends_total.set(len(result.all()))

                # 管理员总数
                result = await session.execute(select(User.qq).where(User.relation == "admin"))
                personnel_admins_total.set(len(result.all()))

                # 活跃群总数
                result = await session.execute(
                    select(Group.group_id).where(Group.is_active.is_(True))
                )
                personnel_groups_total.set(len(result.all()))

                # 活跃成员关系总数
                result = await session.execute(
                    select(GroupMembership.id).where(GroupMembership.is_active.is_(True))
                )
                personnel_memberships_total.set(len(result.all()))
        except Exception as exc:
            logger.warning(
                "更新 Gauge 指标失败", error=str(exc), event_type="personnel.metrics_error"
            )

    async def _invalidate_all_relation_cache(self) -> None:
        """清除所有用户关系缓存（全量同步后）。"""
        try:
            redis = self._cache._redis  # noqa: SLF001
            cursor = 0
            pattern = "texas:personnel:user:*:relation"
            while True:
                cursor, keys = await redis.scan(cursor=cursor, match=pattern, count=100)
                if keys:
                    await redis.delete(*keys)
                if cursor == 0:
                    break
        except Exception as exc:
            logger.warning(
                "清除关系缓存失败", error=str(exc), event_type="personnel.cache_invalidate_error"
            )

        # 同时清除管理员集合缓存
        await self._cache.delete(admin_set_key())
