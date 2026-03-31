"""auto

Revision ID: 909e0f6e41ff
Revises: e1f2a3b4c5d6
Create Date: 2026-03-31 10:12:50.329667

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "909e0f6e41ff"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 先创建枚举类型（ALTER COLUMN 之前必须存在，值均为小写）
    op.execute("CREATE TYPE feedback_type_enum AS ENUM ('bug', 'suggestion', 'complaint', 'other')")
    op.execute("CREATE TYPE feedback_status_enum AS ENUM ('pending', 'processed')")
    op.execute("CREATE TYPE feedback_source_enum AS ENUM ('group', 'private')")

    # 2. 纯注释变更（不涉及类型）
    op.alter_column(
        "feedbacks",
        "id",
        existing_type=sa.UUID(),
        comment=None,
        existing_comment="反馈 ID",
        existing_nullable=False,
    )
    op.alter_column(
        "feedbacks",
        "user_id",
        existing_type=sa.BIGINT(),
        comment="提交反馈的用户 QQ 号",
        existing_comment="提交者 QQ 号",
        existing_nullable=False,
    )
    op.alter_column(
        "feedbacks",
        "group_id",
        existing_type=sa.BIGINT(),
        comment="群号（仅群聊反馈）",
        existing_comment="群号",
        existing_nullable=True,
    )
    op.alter_column(
        "feedbacks",
        "created_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        comment="创建时间",
        existing_comment="提交时间",
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )

    # 3. feedback_type: VARCHAR -> enum（nullable，无 server_default，值已是小写）
    op.alter_column(
        "feedbacks",
        "feedback_type",
        existing_type=sa.VARCHAR(length=20),
        type_=sa.Enum("bug", "suggestion", "complaint", "other", name="feedback_type_enum"),
        postgresql_using="feedback_type::feedback_type_enum",
        existing_comment="反馈类型",
        existing_nullable=True,
    )

    # 4. status: 有 server_default='pending'，必须先 DROP DEFAULT 再转换再 SET DEFAULT
    op.execute("ALTER TABLE feedbacks ALTER COLUMN status DROP DEFAULT")
    op.execute(
        "ALTER TABLE feedbacks ALTER COLUMN status "
        "TYPE feedback_status_enum USING status::feedback_status_enum"
    )
    op.execute(
        "ALTER TABLE feedbacks ALTER COLUMN status SET DEFAULT 'pending'::feedback_status_enum"
    )
    op.alter_column(
        "feedbacks",
        "status",
        existing_type=sa.Enum("pending", "processed", name="feedback_status_enum"),
        comment="处理状态",
        existing_comment="状态",
        existing_nullable=False,
    )

    # 5. source: VARCHAR -> enum（无 server_default，值已是小写）
    op.alter_column(
        "feedbacks",
        "source",
        existing_type=sa.VARCHAR(length=20),
        type_=sa.Enum("group", "private", name="feedback_source_enum"),
        postgresql_using="source::feedback_source_enum",
        comment="反馈来源",
        existing_comment="来源",
        existing_nullable=False,
    )

    op.drop_index(op.f("ix_feedbacks_created_at"), table_name="feedbacks")


def downgrade() -> None:
    op.create_index(op.f("ix_feedbacks_created_at"), "feedbacks", ["created_at"], unique=False)

    op.alter_column(
        "feedbacks",
        "created_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        comment="提交时间",
        existing_comment="创建时间",
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "feedbacks",
        "group_id",
        existing_type=sa.BIGINT(),
        comment="群号",
        existing_comment="群号（仅群聊反馈）",
        existing_nullable=True,
    )

    # source: enum -> VARCHAR
    op.alter_column(
        "feedbacks",
        "source",
        existing_type=sa.Enum("group", "private", name="feedback_source_enum"),
        type_=sa.VARCHAR(length=20),
        postgresql_using="source::varchar",
        comment="来源",
        existing_comment="反馈来源",
        existing_nullable=False,
    )

    # status: 先 DROP DEFAULT，转回 VARCHAR，再 SET DEFAULT
    op.execute("ALTER TABLE feedbacks ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE feedbacks ALTER COLUMN status TYPE VARCHAR(20) USING status::varchar")
    op.execute("ALTER TABLE feedbacks ALTER COLUMN status SET DEFAULT 'pending'")
    op.alter_column(
        "feedbacks",
        "status",
        existing_type=sa.VARCHAR(length=20),
        comment="状态",
        existing_comment="处理状态",
        existing_nullable=False,
    )

    # feedback_type: enum -> VARCHAR
    op.alter_column(
        "feedbacks",
        "feedback_type",
        existing_type=sa.Enum("bug", "suggestion", "complaint", "other", name="feedback_type_enum"),
        type_=sa.VARCHAR(length=20),
        postgresql_using="feedback_type::varchar",
        existing_comment="反馈类型",
        existing_nullable=True,
    )

    op.alter_column(
        "feedbacks",
        "user_id",
        existing_type=sa.BIGINT(),
        comment="提交者 QQ 号",
        existing_comment="提交反馈的用户 QQ 号",
        existing_nullable=False,
    )
    op.alter_column(
        "feedbacks", "id", existing_type=sa.UUID(), comment="反馈 ID", existing_nullable=False
    )

    # 删除枚举类型
    op.execute("DROP TYPE IF EXISTS feedback_source_enum")
    op.execute("DROP TYPE IF EXISTS feedback_status_enum")
    op.execute("DROP TYPE IF EXISTS feedback_type_enum")
