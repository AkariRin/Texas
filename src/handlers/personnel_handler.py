"""用户数据增量更新 —— 监听群与好友变动事件。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from src.core.framework.decorators import controller, on_notice

if TYPE_CHECKING:
    from src.core.framework.context import Context

from src.services.personnel import PersonnelService

logger = structlog.get_logger()


@controller(name="personnel_event", description="用户数据增量更新处理器", version="1.0.0")
class PersonnelEventHandler:
    """用户数据增量更新 —— 监听群与好友变动事件。

    通过 ``ctx.get_service(PersonnelService)`` 获取用户服务实例，
    服务由 ``EventDispatcher`` 在分发时注入到 ``Context`` 中。
    """

    @on_notice(notice_type="friend_add")
    async def on_friend_add(self, ctx: Context) -> bool:
        """好友添加事件：若非管理员则升级为 friend。"""
        if not ctx.has_service(PersonnelService):
            return False

        user_id: int = getattr(ctx.event, "user_id", 0)
        if not user_id:
            return False

        try:
            personnel_service = ctx.get_service(PersonnelService)
            await personnel_service.on_friend_add(user_id)
        except Exception as exc:
            logger.error(
                "处理好友添加事件失败",
                user_id=user_id,
                error=str(exc),
                event_type="personnel.handler_error",
            )
        return False  # 不阻止后续处理器

    @on_notice(notice_type="group_increase")
    async def on_group_increase(self, ctx: Context) -> bool:
        """群成员增加事件：创建成员关系记录。"""
        if not ctx.has_service(PersonnelService):
            return False

        group_id: int = getattr(ctx.event, "group_id", 0)
        user_id: int = getattr(ctx.event, "user_id", 0)
        if not group_id or not user_id:
            return False

        try:
            personnel_service = ctx.get_service(PersonnelService)
            await personnel_service.on_group_increase(group_id, user_id)
        except Exception as exc:
            logger.error(
                "处理群成员增加事件失败",
                group_id=group_id,
                user_id=user_id,
                error=str(exc),
                event_type="personnel.handler_error",
            )
        return False

    @on_notice(notice_type="group_decrease")
    async def on_group_decrease(self, ctx: Context) -> bool:
        """群成员减少事件：标记成员关系为非活跃，重算 relation。"""
        if not ctx.has_service(PersonnelService):
            return False

        group_id: int = getattr(ctx.event, "group_id", 0)
        user_id: int = getattr(ctx.event, "user_id", 0)
        sub_type: str = getattr(ctx.event, "sub_type", "")
        if not group_id or not user_id:
            return False

        try:
            personnel_service = ctx.get_service(PersonnelService)
            await personnel_service.on_group_decrease(group_id, user_id, sub_type)
        except Exception as exc:
            logger.error(
                "处理群成员减少事件失败",
                group_id=group_id,
                user_id=user_id,
                error=str(exc),
                event_type="personnel.handler_error",
            )
        return False

    @on_notice(notice_type="group_admin")
    async def on_group_admin(self, ctx: Context) -> bool:
        """群管理员变动事件：更新 role 字段。"""
        if not ctx.has_service(PersonnelService):
            return False

        group_id: int = getattr(ctx.event, "group_id", 0)
        user_id: int = getattr(ctx.event, "user_id", 0)
        sub_type: str = getattr(ctx.event, "sub_type", "")
        if not group_id or not user_id:
            return False

        try:
            personnel_service = ctx.get_service(PersonnelService)
            await personnel_service.on_group_admin_change(group_id, user_id, sub_type)
        except Exception as exc:
            logger.error(
                "处理群管理员变动事件失败",
                group_id=group_id,
                user_id=user_id,
                error=str(exc),
                event_type="personnel.handler_error",
            )
        return False

    @on_notice(notice_type="group_card")
    async def on_group_card(self, ctx: Context) -> bool:
        """群名片变更事件：更新 card 字段。"""
        if not ctx.has_service(PersonnelService):
            return False

        group_id: int = getattr(ctx.event, "group_id", 0)
        user_id: int = getattr(ctx.event, "user_id", 0)
        card_new: str = getattr(ctx.event, "card_new", "")
        if not group_id or not user_id:
            return False

        try:
            personnel_service = ctx.get_service(PersonnelService)
            await personnel_service.on_group_card_change(group_id, user_id, card_new)
        except Exception as exc:
            logger.error(
                "处理群名片变更事件失败",
                group_id=group_id,
                user_id=user_id,
                error=str(exc),
                event_type="personnel.handler_error",
            )
        return False
