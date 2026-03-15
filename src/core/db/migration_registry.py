"""Alembic 迁移目标注册表 —— 支持多数据库水平拓展。

每个需要 Alembic 管理的数据库抽象为一个 MigrationTarget，
通过注册表统一驱动迁移逻辑，新增数据库只需注册即可。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy import MetaData

    from src.core.config import Settings


@dataclass(frozen=True)
class MigrationTarget:
    """描述一个需要 Alembic 管理的数据库迁移目标。

    Attributes:
        name: 标识名，如 "main", "chat"，用于日志前缀。
        ini_name: alembic 配置文件名（相对项目根目录），如 "alembic.ini"。
        metadata: SQLAlchemy MetaData 实例（来自 Base.metadata）。
        get_db_url: 从 Settings 对象提取数据库 URL 的 callable。
        schema: 专属 schema（None 表示 public）。
        version_table_schema: alembic_version 表所在 schema。
        include_schemas: autogenerate 仅包含这些 schema（互斥于 exclude_schemas）。
        exclude_schemas: autogenerate 排除这些 schema。
        autogenerate: 开发环境是否自动生成迁移脚本（分区表等需手写迁移时设为 False）。
        model_import: 需导入以触发模型注册的模块路径。
    """

    name: str
    ini_name: str
    metadata: MetaData
    get_db_url: Callable[[Settings], str]
    schema: str | None = None
    version_table_schema: str | None = None
    include_schemas: frozenset[str] = field(default_factory=frozenset)
    exclude_schemas: frozenset[str] = field(default_factory=frozenset)
    autogenerate: bool = True
    model_import: str = ""


# ── 全局注册表 ──

_registry: list[MigrationTarget] = []


def register_migration_target(target: MigrationTarget) -> None:
    """注册一个迁移目标。各模块在自己的 __init__.py 中调用。"""
    _registry.append(target)


def get_all_targets() -> list[MigrationTarget]:
    """返回所有已注册的迁移目标（副本）。"""
    return list(_registry)


def get_target(name: str) -> MigrationTarget | None:
    """按名称查找迁移目标。"""
    for t in _registry:
        if t.name == name:
            return t
    return None
