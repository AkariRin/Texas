"""移除 chat_history 表中无用的 self_id 列

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-16 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE chat.chat_history DROP COLUMN IF EXISTS self_id")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE chat.chat_history ADD COLUMN self_id BIGINT NOT NULL DEFAULT 0"
    )

