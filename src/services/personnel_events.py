"""用户事件处理服务 —— 处理好友/群成员的增量变更事件。

处理来自 Bot 的实时事件（好友添加、群成员进出、群管理员变动等），
将增量变更持久化到数据库并维护 Redis 缓存。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import case, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.core.cache.keys import user_relation_key
from src.core.utils import SHANGHAI_TZ
from src.models.enums import GroupRole, UserRelation
from src.models.personnel import Group, GroupMembership, User
from src.services.personnel import compute_relation

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from src.core.cache.client import CacheClient

logger = structlog.get_logger()


class PersonnelEventService:
    """处理 Bot 实时增量事件，维护用户与群成员关系的即时状态。"""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        cache: CacheClient,
    ) -> None:
        self._session_factory = session_factory
        self._cache = cache

    async def on_friend_add(self, user_id: int) -> None:
        """好友添加：若非 admin 则升级为 friend。"""
        async with self._session_factory() as session, session.begin():
            stmt = pg_insert(User).values(
                qq=user_id,
                nickname="",
                relation=UserRelation.friend,
                last_synced=datetime.now(SHANGHAI_TZ),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["qq"],
                set_={
                    "last_synced": stmt.excluded.last_synced,
                    "relation": case(
                        (User.__table__.c.relation == UserRelation.admin, UserRelation.admin),
                        else_=UserRelation.friend,
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
                relation=UserRelation.group_member,
                last_synced=datetime.now(SHANGHAI_TZ),
            )
            user_stmt = user_stmt.on_conflict_do_update(
                index_elements=["qq"],
                set_={
                    "last_synced": user_stmt.excluded.last_synced,
                    "relation": case(
                        (User.__table__.c.relation == UserRelation.admin, UserRelation.admin),
                        (User.__table__.c.relation == UserRelation.friend, UserRelation.friend),
                        else_=UserRelation.group_member,
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
            if user and user.relation != UserRelation.admin:
                mem_result = await session.execute(
                    select(GroupMembership.id)
                    .where(
                        GroupMembership.user_id == user_id,
                        GroupMembership.is_active.is_(True),
                    )
                    .limit(1)
                )
                has_membership = mem_result.scalar_one_or_none() is not None
                is_friend = user.relation == UserRelation.friend
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
        new_role = GroupRole.admin if sub_type == "set" else GroupRole.member
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
