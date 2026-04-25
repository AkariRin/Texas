"""聊天库迁移目标注册 —— 由 lifespan.py / cli.py 触发 import 时自动注册。"""

from __future__ import annotations

from src.core.db.base import ChatBase
from src.core.db.migration_registry import MigrationTarget, register_migration_target


def _get_chat_db_url(_settings: object) -> str:
    """从 ChatDatabaseSettings 获取聊天库 URL（独立配置类，不依赖主 Settings）。"""
    from src.core.services.chat import ChatDatabaseSettings

    return ChatDatabaseSettings().CHAT_DATABASE_URL


register_migration_target(
    MigrationTarget(
        name="chat",
        script_location="src/core/db/migrations/chat",
        metadata=ChatBase.metadata,
        get_db_url=_get_chat_db_url,
        schema="chat",
        version_table_schema="chat",
        include_schemas=frozenset({"chat"}),
        autogenerate=False,  # 分区表需手写迁移，禁止 autogenerate
        model_import="src.models.chat",
    )
)
