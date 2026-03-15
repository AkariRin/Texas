"""启动时数据库连接检查与 Alembic 迁移管理。

行为类似 Hibernate 的 auto-DDL：
  - 开发环境：自动检测模型差异 → autogenerate 迁移脚本 → upgrade head
  - 生产环境：检测到未应用迁移或模型漂移 → CRITICAL 日志 → sys.exit(1)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from sqlalchemy import text

# ── 确保 Base.metadata 包含所有模型 ──
import src.models  # noqa: F401
from src.core.db.base import Base, ChatBase

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from src.core.config import Settings

logger = structlog.get_logger()

# 项目根目录（alembic.ini 所在位置）
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _build_alembic_config(
    db_url: str,
    ini_name: str = "alembic.ini",
) -> Config:
    """构建 Alembic Config 并注入数据库连接字符串。

    Args:
        db_url: asyncpg 格式的数据库 URL。
        ini_name: alembic 配置文件名（相对项目根目录）。
    """
    ini_path = _PROJECT_ROOT / ini_name
    cfg = Config(str(ini_path))
    # 将 asyncpg URL 转为同步 psycopg URL 供 Alembic CLI 使用
    sync_url = db_url.replace("+asyncpg", "+psycopg")
    cfg.set_main_option("sqlalchemy.url", sync_url)
    return cfg


# ─────────────────────────── 连接检查 ───────────────────────────


async def _check_connection(engine: AsyncEngine) -> None:
    """尝试连接数据库，失败则 CRITICAL 日志并退出。"""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("数据库连接检查通过", event_type="db.connection_ok")
    except Exception as exc:
        logger.critical(
            "无法连接数据库，拒绝启动",
            error=str(exc),
            event_type="db.connection_failed",
        )
        sys.exit(1)


# ─────────────────────── 迁移状态检测 ───────────────────────


async def _get_current_revision(engine: AsyncEngine) -> str | None:
    """获取数据库当前的 Alembic revision。"""

    def _inspect(connection):  # type: ignore[no-untyped-def]
        ctx = MigrationContext.configure(connection)
        return ctx.get_current_revision()

    async with engine.connect() as conn:
        return await conn.run_sync(_inspect)


def _get_head_revision(alembic_cfg: Config) -> str | None:
    """获取迁移脚本目录中的 head revision。"""
    script = ScriptDirectory.from_config(alembic_cfg)
    heads = script.get_heads()
    return heads[0] if heads else None


async def _detect_schema_diff(engine: AsyncEngine) -> list[Any]:
    """使用 autogenerate 比对主库 ORM 模型与数据库表结构差异。

    排除 chat schema，只比对 Base.metadata 管辖的表。
    """

    def _include_name(
        name: str | None,
        type_: str,
        parent_names: dict[str, str | None],  # noqa: ARG001
    ) -> bool:
        if type_ == "schema":
            return name not in {"chat"}
        return True

    def _compare(connection):  # type: ignore[no-untyped-def]
        ctx = MigrationContext.configure(
            connection,
            opts={"include_schemas": True, "include_name": _include_name},
        )
        return compare_metadata(ctx, Base.metadata)

    async with engine.connect() as conn:
        return await conn.run_sync(_compare)


async def _detect_chat_schema_diff(engine: AsyncEngine) -> list[Any]:
    """使用 autogenerate 比对聊天库 ORM 模型与数据库表结构差异。

    只比对 chat schema，使用 ChatBase.metadata。
    """

    def _include_name(
        name: str | None,
        type_: str,
        parent_names: dict[str, str | None],  # noqa: ARG001
    ) -> bool:
        if type_ == "schema":
            return name == "chat"
        return True

    def _compare(connection):  # type: ignore[no-untyped-def]
        ctx = MigrationContext.configure(
            connection,
            opts={
                "version_table_schema": "chat",
                "include_schemas": True,
                "include_name": _include_name,
            },
        )
        return compare_metadata(ctx, ChatBase.metadata)

    async with engine.connect() as conn:
        return await conn.run_sync(_compare)


def _revision_exists(alembic_cfg: Config, rev_id: str) -> bool:
    """检查给定的 revision ID 在迁移脚本目录中是否存在。"""
    script = ScriptDirectory.from_config(alembic_cfg)
    try:
        script.get_revision(rev_id)
        return True
    except (CommandError, Exception):
        return False


async def _force_clear_alembic_version(engine: AsyncEngine) -> None:
    """直接清空 alembic_version 表，绕过 Alembic 的版本解析逻辑。
    用于处理数据库中存有孤立 revision（脚本文件已删除）的情况。
    """
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM alembic_version"))


# ─────────────────────── 迁移执行（开发环境） ───────────────────────


def _autogenerate_revision(alembic_cfg: Config, message: str = "auto") -> None:
    """调用 Alembic autogenerate 生成新迁移脚本。"""
    command.revision(alembic_cfg, message=message, autogenerate=True)


def _upgrade_head(alembic_cfg: Config) -> None:
    """执行 alembic upgrade head。"""
    command.upgrade(alembic_cfg, "head")


def _ensure_initial_stamp(alembic_cfg: Config, engine_url: str) -> None:
    """若数据库无 alembic_version 表但已有迁移脚本，执行 stamp head。"""
    command.stamp(alembic_cfg, "head")


# ─────────────────────── 主入口 ───────────────────────


async def run_startup_db_check(engine: AsyncEngine, settings: Settings) -> None:
    """应用启动时的数据库检查与迁移管理入口。

    开发环境：自动生成迁移 + 升级
    生产环境：检测到差异则阻止启动
    """
    # 1. 连接检查
    await _check_connection(engine)

    alembic_cfg = _build_alembic_config(settings.DATABASE_URL)
    head_rev = _get_head_revision(alembic_cfg)
    current_rev = await _get_current_revision(engine)

    if settings.is_production:
        await _handle_production(engine, alembic_cfg, current_rev, head_rev)
    else:
        await _handle_development(engine, alembic_cfg, current_rev, head_rev)


async def _handle_production(
    engine: AsyncEngine,
    alembic_cfg: Config,
    current_rev: str | None,
    head_rev: str | None,
) -> None:
    """生产环境：版本不匹配或模型漂移 → 强制终止启动。"""
    has_error = False

    if head_rev and current_rev != head_rev:
        logger.critical(
            "数据库迁移版本不匹配，拒绝启动",
            current=current_rev,
            expected=head_rev,
            event_type="db.migration_pending",
        )
        has_error = True

    diff = await _detect_schema_diff(engine)
    if diff:
        logger.critical(
            "ORM 模型与数据库表结构不一致，拒绝启动",
            diff_count=len(diff),
            event_type="db.schema_drift",
        )
        has_error = True

    if has_error:
        sys.exit(1)

    logger.info("数据库版本匹配", event_type="db.production_check_ok")


async def _handle_development(
    engine: AsyncEngine,
    alembic_cfg: Config,
    current_rev: str | None,
    head_rev: str | None,
) -> None:
    """开发环境：自动检测差异 → 生成迁移脚本 → 升级到最新，仅输出最终结果。"""

    # 0. 若数据库记录的 revision 在脚本目录中不存在（孤立版本），直接清空版本表
    if current_rev is not None and not _revision_exists(alembic_cfg, current_rev):
        logger.warning(
            "数据库记录的迁移版本在脚本目录中不存在，重置为 base",
            stale_revision=current_rev,
            event_type="db.stale_revision_reset",
        )
        await _force_clear_alembic_version(engine)
        current_rev = None

    # 1. 先将数据库升级到当前 head（autogenerate 要求数据库处于最新版本）
    if head_rev and current_rev != head_rev:
        _upgrade_head(alembic_cfg)
        logger.info("数据库迁移完成", event_type="db.upgrade_done")

    # 2. 检测模型与表结构差异，自动生成迁移脚本
    diff = await _detect_schema_diff(engine)
    if diff:
        _autogenerate_revision(alembic_cfg, message="auto")
        head_rev = _get_head_revision(alembic_cfg)

        # 3. 应用刚生成的迁移脚本
        _upgrade_head(alembic_cfg)
        logger.info("数据库迁移完成", event_type="db.upgrade_done")
    elif head_rev is None and current_rev is None:
        logger.info("数据库无迁移脚本，跳过", event_type="db.no_migrations")
    else:
        logger.info("数据库已是最新版本", event_type="db.up_to_date")


# ─────────────────────── 聊天记录库迁移 ───────────────────────


async def _get_chat_current_revision(engine: AsyncEngine) -> str | None:
    """获取聊天库当前的 Alembic revision（版本表位于 chat schema）。"""

    def _inspect(connection):  # type: ignore[no-untyped-def]
        ctx = MigrationContext.configure(
            connection,
            opts={"version_table_schema": "chat"},
        )
        return ctx.get_current_revision()

    async with engine.connect() as conn:
        return await conn.run_sync(_inspect)


async def _force_clear_chat_alembic_version(engine: AsyncEngine) -> None:
    """清空聊天库的 alembic_version 表（chat schema）。"""
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM chat.alembic_version"))


async def run_startup_chat_db_check(engine: AsyncEngine, settings: Settings) -> None:
    """聊天记录库的启动检查与迁移管理。

    与主库逻辑类似，但使用 alembic_chat.ini 配置和 ChatBase.metadata，
    版本表位于 chat schema，且不做 autogenerate（分区表需手写迁移）。
    """
    # 确保 ChatBase.metadata 已注册 chat 模型
    import src.core.chat.models  # noqa: F401

    # 1. 连接检查
    await _check_connection(engine)

    # 2. 确保 chat schema 存在（Alembic 需要该 schema 来存放 alembic_version 表）
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS chat"))

    alembic_cfg = _build_alembic_config(settings.CHAT_DATABASE_URL, ini_name="alembic_chat.ini")
    head_rev = _get_head_revision(alembic_cfg)
    current_rev = await _get_chat_current_revision(engine)

    if settings.is_production:
        has_error = False

        # 版本不匹配检查
        if head_rev and current_rev != head_rev:
            logger.critical(
                "聊天库迁移版本不匹配，拒绝启动",
                current=current_rev,
                expected=head_rev,
                event_type="chat_db.migration_pending",
            )
            has_error = True

        # 模型与表结构漂移检查（使用 ChatBase.metadata）
        diff = await _detect_chat_schema_diff(engine)
        if diff:
            logger.critical(
                "聊天库 ORM 模型与数据库表结构不一致，拒绝启动",
                diff_count=len(diff),
                event_type="chat_db.schema_drift",
            )
            has_error = True

        if has_error:
            sys.exit(1)

        logger.info("聊天库版本匹配", event_type="chat_db.production_check_ok")
    else:
        # 开发环境：自动升级（不做 autogenerate，分区表迁移需手写）

        # 处理孤立版本
        if current_rev is not None and not _revision_exists(alembic_cfg, current_rev):
            logger.warning(
                "聊天库记录的迁移版本在脚本目录中不存在，重置为 base",
                stale_revision=current_rev,
                event_type="chat_db.stale_revision_reset",
            )
            await _force_clear_chat_alembic_version(engine)
            current_rev = None

        if head_rev and current_rev != head_rev:
            _upgrade_head(alembic_cfg)
            logger.info("聊天库迁移完成", event_type="chat_db.upgrade_done")
        elif head_rev is None and current_rev is None:
            logger.info("聊天库无迁移脚本，跳过", event_type="chat_db.no_migrations")
        else:
            logger.info("聊天库已是最新版本", event_type="chat_db.up_to_date")
