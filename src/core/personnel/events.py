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

from src.core.personnel.main import compute_relation, user_relation_key
from src.core.utils import SHANGHAI_TZ
from src.models.enums import GroupRole, UserRelation
from src.models.personnel import Group, GroupMembership, User

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from src.core.cache.client import CacheClient
    from src.core.framework.context import Context
    from src.core.permission.main import FeaturePermissionService

logger = structlog.get_logger()


class PersonnelEventService:
    """处理 Bot 实时增量事件，维护用户与群成员关系的即时状态。"""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        cache: CacheClient,
        permission_service: FeaturePermissionService | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._cache = cache
        self._permission_service = permission_service

    def configure_permission_service(self, svc: FeaturePermissionService) -> None:
        """延迟注入权限服务（由 permission @startup 在就绪后调用）。"""
        self._permission_service = svc

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

    async def on_group_increase(self, group_id: int, user_id: int, self_id: int = 0) -> None:
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
        # Bot 自身加入新群时，初始化该群的全量权限记录
        if self_id and user_id == self_id and self._permission_service is not None:
            await self._permission_service.sync_group_permissions(group_id)

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


# ── 直接注册事件处理器（替代 @component / ComponentScanner 动态注册）──

import structlog as _structlog  # noqa: E402

from src.core.framework.mapping import CompositeHandlerMapping, HandlerMethod  # noqa: E402

_reg_logger = _structlog.get_logger()


def register_event_handlers(
    mapping: CompositeHandlerMapping,
    svc: PersonnelEventService,
) -> None:
    """向 EventTypeHandlerMapping 直接注册人员事件处理器。

    mapping_type="event_type" 是 CompositeHandlerMapping.register() 路由到
    EventTypeHandlerMapping 的必须字段，缺少会导致 handler 被静默丢弃。

    每个 method 必须是接受 Context 的可调用对象（dispatcher 以 method(ctx) 调用），
    因此使用闭包包装器从 ctx.event 提取字段后再调用服务方法。
    """

    async def _on_friend_add(ctx: Context) -> bool:
        user_id: int = getattr(ctx.event, "user_id", 0)
        if not user_id:
            return False
        try:
            await svc.on_friend_add(user_id)
        except Exception as exc:
            _reg_logger.error(
                "处理好友添加事件失败",
                user_id=user_id,
                error=str(exc),
                event_type="personnel.handler_error",
            )
        return False

    async def _on_group_increase(ctx: Context) -> bool:
        group_id: int = getattr(ctx.event, "group_id", 0)
        user_id: int = getattr(ctx.event, "user_id", 0)
        if not group_id or not user_id:
            return False
        try:
            bot_qq: int = getattr(ctx.event, "self_id", 0)
            await svc.on_group_increase(group_id, user_id, self_id=bot_qq)
        except Exception as exc:
            _reg_logger.error(
                "处理群成员增加事件失败",
                group_id=group_id,
                user_id=user_id,
                error=str(exc),
                event_type="personnel.handler_error",
            )
        return False

    async def _on_group_decrease(ctx: Context) -> bool:
        group_id: int = getattr(ctx.event, "group_id", 0)
        user_id: int = getattr(ctx.event, "user_id", 0)
        sub_type: str = getattr(ctx.event, "sub_type", "")
        if not group_id or not user_id:
            return False
        try:
            await svc.on_group_decrease(group_id, user_id, sub_type)
        except Exception as exc:
            _reg_logger.error(
                "处理群成员减少事件失败",
                group_id=group_id,
                user_id=user_id,
                error=str(exc),
                event_type="personnel.handler_error",
            )
        return False

    async def _on_group_admin(ctx: Context) -> bool:
        group_id: int = getattr(ctx.event, "group_id", 0)
        user_id: int = getattr(ctx.event, "user_id", 0)
        sub_type: str = getattr(ctx.event, "sub_type", "")
        if not group_id or not user_id:
            return False
        try:
            await svc.on_group_admin_change(group_id, user_id, sub_type)
        except Exception as exc:
            _reg_logger.error(
                "处理群管理员变动事件失败",
                group_id=group_id,
                user_id=user_id,
                error=str(exc),
                event_type="personnel.handler_error",
            )
        return False

    async def _on_group_card(ctx: Context) -> bool:
        group_id: int = getattr(ctx.event, "group_id", 0)
        user_id: int = getattr(ctx.event, "user_id", 0)
        card_new: str = getattr(ctx.event, "card_new", "")
        if not group_id or not user_id:
            return False
        try:
            await svc.on_group_card_change(group_id, user_id, card_new)
        except Exception as exc:
            _reg_logger.error(
                "处理群名片变更事件失败",
                group_id=group_id,
                user_id=user_id,
                error=str(exc),
                event_type="personnel.handler_error",
            )
        return False

    for notice_type, handler_fn in (
        ("friend_add", _on_friend_add),
        ("group_increase", _on_group_increase),
        ("group_decrease", _on_group_decrease),
        ("group_admin", _on_group_admin),
        ("group_card", _on_group_card),
    ):
        mapping.register(
            HandlerMethod(
                component=svc,
                method=handler_fn,
                metadata={
                    "mapping_type": "event_type",
                    "event_type": "notice",
                    "notice_type": notice_type,
                },
                component_name="personnel_event",
            )
        )
