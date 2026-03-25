"""添加功能级权限控制表

Revision ID: a1b2c3d4e5f6
Revises: b8db8cff95a9
Create Date: 2026-03-25 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "b8db8cff95a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # feature_registry
    op.create_table(
        "feature_registry",
        sa.Column("name", sa.String(64), nullable=False, comment="功能唯一标识"),
        sa.Column(
            "parent",
            sa.String(64),
            sa.ForeignKey("feature_registry.name", ondelete="CASCADE"),
            nullable=True,
            comment="父功能",
        ),
        sa.Column(
            "display_name", sa.String(128), nullable=False, server_default="", comment="显示名称"
        ),
        sa.Column(
            "description", sa.String(256), nullable=False, server_default="", comment="功能描述"
        ),
        sa.Column(
            "default_enabled",
            sa.Boolean,
            nullable=False,
            server_default=sa.true(),
            comment="默认启用状态",
        ),
        sa.Column(
            "enabled", sa.Boolean, nullable=False, server_default=sa.true(), comment="全局开关"
        ),
        sa.Column(
            "private_mode",
            sa.String(16),
            nullable=False,
            server_default="blacklist",
            comment="私聊模式",
        ),
        sa.Column(
            "is_active", sa.Boolean, nullable=False, server_default=sa.true(), comment="是否活跃"
        ),
        sa.PrimaryKeyConstraint("name"),
    )
    op.create_index("ix_feature_registry_parent", "feature_registry", ["parent"])

    # group_feature_permissions
    op.create_table(
        "group_feature_permissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "group_id",
            sa.BigInteger,
            sa.ForeignKey("groups.group_id", ondelete="CASCADE"),
            nullable=False,
            comment="群号",
        ),
        sa.Column(
            "feature_name",
            sa.String(64),
            sa.ForeignKey("feature_registry.name", ondelete="CASCADE"),
            nullable=False,
            comment="功能标识",
        ),
        sa.Column("enabled", sa.Boolean, nullable=False, comment="是否在该群启用"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "feature_name", name="uq_group_feature"),
    )
    op.create_index(
        "ix_group_feature_permissions_group_id",
        "group_feature_permissions",
        ["group_id"],
    )

    # private_feature_permissions
    op.create_table(
        "private_feature_permissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "feature_name",
            sa.String(64),
            sa.ForeignKey("feature_registry.name", ondelete="CASCADE"),
            nullable=False,
            comment="功能标识",
        ),
        sa.Column(
            "user_qq",
            sa.BigInteger,
            sa.ForeignKey("users.qq", ondelete="CASCADE"),
            nullable=False,
            comment="用户 QQ 号",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("feature_name", "user_qq", name="uq_private_feature_user"),
    )
    op.create_index(
        "ix_private_feature_permissions_feature_name",
        "private_feature_permissions",
        ["feature_name"],
    )


def downgrade() -> None:
    op.drop_table("private_feature_permissions")
    op.drop_table("group_feature_permissions")
    op.drop_index("ix_feature_registry_parent", table_name="feature_registry")
    op.drop_table("feature_registry")
