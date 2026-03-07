"""MessageLog —— 存储用于分析的消息历史记录。"""

from __future__ import annotations

from sqlalchemy import BigInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db.base import Base


class MessageLog(Base):
    __tablename__ = "message_logs"

    # NapCat 的消息 ID 是哈希生成的正整数（非顺序）。
    # LRU 淘汰前约可保留 5000 条消息。已撤回的消息无法恢复。
    message_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    group_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    message_type: Mapped[str] = mapped_column(String(16))  # private | group
    raw_message: Mapped[str] = mapped_column(Text, default="")
