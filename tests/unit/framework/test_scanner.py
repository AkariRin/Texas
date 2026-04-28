"""测试 ComponentScanner 与 _compute_trigger 函数。"""

from __future__ import annotations

from src.core.framework.decorators import (
    FEATURE_META,
    component,
    feature,
    on_command,
    on_endswith,
    on_event,
    on_fullmatch,
    on_keyword,
    on_regex,
    on_startswith,
)
from src.core.framework.mapping import (
    CommandHandlerMapping,
    CompositeHandlerMapping,
    EndsWithHandlerMapping,
    EventTypeHandlerMapping,
    FullMatchHandlerMapping,
    KeywordHandlerMapping,
    RegexHandlerMapping,
    StartsWithHandlerMapping,
)
from src.core.framework.scanner import ComponentScanner, _compute_trigger

# ── 工厂函数 ──────────────────────────────────────────────────────────────────


def _make_scanner() -> ComponentScanner:
    """创建一个带全量映射的独立 ComponentScanner，避免测试间共享状态。"""
    mapping = CompositeHandlerMapping()
    mapping.add_mapping(CommandHandlerMapping())
    mapping.add_mapping(RegexHandlerMapping())
    mapping.add_mapping(KeywordHandlerMapping())
    mapping.add_mapping(StartsWithHandlerMapping())
    mapping.add_mapping(EndsWithHandlerMapping())
    mapping.add_mapping(FullMatchHandlerMapping())
    mapping.add_mapping(EventTypeHandlerMapping())
    return ComponentScanner(mapping)


# ── _compute_trigger 单元测试 ─────────────────────────────────────────────────


class TestComputeTrigger:
    """验证 _compute_trigger 的各种 mapping_type 分支。"""

    def test_command_only_primary(self):
        """command 类型，仅有主命令，无别名。"""
        meta = {"mapping_type": "command", "cmd": "/echo", "aliases": set()}
        assert _compute_trigger(meta) == "/echo"

    def test_command_with_aliases(self):
        """command 类型，含别名时，别名按字母序排列在后。"""
        meta = {"mapping_type": "command", "cmd": "/反馈", "aliases": {"/feedback", "/fb"}}
        result = _compute_trigger(meta)
        # 主命令在首位
        assert result.startswith("/反馈")
        # 别名均出现在结果中
        assert "/feedback" in result
        assert "/fb" in result
        # 格式：以 " | " 分隔
        parts = result.split(" | ")
        assert len(parts) == 3

    def test_command_empty_cmd(self):
        """command 类型，cmd 为空字符串时跳过空段。"""
        meta = {"mapping_type": "command", "cmd": "", "aliases": {"/t"}}
        result = _compute_trigger(meta)
        assert result == "/t"

    def test_keyword(self):
        """keyword 类型，关键词按排序拼接。"""
        meta = {"mapping_type": "keyword", "keywords": {"签到", "打卡"}}
        result = _compute_trigger(meta)
        assert "签到" in result
        assert "打卡" in result

    def test_keyword_empty(self):
        """keyword 类型，无关键词时返回空字符串。"""
        meta = {"mapping_type": "keyword", "keywords": set()}
        assert _compute_trigger(meta) == ""

    def test_fullmatch(self):
        """fullmatch 类型，返回匹配文本。"""
        meta = {"mapping_type": "fullmatch", "text": "签到"}
        assert _compute_trigger(meta) == "签到"

    def test_fullmatch_empty_text(self):
        """fullmatch 类型，text 为空时返回空字符串。"""
        meta = {"mapping_type": "fullmatch", "text": ""}
        assert _compute_trigger(meta) == ""

    def test_startswith(self):
        """startswith 类型，返回 prefix... 格式。"""
        meta = {"mapping_type": "startswith", "prefix": "晚安"}
        assert _compute_trigger(meta) == "晚安..."

    def test_startswith_empty_prefix(self):
        """startswith 类型，prefix 为空时返回空字符串。"""
        meta = {"mapping_type": "startswith", "prefix": ""}
        assert _compute_trigger(meta) == ""

    def test_endswith(self):
        """endswith 类型，返回 ...suffix 格式。"""
        meta = {"mapping_type": "endswith", "suffix": "晚安"}
        assert _compute_trigger(meta) == "...晚安"

    def test_endswith_empty_suffix(self):
        """endswith 类型，suffix 为空时返回空字符串。"""
        meta = {"mapping_type": "endswith", "suffix": ""}
        assert _compute_trigger(meta) == ""

    def test_regex_returns_empty(self):
        """regex 类型，不适合展示，返回空字符串。"""
        meta = {"mapping_type": "regex", "pattern": r"\d+"}
        assert _compute_trigger(meta) == ""

    def test_event_type_returns_empty(self):
        """event_type 类型，不适合展示，返回空字符串。"""
        meta = {"mapping_type": "event_type", "event_type": "notice"}
        assert _compute_trigger(meta) == ""

    def test_unknown_mapping_type_returns_empty(self):
        """未知 mapping_type 返回空字符串。"""
        meta = {"mapping_type": "unknown_type"}
        assert _compute_trigger(meta) == ""

    def test_empty_mapping_type_returns_empty(self):
        """mapping_type 为空字符串时返回空字符串。"""
        meta = {"mapping_type": ""}
        assert _compute_trigger(meta) == ""

    def test_missing_mapping_type_returns_empty(self):
        """mapping_type 字段缺失时返回空字符串。"""
        meta = {}
        assert _compute_trigger(meta) == ""


