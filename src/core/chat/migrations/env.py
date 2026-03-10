"""Alembic async migrations environment — 聊天记录库 (chat_history)。

与主库独立的迁移环境，连接 CHAT_DATABASE_URL，
alembic_version 表存放于 chat schema 以避免冲突。
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

import src.core.chat.models  # noqa: F401  — 触发 ChatBase 模型注册

# ── 导入 ChatBase，确保 metadata 包含 chat schema 全部表定义 ──
from src.core.db.base import ChatBase

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection


config = context.config

# 仅管理 chat schema 下的表
target_metadata = ChatBase.metadata

# ── 聊天库专用 schema ──
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
    url = config.get_main_option("sqlalchemy.url", "")
    if url:
        return url.replace("+psycopg", "+asyncpg")
    from src.core.config import Settings

    settings = Settings()
    return settings.CHAT_DATABASE_URL


def run_migrations_offline() -> None:
    """以 'offline' 模式运行迁移。"""
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=_CHAT_SCHEMA,
        include_schemas=True,
        include_name=_include_name,  # type: ignore[arg-type]
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """在同步连接上执行迁移。"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema=_CHAT_SCHEMA,
        include_schemas=True,
        include_name=_include_name,  # type: ignore[arg-type]
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """创建异步引擎并在 run_sync 中执行迁移。"""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _get_url()
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        echo=False,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """以 'online' 模式运行迁移。"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(lambda: asyncio.run(run_async_migrations()))
            future.result()
    else:
        asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
