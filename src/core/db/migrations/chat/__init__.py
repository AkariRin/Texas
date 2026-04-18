"""聊天库迁移目标注册 —— 由 lifespan.py / cli.py 触发 import 时自动注册。"""

from src.core.db.base import ChatBase
from src.core.db.migration_registry import MigrationTarget, register_migration_target

register_migration_target(
    MigrationTarget(
        name="chat",
        script_location="src/core/db/migrations/chat",
        metadata=ChatBase.metadata,
        get_db_url=lambda s: s.CHAT_DATABASE_URL,
        schema="chat",
        version_table_schema="chat",
        include_schemas=frozenset({"chat"}),
        autogenerate=False,  # 分区表需手写迁移，禁止 autogenerate
        model_import="src.models.chat",
    )
)
