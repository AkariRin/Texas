"""rename feedback_status processed to done

Revision ID: b1c2d3e4f5a6
Revises: 909e0f6e41ff
Create Date: 2026-03-30 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "40462e8f06d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 将枚举值 'processed' 重命名为 'done'（PostgreSQL 10+）
    op.execute("ALTER TYPE feedback_status_enum RENAME VALUE 'processed' TO 'done'")


def downgrade() -> None:
    op.execute("ALTER TYPE feedback_status_enum RENAME VALUE 'done' TO 'processed'")
