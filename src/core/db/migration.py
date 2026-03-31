"""启动时数据库连接检查与 Alembic 迁移管理（通用版）。

通过 MigrationTarget 注册表驱动，支持任意数量的数据库，
无需为每个库复制迁移函数。

行为类似 Hibernate 的 auto-DDL：
  - 开发环境：自动检测模型差异 → autogenerate 迁移脚本 → upgrade head
  - 生产环境：检测到未应用迁移或模型漂移 → CRITICAL 日志 → sys.exit(1)
"""

from __future__ import annotations

import importlib
import re
import sys
from typing import TYPE_CHECKING, Any

import structlog
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from sqlalchemy import text

from src.core.db.alembic_config_factory import build_alembic_config

if TYPE_CHECKING:
    from alembic.config import Config
    from sqlalchemy.ext.asyncio import AsyncEngine

    from src.core.config import Settings
    from src.core.db.migration_registry import MigrationTarget

logger = structlog.get_logger()


# ─────────────────────── 基础工具 ───────────────────────

_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$")


def _validate_identifier(name: str, label: str = "标识符") -> None:
    """校验 SQL 标识符合法性（仅允许字母、数字、下划线，防止注入）。"""
    if not _SAFE_IDENTIFIER_RE.match(name):
        raise ValueError(f"非法 SQL {label}: {name!r}")


async def _check_connection(engine: AsyncEngine, target_name: str) -> None:
    """尝试连接数据库，失败则 CRITICAL 日志并退出。"""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("数据库连接检查通过", target=target_name, event_type="db.connection_ok")
    except Exception as exc:
        logger.critical(
            "无法连接数据库，拒绝启动",
            target=target_name,
            error=str(exc),
            event_type="db.connection_failed",
        )
        sys.exit(1)


# ─────────────────────── 迁移状态检测 ───────────────────────


async def _get_current_revision(engine: AsyncEngine, target: MigrationTarget) -> str | None:
    """获取数据库当前的 Alembic revision。"""

    def _inspect(connection):  # type: ignore[no-untyped-def]
        opts: dict[str, Any] = {}
        if target.version_table_schema:
            opts["version_table_schema"] = target.version_table_schema
        ctx = MigrationContext.configure(connection, opts=opts)
        return ctx.get_current_revision()

    async with engine.connect() as conn:
        return await conn.run_sync(_inspect)


def _get_head_revision(alembic_cfg) -> str | None:  # type: ignore[no-untyped-def]
    """获取迁移脚本目录中的 head revision。"""
    script = ScriptDirectory.from_config(alembic_cfg)
    heads = script.get_heads()
    return heads[0] if heads else None


def _build_include_name(target: MigrationTarget):  # type: ignore[no-untyped-def]
    """根据 MigrationTarget 的 schema 过滤规则构建 include_name 回调。"""

    def _include_name(
        name: str | None,
        type_: str,
        parent_names: dict[str, str | None],  # noqa: ARG001
    ) -> bool:
        if type_ == "schema":
            if target.include_schemas:
                return name in target.include_schemas
            if target.exclude_schemas:
                return name not in target.exclude_schemas
        return True

    return _include_name


async def _detect_schema_diff(engine: AsyncEngine, target: MigrationTarget) -> list[Any]:
    """使用 autogenerate 比对 ORM 模型与数据库表结构差异。"""
    _include_name = _build_include_name(target)

    def _compare(connection):  # type: ignore[no-untyped-def]
        opts: dict[str, Any] = {
            "include_schemas": True,
            "include_name": _include_name,
        }
        if target.version_table_schema:
            opts["version_table_schema"] = target.version_table_schema
        ctx = MigrationContext.configure(connection, opts=opts)
        return compare_metadata(ctx, target.metadata)

    async with engine.connect() as conn:
        return await conn.run_sync(_compare)


def _revision_exists(alembic_cfg, rev_id: str) -> bool:  # type: ignore[no-untyped-def]
    """检查给定的 revision ID 在迁移脚本目录中是否存在。"""
    script = ScriptDirectory.from_config(alembic_cfg)
    try:
        script.get_revision(rev_id)
        return True
    except CommandError, Exception:
        return False


async def _force_clear_alembic_version(engine: AsyncEngine, target: MigrationTarget) -> None:
    """直接清空 alembic_version 表，用于处理孤立 revision。"""
    schema = target.version_table_schema
    if schema:
        _validate_identifier(schema, "schema")
        table = f"{schema}.alembic_version"
    else:
        table = "alembic_version"
    async with engine.begin() as conn:
        await conn.execute(text(f"DELETE FROM {table}"))  # noqa: S608


# ─────────────────────── 迁移执行 ───────────────────────


def _autogenerate_revision(alembic_cfg, message: str = "auto") -> None:  # type: ignore[no-untyped-def]
    """调用 Alembic autogenerate 生成新迁移脚本。"""
    command.revision(alembic_cfg, message=message, autogenerate=True)


def _upgrade_head(alembic_cfg) -> None:  # type: ignore[no-untyped-def]
    """执行 alembic upgrade head。"""
    command.upgrade(alembic_cfg, "head")


