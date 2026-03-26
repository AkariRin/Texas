"""add system and bot_enabled

Revision ID: d1e2f3a4b5c6
Revises: c352f39d1de8
Create Date: 2026-03-26 00:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: str | None = "c352f39d1de8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # feature_registry 新增 system 列
    op.add_column(
        "feature_registry",
        sa.Column(
            "system",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="系统级功能，强制启用且前端不可见",
        ),
    )

    # groups 新增 bot_enabled 列
    op.add_column(
        "groups",
        sa.Column(
            "bot_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            comment="Bot 总开关（可关闭该群所有功能）",
        ),
    )


def downgrade() -> None:
    op.drop_column("groups", "bot_enabled")
    op.drop_column("feature_registry", "system")
