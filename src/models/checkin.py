"""用户群签到记录 ORM 模型。"""

from __future__ import annotations

from datetime import date as date_
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db.base import Base

if TYPE_CHECKING:
    from src.models.personnel import Group, User


class CheckinRecord(Base):
    """用户群签到记录表。

    每行代表某用户在某群某日的一次签到，UNIQUE 约束防止重复签到。
    streak / total_count 不存于 DB，由 Redis 缓存或按需从历史日期重建。
    """

    __tablename__ = "checkin"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("groups.group_id", ondelete="CASCADE"),
        index=True,
        comment="群号",
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.qq", ondelete="CASCADE"),
        comment="签到用户 QQ",
    )
    checkin_date: Mapped[date_] = mapped_column(
        Date,
        index=True,
        comment="北京时间自然日，如 2026-04-17",
    )
    checkin_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        comment="精确签到时间（UTC），用于今日排名排序",
    )

    # ── 关系 ──
    group: Mapped["Group"] = relationship("Group", foreign_keys=[group_id], lazy="raise")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], lazy="raise")

    __table_args__ = (
        # 防止同一用户在同一群同一天重复签到（也是并发安全网）
        UniqueConstraint("group_id", "user_id", "checkin_date", name="uq_checkin_group_user_date"),
        Index("idx_checkin_user_group", "user_id", "group_id", "checkin_date"),
    )
