"""add feedback table

Revision ID: e1f2a3b4c5d6
Revises: d1e2f3a4b5c6
Create Date: 2026-03-30 00:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: str | None = "d1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建 feedbacks 表。"""
    op.create_table(
        "feedbacks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="反馈 ID",
        ),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.qq", ondelete="CASCADE"),
            nullable=False,
            comment="提交者 QQ 号",
        ),
        sa.Column(
            "feedback_type",
            sa.String(20),
            nullable=True,
            comment="反馈类型",
        ),
        sa.Column(
            "content",
            sa.Text,
            nullable=False,
            comment="反馈内容",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            comment="状态",
        ),
        sa.Column(
            "admin_reply",
            sa.Text,
            nullable=True,
            comment="管理员回复",
        ),
        sa.Column(
            "source",
            sa.String(20),
            nullable=False,
            comment="来源",
        ),
        sa.Column(
            "group_id",
            sa.BigInteger,
            sa.ForeignKey("groups.group_id", ondelete="SET NULL"),
            nullable=True,
            comment="群号",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="提交时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="更新时间",
        ),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="处理时间",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "(source != 'group') OR (group_id IS NOT NULL)",
            name="ck_group_source_requires_group_id",
        ),
    )

    # 创建索引
    op.create_index("ix_feedbacks_user_id", "feedbacks", ["user_id"])
    op.create_index("ix_feedbacks_status", "feedbacks", ["status"])
    op.create_index("ix_feedbacks_created_at", "feedbacks", ["created_at"])
    op.create_index("ix_feedbacks_feedback_type", "feedbacks", ["feedback_type"])
    op.create_index("ix_feedbacks_group_id", "feedbacks", ["group_id"])


def downgrade() -> None:
    """删除 feedbacks 表。"""
    op.drop_index("ix_feedbacks_group_id", table_name="feedbacks")
    op.drop_index("ix_feedbacks_feedback_type", table_name="feedbacks")
    op.drop_index("ix_feedbacks_created_at", table_name="feedbacks")
    op.drop_index("ix_feedbacks_status", table_name="feedbacks")
    op.drop_index("ix_feedbacks_user_id", table_name="feedbacks")
    op.drop_table("feedbacks")
