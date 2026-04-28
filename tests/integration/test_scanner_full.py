"""ComponentScanner 完整扫描流程集成测试。

直接调用 _register_controller / _build_feature_metadata，
绕过模块扫描时的 __module__ 检查，专注验证注册逻辑正确性。
"""

from __future__ import annotations

from src.core.framework.decorators import (
    COMPONENT_META,
    FEATURE_META,
    Permission,
    component,
    feature,
    on_command,
    on_keyword,
)
from src.core.framework.mapping import (
    CommandHandlerMapping,
    CompositeHandlerMapping,
    KeywordHandlerMapping,
)
from src.core.framework.scanner import ComponentScanner


def _make_scanner() -> ComponentScanner:
    """每次创建独立的 scanner 实例，避免跨测试状态污染。"""
    mapping = CompositeHandlerMapping([CommandHandlerMapping(), KeywordHandlerMapping()])
    return ComponentScanner(mapping)


class TestControllerRegistrationAndRegistry:
    """注册 controller + build_feature_metadata → registry 正确性验证。"""

    def test_registry_contains_controller_and_method(self) -> None:
        """注册 controller 后 registry 应同时包含 controller 和 method 条目。"""
        scanner = _make_scanner()

        @component(
            name="sf_echo_unique_2",
            description="回声功能",
            default_enabled=True,
        )
        class EchoHandler:
            @on_command("echo", permission=Permission.ANYONE)
            async def handle(self) -> None: ...

        ctrl_meta = getattr(EchoHandler, COMPONENT_META)
        scanner._register_controller(EchoHandler, ctrl_meta)
        scanner._build_feature_metadata()

        registry = scanner.feature_registry
        assert "sf_echo_unique_2" in registry
        assert "sf_echo_unique_2.handle" in registry

    def test_controller_default_enabled_propagates_to_method(self) -> None:
        """当 method 未指定 default_enabled 时，应继承 controller 的值。"""
        scanner = _make_scanner()

        @component(name="sf_enabled_unique_2", default_enabled=True)
        class EnabledHandler:
            @on_command("cmd")
            async def handle(self) -> None: ...

        ctrl_meta = getattr(EnabledHandler, COMPONENT_META)
        scanner._register_controller(EnabledHandler, ctrl_meta)
        scanner._build_feature_metadata()

        registry = scanner.feature_registry
        assert registry["sf_enabled_unique_2"].default_enabled is True
        assert registry["sf_enabled_unique_2.handle"].default_enabled is True

    def test_controller_default_disabled(self) -> None:
        """default_enabled=False 时 controller 和 method 均应为 False。"""
        scanner = _make_scanner()

        @component(name="sf_disabled_unique_2", default_enabled=False)
        class DisabledHandler:
            @on_command("dis")
            async def handle(self) -> None: ...

        ctrl_meta = getattr(DisabledHandler, COMPONENT_META)
        scanner._register_controller(DisabledHandler, ctrl_meta)
        scanner._build_feature_metadata()

        registry = scanner.feature_registry
        assert registry["sf_disabled_unique_2"].default_enabled is False
        assert registry["sf_disabled_unique_2.handle"].default_enabled is False

    def test_trigger_computed_for_command(self) -> None:
        """command 类型的 method 应正确计算 trigger 字段。"""
        scanner = _make_scanner()

        @component(name="sf_trigger_unique_2", default_enabled=True)
        class TriggerHandler:
            @on_command("greet", aliases={"hello"})
            async def handle(self) -> None: ...

        ctrl_meta = getattr(TriggerHandler, COMPONENT_META)
        scanner._register_controller(TriggerHandler, ctrl_meta)
        scanner._build_feature_metadata()

        method_meta = scanner.feature_registry["sf_trigger_unique_2.handle"]
        # trigger 应包含命令名和别名，以 " | " 分隔
        assert "greet" in method_meta.trigger
        assert "hello" in method_meta.trigger


class TestControllerChildren:
    """controller 的 children 字段匹配注册方法。"""

    def test_children_matches_registered_methods(self) -> None:
        """controller 的 children 应恰好包含所有已注册 method 的完整名称。"""
        scanner = _make_scanner()

        @component(name="sf_children_unique_2", default_enabled=True)
        class MultiMethodHandler:
            @on_command("cmd_a")
            async def handle_a(self) -> None: ...

            @on_command("cmd_b")
            async def handle_b(self) -> None: ...

        ctrl_meta = getattr(MultiMethodHandler, COMPONENT_META)
        scanner._register_controller(MultiMethodHandler, ctrl_meta)
        scanner._build_feature_metadata()

        ctrl_entry = scanner.feature_registry["sf_children_unique_2"]
        child_names = set(ctrl_entry.children)
        assert "sf_children_unique_2.handle_a" in child_names
        assert "sf_children_unique_2.handle_b" in child_names
        assert len(child_names) == 2

    def test_children_parent_back_reference(self) -> None:
        """每个 child method 的 parent 应指向其 controller。"""
        scanner = _make_scanner()

        @component(name="sf_parent_unique_2", default_enabled=True)
        class ParentRefHandler:
            @on_command("ref")
            async def handle(self) -> None: ...

        ctrl_meta = getattr(ParentRefHandler, COMPONENT_META)
        scanner._register_controller(ParentRefHandler, ctrl_meta)
        scanner._build_feature_metadata()

        method_entry = scanner.feature_registry["sf_parent_unique_2.handle"]
        assert method_entry.parent == "sf_parent_unique_2"


