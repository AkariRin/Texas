"""用户反馈 ORM 模型 —— Feedback 及相关枚举。"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.core.db.base import Base
from src.models.personnel import User


class FeedbackType(enum.StrEnum):
    """反馈类型枚举。"""

    BUG = "bug"
    SUGGESTION = "suggestion"
    COMPLAINT = "complaint"
    OTHER = "other"


class FeedbackStatus(enum.StrEnum):
    """反馈状态枚举。"""

    PENDING = "pending"
    PROCESSED = "processed"


class FeedbackSource(enum.StrEnum):
    """反馈来源枚举。"""

    GROUP = "group"
    PRIVATE = "private"


class Feedback(Base):
    """用户反馈表。"""

    __tablename__ = "feedbacks"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.qq"), index=True, comment="提交反馈的用户 QQ 号"
    )
    feedback_type: Mapped[FeedbackType | None] = mapped_column(
        Enum(FeedbackType, name="feedback_type_enum"), nullable=True, comment="反馈类型"
    )
    content: Mapped[str] = mapped_column(Text, comment="反馈内容")
    status: Mapped[FeedbackStatus] = mapped_column(
        Enum(FeedbackStatus, name="feedback_status_enum"),
        default=FeedbackStatus.PENDING,
        index=True,
        comment="处理状态",
    )
    admin_reply: Mapped[str | None] = mapped_column(Text, nullable=True, comment="管理员回复")
    source: Mapped[FeedbackSource] = mapped_column(
        Enum(FeedbackSource, name="feedback_source_enum"), comment="反馈来源"
    )
    group_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, index=True, comment="群号（仅群聊反馈）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="处理时间"
    )

    # CHECK 约束：source='group' 时 group_id 必须非空
    __table_args__ = (
        CheckConstraint(
            "(source != 'group') OR (group_id IS NOT NULL)",
            name="ck_group_feedback_has_group_id",
        ),
    )

    # 关联
    user: Mapped[User] = relationship(lazy="selectin")
