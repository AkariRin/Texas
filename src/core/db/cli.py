"""统一数据库迁移 CLI —— 消灭 alembic -c xxx.ini 的碎片化调用。

用法:
    python -m src.core.db.cli migrate [--target NAME]
    python -m src.core.db.cli revision --target NAME [-m MESSAGE]
    python -m src.core.db.cli autogenerate --target NAME [-m MESSAGE]
    python -m src.core.db.cli current [--target NAME]
    python -m src.core.db.cli history --target NAME
    python -m src.core.db.cli downgrade --target NAME REVISION
    python -m src.core.db.cli heads [--target NAME]
"""

from __future__ import annotations

import argparse
import importlib
import re
import sys
from typing import TYPE_CHECKING

from alembic import command

if TYPE_CHECKING:
    from alembic.config import Config

    from src.core.config import Settings
    from src.core.db.migration_registry import MigrationTarget

# 与 migration.py 保持一致的标识符校验正则
_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$")


# ─────────────────────── 内部工具 ───────────────────────


def _load_registries() -> None:
    """触发所有模块的迁移目标注册（通过各模块 __init__.py 的 register_migration_target 调用）。"""
    importlib.import_module("src.core.db")
    importlib.import_module("src.core.db.migrations.chat")


def _get_settings() -> Settings:
    from src.core.config import get_settings

    return get_settings()


def _get_target(name: str) -> MigrationTarget:
    from src.core.db.migration_registry import get_all_targets, get_target

    _load_registries()
    target = get_target(name)
    if target is None:
        available = ", ".join(t.name for t in get_all_targets())
        print(f"错误：未知迁移目标 {name!r}（可用: {available}）", file=sys.stderr)
        sys.exit(1)
    return target


def _get_all_targets() -> list[MigrationTarget]:
    from src.core.db.migration_registry import get_all_targets

    _load_registries()
    return get_all_targets()


def _build_cfg(target: MigrationTarget, settings: Settings | None = None) -> Config:
    from src.core.db.alembic_config_factory import build_alembic_config

    if settings is None:
        settings = _get_settings()
    return build_alembic_config(target, settings)


def _prepare_target(target: MigrationTarget, settings: Settings) -> None:
    """迁移前置准备：导入模型、连接预检、确保 schema 存在。

    与 migration.py 的 run_startup_migration 保持对齐，
    修复 CLI 长期缺失的前置步骤导致的报错问题。
    """
    from sqlalchemy import create_engine, text

    # 1. 确保 ORM 模型注册到 metadata（autogenerate 需要）
    if target.model_import:
        importlib.import_module(target.model_import)

    sync_url = target.get_db_url(settings).replace("+asyncpg", "+psycopg")
    engine = create_engine(sync_url, pool_pre_ping=True)
    try:
        # 2. 连接预检：提前给出友好错误而非晦涩的底层异常
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"[{target.name}] 数据库连接正常")

        # 3. 确保专属 schema 存在（chat 目标需要 chat schema）
        if target.schema:
            if not _SAFE_IDENTIFIER_RE.match(target.schema):
                print(f"错误：非法 schema 名称 {target.schema!r}", file=sys.stderr)
                sys.exit(1)
            with engine.begin() as conn:
                conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {target.schema}"))
            print(f"[{target.name}] schema '{target.schema}' 已就绪")
    except Exception as exc:
        print(f"错误：[{target.name}] 无法连接数据库 —— {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        engine.dispose()


# ─────────────────────── 子命令实现 ───────────────────────


def cmd_migrate(args: argparse.Namespace) -> None:
    """upgrade head —— 升级所有（或指定）数据库。"""
    settings = _get_settings()
    targets = [_get_target(args.target)] if args.target else _get_all_targets()
    for t in targets:
        _prepare_target(t, settings)
        print(f"\n[{t.name}] upgrade head ...")
        command.upgrade(_build_cfg(t, settings), "head")


def cmd_revision(args: argparse.Namespace) -> None:
    """创建手动迁移脚本。"""
    settings = _get_settings()
    target = _get_target(args.target)
    _prepare_target(target, settings)
    command.revision(_build_cfg(target, settings), message=args.message or "manual")


def cmd_autogenerate(args: argparse.Namespace) -> None:
    """自动检测 ORM 与数据库差异并生成迁移脚本。"""
    settings = _get_settings()
    target = _get_target(args.target)
    _prepare_target(target, settings)
    command.revision(
        _build_cfg(target, settings), message=args.message or "auto", autogenerate=True
    )


def cmd_current(args: argparse.Namespace) -> None:
    """显示当前迁移版本。"""
    settings = _get_settings()
    targets = [_get_target(args.target)] if args.target else _get_all_targets()
    for t in targets:
        print(f"\n[{t.name}]")
        command.current(_build_cfg(t, settings))


def cmd_history(args: argparse.Namespace) -> None:
    """显示迁移历史。"""
    target = _get_target(args.target)
    command.history(_build_cfg(target))


def cmd_downgrade(args: argparse.Namespace) -> None:
    """回退迁移到指定版本。"""
    target = _get_target(args.target)
    command.downgrade(_build_cfg(target), args.revision)


def cmd_heads(args: argparse.Namespace) -> None:
    """显示 head 版本。"""
    settings = _get_settings()
    targets = [_get_target(args.target)] if args.target else _get_all_targets()
    for t in targets:
        print(f"\n[{t.name}]")
        command.heads(_build_cfg(t, settings))


# ─────────────────────── CLI 入口 ───────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m src.core.db.cli",
        description="Texas 多数据库迁移工具",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # migrate
    p = sub.add_parser("migrate", help="升级到 head")
    p.add_argument("--target", help="迁移目标名称（默认全部）")
    p.set_defaults(func=cmd_migrate)

    # revision
    p = sub.add_parser("revision", help="创建手动迁移脚本")
    p.add_argument("--target", required=True, help="迁移目标名称")
    p.add_argument("-m", "--message", help="迁移说明")
    p.set_defaults(func=cmd_revision)

    # autogenerate
    p = sub.add_parser("autogenerate", help="自动生成迁移脚本")
    p.add_argument("--target", required=True, help="迁移目标名称")
    p.add_argument("-m", "--message", help="迁移说明")
    p.set_defaults(func=cmd_autogenerate)

    # current
    p = sub.add_parser("current", help="显示当前版本")
    p.add_argument("--target", help="迁移目标名称（默认全部）")
    p.set_defaults(func=cmd_current)

    # history
    p = sub.add_parser("history", help="显示迁移历史")
    p.add_argument("--target", required=True, help="迁移目标名称")
    p.set_defaults(func=cmd_history)

    # downgrade
    p = sub.add_parser("downgrade", help="回退迁移")
    p.add_argument("--target", required=True, help="迁移目标名称")
    p.add_argument("revision", help="目标版本（如 -1, base, abc123）")
    p.set_defaults(func=cmd_downgrade)

    # heads
    p = sub.add_parser("heads", help="显示 head 版本")
    p.add_argument("--target", help="迁移目标名称（默认全部）")
    p.set_defaults(func=cmd_heads)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
