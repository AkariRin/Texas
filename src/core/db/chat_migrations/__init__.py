"""聊天库迁移目标注册。"""

from src.core.db.base import ChatBase
from src.core.db.migration_registry import MigrationTarget, register_migration_target

# ── 注册聊天库迁移目标 ──
register_migration_target(
    MigrationTarget(
        name="chat",
        script_location="src/core/db/chat_migrations",
        metadata=ChatBase.metadata,
        get_db_url=lambda s: s.CHAT_DATABASE_URL,
        schema="chat",
        version_table_schema="chat",
        include_schemas=frozenset({"chat"}),
        autogenerate=False,  # 分区表需手写迁移
        model_import="src.models.chat",
    )
)
