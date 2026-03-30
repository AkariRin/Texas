"""用户反馈业务逻辑 —— 反馈创建、查询、状态更新、通知。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from src.core.db.utils import escape_like as _escape_like
from src.core.utils import SHANGHAI_TZ
from src.models.enums import FeedbackSource, FeedbackStatus, FeedbackType
from src.models.feedback import Feedback
from src.models.personnel import User

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.core.protocol.api import BotAPI

logger = structlog.get_logger()


class FeedbackService:
    """用户反馈核心服务 —— 封装反馈 CRUD 和通知。"""

    def __init__(
        self,
        session_factory: async_sessionmaker[Any],
        bot_api: BotAPI,
    ) -> None:
        self._session_factory = session_factory
        self._bot_api = bot_api

    # ════════════════════════════════════════════
    #  反馈 CRUD
    # ════════════════════════════════════════════

    async def create_feedback(
        self,
        user_id: int,
        content: str,
        source: FeedbackSource,
        group_id: int | None = None,
        feedback_type: FeedbackType | None = None,
    ) -> Feedback:
        """创建反馈记录并通知所有管理员。"""
        feedback = Feedback(
            user_id=user_id,
            content=content,
            source=source,
            group_id=group_id,
            feedback_type=feedback_type,
            status=FeedbackStatus.PENDING,
        )

        async with self._session_factory() as session, session.begin():
            session.add(feedback)
            await session.flush()
            await session.refresh(feedback)

        # 通知管理员（异步，不阻塞主流程）
        try:
            await self._notify_admins(feedback)
        except Exception:
            logger.exception(
                "通知管理员失败",
                feedback_id=str(feedback.id),
                event_type="feedback.notify_admins_error",
            )

        logger.info(
            "反馈已创建",
            feedback_id=str(feedback.id),
            user_id=user_id,
            source=source,
            event_type="feedback.created",
        )
        return feedback

    async def list_feedbacks(
        self,
        page: int = 1,
        page_size: int = 20,
        status: FeedbackStatus | None = None,
        feedback_type: FeedbackType | None = None,
        user_id: int | None = None,
        source: FeedbackSource | None = None,
        search: str | None = None,
    ) -> tuple[list[Feedback], int]:
        """分页查询反馈列表，支持多条件筛选和搜索。"""
        stmt = select(Feedback).options(selectinload(Feedback.user))
        count_stmt = select(func.count()).select_from(Feedback)

        # 筛选条件
        if status:
            stmt = stmt.where(Feedback.status == status)
            count_stmt = count_stmt.where(Feedback.status == status)
        if feedback_type:
            stmt = stmt.where(Feedback.feedback_type == feedback_type)
            count_stmt = count_stmt.where(Feedback.feedback_type == feedback_type)
        if user_id:
            stmt = stmt.where(Feedback.user_id == user_id)
            count_stmt = count_stmt.where(Feedback.user_id == user_id)
        if source:
            stmt = stmt.where(Feedback.source == source)
            count_stmt = count_stmt.where(Feedback.source == source)
        if search:
            search_filter = or_(
                Feedback.content.ilike(f"%{_escape_like(search)}%", escape="\\"),
                Feedback.admin_reply.ilike(f"%{_escape_like(search)}%", escape="\\"),
            )
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        # 分页
        stmt = stmt.order_by(Feedback.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        async with self._session_factory() as session:
            total_result = await session.execute(count_stmt)
            total = total_result.scalar() or 0

            result = await session.execute(stmt)
            feedbacks = list(result.scalars().all())

        return feedbacks, total

    async def get_feedback(self, feedback_id: UUID) -> Feedback | None:
        """获取反馈详情（包含用户和群组信息）。"""
        stmt = (
            select(Feedback).where(Feedback.id == feedback_id).options(selectinload(Feedback.user))
        )

        async with self._session_factory() as session:
            result = await session.execute(stmt)
            feedback: Feedback | None = result.scalars().first()
            return feedback

    async def update_status(
        self,
        feedback_id: UUID,
        status: FeedbackStatus,
        admin_reply: str | None = None,
    ) -> Feedback | None:
        """更新反馈状态,若状态变为 processed 则通知用户。"""
        feedback: Feedback | None = None
        old_status: FeedbackStatus | None = None

        async with self._session_factory() as session, session.begin():
            feedback = await session.get(Feedback, feedback_id)
            if not feedback:
                return None

            old_status = feedback.status
            feedback.status = status
            if admin_reply is not None:
                feedback.admin_reply = admin_reply
            if status == FeedbackStatus.PROCESSED and old_status != FeedbackStatus.PROCESSED:
                feedback.processed_at = datetime.now(SHANGHAI_TZ)

            await session.flush()
            await session.refresh(feedback)

        # 通知用户（异步，不阻塞主流程）
        if (
            feedback is not None
            and status == FeedbackStatus.PROCESSED
            and old_status != FeedbackStatus.PROCESSED
        ):
            try:
                await self._notify_user(feedback)
            except Exception:
                logger.exception(
                    "通知用户失败",
                    feedback_id=str(feedback.id),
                    event_type="feedback.notify_user_error",
                )

        if feedback is not None and old_status is not None:
            logger.info(
                "反馈状态已更新",
                feedback_id=str(feedback.id),
                old_status=old_status,
                new_status=status,
                event_type="feedback.status_updated",
            )
        return feedback

    async def get_user_feedbacks(self, user_id: int, limit: int = 5) -> list[Feedback]:
        """获取用户自己的反馈列表（最近 N 条）。"""
        stmt = (
            select(Feedback)
            .where(Feedback.user_id == user_id)
            .order_by(Feedback.created_at.desc())
            .limit(limit)
        )

        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    # ════════════════════════════════════════════
    #  内部辅助
    # ════════════════════════════════════════════

    async def _notify_admins(self, feedback: Feedback) -> None:
        """通知所有管理员有新反馈（私有方法）。"""
        # 查询所有管理员
        async with self._session_factory() as session:
            result = await session.execute(select(User).where(User.relation == "admin"))
            admins = result.scalars().all()

        if not admins:
            logger.warning("无管理员可通知", event_type="feedback.no_admins")
            return

        # 构造通知消息
        source_text = "群聊" if feedback.source == FeedbackSource.GROUP else "私聊"
        type_text = feedback.feedback_type.value if feedback.feedback_type else "未分类"
        message = (
            f"【新反馈通知】\n"
            f"来源：{source_text}\n"
            f"类型：{type_text}\n"
            f"用户：{feedback.user_id}\n"
            f"内容：{feedback.content}\n"
            f"ID：{feedback.id}"
        )

        # 发送私聊消息给所有管理员
        for admin in admins:
            try:
                await self._bot_api.send_private_msg(admin.qq, message)
            except Exception:
                logger.warning(
                    "通知管理员失败",
                    admin_qq=admin.qq,
                    feedback_id=str(feedback.id),
                    event_type="feedback.notify_admin_failed",
                )

    async def _notify_user(self, feedback: Feedback) -> None:
        """通知用户反馈已处理（私有方法）。"""
        content_preview = (
            f"{feedback.content[:50]}..." if len(feedback.content) > 50 else feedback.content
        )
        message = f"【反馈处理通知】\n您的反馈已处理完成。\n反馈内容：{content_preview}\n"
        if feedback.admin_reply:
            message += f"管理员回复：{feedback.admin_reply}"

        try:
            if feedback.source == FeedbackSource.GROUP and feedback.group_id:
                await self._bot_api.send_group_msg(feedback.group_id, message)
            else:
                await self._bot_api.send_private_msg(feedback.user_id, message)
        except Exception:
            logger.warning(
                "通知用户失败",
                user_id=feedback.user_id,
                feedback_id=str(feedback.id),
                event_type="feedback.notify_user_failed",
            )
