"""Alembic async migrations environment — 聊天记录库 (chat_history)。"""

from __future__ import annotations

from alembic import context

import src.core.chat.models  # noqa: F401  — 触发 ChatBase 模型注册
from src.core.db.alembic_env_common import run_env
from src.core.db.base import ChatBase

_CHAT_SCHEMA = "chat"


def _include_name(
    name: str | None,
    type_: str,
    parent_names: dict[str, str | None],  # noqa: ARG001
) -> bool:
    """只包含 chat schema 下的对象。"""
    if type_ == "schema":
        return name == _CHAT_SCHEMA
    return True


def _get_url() -> str:
    """获取聊天数据库连接 URL（asyncpg 格式）。"""
    url = context.config.get_main_option("sqlalchemy.url", "")
    if url:
        return url.replace("+psycopg", "+asyncpg")
    from src.core.config import get_settings

    return get_settings().CHAT_DATABASE_URL


run_env(
    target_metadata=ChatBase.metadata,
    include_name=_include_name,
    get_url=_get_url,
    version_table_schema=_CHAT_SCHEMA,
)
