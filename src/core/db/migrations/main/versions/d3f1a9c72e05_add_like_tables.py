"""add_like_tables

Revision ID: d3f1a9c72e05
Revises: c9e3a17f2b84
Create Date: 2026-04-18 00:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d3f1a9c72e05"
down_revision: str | None = "c9e3a17f2b84"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 点赞来源枚举类型
    op.execute("CREATE TYPE likesource AS ENUM ('manual', 'scheduled')")

    # 定时点赞任务表
    op.create_table(
        "like_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "qq",
            sa.BigInteger(),
            nullable=False,
            comment="被点赞用户 QQ（无外键约束，全局唯一）",
        ),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
            comment="注册时间（UTC）",
        ),
        sa.Column(
            "registered_group_id",
            sa.BigInteger(),
            nullable=True,
            comment="注册时所在群（私聊注册为 null）",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("qq", name="uq_like_tasks_qq"),
    )

    # 点赞执行历史表
    op.create_table(
        "like_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "qq",
            sa.BigInteger(),
            nullable=False,
            comment="被点赞对象 QQ（无外键约束）",
        ),
        sa.Column("times", sa.SmallInteger(), nullable=False, comment="本次点赞次数"),
        sa.Column(
            "triggered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
            comment="执行时间（UTC）",
        ),
        sa.Column(
            "source",
            sa.Enum("manual", "scheduled", name="likesource"),
            nullable=False,
            comment="触发来源",
        ),
        sa.Column("success", sa.Boolean(), nullable=False, comment="是否成功"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_like_history_qq_triggered_at",
        "like_history",
        ["qq", "triggered_at"],
    )
    op.create_index(
        "ix_like_history_source_triggered_at",
        "like_history",
        ["source", "triggered_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_like_history_source_triggered_at", table_name="like_history")
    op.drop_index("ix_like_history_qq_triggered_at", table_name="like_history")
    op.drop_table("like_history")
    op.drop_table("like_tasks")
    op.execute("DROP TYPE IF EXISTS likesource")