# ─────────────────────── 生产环境 ───────────────────────


async def _handle_production(
    engine: AsyncEngine,
    alembic_cfg: Config,
    current_rev: str | None,
    head_rev: str | None,
    target: MigrationTarget,
) -> None:
    """生产环境：版本不匹配或模型漂移 → 强制终止启动。"""
    has_error = False

    if head_rev and current_rev != head_rev:
        logger.critical(
            "数据库迁移版本不匹配，拒绝启动",
            target=target.name,
            current=current_rev,
            expected=head_rev,
            event_type=f"{target.name}_db.migration_pending",
        )
        has_error = True

    diff = await _detect_schema_diff(engine, target)
    if diff:
        logger.critical(
            "ORM 模型与数据库表结构不一致，拒绝启动",
            target=target.name,
            diff_count=len(diff),
            event_type=f"{target.name}_db.schema_drift",
        )
        has_error = True

    if has_error:
        sys.exit(1)

    logger.info(
        "数据库版本匹配",
        target=target.name,
        event_type=f"{target.name}_db.production_check_ok",
    )


# ─────────────────────── 开发环境 ───────────────────────


async def _handle_development(
    engine: AsyncEngine,
    alembic_cfg: Config,
    current_rev: str | None,
    head_rev: str | None,
    target: MigrationTarget,
) -> None:
    """开发环境：自动检测差异 → 生成迁移脚本 → 升级到最新。"""
    evt = target.name  # 日志事件前缀

    # 0. 孤立版本清理
    if current_rev is not None and not _revision_exists(alembic_cfg, current_rev):
        logger.warning(
            "数据库记录的迁移版本在脚本目录中不存在，重置为 base",
            target=target.name,
            stale_revision=current_rev,
            event_type=f"{evt}_db.stale_revision_reset",
        )
        await _force_clear_alembic_version(engine, target)
        current_rev = None

    # 1. 先升级到当前 head
    if head_rev and current_rev != head_rev:
        _upgrade_head(alembic_cfg)
        logger.info("数据库迁移完成", target=target.name, event_type=f"{evt}_db.upgrade_done")

    # 2. 若支持 autogenerate，检测模型差异并生成新迁移
    if target.autogenerate:
        diff = await _detect_schema_diff(engine, target)
        if diff:
            _autogenerate_revision(alembic_cfg, message="auto")
            _upgrade_head(alembic_cfg)
            logger.info("数据库迁移完成", target=target.name, event_type=f"{evt}_db.upgrade_done")
        elif head_rev is None and current_rev is None:
            logger.info(
                "数据库无迁移脚本，跳过", target=target.name, event_type=f"{evt}_db.no_migrations"
            )
        else:
            logger.info("数据库已是最新版本", target=target.name, event_type=f"{evt}_db.up_to_date")
    else:
        # 不做 autogenerate（如分区表需手写迁移）
        if head_rev is None and current_rev is None:
            logger.info(
                "数据库无迁移脚本，跳过", target=target.name, event_type=f"{evt}_db.no_migrations"
            )
        elif not head_rev or current_rev == head_rev:
            logger.info("数据库已是最新版本", target=target.name, event_type=f"{evt}_db.up_to_date")


# ─────────────────────── 公共入口 ───────────────────────


async def run_startup_migration(
    engine: AsyncEngine, settings: Settings, target: MigrationTarget
) -> None:
    """通用启动迁移入口 —— 适用于任意 MigrationTarget。

    Args:
        engine: 数据库异步引擎。
        settings: 应用配置。
        target: 迁移目标描述。
    """
    # 确保模型已注册到 metadata
    if target.model_import:
        importlib.import_module(target.model_import)

    # 连接检查
    await _check_connection(engine, target.name)

    # 确保 schema 存在（如 chat schema）
    if target.schema:
        _validate_identifier(target.schema, "schema")
        async with engine.begin() as conn:
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {target.schema}"))

    alembic_cfg = build_alembic_config(target, settings)
    head_rev = _get_head_revision(alembic_cfg)
    current_rev = await _get_current_revision(engine, target)

    if settings.is_production:
        await _handle_production(engine, alembic_cfg, current_rev, head_rev, target)
    else:
        await _handle_development(engine, alembic_cfg, current_rev, head_rev, target)


async def run_all_startup_migrations(engines: dict[str, AsyncEngine], settings: Settings) -> None:
    """遍历所有已注册的迁移目标，依次执行启动迁移。

    Args:
        engines: 引擎字典，键为 MigrationTarget.name，值为对应的 AsyncEngine。
                 未在字典中找到引擎的目标将跳过并输出警告。
        settings: 应用配置。
    """
    from src.core.db.migration_registry import get_all_targets

    for target in get_all_targets():
        engine = engines.get(target.name)
        if engine is None:
            logger.warning(
                "未找到迁移目标引擎，跳过",
                target=target.name,
                event_type="db.missing_engine",
            )
            continue
        await run_startup_migration(engine, settings, target)
