"""测试 feature_registry.py —— build_registry() 与 FeatureRegistry 接口。"""

from __future__ import annotations

import pytest

from src.core.registries.feature_registry import build_registry


def _ctrl(
    name: str,
    enabled: bool = False,
    system: bool = False,
    admin: bool = False,
    methods: list | None = None,
) -> dict:
    return {
        "name": name,
        "display_name": name.title(),
        "description": f"{name} desc",
        "default_enabled": enabled,
        "admin": admin,
        "system": system,
        "tags": ["tag1"],
        "methods": methods or [],
    }


def _method(
    name: str,
    enabled: bool | None = None,
    admin: bool | None = None,
    scope: str = "all",
    trigger: str = "",
) -> dict:
    return {
        "method": name,
        "display_name": name,
        "description": "",
        "default_enabled": enabled,
        "admin": admin,
        "message_scope": scope,
        "mapping_type": "command",
        "trigger": trigger or f"/{name}",
    }


class TestBuildRegistry:
    def test_controller_registered(self):
        reg = build_registry([_ctrl("feedback")])
        assert "feedback" in reg

    def test_method_registered_with_parent(self):
        reg = build_registry([_ctrl("feedback", methods=[_method("submit")])])
        assert "feedback.submit" in reg
        assert reg["feedback.submit"].parent == "feedback"

    def test_controller_has_correct_children(self):
        reg = build_registry(
            [_ctrl("feedback", methods=[_method("submit"), _method("list_feedbacks")])]
        )
        assert "feedback.submit" in reg["feedback"].children
        assert "feedback.list_feedbacks" in reg["feedback"].children

    def test_method_inherits_enabled_from_ctrl(self):
        reg = build_registry([_ctrl("fb", enabled=True, methods=[_method("submit", enabled=None)])])
        assert reg["fb.submit"].default_enabled is True

    def test_method_overrides_enabled_with_false(self):
        reg = build_registry(
            [_ctrl("fb", enabled=True, methods=[_method("submit", enabled=False)])]
        )
        assert reg["fb.submit"].default_enabled is False

    def test_method_inherits_admin_from_ctrl(self):
        ctrl = {**_ctrl("admin_ctrl", methods=[_method("cmd")]), "admin": True}
        reg = build_registry([ctrl])
        assert reg["admin_ctrl.cmd"].admin is True

    def test_method_admin_none_inherits_ctrl(self):
        ctrl = {**_ctrl("a", methods=[_method("m", admin=None)]), "admin": True}
        reg = build_registry([ctrl])
        assert reg["a.m"].admin is True

    def test_system_flag_propagates_to_methods(self):
        reg = build_registry([_ctrl("sys", system=True, methods=[_method("m")])])
        assert reg["sys"].system is True
        assert reg["sys.m"].system is True

    def test_trigger_stored_in_method(self):
        m = _method("handle", trigger="/echo | /e")
        reg = build_registry([_ctrl("echo", methods=[m])])
        assert reg["echo.handle"].trigger == "/echo | /e"

    def test_controller_trigger_always_empty(self):
        reg = build_registry([_ctrl("echo", methods=[_method("handle")])])
        assert reg["echo"].trigger == ""

    def test_standalone_feature_registered(self):
        reg = build_registry(
            [],
            [
                {
                    "name": "daily_like",
                    "display_name": "每日点赞",
                    "description": "",
                    "tags": [],
                    "default_enabled": True,
                    "system": False,
                }
            ],
        )
        assert "daily_like" in reg
        assert reg["daily_like"].parent is None
        assert reg["daily_like"].children == ()

    def test_multiple_controllers(self):
        reg = build_registry([_ctrl("a"), _ctrl("b")])
        assert "a" in reg
        assert "b" in reg


class TestFeatureRegistry:
    def _reg(self):
        return build_registry(
            [
                _ctrl("echo", enabled=True, methods=[_method("handle")]),
                _ctrl("personnel", system=True, methods=[_method("sync")]),
            ]
        )

    def test_get_existing(self):
        reg = self._reg()
        assert reg.get("echo") is not None
        assert reg.get("echo").name == "echo"

    def test_get_nonexistent_returns_none(self):
        assert self._reg().get("not_exist") is None

    def test_contains(self):
        reg = self._reg()
        assert "echo" in reg
        assert "ghost" not in reg

    def test_active_names_includes_system(self):
        reg = self._reg()
        assert "personnel" in reg.active_names()
        assert "echo" in reg.active_names()

    def test_non_system_names_excludes_system(self):
        reg = self._reg()
        assert "personnel" not in reg.non_system_names()
        assert "personnel.sync" not in reg.non_system_names()

    def test_sorted_non_system_names_is_sorted(self):
        reg = build_registry([_ctrl("zzz"), _ctrl("aaa")])
        names = reg.sorted_non_system_names()
        assert list(names) == sorted(names)

    def test_immutability(self):
        reg = self._reg()
        with pytest.raises(TypeError):
            reg._data["new_key"] = None  # type: ignore[index]

    def test_non_system_tree_excludes_system_ctrl(self):
        reg = self._reg()
        tree = reg.non_system_tree()
        ctrl_names = {node["name"] for node in tree}
        assert "echo" in ctrl_names
        assert "personnel" not in ctrl_names

    def test_non_system_tree_with_global_enabled_override(self):
        reg = self._reg()
        tree = reg.non_system_tree(global_enabled={"echo": False})
        echo_node = next(n for n in tree if n["name"] == "echo")
        assert echo_node["enabled"] is False

    def test_tree_children_included(self):
        reg = build_registry([_ctrl("fb", methods=[_method("submit"), _method("query")])])
        tree = reg.non_system_tree()
        fb_node = next(n for n in tree if n["name"] == "fb")
        child_names = [c["name"] for c in fb_node["children"]]
        assert "fb.submit" in child_names
        assert "fb.query" in child_names

    def test_len_and_iter(self):
        reg = self._reg()
        assert len(reg) > 0
        keys = list(reg)
        assert "echo" in keys
