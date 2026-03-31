"""add_enum_types_for_relation_role_archive_status_private_mode

Revision ID: 40462e8f06d4
Revises: 909e0f6e41ff
Create Date: 2026-03-31 10:42:25.609348

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "40462e8f06d4"
down_revision: Union[str, None] = "909e0f6e41ff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 先创建 PostgreSQL 枚举类型（值均为小写，与现有数据一致）
    op.execute(
        "CREATE TYPE user_relation_enum AS ENUM ('stranger', 'group_member', 'friend', 'admin')"
    )
    op.execute("CREATE TYPE group_role_enum AS ENUM ('owner', 'admin', 'member')")
    op.execute(
        "CREATE TYPE archive_status_enum AS ENUM "
        "('pending', 'exporting', 'uploading', 'uploaded', 'partition_dropped', 'completed', 'failed')"
    )
    op.execute("CREATE TYPE private_mode_enum AS ENUM ('blacklist', 'whitelist')")

    # 2. users.relation: VARCHAR(20) → user_relation_enum
    op.alter_column(
        "users",
        "relation",
        existing_type=sa.VARCHAR(length=20),
        type_=sa.Enum("stranger", "group_member", "friend", "admin", name="user_relation_enum"),
        postgresql_using="relation::user_relation_enum",
        existing_comment="关系等级: stranger/group_member/friend/admin",
        existing_nullable=False,
    )

    # 3. group_memberships.role: VARCHAR(20) → group_role_enum
    op.alter_column(
        "group_memberships",
        "role",
        existing_type=sa.VARCHAR(length=20),
        type_=sa.Enum("owner", "admin", "member", name="group_role_enum"),
        postgresql_using="role::group_role_enum",
        existing_comment="群内角色: owner/admin/member",
        existing_nullable=False,
    )

    # 4. chat_archive_log.status: VARCHAR(20) → archive_status_enum
    #    status 有 default='pending'，需先 DROP DEFAULT 再转换再 SET DEFAULT
    op.execute("ALTER TABLE chat_archive_log ALTER COLUMN status DROP DEFAULT")
    op.execute(
        "ALTER TABLE chat_archive_log ALTER COLUMN status "
        "TYPE archive_status_enum USING status::archive_status_enum"
    )
    op.execute(
        "ALTER TABLE chat_archive_log ALTER COLUMN status "
        "SET DEFAULT 'pending'::archive_status_enum"
    )

    # 5. feature_registry.private_mode: VARCHAR(16) → private_mode_enum
    #    private_mode 有 server_default='blacklist'，需先 DROP DEFAULT 再转换再 SET DEFAULT
    op.execute("ALTER TABLE feature_registry ALTER COLUMN private_mode DROP DEFAULT")
    op.execute(
        "ALTER TABLE feature_registry ALTER COLUMN private_mode "
        "TYPE private_mode_enum USING private_mode::private_mode_enum"
    )
    op.execute(
        "ALTER TABLE feature_registry ALTER COLUMN private_mode "
        "SET DEFAULT 'blacklist'::private_mode_enum"
    )


def downgrade() -> None:
    # 1. feature_registry.private_mode: enum → VARCHAR(16)
    op.execute("ALTER TABLE feature_registry ALTER COLUMN private_mode DROP DEFAULT")
    op.execute(
        "ALTER TABLE feature_registry ALTER COLUMN private_mode "
        "TYPE VARCHAR(16) USING private_mode::varchar"
    )
    op.execute("ALTER TABLE feature_registry ALTER COLUMN private_mode SET DEFAULT 'blacklist'")

    # 2. chat_archive_log.status: enum → VARCHAR(20)
    op.execute("ALTER TABLE chat_archive_log ALTER COLUMN status DROP DEFAULT")
    op.execute(
        "ALTER TABLE chat_archive_log ALTER COLUMN status TYPE VARCHAR(20) USING status::varchar"
    )
    op.execute("ALTER TABLE chat_archive_log ALTER COLUMN status SET DEFAULT 'pending'")

    # 3. group_memberships.role: enum → VARCHAR(20)
    op.alter_column(
        "group_memberships",
        "role",
        existing_type=sa.Enum("owner", "admin", "member", name="group_role_enum"),
        type_=sa.VARCHAR(length=20),
        postgresql_using="role::varchar",
        existing_comment="群内角色: owner/admin/member",
        existing_nullable=False,
    )

    # 4. users.relation: enum → VARCHAR(20)
    op.alter_column(
        "users",
        "relation",
        existing_type=sa.Enum(
            "stranger", "group_member", "friend", "admin", name="user_relation_enum"
        ),
        type_=sa.VARCHAR(length=20),
        postgresql_using="relation::varchar",
        existing_comment="关系等级: stranger/group_member/friend/admin",
        existing_nullable=False,
    )

    # 5. 删除枚举类型
    op.execute("DROP TYPE IF EXISTS private_mode_enum")
    op.execute("DROP TYPE IF EXISTS archive_status_enum")
    op.execute("DROP TYPE IF EXISTS group_role_enum")
    op.execute("DROP TYPE IF EXISTS user_relation_enum")
