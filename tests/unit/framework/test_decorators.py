"""测试 decorators.py —— @component 与 @on_* 元数据注入。"""

from __future__ import annotations

import re

from src.core.framework.decorators import (
    COMPONENT_META,
    FEATURE_META,
    HANDLER_META,
    MessageScope,
    Permission,
    component,
    feature,
    on_command,
    on_endswith,
    on_event,
    on_fullmatch,
    on_keyword,
    on_notice,
    on_regex,
    on_startswith,
)


class TestComponentDecorator:
    def test_sets_all_fields(self):
        @component(
            name="echo",
            description="复读",
            display_name="回声",
            default_enabled=True,
            system=False,
            admin=False,
            tags=["fun"],
        )
        class Echo:
            pass

        meta = getattr(Echo, COMPONENT_META)
        assert meta["name"] == "echo"
        assert meta["description"] == "复读"
        assert meta["display_name"] == "回声"
        assert meta["default_enabled"] is True
        assert meta["system"] is False
        assert meta["admin"] is False
        assert meta["tags"] == ["fun"]

    def test_display_name_defaults_to_name(self):
        @component(name="foo")
        class Foo:
            pass

        assert getattr(Foo, COMPONENT_META)["display_name"] == "foo"

    def test_system_flag(self):
        @component(name="sys", system=True)
        class Sys:
            pass

        assert getattr(Sys, COMPONENT_META)["system"] is True

    def test_tags_default_empty(self):
        @component(name="notag")
        class NoTag:
            pass

        assert getattr(NoTag, COMPONENT_META)["tags"] == []

    def test_returns_same_class(self):
        @component(name="iden")
        class Iden:
            pass

        assert isinstance(Iden(), Iden)


class TestOnCommandDecorator:
    def test_sets_handler_meta(self):
        @on_command("/test", aliases={"/t"})
        def handler():
            pass

        metas = getattr(handler, HANDLER_META)
        assert len(metas) == 1
        meta = metas[0]
        assert meta["mapping_type"] == "command"
        assert meta["cmd"] == "/test"
        assert "/t" in meta["aliases"]

    def test_default_permission_is_anyone(self):
        @on_command("/cmd")
        def handler():
            pass

        assert getattr(handler, HANDLER_META)[0]["permission"] == Permission.ANYONE

    def test_admin_true_sets_admin_permission(self):
        @on_command("/admin_cmd", admin=True)
        def handler():
            pass

        assert getattr(handler, HANDLER_META)[0]["permission"] == Permission.ADMIN

    def test_admin_none_keeps_original_permission(self):
        """admin=None（默认）不覆盖 permission 参数。"""

        @on_command("/cmd", permission=Permission.GROUP_OWNER)
        def handler():
            pass

        assert getattr(handler, HANDLER_META)[0]["permission"] == Permission.GROUP_OWNER

    def test_message_scope_group(self):
        @on_command("/grp", message_scope=MessageScope.group)
        def handler():
            pass

        assert getattr(handler, HANDLER_META)[0]["message_scope"] == "group"

    def test_stacked_decorators_append(self):
        """同一方法叠加两个 on_command 时，列表长度为 2。"""

        @on_command("/a")
        @on_command("/b")
        def handler():
            pass

        assert len(getattr(handler, HANDLER_META)) == 2


class TestOnRegexDecorator:
    def test_compiles_pattern(self):
        @on_regex(r"\d+")
        def handler():
            pass

        meta = getattr(handler, HANDLER_META)[0]
        assert meta["mapping_type"] == "regex"
        assert meta["pattern"] == r"\d+"
        assert isinstance(meta["compiled_pattern"], re.Pattern)

    def test_flags_applied(self):
        @on_regex(r"hello", flags=re.IGNORECASE)
        def handler():
            pass

        meta = getattr(handler, HANDLER_META)[0]
        assert meta["compiled_pattern"].flags & re.IGNORECASE


class TestOnKeywordDecorator:
    def test_keywords_stored(self):
        @on_keyword({"签到", "打卡"})
        def handler():
            pass

        meta = getattr(handler, HANDLER_META)[0]
        assert meta["mapping_type"] == "keyword"
        assert "签到" in meta["keywords"]


class TestOnStartsEndsWith:
    def test_startswith_meta(self):
        @on_startswith("晚安")
        def handler():
            pass

        meta = getattr(handler, HANDLER_META)[0]
        assert meta["mapping_type"] == "startswith"
        assert meta["prefix"] == "晚安"

    def test_endswith_meta(self):
        @on_endswith("晚安")
        def handler():
            pass

        meta = getattr(handler, HANDLER_META)[0]
        assert meta["mapping_type"] == "endswith"
        assert meta["suffix"] == "晚安"


class TestOnFullmatch:
    def test_fullmatch_meta(self):
        @on_fullmatch("签到")
        def handler():
            pass

        meta = getattr(handler, HANDLER_META)[0]
        assert meta["mapping_type"] == "fullmatch"
        assert meta["text"] == "签到"


class TestOnEvent:
    def test_on_event_meta(self):
        """on_event 的 mapping_type 为 event_type，event_type 字段存储事件类型。"""

        @on_event("notice")
        def handler():
            pass

        meta = getattr(handler, HANDLER_META)[0]
        assert meta["mapping_type"] == "event_type"
        assert meta["event_type"] == "notice"

    def test_on_notice_sets_notice_type(self):
        @on_notice(notice_type="group_increase")
        def handler():
            pass

        meta = getattr(handler, HANDLER_META)[0]
        assert meta["mapping_type"] == "event_type"
        assert meta["event_type"] == "notice"
        assert meta["notice_type"] == "group_increase"


class TestFeatureDecorator:
    def test_feature_meta_fields(self):
        @feature(name="daily_task", display_name="日常任务", tags=["task"])
        class DailyTask:
            pass

        meta = getattr(DailyTask, FEATURE_META)
        assert meta["name"] == "daily_task"
        assert meta["display_name"] == "日常任务"
        assert "task" in meta["tags"]
        assert meta["system"] is False

    def test_feature_display_name_defaults_to_name(self):
        @feature(name="autofeat")
        class AutoFeat:
            pass

        assert getattr(AutoFeat, FEATURE_META)["display_name"] == "autofeat"


class TestPermissionEnum:
    def test_ordering(self):
        assert Permission.ANYONE < Permission.GROUP_MEMBER
        assert Permission.GROUP_MEMBER < Permission.GROUP_ADMIN
        assert Permission.GROUP_ADMIN < Permission.GROUP_OWNER
        assert Permission.GROUP_OWNER < Permission.ADMIN
