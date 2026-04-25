"""add_checkin_table

Revision ID: e2d880c45b41
Revises: d3f1a9c72e05
Create Date: 2026-04-18 14:22:41.680062

"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2d880c45b41"
down_revision: str | None = "d3f1a9c72e05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "checkin",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("group_id", sa.BigInteger(), nullable=False, comment="群号"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="签到用户 QQ"),
        sa.Column(
            "checkin_date", sa.Date(), nullable=False, comment="北京时间自然日，如 2026-04-17"
        ),
        sa.Column(
            "checkin_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="精确签到时间（UTC），用于今日排名排序",
        ),
        sa.ForeignKeyConstraint(["group_id"], ["groups.group_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.qq"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "group_id", "user_id", "checkin_date", name="uq_checkin_group_user_date"
        ),
    )
    op.create_index(
        "idx_checkin_user_group", "checkin", ["user_id", "group_id", "checkin_date"], unique=False
    )
    op.create_index(op.f("ix_checkin_checkin_date"), "checkin", ["checkin_date"], unique=False)
    op.create_index(op.f("ix_checkin_group_id"), "checkin", ["group_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_checkin_group_id"), table_name="checkin")
    op.drop_index(op.f("ix_checkin_checkin_date"), table_name="checkin")
    op.drop_index("idx_checkin_user_group", table_name="checkin")
    op.drop_table("checkin")
