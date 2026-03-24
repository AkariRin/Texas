"""注册表驱动的通用 Alembic env.py 逻辑。

各 migrations/env.py 简化为 2 行：

    from src.core.db.shared.env import run_env_for_target
    run_env_for_target("main")  # 或 "chat"

run_env_for_target() 内部：从注册表取 target → 导入模型 → 构建 schema 过滤
→ 获取 URL → 委托 alembic_env_common.run_env()。
"""

from __future__ import annotations

import importlib

from alembic import context

from src.core.db.alembic_env_common import run_env


def run_env_for_target(name: str) -> None:
    """按注册表名称驱动通用 Alembic env 逻辑。

    Args:
        name: 已注册的迁移目标名称，如 "main"、"chat"。

    Raises:
        ValueError: 若名称在注册表中不存在。
    """
    from src.core.db.migration_registry import get_target

    target = get_target(name)
    if target is None:
        raise ValueError(
            f"未找到迁移目标: {name!r}，"
            "请确认已在对应 __init__.py 中调用 register_migration_target()"
        )

    # 触发模型注册到 metadata
    if target.model_import:
        importlib.import_module(target.model_import)

    def _include_name(
        obj_name: str | None,
        type_: str,
        parent_names: dict[str, str | None],  # noqa: ARG001
    ) -> bool:
        if type_ == "schema":
            if target.include_schemas:
                return obj_name in target.include_schemas
            if target.exclude_schemas:
                return obj_name not in target.exclude_schemas
        return True

    def _get_url() -> str:
        # 运行时由 build_alembic_config 注入 psycopg URL，转换回 asyncpg 供引擎使用
        url = context.config.get_main_option("sqlalchemy.url", "")
        if url:
            return url.replace("+psycopg", "+asyncpg")
        # CLI 回退：直接从 Settings 读取（URL 未注入时）
        from src.core.config import get_settings

        return target.get_db_url(get_settings())

    run_env(
        target_metadata=target.metadata,
        include_name=_include_name,
        get_url=_get_url,
        version_table_schema=target.version_table_schema,
    )
