"""auto — chat_history 已迁移至独立 Alembic 实例 (alembic_chat.ini)，此版本保留为空。

Revision ID: b8db8cff95a9
Revises: ca4d83f14568
Create Date: 2026-03-10 18:27:39.286569

"""

from __future__ import annotations

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "b8db8cff95a9"
down_revision: Union[str, None] = "ca4d83f14568"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # chat.chat_history 及其索引由 alembic_chat.ini 独立管理，主库不再处理。
    pass


def downgrade() -> None:
    # chat.chat_history 及其索引由 alembic_chat.ini 独立管理，主库不再处理。
    pass
