"""今日老婆（jrlp）抽取/预设记录 ORM 模型。"""

from __future__ import annotations

from datetime import date as date_
from datetime import datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db.base import Base
from src.models.personnel import Group, User


class WifeRecord(Base):
    """今日老婆抽取/预设记录表。

    drawn_at 为 null 表示管理员预设但用户尚未触发抽取；有值表示用户已抽取，值为抽取时间。
    """

    __tablename__ = "jrlp"

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
        index=True,
        comment="抽取者 QQ",
    )
    wife_qq: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.qq", ondelete="CASCADE"),
        comment="老婆 QQ",
    )
    date: Mapped[date_] = mapped_column(
        Date, index=True, comment="自然日（北京时间），如 2026-04-06"
    )
    drawn_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="抽取时间；null = 管理员预设未触发；有值 = 用户已抽取",
    )

    # ── 关系 ──
    group: Mapped[Group] = relationship(
        "Group",
        foreign_keys=[group_id],
        lazy="raise",
    )
    user: Mapped[User] = relationship(
        "User",
        foreign_keys=[user_id],
        lazy="raise",
    )
    wife: Mapped[User] = relationship(
        "User",
        foreign_keys=[wife_qq],
        lazy="raise",
    )

    __table_args__ = (
        UniqueConstraint("group_id", "user_id", "date", name="uq_jrlp_group_user_date"),
    )
