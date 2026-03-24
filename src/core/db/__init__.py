"""数据库核心模块 —— 引擎、基类、迁移注册。"""

from src.core.db.base import Base
from src.core.db.migration_registry import MigrationTarget, register_migration_target

# ── 注册主库迁移目标 ──
register_migration_target(
    MigrationTarget(
        name="main",
        script_location="src/core/db/migrations",
        metadata=Base.metadata,
        get_db_url=lambda s: s.DATABASE_URL,
        exclude_schemas=frozenset({"chat"}),
        autogenerate=True,
        model_import="src.models",
    )
)
