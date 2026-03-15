"""聊天记录 ORM 模型 —— 基于 PostgreSQL 范围分区。"""

from __future__ import annotations

from datetime import datetime
from enum import IntEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Index,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db.base import ChatBase


class MessageType(IntEnum):
    """消息类型枚举。"""

    PRIVATE = 1
    GROUP = 2
    SELF_SENT = 3


class ChatMessage(ChatBase):
    """聊天记录分区表 ORM 模型。

    底层是 PostgreSQL 按月范围分区表，ORM 只操作逻辑父表，
    PostgreSQL 自动将数据路由到正确的分区。
    """

    __tablename__ = "chat_history"
    __table_args__ = (
        # ── 索引 ──
        Index(
            "ix_chat_group_time",
            "group_id",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
            postgresql_where="group_id IS NOT NULL",
        ),
        Index(
            "ix_chat_user_time",
            "user_id",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
        ),
        Index(
            "ix_chat_message_id",
            "message_id",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
        ),
        Index(
            "ix_chat_type_time",
            "message_type",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
        ),
        # ── 分区声明 ──
        {
            "schema": "chat",
            "postgresql_partition_by": "RANGE (created_at)",
        },
    )

    # ── 主键（分区表主键必须包含分区键） ──
    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="自增主键",
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        primary_key=True,
        comment="消息发送时间（分区键）",
    )

    # ── 消息标识 ──
    message_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="OneBot message_id",
    )

    # ── 消息上下文 ──
    message_type: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        comment="1=private, 2=group, 3=self_sent",
    )
    group_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="群号（私聊为 NULL）",
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="发送者 QQ",
    )

    # ── 消息内容 ──
    raw_message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        comment="纯文本消息摘要",
    )
    segments: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="完整消息段数组（OneBot array 格式）",
    )

    # ── 发送者快照 ──
    sender_nickname: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="",
        comment="发送者昵称",
    )
    sender_card: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="群名片",
    )
    sender_role: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="群身份: owner/admin/member",
    )

    # ── 入库时间 ──
    stored_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default="NOW()",
        comment="实际入库时间",
    )
