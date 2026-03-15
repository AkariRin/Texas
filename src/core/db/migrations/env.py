"""Alembic async migrations environment — 主库。"""

from __future__ import annotations

from alembic import context

import src.models  # noqa: F401  — 触发模型注册
from src.core.db.alembic_env_common import run_env
from src.core.db.base import Base

# chat schema 由独立的 alembic_chat.ini 管理，主库迁移需排除
_EXCLUDED_SCHEMAS = {"chat"}


def _include_name(
    name: str | None,
    type_: str,
    parent_names: dict[str, str | None],  # noqa: ARG001
) -> bool:
    """排除 chat schema 下的对象。"""
    if type_ == "schema":
        return name not in _EXCLUDED_SCHEMAS
    return True


def _get_url() -> str:
    """获取数据库连接 URL（asyncpg 格式）。"""
    url = context.config.get_main_option("sqlalchemy.url", "")
    if url:
        return url.replace("+psycopg", "+asyncpg")
    from src.core.config import get_settings

    return get_settings().DATABASE_URL


run_env(
    target_metadata=Base.metadata,
    include_name=_include_name,
    get_url=_get_url,
)
