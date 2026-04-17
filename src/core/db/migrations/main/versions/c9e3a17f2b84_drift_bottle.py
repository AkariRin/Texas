"""drift_bottle

Revision ID: c9e3a17f2b84
Revises: 99895e523017
Create Date: 2026-04-18 00:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c9e3a17f2b84"
down_revision: str | None = "99895e523017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 漂流瓶池表（id=0 为系统保留默认池，由后续 seed 写入）
    op.create_table(
        "drift_bottle_pools",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=False,
            nullable=False,
            comment="0=默认池（seed），1+ 用户自建",
        ),
        sa.Column("name", sa.String(length=64), nullable=False, comment="池名称"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # 群池映射表（无记录的群隐式属于默认池 id=0）
    op.create_table(
        "drift_bottle_group_pools",
        sa.Column("group_id", sa.BigInteger(), nullable=False, comment="群号（无外键约束）"),
        sa.Column("pool_id", sa.Integer(), nullable=False, comment="所属漂流瓶池 id"),
        sa.ForeignKeyConstraint(["pool_id"], ["drift_bottle_pools.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("group_id"),
    )

    # 漂流瓶本体表
    op.create_table(
        "drift_bottle_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("pool_id", sa.Integer(), nullable=False, comment="所属池 id"),
        sa.Column(
            "sender_id",
            sa.BigInteger(),
            nullable=False,
            comment="发送者 QQ（无外键，防级联删）",
        ),
        sa.Column("sender_group_id", sa.BigInteger(), nullable=False, comment="来源群号"),
        sa.Column(
            "content",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="过滤后消息段（仅 text/image，OneBot array 格式）",
        ),
        sa.Column(
            "is_picked",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="false=待捞取，true=已捞取",
        ),
        sa.Column("picked_by", sa.BigInteger(), nullable=True, comment="捞取者 QQ"),
        sa.Column(
            "picked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="捞取时间",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
            comment="投入时间",
        ),
        sa.ForeignKeyConstraint(["pool_id"], ["drift_bottle_pools.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    # 捞瓶核心查询路径：按池过滤未捞取的瓶子
    op.create_index(
        "ix_drift_bottle_items_pool_is_picked",
        "drift_bottle_items",
        ["pool_id", "is_picked"],
    )
    # 查询用户自己历史的索引
    op.create_index(
        op.f("ix_drift_bottle_items_sender_id"),
        "drift_bottle_items",
        ["sender_id"],
    )

    # 用户自建池序列（从 1 开始，与手动 seed 的 id=0 无冲突）
    op.execute("CREATE SEQUENCE drift_bottle_pools_id_seq START 1 MINVALUE 1")
    op.execute(
        "ALTER TABLE drift_bottle_pools "
        "ALTER COLUMN id SET DEFAULT nextval('drift_bottle_pools_id_seq')"
    )
    # seed 默认池（显式绕过序列写入 id=0）
    op.execute("INSERT INTO drift_bottle_pools (id, name) VALUES (0, '默认漂流瓶池')")


def downgrade() -> None:
    # 先清理 seed 数据和序列
    op.execute("DELETE FROM drift_bottle_pools WHERE id = 0")
    op.execute("ALTER TABLE drift_bottle_pools ALTER COLUMN id DROP DEFAULT")
    op.execute("DROP SEQUENCE IF EXISTS drift_bottle_pools_id_seq")

    # 再删表（顺序：有外键依赖的先删）
    op.drop_index(op.f("ix_drift_bottle_items_sender_id"), table_name="drift_bottle_items")
    op.drop_index("ix_drift_bottle_items_pool_is_picked", table_name="drift_bottle_items")
    op.drop_table("drift_bottle_items")
    op.drop_table("drift_bottle_group_pools")
    op.drop_table("drift_bottle_pools")
