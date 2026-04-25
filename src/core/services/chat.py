"""聊天记录业务逻辑 —— 消息持久化、查询、统计。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import func, select, text

from src.core.db.utils import escape_like as _escape_like
from src.core.utils import SHANGHAI_TZ
from src.models.chat import ChatMessage, MessageType

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from src.core.protocol.models.events import (
        MessageEvent,
    )


class ChatDatabaseSettings(BaseSettings):
    """聊天库数据库配置（就近定义，env 变量名与全局 Settings 保持一致）。"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True
    )

    CHAT_DATABASE_URL: str = "postgresql+asyncpg://texas:texas@localhost:5432/chat_history"
    CHAT_DB_POOL_SIZE: int = Field(default=5, ge=1)
    CHAT_DB_MAX_OVERFLOW: int = Field(default=10, ge=0)

    @field_validator("CHAT_DATABASE_URL")
    @classmethod
    def validate_pg_url(cls, v: str) -> str:
        """校验数据库 URL 必须以 postgresql 开头。"""
        if not v.startswith("postgresql"):
            raise ValueError(f"数据库 URL 必须以 'postgresql' 开头，当前值: {v!r}")
        return v


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
            raw_message=event.raw_message,
            segments=segments,
            sender_nickname=event.sender.nickname or "",
            sender_card=getattr(event.sender, "card", None),
            sender_role=getattr(event.sender, "role", None),
            created_at=datetime.fromtimestamp(event.time, tz=SHANGHAI_TZ),
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
            stmt = stmt.where(
                ChatMessage.raw_message.ilike(f"%{_escape_like(keyword)}%", escape="\\")
            )
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
        keyword_filter = ChatMessage.raw_message.ilike(f"%{_escape_like(keyword)}%", escape="\\")
        stmt = select(ChatMessage).where(keyword_filter).order_by(ChatMessage.created_at.desc())

        count_stmt = select(func.count()).select_from(ChatMessage).where(keyword_filter)

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


# ── 生命周期注册 ──

from src.core.lifecycle import startup  # noqa: E402


@startup(
    name="chat",
    provides=["chat_service", "archive_service"],
    requires=["chat_engine", "session_factory"],
)
async def _lifecycle_start(deps: dict[str, Any]) -> dict[str, Any]:
    """聊天记录模块启动（聊天库 session factory 在此创建）。"""
    from src.core.db.engine import create_session_factory
    from src.core.services.archive_exporter import ChatArchiveSettings
    from src.core.services.archive_s3 import S3Settings
    from src.core.services.chat_archive import ArchiveService

    chat_session_factory = create_session_factory(deps["chat_engine"])
    chat_service = ChatHistoryService(session_factory=chat_session_factory)
    archive_service = ArchiveService(
        chat_session_factory=chat_session_factory,
        main_session_factory=deps["session_factory"],
        archive_settings=ChatArchiveSettings(),
        s3_settings=S3Settings(),
    )
    try:
        await archive_service.ensure_partitions()
        logger.info("聊天分区已就绪", event_type="chat.partitions_ensured")
    except Exception:
        logger.exception("启动时分区预创建失败", event_type="chat.partition_ensure_error")
    return {"chat_service": chat_service, "archive_service": archive_service}
