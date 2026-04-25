"""配置注册表 —— 各模块自持的 Settings 实例动态注册中心。"""

from __future__ import annotations

from typing import Any, TypeVar, cast

from pydantic_settings import BaseSettings

T = TypeVar("T", bound=BaseSettings)


class ConfigRegistry:
    """各业务模块的配置实例注册表。

    每个模块在 @startup 中可选注册自己的 Settings 实例，
    运维工具可遍历此注册表获取所有有效配置的当前值。
    """

    def __init__(self) -> None:
        self._store: dict[str, BaseSettings] = {}

    def register(self, name: str, settings: BaseSettings) -> None:
        """注册配置实例。"""
        self._store[name] = settings

    def get_typed(self, cls: type[T], name: str) -> T:
        """按名称获取配置实例并转换为目标类型。"""
        value = self._store.get(name)
        if value is None:
            raise KeyError(f"ConfigRegistry 中不存在配置：{name!r}")
        return cast("T", value)

    def all(self) -> dict[str, Any]:
        """返回所有配置实例的 model_dump 聚合（用于运维诊断）。"""
        return {name: cfg.model_dump() for name, cfg in self._store.items()}
