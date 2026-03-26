"""初始化聊天记录库 — schema、分区表、索引、分区管理函数

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-03-10 00:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. 创建 schema
    op.execute("CREATE SCHEMA IF NOT EXISTS chat")

    # 2. 创建分区父表
    op.execute("""
        CREATE TABLE chat.chat_history (
            id              BIGINT GENERATED ALWAYS AS IDENTITY,
            message_id      BIGINT          NOT NULL,
            message_type    SMALLINT        NOT NULL,
            group_id        BIGINT,
            user_id         BIGINT          NOT NULL,
            self_id         BIGINT          NOT NULL,
            raw_message     TEXT            NOT NULL DEFAULT '',
            segments        JSONB           NOT NULL,
            sender_nickname VARCHAR(64)     NOT NULL DEFAULT '',
            sender_card     VARCHAR(64),
            sender_role     VARCHAR(10),
            created_at      TIMESTAMPTZ     NOT NULL,
            stored_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at)
    """)

    # 3. 索引（自动继承到所有分区）
    op.execute("""
        CREATE INDEX ix_chat_group_time
            ON chat.chat_history (group_id, created_at DESC)
            WHERE group_id IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX ix_chat_user_time
            ON chat.chat_history (user_id, created_at DESC)
    """)
    op.execute("""
        CREATE INDEX ix_chat_message_id
            ON chat.chat_history (message_id, created_at DESC)
    """)
    op.execute("""
        CREATE INDEX ix_chat_type_time
            ON chat.chat_history (message_type, created_at DESC)
    """)

    # 4. 分区创建函数
    op.execute("""
        CREATE OR REPLACE FUNCTION chat.create_monthly_partition(
            target_date DATE DEFAULT CURRENT_DATE + INTERVAL '1 month'
        )
        RETURNS TEXT AS $$
        DECLARE
            partition_name TEXT;
            start_date DATE;
            end_date DATE;
        BEGIN
            start_date := DATE_TRUNC('month', target_date);
            end_date := start_date + INTERVAL '1 month';
            partition_name := 'chat_history_' || TO_CHAR(start_date, 'YYYY_MM');

            EXECUTE format(
                'CREATE TABLE IF NOT EXISTS chat.%I PARTITION OF chat.chat_history
                 FOR VALUES FROM (%L) TO (%L)',
                partition_name, start_date, end_date
            );

            RETURN partition_name;
        END;
        $$ LANGUAGE plpgsql
    """)

    # 5. 创建当月和下月分区
    op.execute("SELECT chat.create_monthly_partition(CURRENT_DATE)")
    op.execute("SELECT chat.create_monthly_partition((CURRENT_DATE + INTERVAL '1 month')::DATE)")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS chat.create_monthly_partition(DATE)")
    op.execute("DROP TABLE IF EXISTS chat.chat_history CASCADE")
    op.execute("DROP SCHEMA IF EXISTS chat CASCADE")
