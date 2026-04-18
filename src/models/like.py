"""点赞任务与历史记录 ORM 模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Index, Integer, SmallInteger, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db.base import Base
from src.models.enums import LikeSource


class LikeTask(Base):
    """定时点赞任务表。

    每条记录代表一个已注册每日自动点赞的用户，全局唯一（一人一条）。
    qq 字段不设外键约束，避免用户未入库时注册失败。
    """

    __tablename__ = "like_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    qq: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        comment="被点赞用户 QQ（无外键约束，全局唯一）",
    )
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="注册时间（UTC）",
    )
    registered_group_id: Mapped[int | None] = mapped_column(
        BigInteger,
        comment="注册时所在群（私聊注册为 null），仅记录来源，不影响执行",
    )


class LikeHistory(Base):
    """点赞执行历史记录表。

    记录每次点赞操作（手动或定时），qq 不设外键约束，允许用户已不存在。
    """

    __tablename__ = "like_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    qq: Mapped[int] = mapped_column(
        BigInteger,
        comment="被点赞对象 QQ（无外键约束）",
    )
    times: Mapped[int] = mapped_column(
        SmallInteger,
        comment="本次点赞次数",
    )
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="执行时间（UTC）",
    )
    source: Mapped[LikeSource] = mapped_column(
        Enum(LikeSource, name="likesource"),
        comment="触发来源：manual=手动，scheduled=定时",
    )
    success: Mapped[bool] = mapped_column(
        Boolean,
        comment="是否成功",
    )

    __table_args__ = (
        Index("ix_like_history_qq_triggered_at", "qq", "triggered_at"),
        Index("ix_like_history_source_triggered_at", "source", "triggered_at"),
    )
