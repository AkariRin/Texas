"""Alembic Config 工厂 —— 程序化构建配置，消灭 .ini 文件。

通过 Config() + set_main_option() 按 MigrationTarget 注册信息动态生成配置，
被 migration.py（启动迁移）和 cli.py（命令行）共用。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic.config import Config

if TYPE_CHECKING:
    from src.core.config import Settings
    from src.core.db.migration_registry import MigrationTarget


def build_alembic_config(target: MigrationTarget, settings: Settings) -> Config:
    """为指定迁移目标构建 Alembic Config（无需 .ini 文件）。

    Args:
        target: 迁移目标描述（包含 script_location、get_db_url 等）。
        settings: 应用配置，用于提取数据库连接字符串。

    Returns:
        配置完整的 Alembic Config 对象，sqlalchemy.url 已注入 psycopg 格式。
    """
    cfg = Config()
    cfg.set_main_option("script_location", target.script_location)

    # asyncpg 用于异步引擎，psycopg 用于 Alembic 同步执行
    sync_url = target.get_db_url(settings).replace("+asyncpg", "+psycopg")
    cfg.set_main_option("sqlalchemy.url", sync_url)

    cfg.set_main_option("prepend_sys_path", ".")
    cfg.set_main_option("version_path_separator", "os")
    return cfg
