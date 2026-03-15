"""Alembic env.py 共享逻辑 —— 消除多数据库 env.py 的重复代码。

每个 env.py 只需调用 run_env() 并传入自己的配置参数。
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy import MetaData
    from sqlalchemy.engine import Connection


def run_env(
    *,
    target_metadata: MetaData,
    include_name: Callable[[str | None, str, dict[str, str | None]], bool],
    get_url: Callable[[], str],
    version_table_schema: str | None = None,
) -> None:
    """通用 Alembic env.py 入口。

    Args:
        target_metadata: ORM 模型的 MetaData 实例。
        include_name: schema/对象过滤回调。
        get_url: 返回 asyncpg 格式数据库 URL 的 callable。
        version_table_schema: alembic_version 表所在 schema（None 表示默认）。
    """
    config = context.config

    if context.is_offline_mode():
        _run_migrations_offline(
            config=config,
            target_metadata=target_metadata,
            include_name=include_name,
            get_url=get_url,
            version_table_schema=version_table_schema,
        )
    else:
        _run_migrations_online(
            config=config,
            target_metadata=target_metadata,
            include_name=include_name,
            get_url=get_url,
            version_table_schema=version_table_schema,
        )


def _run_migrations_offline(
    *,
    config: Any,
    target_metadata: MetaData,
    include_name: Callable[..., bool],
    get_url: Callable[[], str],
    version_table_schema: str | None,
) -> None:
    """以 'offline' 模式运行迁移（仅生成 SQL 脚本）。"""
    url = get_url()
    kwargs: dict[str, Any] = {
        "url": url,
        "target_metadata": target_metadata,
        "literal_binds": True,
        "dialect_opts": {"paramstyle": "named"},
        "include_schemas": True,
        "include_name": include_name,
    }
    if version_table_schema:
        kwargs["version_table_schema"] = version_table_schema

    context.configure(**kwargs)

    with context.begin_transaction():
        context.run_migrations()


def _run_migrations_online(
    *,
    config: Any,
    target_metadata: MetaData,
    include_name: Callable[..., bool],
    get_url: Callable[[], str],
    version_table_schema: str | None,
) -> None:
    """以 'online' 模式运行迁移（连接数据库）。"""

    def do_run_migrations(connection: Connection) -> None:
        kwargs: dict[str, Any] = {
            "connection": connection,
            "target_metadata": target_metadata,
            "include_schemas": True,
            "include_name": include_name,
        }
        if version_table_schema:
            kwargs["version_table_schema"] = version_table_schema

        context.configure(**kwargs)

        with context.begin_transaction():
            context.run_migrations()

    async def run_async_migrations() -> None:
        configuration = config.get_section(config.config_ini_section, {})
        configuration["sqlalchemy.url"] = get_url()
        connectable = async_engine_from_config(
            configuration,
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
            echo=False,
        )

        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)

        await connectable.dispose()

    # 兼容 CLI（无事件循环）和应用内调用（已有事件循环）
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