class TestNonSystemTree:
    """non_system_tree 应排除 system=True 的 controller。"""

    def test_system_controller_excluded_from_tree(self) -> None:
        """system=True 的 controller 不应出现在 non_system_tree 中。"""
        scanner = _make_scanner()

        @component(name="sf_sys_unique_2", system=True, default_enabled=True)
        class SystemHandler:
            @on_command("sys_cmd")
            async def handle(self) -> None: ...

        @component(name="sf_user_unique_2", system=False, default_enabled=True)
        class UserHandler:
            @on_command("user_cmd")
            async def handle(self) -> None: ...

        scanner._register_controller(SystemHandler, getattr(SystemHandler, COMPONENT_META))
        scanner._register_controller(UserHandler, getattr(UserHandler, COMPONENT_META))
        scanner._build_feature_metadata()

        tree_names = [node["name"] for node in scanner.feature_registry.non_system_tree()]
        assert "sf_sys_unique_2" not in tree_names
        assert "sf_user_unique_2" in tree_names

    def test_system_controller_in_registry_but_not_tree(self) -> None:
        """system controller 虽出现在 registry 中，但不应出现在 non_system_tree。"""
        scanner = _make_scanner()

        @component(name="sf_sysonly_unique_2", system=True, default_enabled=True)
        class SysOnlyHandler:
            @on_command("so_cmd")
            async def handle(self) -> None: ...

        scanner._register_controller(SysOnlyHandler, getattr(SysOnlyHandler, COMPONENT_META))
        scanner._build_feature_metadata()

        registry = scanner.feature_registry
        assert "sf_sysonly_unique_2" in registry  # registry 中存在

        tree_names = [node["name"] for node in registry.non_system_tree()]
        assert "sf_sysonly_unique_2" not in tree_names  # tree 中不存在


class TestStandaloneFeature:
    """独立 @feature 添加到 _standalone_features → registry 正确性。"""

    def test_standalone_feature_in_registry(self) -> None:
        """@feature 装饰的类应出现在 registry 中。"""
        scanner = _make_scanner()

        @feature(name="sf_daily_unique_2", default_enabled=True)
        class DailyTask: ...

        scanner._standalone_features.append(getattr(DailyTask, FEATURE_META))
        scanner._build_feature_metadata()

        assert "sf_daily_unique_2" in scanner.feature_registry

    def test_standalone_feature_parent_is_none(self) -> None:
        """独立 @feature 的 parent 应为 None（无父 controller）。"""
        scanner = _make_scanner()

        @feature(name="sf_parent_none_unique_2", default_enabled=False)
        class StandaloneTask: ...

        scanner._standalone_features.append(getattr(StandaloneTask, FEATURE_META))
        scanner._build_feature_metadata()

        entry = scanner.feature_registry["sf_parent_none_unique_2"]
        assert entry.parent is None

    def test_standalone_feature_children_empty(self) -> None:
        """独立 @feature 的 children 应为空 tuple。"""
        scanner = _make_scanner()

        @feature(name="sf_no_children_unique_2", default_enabled=True)
        class ChildlessTask: ...

        scanner._standalone_features.append(getattr(ChildlessTask, FEATURE_META))
        scanner._build_feature_metadata()

        entry = scanner.feature_registry["sf_no_children_unique_2"]
        assert entry.children == ()

    def test_standalone_feature_default_enabled_preserved(self) -> None:
        """@feature 的 default_enabled 值应原样保留在 registry 中。"""
        scanner = _make_scanner()

        @feature(name="sf_enabled_state_unique_2", default_enabled=True)
        class EnabledTask: ...

        scanner._standalone_features.append(getattr(EnabledTask, FEATURE_META))
        scanner._build_feature_metadata()

        entry = scanner.feature_registry["sf_enabled_state_unique_2"]
        assert entry.default_enabled is True


class TestMultipleDecorators:
    """叠加两个装饰器 → handler_count = 2。"""

    def test_stacked_decorators_handler_count(self) -> None:
        """同一个方法叠加两个 handler 装饰器时，handler_count 应为 2。"""
        scanner = _make_scanner()

        @component(name="sf_multi_unique_3", default_enabled=True)
        class MultiDecoratorHandler:
            @on_command("multi_cmd")
            @on_keyword({"multi_kw"})
            async def handle(self) -> None: ...

        ctrl_meta = getattr(MultiDecoratorHandler, COMPONENT_META)
        scanner._register_controller(MultiDecoratorHandler, ctrl_meta)
        scanner._build_feature_metadata()

        ctrl = scanner.controllers[0]
        assert ctrl["handler_count"] == 2

    def test_stacked_decorators_methods_count(self) -> None:
        """叠加两个装饰器时，methods 列表应有 2 个条目。"""
        scanner = _make_scanner()

        @component(name="sf_multi_methods_unique_3", default_enabled=True)
        class MultiMethodsHandler:
            @on_command("mm_cmd")
            @on_keyword({"mm_kw"})
            async def handle(self) -> None: ...

        ctrl_meta = getattr(MultiMethodsHandler, COMPONENT_META)
        scanner._register_controller(MultiMethodsHandler, ctrl_meta)

        ctrl = scanner.controllers[0]
        assert len(ctrl["methods"]) == 2

    def test_stacked_decorators_mapping_types(self) -> None:
        """叠加的两个装饰器应分别对应 command 和 keyword mapping_type。"""
        scanner = _make_scanner()

        @component(name="sf_multi_types_unique_3", default_enabled=True)
        class MultiTypesHandler:
            @on_command("mt_cmd")
            @on_keyword({"mt_kw"})
            async def handle(self) -> None: ...

        ctrl_meta = getattr(MultiTypesHandler, COMPONENT_META)
        scanner._register_controller(MultiTypesHandler, ctrl_meta)

        ctrl = scanner.controllers[0]
        mapping_types = {m["mapping_type"] for m in ctrl["methods"]}
        assert "command" in mapping_types
        assert "keyword" in mapping_types
