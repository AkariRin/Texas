"""生命周期注册表 —— @startup / @shutdown 装饰器与全局注册表。

业务模块在自身 service 文件末尾使用装饰器声明启动/关闭逻辑，
装饰器在 import 时自动注册到此注册表，由 LifecycleOrchestrator 统一驱动。

设计参考：src/core/db/migration_registry.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True)
class StartupEntry:
    """描述一个业务模块的启动逻辑。

    Attributes:
        name: 模块标识名，如 "personnel"、"llm"。
        provides: 该模块向注册表提供的服务键名（对应 app.state 属性名）。
        requires: 启动时需要的依赖键名（由基础设施或其他模块 provides）。
        factory: 异步工厂函数，接收 requires dict，返回 provides dict。
        dispatcher_services: provides_key 集合，这些服务需注册到 EventDispatcher.services。
    """

    name: str
    provides: tuple[str, ...]
    requires: tuple[str, ...]
    factory: Any  # async (dict[str, Any]) -> dict[str, Any]
    dispatcher_services: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class ShutdownEntry:
    """描述一个业务模块的关闭逻辑。

    Attributes:
        name: 对应 StartupEntry 的模块标识名。
        hook: 异步关闭函数，接收本模块 provides 的服务 dict。
    """

    name: str
    hook: Any  # async (dict[str, Any]) -> None


# ── 全局注册表 ──

_startups: list[StartupEntry] = []
_shutdowns: list[ShutdownEntry] = []


def startup(
    name: str,
    provides: list[str],
    requires: list[str] | None = None,
    dispatcher_services: list[str] | None = None,
) -> Callable[[Any], Any]:
    """声明业务模块启动逻辑的装饰器。

    在 import 时执行注册，装饰器返回原函数不变。

    Args:
        name: 模块唯一标识名。
        provides: 该启动函数提供的服务键名列表（写入 app.state 的属性名）。
        requires: 依赖的服务键名列表（来自基础设施或其他模块）。
        dispatcher_services: 需注册到 EventDispatcher.services 的 provides_key 列表。
    """

    def decorator(fn: Any) -> Any:
        _startups.append(
            StartupEntry(
                name=name,
                provides=tuple(provides),
                requires=tuple(requires or []),
                factory=fn,
                dispatcher_services=frozenset(dispatcher_services or []),
            )
        )
        return fn

    return decorator


def shutdown(name: str) -> Callable[[Any], Any]:
    """声明业务模块关闭逻辑的装饰器。

    在 import 时执行注册，装饰器返回原函数不变。

    Args:
        name: 对应的 @startup 模块标识名。
    """

    def decorator(fn: Any) -> Any:
        _shutdowns.append(ShutdownEntry(name=name, hook=fn))
        return fn

    return decorator


def get_all_startups() -> list[StartupEntry]:
    """返回所有已注册的启动入口（副本）。"""
    return list(_startups)


def get_all_shutdowns() -> list[ShutdownEntry]:
    """返回所有已注册的关闭入口（副本）。"""
    return list(_shutdowns)
