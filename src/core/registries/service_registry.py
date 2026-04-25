"""运行时服务注册表 —— 替代 AppState dataclass，启动后冻结为只读。"""

from __future__ import annotations

from typing import Any, TypeVar, cast

T = TypeVar("T")


class ServiceRegistry:
    """运行时服务注册表。启动完成后冻结为只读，按名称和类型获取服务实例。"""

    __slots__ = ("_store", "_frozen")

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
        self._frozen = False

    def register(self, name: str, instance: Any) -> None:
        """注册服务实例。冻结后调用抛出 RuntimeError。"""
        if self._frozen:
            raise RuntimeError(f"ServiceRegistry 已冻结，禁止在运行期注册服务（name={name!r}）")
        self._store[name] = instance

    def freeze(self) -> None:
        """冻结注册表，禁止后续注册。由 lifespan 在所有服务启动完成后调用。"""
        self._frozen = True

    def get(self, name: str) -> Any | None:
        """按名称获取服务实例，不存在时返回 None。"""
        return self._store.get(name)

    def get_typed(self, cls: type[T], key: str) -> T:
        """按名称获取服务实例并强制转换为指定类型。key 不存在时抛出 KeyError。"""
        return cast("T", self._store[key])

    def __contains__(self, name: str) -> bool:
        return name in self._store

    def __repr__(self) -> str:
        status = "frozen" if self._frozen else "open"
        return f"ServiceRegistry({status}, keys={list(self._store.keys())})"