# ── ComponentScanner._register_controller 测试 ───────────────────────────────


class TestRegisterController:
    """验证 _register_controller 和 _build_feature_metadata 的行为。"""

    def test_simple_component_controllers_length(self):
        """注册简单组件后，controllers 长度为 1。"""
        scanner = _make_scanner()

        @component(name="t_simple_1", description="测试")
        class SimpleComp:
            @on_command("simple1")
            async def handle(self) -> None:
                pass

        scanner._register_controller(SimpleComp, SimpleComp.__component_meta__)  # type: ignore[attr-defined]
        assert len(scanner.controllers) == 1

    def test_simple_component_name_correct(self):
        """注册后，controller 的 component_name 与装饰器中的 name 一致。"""
        scanner = _make_scanner()

        @component(name="t_name_check_2")
        class NamedComp:
            @on_command("named2")
            async def handle(self) -> None:
                pass

        scanner._register_controller(NamedComp, NamedComp.__component_meta__)  # type: ignore[attr-defined]
        ctrl = scanner.controllers[0]
        assert ctrl["name"] == "t_name_check_2"

    def test_build_feature_metadata_contains_controller(self):
        """_build_feature_metadata 后，feature_registry 中包含 controller 级条目。"""
        scanner = _make_scanner()

        @component(name="t_reg_test_3")
        class RegTestComp:
            @on_command("reg3")
            async def handle(self) -> None:
                pass

        scanner._register_controller(RegTestComp, RegTestComp.__component_meta__)  # type: ignore[attr-defined]
        scanner._build_feature_metadata()
        assert "t_reg_test_3" in scanner.feature_registry

    def test_build_feature_metadata_contains_method(self):
        """_build_feature_metadata 后，feature_registry 中包含 method 级条目。"""
        scanner = _make_scanner()

        @component(name="t_method_test_4")
        class MethodTestComp:
            @on_command("mtest4")
            async def handle(self) -> None:
                pass

        scanner._register_controller(MethodTestComp, MethodTestComp.__component_meta__)  # type: ignore[attr-defined]
        scanner._build_feature_metadata()
        assert "t_method_test_4.handle" in scanner.feature_registry

    def test_standalone_feature_in_registry(self):
        """独立 @feature 添加到 _standalone_features 后，build_feature_metadata 包含该功能。"""
        scanner = _make_scanner()

        @feature(name="t_standalone_5", display_name="独立功能", description="测试独立功能")
        class StandaloneFeature:
            pass

        feat_meta = getattr(StandaloneFeature, FEATURE_META)
        scanner._standalone_features.append(feat_meta)
        scanner._build_feature_metadata()
        assert "t_standalone_5" in scanner.feature_registry

    def test_standalone_feature_metadata_fields(self):
        """独立 @feature 注册后，registry 中的元数据字段正确。"""
        scanner = _make_scanner()

        @feature(name="t_standalone_fields_6", display_name="独立功能字段测试", tags=["test"])
        class StandaloneFieldsFeature:
            pass

        feat_meta = getattr(StandaloneFieldsFeature, FEATURE_META)
        scanner._standalone_features.append(feat_meta)
        scanner._build_feature_metadata()
        fm = scanner.feature_registry.get("t_standalone_fields_6")
        assert fm is not None
        assert fm.display_name == "独立功能字段测试"
        assert "test" in fm.tags

    def test_stacked_decorators_handler_count_is_2(self):
        """叠加两个 @on_* 装饰器时，controller 的 handler_count 为 2。"""
        scanner = _make_scanner()

        @component(name="t_stacked_7")
        class StackedComp:
            @on_command("stack7a")
            @on_command("stack7b")
            async def handle(self) -> None:
                pass

        scanner._register_controller(StackedComp, StackedComp.__component_meta__)  # type: ignore[attr-defined]
        ctrl = scanner.controllers[0]
        assert ctrl["handler_count"] == 2

    def test_no_handler_decorator_not_registered(self):
        """没有 @on_* 装饰器的方法不被注册为 handler，handler_count 为 0。"""
        scanner = _make_scanner()

        @component(name="t_no_handler_8")
        class NoHandlerComp:
            async def plain_method(self) -> None:
                pass

            async def another_plain(self) -> None:
                pass

        scanner._register_controller(NoHandlerComp, NoHandlerComp.__component_meta__)  # type: ignore[attr-defined]
        ctrl = scanner.controllers[0]
        assert ctrl["handler_count"] == 0

    def test_system_component_in_registry_has_system_true(self):
        """system=True 的 component 在 feature_registry 中 system 字段为 True。"""
        scanner = _make_scanner()

        @component(name="t_sys_comp_9", system=True)
        class SysComp:
            @on_command("syscmd9")
            async def handle(self) -> None:
                pass

        scanner._register_controller(SysComp, SysComp.__component_meta__)  # type: ignore[attr-defined]
        scanner._build_feature_metadata()
        fm = scanner.feature_registry.get("t_sys_comp_9")
        assert fm is not None
        assert fm.system is True

    def test_system_component_method_has_system_true(self):
        """system=True 的 component，其 method 级条目的 system 字段也为 True。"""
        scanner = _make_scanner()

        @component(name="t_sys_method_10", system=True)
        class SysMethodComp:
            @on_command("syscmd10")
            async def handle(self) -> None:
                pass

        scanner._register_controller(SysMethodComp, SysMethodComp.__component_meta__)  # type: ignore[attr-defined]
        scanner._build_feature_metadata()
        fm = scanner.feature_registry.get("t_sys_method_10.handle")
        assert fm is not None
        assert fm.system is True

    def test_trigger_field_computed_by_compute_trigger(self):
        """注册后，method 级元数据的 trigger 字段由 _compute_trigger 计算填充。"""
        scanner = _make_scanner()

        @component(name="t_trigger_11")
        class TriggerComp:
            @on_command("/trigger_cmd_11")
            async def handle(self) -> None:
                pass

        scanner._register_controller(TriggerComp, TriggerComp.__component_meta__)  # type: ignore[attr-defined]
        ctrl = scanner.controllers[0]
        assert len(ctrl["methods"]) == 1
        method_info = ctrl["methods"][0]
        # trigger 应由 _compute_trigger 填充为命令名
        assert "/trigger_cmd_11" in method_info["trigger"]

    def test_trigger_empty_for_regex_handler(self):
        """regex 类型 handler 的 trigger 字段为空字符串。"""
        scanner = _make_scanner()

        @component(name="t_trigger_regex_12")
        class TriggerRegexComp:
            @on_regex(r"\d+")
            async def handle(self) -> None:
                pass

        scanner._register_controller(TriggerRegexComp, TriggerRegexComp.__component_meta__)  # type: ignore[attr-defined]
        ctrl = scanner.controllers[0]
        method_info = ctrl["methods"][0]
        assert method_info["trigger"] == ""

    def test_trigger_empty_for_event_type_handler(self):
        """event_type 类型 handler 的 trigger 字段为空字符串。"""
        scanner = _make_scanner()

        @component(name="t_trigger_event_13")
        class TriggerEventComp:
            @on_event("notice")
            async def handle(self) -> None:
                pass

        scanner._register_controller(TriggerEventComp, TriggerEventComp.__component_meta__)  # type: ignore[attr-defined]
        ctrl = scanner.controllers[0]
        method_info = ctrl["methods"][0]
        assert method_info["trigger"] == ""

    def test_keyword_trigger_field(self):
        """keyword 类型 handler 的 trigger 字段包含关键词。"""
        scanner = _make_scanner()

        @component(name="t_trigger_kw_14")
        class TriggerKwComp:
            @on_keyword({"hello", "world"})
            async def handle(self) -> None:
                pass

        scanner._register_controller(TriggerKwComp, TriggerKwComp.__component_meta__)  # type: ignore[attr-defined]
        ctrl = scanner.controllers[0]
        method_info = ctrl["methods"][0]
        assert "hello" in method_info["trigger"]
        assert "world" in method_info["trigger"]

    def test_multiple_components_independent(self):
        """注册多个组件后，controllers 长度正确，各自独立。"""
        scanner = _make_scanner()

        @component(name="t_multi_a_15")
        class MultiCompA:
            @on_command("multi15a")
            async def handle(self) -> None:
                pass

        @component(name="t_multi_b_15")
        class MultiCompB:
            @on_command("multi15b")
            async def handle(self) -> None:
                pass

        scanner._register_controller(MultiCompA, MultiCompA.__component_meta__)  # type: ignore[attr-defined]
        scanner._register_controller(MultiCompB, MultiCompB.__component_meta__)  # type: ignore[attr-defined]
        assert len(scanner.controllers) == 2
        names = {c["name"] for c in scanner.controllers}
        assert "t_multi_a_15" in names
        assert "t_multi_b_15" in names

    def test_controller_level_feature_has_no_parent(self):
        """controller 级别的 feature metadata parent 为 None。"""
        scanner = _make_scanner()

        @component(name="t_parent_ctrl_16")
        class ParentCtrlComp:
            @on_command("parentcmd16")
            async def handle(self) -> None:
                pass

        scanner._register_controller(ParentCtrlComp, ParentCtrlComp.__component_meta__)  # type: ignore[attr-defined]
        scanner._build_feature_metadata()
        fm = scanner.feature_registry.get("t_parent_ctrl_16")
        assert fm is not None
        assert fm.parent is None

    def test_method_level_feature_has_controller_as_parent(self):
        """method 级别的 feature metadata parent 为 controller name。"""
        scanner = _make_scanner()

        @component(name="t_parent_method_17")
        class ParentMethodComp:
            @on_command("parentcmd17")
            async def handle(self) -> None:
                pass

        scanner._register_controller(ParentMethodComp, ParentMethodComp.__component_meta__)  # type: ignore[attr-defined]
        scanner._build_feature_metadata()
        fm = scanner.feature_registry.get("t_parent_method_17.handle")
        assert fm is not None
        assert fm.parent == "t_parent_method_17"

    def test_startswith_trigger_format(self):
        """startswith 类型的 trigger 格式为 prefix...。"""
        scanner = _make_scanner()

        @component(name="t_sw_trigger_18")
        class StartsWithComp:
            @on_startswith("晚安")
            async def handle(self) -> None:
                pass

        scanner._register_controller(StartsWithComp, StartsWithComp.__component_meta__)  # type: ignore[attr-defined]
        ctrl = scanner.controllers[0]
        method_info = ctrl["methods"][0]
        assert method_info["trigger"] == "晚安..."

    def test_endswith_trigger_format(self):
        """endswith 类型的 trigger 格式为 ...suffix。"""
        scanner = _make_scanner()

        @component(name="t_ew_trigger_19")
        class EndsWithComp:
            @on_endswith("晚安")
            async def handle(self) -> None:
                pass

        scanner._register_controller(EndsWithComp, EndsWithComp.__component_meta__)  # type: ignore[attr-defined]
        ctrl = scanner.controllers[0]
        method_info = ctrl["methods"][0]
        assert method_info["trigger"] == "...晚安"

    def test_fullmatch_trigger_format(self):
        """fullmatch 类型的 trigger 返回匹配文本本身。"""
        scanner = _make_scanner()

        @component(name="t_fm_trigger_20")
        class FullMatchComp:
            @on_fullmatch("签到")
            async def handle(self) -> None:
                pass

        scanner._register_controller(FullMatchComp, FullMatchComp.__component_meta__)  # type: ignore[attr-defined]
        ctrl = scanner.controllers[0]
        method_info = ctrl["methods"][0]
        assert method_info["trigger"] == "签到"
