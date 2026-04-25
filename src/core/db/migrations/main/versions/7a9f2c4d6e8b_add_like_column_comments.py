"""add_like_column_comments

Revision ID: 7a9f2c4d6e8b
Revises: e2d880c45b41
Create Date: 2026-04-18 14:23:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "7a9f2c4d6e8b"
down_revision: str | None = "e2d880c45b41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "like_history",
        "qq",
        existing_type=sa.BIGINT(),
        comment="被点赞对象 QQ（无外键约束）",
        existing_nullable=False,
    )
    op.alter_column(
        "like_history",
        "times",
        existing_type=sa.SMALLINT(),
        comment="本次点赞次数",
        existing_nullable=False,
    )
    op.alter_column(
        "like_history",
        "triggered_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        comment="执行时间（UTC）",
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "like_history",
        "source",
        existing_type=postgresql.ENUM("manual", "scheduled", name="likesource"),
        comment="触发来源：manual=手动，scheduled=定时",
        existing_nullable=False,
    )
    op.alter_column(
        "like_history",
        "success",
        existing_type=sa.BOOLEAN(),
        comment="是否成功",
        existing_nullable=False,
    )
    op.alter_column(
        "like_tasks",
        "qq",
        existing_type=sa.BIGINT(),
        comment="被点赞用户 QQ（无外键约束，全局唯一）",
        existing_nullable=False,
    )
    op.alter_column(
        "like_tasks",
        "registered_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        comment="注册时间（UTC）",
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "like_tasks",
        "registered_group_id",
        existing_type=sa.BIGINT(),
        comment="注册时所在群（私聊注册为 null），仅记录来源，不影响执行",
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "like_tasks",
        "registered_group_id",
        existing_type=sa.BIGINT(),
        comment=None,
        existing_comment="注册时所在群（私聊注册为 null），仅记录来源，不影响执行",
        existing_nullable=True,
    )
    op.alter_column(
        "like_tasks",
        "registered_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        comment=None,
        existing_comment="注册时间（UTC）",
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "like_tasks",
        "qq",
        existing_type=sa.BIGINT(),
        comment=None,
        existing_comment="被点赞用户 QQ（无外键约束，全局唯一）",
        existing_nullable=False,
    )
    op.alter_column(
        "like_history",
        "success",
        existing_type=sa.BOOLEAN(),
        comment=None,
        existing_comment="是否成功",
        existing_nullable=False,
    )
    op.alter_column(
        "like_history",
        "source",
        existing_type=postgresql.ENUM("manual", "scheduled", name="likesource"),
        comment=None,
        existing_comment="触发来源：manual=手动，scheduled=定时",
        existing_nullable=False,
    )
    op.alter_column(
        "like_history",
        "triggered_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        comment=None,
        existing_comment="执行时间（UTC）",
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "like_history",
        "times",
        existing_type=sa.SMALLINT(),
        comment=None,
        existing_comment="本次点赞次数",
        existing_nullable=False,
    )
    op.alter_column(
        "like_history",
        "qq",
        existing_type=sa.BIGINT(),
        comment=None,
        existing_comment="被点赞对象 QQ（无外键约束）",
        existing_nullable=False,
    )
