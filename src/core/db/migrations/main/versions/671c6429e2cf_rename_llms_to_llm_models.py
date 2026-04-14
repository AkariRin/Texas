"""rename llms to llm_models

Revision ID: 671c6429e2cf
Revises: 18fc58ec68b1
Create Date: 2026-04-08 12:48:12.600276

"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "671c6429e2cf"
down_revision: str | None = "18fc58ec68b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("llms", "llm_models")
    op.execute("ALTER INDEX IF EXISTS ix_llms_provider_id RENAME TO ix_llm_models_provider_id")


def downgrade() -> None:
    op.rename_table("llm_models", "llms")
    op.execute("ALTER INDEX IF EXISTS ix_llm_models_provider_id RENAME TO ix_llms_provider_id")
