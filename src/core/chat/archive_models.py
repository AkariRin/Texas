"""归档元数据 ORM 模型 —— 位于主库 texas。"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Date, Index, String, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db.base import Base

if TYPE_CHECKING:
    from datetime import date, datetime


class ChatArchiveLog(Base):
    """聊天记录归档日志表 —— 追踪每个月分区的归档状态。

    status 状态机：
        pending → exporting → uploading → uploaded → partition_dropped → completed
        任意阶段 → failed
    """

    __tablename__ = "chat_archive_log"
    __table_args__ = (
        Index("ix_archive_log_status", "status"),
        Index("ix_archive_log_period", "period_start"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    partition_name: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        comment="分区表名，如 chat_history_2024_01",
    )
    period_start: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="归档周期起始日期",
    )
    period_end: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="归档周期结束日期",
    )

    total_rows: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        comment="归档行数",
    )
    original_bytes: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        comment="原始数据大小（字节）",
    )
    compressed_bytes: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        comment="压缩后大小（字节）",
    )

    s3_bucket: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="",
        comment="S3 桶名",
    )
    s3_key: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        default="",
        comment="S3 对象键",
    )
    s3_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="",
        comment="归档文件 SHA256",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="归档状态: pending/exporting/uploading/uploaded/partition_dropped/completed/failed",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="错误信息",
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default="NOW()",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
