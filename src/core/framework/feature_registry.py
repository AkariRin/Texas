"""不可变功能注册表 —— 启动时构建，运行期间只读。

将代码中通过 @controller / @feature 装饰器声明的功能元数据固化为内存单例，
不持久化到数据库，确保运行期间永远不被修改。
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass(frozen=True)
class FeatureMetadata:
    """单个功能的不可变元数据。"""

    name: str
    """功能唯一标识，格式：controller 级为 'echo'，method 级为 'echo.handle_echo'。"""
    display_name: str
    """人类可读名称。"""
    description: str
    """功能描述。"""
    default_enabled: bool
    """代码定义的默认启用状态。"""
    admin: bool
    """是否仅限管理员使用。"""
    message_scope: str
    """消息范围：'all' / 'group' / 'private'。"""
    mapping_type: str
    """Handler 映射类型（command/regex/keyword 等），controller 级为空字符串。"""
    tags: tuple[str, ...]
    """标签列表，仅 controller 级和独立 @feature 有标签。"""
    system: bool
    """系统功能：强制启用，不在前端展示。"""
    parent: str | None
    """父 controller 名称，None 表示顶层。"""
    children: tuple[str, ...]
    """子功能 name 列表，仅 controller 级非空。"""
    trigger: str = ""
    """用户可感知的触发方式描述。controller 级为空字符串，method 级由 Scanner 计算。

    默认值 "" 保证现有所有实例化站点无需强制更新；Scanner 会为 method 级显式传入计算值。
    示例："/反馈 | /feedback"、"jrlp | 今日老婆 | 抽老婆"
    """


class FeatureRegistry:
    """不可变功能注册表单例。

    内部使用 MappingProxyType 保证外部无法修改。
    """

    def __init__(self, metadata: dict[str, FeatureMetadata]) -> None:
        self._data: MappingProxyType[str, FeatureMetadata] = MappingProxyType(metadata)
        # 启动时预计算，运行期只读，避免每次调用重建集合或重新排序
        self._non_system_names: frozenset[str] = frozenset(
            name for name, m in metadata.items() if not m.system
        )
        self._sorted_non_system_names: tuple[str, ...] = tuple(sorted(self._non_system_names))

    def get(self, name: str) -> FeatureMetadata | None:
        """按名称获取功能元数据，不存在时返回 None。"""
        return self._data.get(name)

    def __getitem__(self, name: str) -> FeatureMetadata:
        return self._data[name]

    def __contains__(self, name: object) -> bool:
        return name in self._data

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def active_names(self) -> frozenset[str]:
        """返回所有功能名称集合（含系统功能）。"""
        return frozenset(self._data.keys())

    def non_system_names(self) -> frozenset[str]:
        """返回所有非系统功能名称集合。"""
        return self._non_system_names

    def sorted_non_system_names(self) -> tuple[str, ...]:
        """返回按名称排序后的非系统功能名称序列。"""
        return self._sorted_non_system_names

    def non_system_tree(
        self,
        global_enabled: dict[str, bool] | None = None,
    ) -> list[dict[str, Any]]:
        """构建非系统功能树（controller -> methods）。

        Args:
            global_enabled: {feature_name: enabled} 映射，来自 permission_group group_id=0 行。
                            若提供，则覆盖 default_enabled 作为当前 enabled 状态。
        """
        ctrl_features = [m for m in self._data.values() if m.parent is None and not m.system]
        ctrl_features.sort(key=lambda m: m.name)

        tree = []
        for ctrl in ctrl_features:
            ctrl_enabled = (
                global_enabled.get(ctrl.name, ctrl.default_enabled)
                if global_enabled is not None
                else ctrl.default_enabled
            )
            children = []
            for child_name in ctrl.children:
                child = self._data.get(child_name)
                if child is None:
                    continue
                child_enabled = (
                    global_enabled.get(child.name, child.default_enabled)
                    if global_enabled is not None
                    else child.default_enabled
                )
                children.append(
                    {
                        "name": child.name,
                        "parent": child.parent,
                        "display_name": child.display_name,
                        "description": child.description,
                        "default_enabled": child.default_enabled,
                        "enabled": child_enabled,
                        "admin": child.admin,
                        "message_scope": child.message_scope,
                        "mapping_type": child.mapping_type,
                        "tags": list(child.tags),
                        "is_active": True,
                        "system": child.system,
                        "children": [],
                        "trigger": child.trigger,
                    }
                )
            tree.append(
                {
                    "name": ctrl.name,
                    "parent": ctrl.parent,
                    "display_name": ctrl.display_name,
                    "description": ctrl.description,
                    "default_enabled": ctrl.default_enabled,
                    "enabled": ctrl_enabled,
                    "admin": ctrl.admin,
                    "message_scope": ctrl.message_scope,
                    "mapping_type": ctrl.mapping_type,
                    "tags": list(ctrl.tags),
                    "is_active": True,
                    "system": ctrl.system,
                    "children": children,
                    "trigger": ctrl.trigger,
                }
            )
        return tree


def build_registry(
    controllers: list[dict[str, Any]],
    standalone_features: list[dict[str, Any]] | None = None,
) -> FeatureRegistry:
    """从扫描结果构建不可变 FeatureRegistry。

    Args:
        controllers: ComponentScanner 扫描到的 controller 元数据列表。
        standalone_features: @feature 装饰的独立功能元数据列表。
    """
    metadata: dict[str, FeatureMetadata] = {}

    for ctrl in controllers:
        ctrl_name: str = ctrl["name"]
        ctrl_enabled: bool = ctrl.get("default_enabled", False)
        ctrl_admin: bool = ctrl.get("admin", False)
        ctrl_system: bool = ctrl.get("system", False)
        child_names: list[str] = []

        for method in ctrl.get("methods", []):
            method_name = f"{ctrl_name}.{method['method']}"
            method_enabled_raw = method.get("default_enabled")
            method_enabled = ctrl_enabled if method_enabled_raw is None else method_enabled_raw
            method_admin_raw = method.get("admin")
            method_admin = ctrl_admin if method_admin_raw is None else method_admin_raw

            metadata[method_name] = FeatureMetadata(
                name=method_name,
                display_name=method.get("display_name") or method["method"],
                description=method.get("description", ""),
                default_enabled=method_enabled,
                admin=method_admin,
                message_scope=method.get("message_scope", "all"),
                mapping_type=method.get("mapping_type", ""),
                tags=(),
                system=ctrl_system,
                parent=ctrl_name,
                children=(),
                trigger=method.get("trigger", ""),
            )
            child_names.append(method_name)

        metadata[ctrl_name] = FeatureMetadata(
            name=ctrl_name,
            display_name=ctrl.get("display_name") or ctrl_name,
            description=ctrl.get("description", ""),
            default_enabled=ctrl_enabled,
            admin=ctrl_admin,
            message_scope="all",
            mapping_type="",
            tags=tuple(ctrl.get("tags", [])),
            system=ctrl_system,
            parent=None,
            children=tuple(child_names),
            trigger="",  # controller 级无触发方式，trigger 由 method 级承载
        )

    for feat in standalone_features or []:
        feat_name: str = feat["name"]
        metadata[feat_name] = FeatureMetadata(
            name=feat_name,
            display_name=feat.get("display_name") or feat_name,
            description=feat.get("description", ""),
            default_enabled=feat.get("default_enabled", False),
            admin=False,
            message_scope="all",
            mapping_type="",
            tags=tuple(feat.get("tags", [])),
            system=feat.get("system", False),
            parent=None,
            children=(),
            trigger=feat.get("trigger", ""),
        )

    return FeatureRegistry(metadata)
