"""refactor permission system: remove feature_registry, full permission records

移除 feature_registry 表，权限表改为存储全量记录：
- permission_group: 增加 group_id=0 全局哨兵行（原 Feature.enabled），去掉 FK 约束
- permission_private: 新增 enabled 列，去掉 FK 约束，黑/白名单语义转换
- DROP TABLE feature_registry

Revision ID: b7a85e8cab15
Revises: 671c6429e2cf
Create Date: 2026-04-08

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7a85e8cab15"
down_revision: Union[str, None] = "671c6429e2cf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """迁移步骤（严格有序）：先删 FK 约束 → 数据迁移 → schema 变更 → DROP TABLE。"""
    conn = op.get_bind()

    # ── 步骤 1：为 permission_private 添加 enabled 列（data migration 前需要列存在）──
    op.add_column(
        "permission_private",
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
    )

    # ── 步骤 2：根据 private_mode 语义修正 permission_private.enabled ──
    # blacklist 模式下列表中的用户应被禁用（enabled=False）
    # whitelist 模式下列表中的用户应被允许（enabled=True，已是 server_default）
    conn.execute(
        sa.text("""
            UPDATE permission_private pp
            SET enabled = false
            FROM feature_registry fr
            WHERE pp.feature_name = fr.name
              AND fr.private_mode = 'blacklist'
        """)
    )

    # ── 步骤 3：删除 permission_group 上指向 feature_registry 的 FK 约束 ──
    # 需要先找到约束名，PostgreSQL 自动生成的约束名
    # 通过 pg_constraint 查询实际约束名
    result = conn.execute(
        sa.text("""
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'permission_group'::regclass
              AND contype = 'f'
              AND conname LIKE '%feature%'
        """)
    ).fetchall()
    for row in result:
        op.drop_constraint(row[0], "permission_group", type_="foreignkey")

    # ── 步骤 4：删除 permission_group 上指向 groups 的 FK 约束（允许 group_id=0 哨兵值）──
    # 必须在插入 group_id=0 哨兵行之前删除，否则 FK 校验会拒绝不存在于 groups 表的值
    result = conn.execute(
        sa.text("""
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'permission_group'::regclass
              AND contype = 'f'
              AND conname LIKE '%group%'
        """)
    ).fetchall()
    for row in result:
        op.drop_constraint(row[0], "permission_group", type_="foreignkey")

    # ── 步骤 5：将 feature_registry 中的全局 enabled 写入 permission_group group_id=0 哨兵行 ──
    # 此时 groups FK 约束已删除，group_id=0 可合法插入
    conn.execute(
        sa.text("""
            INSERT INTO permission_group (id, group_id, feature_name, enabled)
            SELECT
                gen_random_uuid(),
                0,
                name,
                enabled
            FROM feature_registry
            WHERE is_active = true
            ON CONFLICT (group_id, feature_name) DO NOTHING
        """)
    )

    # ── 步骤 6：删除 permission_private 上指向 feature_registry 的 FK 约束 ──
    result = conn.execute(
        sa.text("""
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'permission_private'::regclass
              AND contype = 'f'
              AND conname LIKE '%feature%'
        """)
    ).fetchall()
    for row in result:
        op.drop_constraint(row[0], "permission_private", type_="foreignkey")

    # ── 步骤 7：移除 permission_private.enabled 的 server_default（正式列不需要） ──
    op.alter_column("permission_private", "enabled", server_default=None)

    # ── 步骤 8：DROP TABLE feature_registry（级联） ──
    # 自关联 FK 和 Enum type 一并清理
    op.drop_table("feature_registry")

    # ── 步骤 9：删除 PostgreSQL Enum 类型 private_mode_enum ──
    op.execute("DROP TYPE IF EXISTS private_mode_enum")


def downgrade() -> None:
    """单向迁移，不支持回滚。"""
    raise NotImplementedError(
        "权限系统重构为单向迁移，不支持 downgrade。如需回滚，请从备份恢复 feature_registry 表。"
    )
