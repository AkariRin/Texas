"""权限内存快照注册表 —— ComponentScanner 扫描完成后从 FeatureRegistry 派生。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.registries.feature_registry import FeatureRegistry


@dataclass(frozen=True)
class PermissionRule:
    """单个功能的权限规则快照（不可变）。"""

    feature_name: str
    system: bool
    default_enabled: bool
    admin: bool


class PermissionRegistry:
    """只读权限规则快照，ComponentScanner.scan() 完成后由 FeatureRegistry 派生。

    提供零 IO 的内存查询接口，用于热路径权限检查（如 system 功能直通）。
    """

    def __init__(self, rules: dict[str, PermissionRule]) -> None:
        self._rules = rules

    @classmethod
    def from_feature_registry(cls, registry: FeatureRegistry) -> PermissionRegistry:
        """从 FeatureRegistry 构建权限规则快照。

        Args:
            registry: 已构建完成的不可变功能注册表。
        """
        rules: dict[str, PermissionRule] = {}
        for name in registry:
            meta = registry[name]
            rules[name] = PermissionRule(
                feature_name=name,
                system=meta.system,
                default_enabled=meta.default_enabled,
                admin=meta.admin,
            )
        return cls(rules)

    def is_system(self, feature_name: str) -> bool:
        """是否为系统级功能（强制启用，零 IO）。"""
        rule = self._rules.get(feature_name)
        return rule is not None and rule.system

    def is_admin(self, feature_name: str) -> bool:
        """是否仅管理员可用。"""
        rule = self._rules.get(feature_name)
        return rule is not None and rule.admin

    def get_default(self, feature_name: str) -> bool:
        """获取功能默认启用状态。"""
        rule = self._rules.get(feature_name)
        return rule.default_enabled if rule is not None else False
