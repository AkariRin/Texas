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
import sys
from typing import TYPE_CHECKING

from alembic import command
from alembic.config import Config

if TYPE_CHECKING:
    from src.core.config import Settings
    from src.core.db.migration_registry import MigrationTarget


# ─────────────────────── 内部工具 ───────────────────────


def _load_registries() -> None:
    """触发所有模块的迁移目标注册（通过各模块 __init__.py 的 register_migration_target 调用）。"""
    importlib.import_module("src.core.db")
    importlib.import_module("src.core.chat")


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


# ─────────────────────── 子命令实现 ───────────────────────


def cmd_migrate(args: argparse.Namespace) -> None:
    """upgrade head —— 升级所有（或指定）数据库。"""
    settings = _get_settings()
    targets = [_get_target(args.target)] if args.target else _get_all_targets()
    for t in targets:
        print(f"\n[{t.name}] upgrade head ...")
        command.upgrade(_build_cfg(t, settings), "head")


def cmd_revision(args: argparse.Namespace) -> None:
    """创建手动迁移脚本。"""
    target = _get_target(args.target)
    command.revision(_build_cfg(target), message=args.message or "manual")


def cmd_autogenerate(args: argparse.Namespace) -> None:
    """自动检测 ORM 与数据库差异并生成迁移脚本。"""
    target = _get_target(args.target)
    command.revision(_build_cfg(target), message=args.message or "auto", autogenerate=True)


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
