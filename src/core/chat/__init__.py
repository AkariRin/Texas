"""聊天记录存储模块 —— 消息持久化、查询、归档。"""

from src.core.db.base import ChatBase
from src.core.db.migration_registry import MigrationTarget, register_migration_target

# ── 注册聊天库迁移目标 ──
register_migration_target(
    MigrationTarget(
        name="chat",
        script_location="src/core/chat/migrations",
        metadata=ChatBase.metadata,
        get_db_url=lambda s: s.CHAT_DATABASE_URL,
        schema="chat",
        version_table_schema="chat",
        include_schemas=frozenset({"chat"}),
        autogenerate=False,  # 分区表需手写迁移
        model_import="src.core.chat.models",
    )
)
