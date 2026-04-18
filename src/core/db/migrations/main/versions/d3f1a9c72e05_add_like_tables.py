"""add_like_tables

Revision ID: d3f1a9c72e05
Revises: c9e3a17f2b84
Create Date: 2026-04-18 00:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

from alembic import op

revision: str = "d3f1a9c72e05"
down_revision: str | None = "c9e3a17f2b84"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 使用原生 SQL 绕过 SQLAlchemy Enum 事件系统，避免 ORM 模型导入时注册的
    # _on_table_create 监听器与显式 CREATE TYPE 产生竞争导致 DuplicateObjectError

    # 点赞来源枚举类型
    op.execute("CREATE TYPE likesource AS ENUM ('manual', 'scheduled')")

    # 定时点赞任务表
    op.execute("""
        CREATE TABLE like_tasks (
            id         SERIAL        PRIMARY KEY,
            qq         BIGINT        NOT NULL,
            registered_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
            registered_group_id  BIGINT
        )
    """)
    op.execute("ALTER TABLE like_tasks ADD CONSTRAINT uq_like_tasks_qq UNIQUE (qq)")

    # 点赞执行历史表
    op.execute("""
        CREATE TABLE like_history (
            id           SERIAL      PRIMARY KEY,
            qq           BIGINT      NOT NULL,
            times        SMALLINT    NOT NULL,
            triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            source       likesource  NOT NULL,
            success      BOOLEAN     NOT NULL
        )
    """)
    op.execute("CREATE INDEX ix_like_history_qq_triggered_at ON like_history (qq, triggered_at)")
    op.execute(
        "CREATE INDEX ix_like_history_source_triggered_at ON like_history (source, triggered_at)"
    )


def downgrade() -> None:
    op.drop_index("ix_like_history_source_triggered_at", table_name="like_history")
    op.drop_index("ix_like_history_qq_triggered_at", table_name="like_history")
    op.drop_table("like_history")
    op.drop_table("like_tasks")
    op.execute("DROP TYPE IF EXISTS likesource")
