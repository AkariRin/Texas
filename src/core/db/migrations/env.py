"""Alembic async migrations environment — 参考官方 asyncio 模板。"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

import src.models  # noqa: F401  — 触发模型注册

# ── 导入 Base 和所有模型，确保 metadata 包含全部表定义 ──
from src.core.db.base import Base

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection


# Alembic Config 对象
config = context.config

# 不调用 fileConfig —— 日志由 structlog 统一管理，避免 alembic.ini 的 [loggers]
# 节覆盖 root handler 导致 SQLAlchemy 日志绕过 structlog 输出。

target_metadata = Base.metadata

# chat schema 由独立的 alembic_chat.ini 管理，主库迁移需排除
_EXCLUDED_SCHEMAS = {"chat"}


def _include_name(
    name: str | None,
    type_: str,
    parent_names: dict[str, str | None],  # noqa: ARG001
) -> bool:
    """排除 chat schema 下的对象，避免主库迁移产生误差。"""
    if type_ == "schema":
        return name not in _EXCLUDED_SCHEMAS
    return True


def _get_url() -> str:
    """获取数据库连接 URL（asyncpg 格式）。

    优先使用 alembic.ini 中的 sqlalchemy.url；
    若为空则从 Settings 中读取。
    """
    url = config.get_main_option("sqlalchemy.url", "")
    if url:
        # migration.py 注入的是已转为 +psycopg 的同步 URL，转回 asyncpg
        return url.replace("+psycopg", "+asyncpg")
    # 通过 Settings 获取 URL（CLI 直接执行 alembic 时走此分支）
    from src.core.config import Settings

    settings = Settings()
    return settings.DATABASE_URL


def run_migrations_offline() -> None:
    """以 'offline' 模式运行迁移（仅生成 SQL 脚本，不连接数据库）。"""
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
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
        echo=False,  # 迁移时不输出 SQL 日志，避免污染 structlog 输出
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """以 'online' 模式运行迁移（连接数据库）。

    兼容两种场景：
    - CLI 直接执行 alembic 命令（无事件循环）→ asyncio.run()
    - 应用启动时在已有事件循环中调用（FastAPI lifespan）→ 在独立线程中运行
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # 已有事件循环 → 在独立线程中运行，避免 asyncio.run() 报错
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
