"""聊天记录业务逻辑 —— 消息持久化、查询、统计。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import Date, Integer, cast, extract, func, select, text

from src.core.chat.models import ChatMessage, MessageType

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from src.core.protocol.models.events import (
        MessageEvent,
    )

logger = structlog.get_logger()


class ChatHistoryService:
    """聊天记录核心服务 —— 封装消息写入、查询、统计。"""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    # ════════════════════════════════════════════
    #  写入
    # ════════════════════════════════════════════

    async def save_message(self, event: MessageEvent) -> None:
        """将 OneBot 消息事件持久化到聊天记录库。"""
        from src.core.protocol.models.events import (
            GroupMessageEvent,
            MessageSentEvent,
        )

        # 确定消息类型
        if isinstance(event, MessageSentEvent):
            msg_type = MessageType.SELF_SENT
        elif isinstance(event, GroupMessageEvent):
            msg_type = MessageType.GROUP
        else:
            msg_type = MessageType.PRIVATE

        # 序列化 segments
        segments: list[dict[str, Any]]
        if isinstance(event.message, list):
            segments = [seg.model_dump() for seg in event.message]
        else:
            segments = []

        msg = ChatMessage(
            message_id=event.message_id,
            message_type=msg_type,
            group_id=getattr(event, "group_id", None) or None,
            user_id=event.user_id,
            self_id=event.self_id,
            raw_message=event.raw_message,
            segments=segments,
            sender_nickname=event.sender.nickname or "",
            sender_card=getattr(event.sender, "card", None),
            sender_role=getattr(event.sender, "role", None),
            created_at=datetime.fromtimestamp(event.time, tz=UTC),
        )

        try:
            async with self._session_factory() as session:
                session.add(msg)
                await session.commit()
        except Exception:
            logger.exception(
                "消息持久化失败",
                message_id=event.message_id,
                event_type="chat.save_error",
            )

    # ════════════════════════════════════════════
    #  查询
    # ════════════════════════════════════════════

    async def get_group_messages(
        self,
        group_id: int,
        before: datetime | None = None,
        limit: int = 50,
        keyword: str | None = None,
        user_id: int | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """查询群聊消息（游标分页，支持筛选）。"""
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.group_id == group_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )

        if before:
            stmt = stmt.where(ChatMessage.created_at < before)
        elif not start_date:
            # 默认只查最近 30 天，强制分区裁剪
            stmt = stmt.where(ChatMessage.created_at > func.now() - text("INTERVAL '30 days'"))

        if keyword:
            stmt = stmt.where(ChatMessage.raw_message.ilike(f"%{keyword}%"))
        if user_id:
            stmt = stmt.where(ChatMessage.user_id == user_id)
        if start_date:
            stmt = stmt.where(ChatMessage.created_at >= start_date)
        if end_date:
            stmt = stmt.where(ChatMessage.created_at <= end_date)

        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return [self._row_to_dict(row) for row in result.scalars().all()]

    async def get_private_messages(
        self,
        user_id: int,
        before: datetime | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """查询私聊消息（游标分页）。"""
        stmt = (
            select(ChatMessage)
            .where(
                ChatMessage.user_id == user_id,
                ChatMessage.message_type == MessageType.PRIVATE,
            )
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )

        if before:
            stmt = stmt.where(ChatMessage.created_at < before)
        else:
            stmt = stmt.where(ChatMessage.created_at > func.now() - text("INTERVAL '30 days'"))

        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return [self._row_to_dict(row) for row in result.scalars().all()]

    async def get_message_context(
        self,
        message_id: int,
        created_at: datetime,
        context_size: int = 5,
    ) -> dict[str, list[dict[str, Any]]]:
        """获取消息上下文（前后 N 条）。"""
        # 先获取目标消息的 group_id / user_id
        async with self._session_factory() as session:
            target_stmt = select(ChatMessage).where(
                ChatMessage.message_id == message_id,
                ChatMessage.created_at >= created_at - timedelta(seconds=1),
                ChatMessage.created_at <= created_at + timedelta(seconds=1),
            )
            target_result = await session.execute(target_stmt)
            target = target_result.scalars().first()

            if not target:
                return {"before": [], "current": [], "after": []}

            # 构建同会话过滤条件
            if target.group_id:
                session_filter = ChatMessage.group_id == target.group_id
            else:
                session_filter = (ChatMessage.user_id == target.user_id) & (
                    ChatMessage.message_type == MessageType.PRIVATE
                )

            # 获取之前的消息
            before_stmt = (
                select(ChatMessage)
                .where(session_filter, ChatMessage.created_at < target.created_at)
                .order_by(ChatMessage.created_at.desc())
                .limit(context_size)
            )
            before_result = await session.execute(before_stmt)
            before_msgs = [self._row_to_dict(r) for r in reversed(before_result.scalars().all())]

            # 获取之后的消息
            after_stmt = (
                select(ChatMessage)
                .where(session_filter, ChatMessage.created_at > target.created_at)
                .order_by(ChatMessage.created_at.asc())
                .limit(context_size)
            )
            after_result = await session.execute(after_stmt)
            after_msgs = [self._row_to_dict(r) for r in after_result.scalars().all()]

            return {
                "before": before_msgs,
                "current": [self._row_to_dict(target)],
                "after": after_msgs,
            }

    async def search_messages(
        self,
        keyword: str,
        group_id: int | None = None,
        user_id: int | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """搜索消息（关键词 + 筛选条件）。"""
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.raw_message.ilike(f"%{keyword}%"))
            .order_by(ChatMessage.created_at.desc())
        )

        count_stmt = (
            select(func.count())
            .select_from(ChatMessage)
            .where(ChatMessage.raw_message.ilike(f"%{keyword}%"))
        )

        if group_id:
            stmt = stmt.where(ChatMessage.group_id == group_id)
            count_stmt = count_stmt.where(ChatMessage.group_id == group_id)
        if user_id:
            stmt = stmt.where(ChatMessage.user_id == user_id)
            count_stmt = count_stmt.where(ChatMessage.user_id == user_id)
        if start_date:
            stmt = stmt.where(ChatMessage.created_at >= start_date)
            count_stmt = count_stmt.where(ChatMessage.created_at >= start_date)
        if end_date:
            stmt = stmt.where(ChatMessage.created_at <= end_date)
            count_stmt = count_stmt.where(ChatMessage.created_at <= end_date)

        if not start_date and not end_date:
            time_filter = ChatMessage.created_at > func.now() - text("INTERVAL '90 days'")
            stmt = stmt.where(time_filter)
            count_stmt = count_stmt.where(time_filter)

        stmt = stmt.offset(offset).limit(limit)

        async with self._session_factory() as session:
            total_result = await session.execute(count_stmt)
            total = total_result.scalar() or 0

            result = await session.execute(stmt)
            messages = [self._row_to_dict(row) for row in result.scalars().all()]

        return {"items": messages, "total": total}

    # ════════════════════════════════════════════
    #  统计
    # ════════════════════════════════════════════

    async def get_overview_stats(self, group_id: int | None = None) -> dict[str, Any]:
        """获取消息统计概览。"""
        async with self._session_factory() as session:
            base_filter = []
            if group_id:
                base_filter.append(ChatMessage.group_id == group_id)

            # 总消息数
            total_stmt = select(func.count()).select_from(ChatMessage)
            for f in base_filter:
                total_stmt = total_stmt.where(f)
            total_result = await session.execute(total_stmt)
            total_messages = total_result.scalar() or 0

            # 今日新增
            today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            today_stmt = (
                select(func.count())
                .select_from(ChatMessage)
                .where(ChatMessage.created_at >= today_start)
            )
            for f in base_filter:
                today_stmt = today_stmt.where(f)
            today_result = await session.execute(today_stmt)
            today_messages = today_result.scalar() or 0

            # 活跃群数（近 7 天有消息的群）
            active_groups_stmt = select(func.count(func.distinct(ChatMessage.group_id))).where(
                ChatMessage.group_id.is_not(None),
                ChatMessage.created_at > func.now() - text("INTERVAL '7 days'"),
            )
            groups_result = await session.execute(active_groups_stmt)
            active_groups = groups_result.scalar() or 0

            # 活跃用户数（近 7 天有消息的用户）
            active_users_stmt = select(func.count(func.distinct(ChatMessage.user_id))).where(
                ChatMessage.created_at > func.now() - text("INTERVAL '7 days'"),
            )
            for f in base_filter:
                active_users_stmt = active_users_stmt.where(f)
            users_result = await session.execute(active_users_stmt)
            active_users = users_result.scalar() or 0

            return {
                "total_messages": total_messages,
                "today_messages": today_messages,
                "active_groups": active_groups,
                "active_users": active_users,
            }

    async def get_trend_data(
        self,
        group_id: int | None = None,
        granularity: str = "day",
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """获取消息趋势数据。"""
        since = datetime.now(UTC) - timedelta(days=days)

        if granularity == "month":
            date_trunc = func.date_trunc("month", ChatMessage.created_at)
        else:
            date_trunc = func.date_trunc("day", ChatMessage.created_at)

        stmt = (
            select(
                date_trunc.label("period"),
                func.count().label("count"),
            )
            .where(ChatMessage.created_at >= since)
            .group_by("period")
            .order_by("period")
        )

        if group_id:
            stmt = stmt.where(ChatMessage.group_id == group_id)

        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return [{"period": row.period.isoformat(), "count": row.count} for row in result.all()]

    async def get_heatmap_data(self, group_id: int | None = None) -> list[dict[str, Any]]:
        """获取时段热力图数据（星期 × 小时）。"""
        since = datetime.now(UTC) - timedelta(days=90)

        dow = extract("dow", ChatMessage.created_at).label("day_of_week")
        hour = extract("hour", ChatMessage.created_at).label("hour")

        stmt = (
            select(
                cast(dow, Integer),
                cast(hour, Integer),
                func.count().label("count"),
            )
            .where(ChatMessage.created_at >= since)
            .group_by("day_of_week", "hour")
            .order_by("day_of_week", "hour")
        )

        if group_id:
            stmt = stmt.where(ChatMessage.group_id == group_id)

        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return [
                {"day_of_week": row[0], "hour": row[1], "count": row[2]} for row in result.all()
            ]

    async def get_group_ranking(self, limit: int = 10) -> list[dict[str, Any]]:
        """获取群消息量排行。"""
        since = datetime.now(UTC) - timedelta(days=30)

        stmt = (
            select(
                ChatMessage.group_id,
                func.count().label("message_count"),
                func.count(func.distinct(ChatMessage.user_id)).label("active_members"),
            )
            .where(
                ChatMessage.group_id.is_not(None),
                ChatMessage.created_at >= since,
            )
            .group_by(ChatMessage.group_id)
            .order_by(func.count().desc())
            .limit(limit)
        )

        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return [
                {
                    "group_id": row.group_id,
                    "message_count": row.message_count,
                    "active_members": row.active_members,
                }
                for row in result.all()
            ]

    async def get_user_ranking(
        self, group_id: int | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        """获取用户消息量排行。"""
        since = datetime.now(UTC) - timedelta(days=30)

        stmt = (
            select(
                ChatMessage.user_id,
                ChatMessage.sender_nickname,
                func.count().label("message_count"),
            )
            .where(ChatMessage.created_at >= since)
            .group_by(ChatMessage.user_id, ChatMessage.sender_nickname)
            .order_by(func.count().desc())
            .limit(limit)
        )

        if group_id:
            stmt = stmt.where(ChatMessage.group_id == group_id)

        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return [
                {
                    "user_id": row.user_id,
                    "nickname": row.sender_nickname,
                    "message_count": row.message_count,
                }
                for row in result.all()
            ]

    async def get_message_stats(self, group_id: int | None = None) -> dict[str, Any]:
        """获取消息统计详情。"""
        async with self._session_factory() as session:
            base_where = []
            if group_id:
                base_where.append(ChatMessage.group_id == group_id)

            # 消息类型分布
            type_stmt = select(
                ChatMessage.message_type,
                func.count().label("count"),
            ).group_by(ChatMessage.message_type)
            for f in base_where:
                type_stmt = type_stmt.where(f)
            type_result = await session.execute(type_stmt)
            type_dist = {str(row.message_type): row.count for row in type_result.all()}

            # 近 7 天每天消息数
            since = datetime.now(UTC) - timedelta(days=7)
            daily_stmt = (
                select(
                    cast(func.date_trunc("day", ChatMessage.created_at), Date).label("day"),
                    func.count().label("count"),
                )
                .where(ChatMessage.created_at >= since)
                .group_by("day")
                .order_by("day")
            )
            for f in base_where:
                daily_stmt = daily_stmt.where(f)
            daily_result = await session.execute(daily_stmt)
            daily = [{"day": str(row.day), "count": row.count} for row in daily_result.all()]

            return {
                "type_distribution": type_dist,
                "daily_counts": daily,
            }

    # ════════════════════════════════════════════
    #  内部工具
    # ════════════════════════════════════════════

    @staticmethod
    def _row_to_dict(msg: ChatMessage) -> dict[str, Any]:
        """将 ORM 对象转换为字典。"""
        return {
            "id": msg.id,
            "message_id": msg.message_id,
            "message_type": msg.message_type,
            "group_id": msg.group_id,
            "user_id": msg.user_id,
            "raw_message": msg.raw_message,
            "segments": msg.segments,
            "sender_nickname": msg.sender_nickname,
            "sender_card": msg.sender_card,
            "sender_role": msg.sender_role,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
            "stored_at": msg.stored_at.isoformat() if msg.stored_at else None,
        }
