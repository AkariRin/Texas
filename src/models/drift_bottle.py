"""漂流瓶 ORM 模型 —— 漂流瓶池、群池映射、漂流瓶本体。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db.base import Base

DRIFT_BOTTLE_DEFAULT_POOL_ID: Final = 0

# OneBot array 格式消息段，每个元素形如 {"type": "text", "data": {...}}
type MessageSegment = dict[str, Any]


class DriftBottlePool(Base):
    """漂流瓶池表。

    id=0 为系统保留的默认池，由迁移 seed 写入，不可删除。
    用户自建池 id 从 1 自增（独立序列 drift_bottle_pools_id_seq）。
    """

    __tablename__ = "drift_bottle_pools"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=False,
        comment="0=默认池（seed），1+ 用户自建",
    )
    name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        comment="池名称",
    )


class DriftBottleGroupPool(Base):
    """群池映射表。

    无记录的群隐式属于默认池（id=0）。
    group_id 无外键约束，不依赖 groups 表。
    """

    __tablename__ = "drift_bottle_group_pools"

    group_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        comment="群号（无外键约束）",
    )
    pool_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("drift_bottle_pools.id", ondelete="RESTRICT"),
        nullable=False,
        comment="所属漂流瓶池 id",
    )


class DriftBottleItem(Base):
    """漂流瓶本体表。

    每条记录为一个漂流瓶，is_picked=True 表示已被捞取（一次性消耗）。
    """

    __tablename__ = "drift_bottle_items"

    __table_args__ = (
        # 捞瓶核心查询路径：按池过滤未捞取的瓶子
        Index("ix_drift_bottle_items_pool_is_picked", "pool_id", "is_picked"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pool_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("drift_bottle_pools.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属池 id",
    )
    sender_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
        comment="发送者 QQ（无外键，防级联删）",
    )
    sender_group_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="来源群号",
    )
    content: Mapped[list[MessageSegment]] = mapped_column(
        JSONB,
        nullable=False,
        comment="过滤后消息段（仅 text/image，OneBot array 格式）",
    )
    is_picked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="false=待捞取，true=已捞取",
    )
    picked_by: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="捞取者 QQ",
    )
    picked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="捞取时间",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="NOW()",
        comment="投入时间",
    )
