"""add auth tables

Revision ID: 7cace4cf2796
Revises: b1c2d3e4f5a6
Create Date: 2026-03-31 00:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "7cace4cf2796"
down_revision: str | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建 admin_credentials 和 webauthn_credentials 表。"""
    op.create_table(
        "admin_credentials",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "token_hash",
            sa.String(256),
            nullable=False,
            comment="bcrypt 哈希后的静态令牌",
        ),
        sa.Column(
            "totp_secret",
            sa.String(64),
            nullable=True,
            comment="base32 TOTP secret，NULL 表示未启用",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="更新时间",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "webauthn_credentials",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "credential_id",
            sa.LargeBinary,
            nullable=False,
            comment="WebAuthn Credential ID",
        ),
        sa.Column(
            "public_key",
            sa.LargeBinary,
            nullable=False,
            comment="COSE 格式公钥",
        ),
        sa.Column(
            "sign_count",
            sa.Integer,
            nullable=False,
            server_default="0",
            comment="防重放签名计数器",
        ),
        sa.Column(
            "device_name",
            sa.String(64),
            nullable=False,
            server_default="",
            comment="用户自定义设备名称",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="注册时间",
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="最后使用时间",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("credential_id", name="uq_webauthn_credential_id"),
    )


def downgrade() -> None:
    """删除 admin_credentials 和 webauthn_credentials 表。"""
    op.drop_table("webauthn_credentials")
    op.drop_table("admin_credentials")
