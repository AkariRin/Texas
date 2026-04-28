"""测试 mapping.py —— 各 HandlerMapping 策略的 resolve() 逻辑。"""

from __future__ import annotations

import re
from unittest.mock import MagicMock

from src.core.framework.decorators import Permission
from src.core.framework.mapping import (
    CommandHandlerMapping,
    CompositeHandlerMapping,
    EndsWithHandlerMapping,
    EventTypeHandlerMapping,
    FullMatchHandlerMapping,
    HandlerMethod,
    KeywordHandlerMapping,
    RegexHandlerMapping,
    StartsWithHandlerMapping,
)
from tests.conftest import make_group_message_event, make_notice_event, make_private_message_event

# ── 辅助函数 ──────────────────────────────────────────────────────────────────


def _hm(
    mapping_type: str = "command",
    priority: int = 50,
    message_scope: str = "all",
    **meta: object,
) -> HandlerMethod:
    """构造最小可注册的 HandlerMethod。"""
    return HandlerMethod(
        component=MagicMock(),
        method=MagicMock(),
        priority=priority,
        permission=Permission.ANYONE,
        metadata={"mapping_type": mapping_type, "message_scope": message_scope, **meta},
        component_name="test_component",
        method_name="test_method",
    )


# ── CommandHandlerMapping ─────────────────────────────────────────────────────


class TestCommandHandlerMapping:
    """CommandHandlerMapping：通过命令前缀匹配消息文本。"""

    def setup_method(self) -> None:
        self.mapping = CommandHandlerMapping(command_prefix="/")
        self.hm = _hm(mapping_type="command", cmd="echo", aliases={"e"})
        self.mapping.register(self.hm)

    def test_hit_main_command(self) -> None:
        """命中主命令 /echo。"""
        event = make_group_message_event(text="/echo hello")
        result = self.mapping.resolve(event)
        assert len(result) == 1
        assert result[0].handler is self.hm

    def test_hit_alias(self) -> None:
        """命中别名 /e。"""
        event = make_group_message_event(text="/e hello")
        result = self.mapping.resolve(event)
        assert len(result) == 1
        assert result[0].handler is self.hm

    def test_no_hit_wrong_command(self) -> None:
        """不存在的命令不命中。"""
        event = make_group_message_event(text="/unknown")
        result = self.mapping.resolve(event)
        assert result == []

    def test_no_hit_without_prefix(self) -> None:
        """无前缀文本不命中。"""
        event = make_group_message_event(text="echo hello")
        result = self.mapping.resolve(event)
        assert result == []

    def test_no_hit_non_message_event(self) -> None:
        """非消息事件不命中。"""
        event = make_notice_event(notice_type="friend_add")
        result = self.mapping.resolve(event)
        assert result == []

    def test_no_hit_only_prefix(self) -> None:
        """消息仅为 "/" 时，命令名为空，不命中任何已注册命令。"""
        event = make_group_message_event(text="/")
        result = self.mapping.resolve(event)
        assert result == []

    def test_register_strips_prefix_in_key(self) -> None:
        """注册时若 cmd 带前缀，内部去掉前缀后仍能正确 resolve。"""
        mapping = CommandHandlerMapping(command_prefix="/")
        hm = _hm(mapping_type="command", cmd="/ping")
        mapping.register(hm)
        event = make_group_message_event(text="/ping")
        result = mapping.resolve(event)
        assert len(result) == 1
        assert result[0].handler is hm


# ── RegexHandlerMapping ───────────────────────────────────────────────────────


class TestRegexHandlerMapping:
    """RegexHandlerMapping：正则匹配并携带 regex_match。"""

    def setup_method(self) -> None:
        self.mapping = RegexHandlerMapping()
        self.pattern = re.compile(r"hello\s+(\w+)")
        self.hm = _hm(mapping_type="regex", compiled_pattern=self.pattern)
        self.mapping.register(self.hm)

    def test_hit_returns_regex_match(self) -> None:
        """命中时 ResolvedHandler.regex_match 非空，且 group(1) 正确。"""
        event = make_group_message_event(text="hello world")
        result = self.mapping.resolve(event)
        assert len(result) == 1
        assert result[0].handler is self.hm
        assert result[0].regex_match is not None
        assert result[0].regex_match.group(1) == "world"

    def test_no_hit(self) -> None:
        """不匹配正则时返回空列表。"""
        event = make_group_message_event(text="goodbye world")
        result = self.mapping.resolve(event)
        assert result == []

    def test_two_resolves_produce_independent_match_objects(self) -> None:
        """两次 resolve 的 match 对象相互独立，避免并发竞态。"""
        event1 = make_group_message_event(text="hello alice")
        event2 = make_group_message_event(text="hello bob")
        r1 = self.mapping.resolve(event1)
        r2 = self.mapping.resolve(event2)
        assert r1[0].regex_match is not r2[0].regex_match
        assert r1[0].regex_match.group(1) == "alice"  # type: ignore[union-attr]
        assert r2[0].regex_match.group(1) == "bob"  # type: ignore[union-attr]

    def test_no_hit_non_message_event(self) -> None:
        """非消息事件不命中。"""
        event = make_notice_event(notice_type="friend_add")
        result = self.mapping.resolve(event)
        assert result == []

    def test_no_compiled_pattern_not_registered(self) -> None:
        """未提供 compiled_pattern 的 HandlerMethod 不被注册。"""
        mapping = RegexHandlerMapping()
        hm = _hm(mapping_type="regex")  # 无 compiled_pattern
        mapping.register(hm)
        event = make_group_message_event(text="anything")
        assert mapping.resolve(event) == []


# ── KeywordHandlerMapping ─────────────────────────────────────────────────────


class TestKeywordHandlerMapping:
    """KeywordHandlerMapping：任意关键词命中即匹配。"""

    def setup_method(self) -> None:
        self.mapping = KeywordHandlerMapping()
        self.hm_a = _hm(mapping_type="keyword", keywords={"苹果", "香蕉"})
        self.hm_b = _hm(mapping_type="keyword", keywords={"橘子"})
        self.mapping.register(self.hm_a)
        self.mapping.register(self.hm_b)

    def test_hit_first_keyword(self) -> None:
        """包含关键词"苹果"时命中 hm_a。"""
        event = make_group_message_event(text="我想吃苹果")
        result = self.mapping.resolve(event)
        handlers = [r.handler for r in result]
        assert self.hm_a in handlers

    def test_hit_second_keyword(self) -> None:
        """包含关键词"香蕉"时命中 hm_a。"""
        event = make_group_message_event(text="香蕉很好吃")
        result = self.mapping.resolve(event)
        handlers = [r.handler for r in result]
        assert self.hm_a in handlers

    def test_hit_second_handler(self) -> None:
        """包含关键词"橘子"时命中 hm_b。"""
        event = make_group_message_event(text="来一个橘子")
        result = self.mapping.resolve(event)
        handlers = [r.handler for r in result]
        assert self.hm_b in handlers

    def test_no_hit(self) -> None:
        """不含任何关键词时返回空列表。"""
        event = make_group_message_event(text="今天天气不错")
        result = self.mapping.resolve(event)
        assert result == []

    def test_no_hit_non_message_event(self) -> None:
        """非消息事件不命中。"""
        event = make_notice_event(notice_type="friend_add")
        result = self.mapping.resolve(event)
        assert result == []


# ── StartsWithHandlerMapping ──────────────────────────────────────────────────


class TestStartsWithHandlerMapping:
    """StartsWithHandlerMapping：前缀匹配。"""

    def setup_method(self) -> None:
        self.mapping = StartsWithHandlerMapping()
        self.hm = _hm(mapping_type="startswith", prefix="#天气")
        self.mapping.register(self.hm)

    def test_hit_when_text_starts_with_prefix(self) -> None:
        """以前缀开头时命中。"""
        event = make_group_message_event(text="#天气 北京")
        result = self.mapping.resolve(event)
        assert len(result) == 1
        assert result[0].handler is self.hm

    def test_no_hit_when_prefix_in_middle(self) -> None:
        """前缀出现在中间时不命中。"""
        event = make_group_message_event(text="查询#天气 北京")
        result = self.mapping.resolve(event)
        assert result == []

    def test_no_hit_non_message_event(self) -> None:
        """非消息事件不命中。"""
        event = make_notice_event(notice_type="friend_add")
        result = self.mapping.resolve(event)
        assert result == []

    def test_no_prefix_not_registered(self) -> None:
        """未提供 prefix 的 HandlerMethod 不被注册。"""
        mapping = StartsWithHandlerMapping()
        hm = _hm(mapping_type="startswith")  # 无 prefix
        mapping.register(hm)
        event = make_group_message_event(text="任意内容")
        assert mapping.resolve(event) == []


# ── EndsWithHandlerMapping ────────────────────────────────────────────────────


class TestEndsWithHandlerMapping:
    """EndsWithHandlerMapping：后缀匹配。"""

    def setup_method(self) -> None:
        self.mapping = EndsWithHandlerMapping()
        self.hm = _hm(mapping_type="endswith", suffix="结束")
        self.mapping.register(self.hm)

    def test_hit_when_text_ends_with_suffix(self) -> None:
        """以后缀结尾时命中。"""
        event = make_group_message_event(text="任务结束")
        result = self.mapping.resolve(event)
        assert len(result) == 1
        assert result[0].handler is self.hm

    def test_no_hit_when_suffix_at_start(self) -> None:
        """后缀出现在开头时不命中。"""
        event = make_group_message_event(text="结束之后继续")
        result = self.mapping.resolve(event)
        assert result == []

    def test_no_hit_non_message_event(self) -> None:
        """非消息事件不命中。"""
        event = make_notice_event(notice_type="friend_add")
        result = self.mapping.resolve(event)
        assert result == []


# ── FullMatchHandlerMapping ───────────────────────────────────────────────────


class TestFullMatchHandlerMapping:
    """FullMatchHandlerMapping：精确匹配消息文本。"""

    def setup_method(self) -> None:
        self.mapping = FullMatchHandlerMapping()
        self.hm = _hm(mapping_type="fullmatch", text="签到")
        self.mapping.register(self.hm)

    def test_hit_exact_match(self) -> None:
        """精确匹配时命中。"""
        event = make_group_message_event(text="签到")
        result = self.mapping.resolve(event)
        assert len(result) == 1
        assert result[0].handler is self.hm

    def test_no_hit_partial_match(self) -> None:
        """部分匹配（文本中包含关键词但不等于）不命中。"""
        event = make_group_message_event(text="我要签到")
        result = self.mapping.resolve(event)
        assert result == []

    def test_no_hit_non_message_event(self) -> None:
        """非消息事件不命中。"""
        event = make_notice_event(notice_type="friend_add")
        result = self.mapping.resolve(event)
        assert result == []

    def test_no_text_not_registered(self) -> None:
        """未提供 text 的 HandlerMethod 不被注册。"""
        mapping = FullMatchHandlerMapping()
        hm = _hm(mapping_type="fullmatch")  # 无 text
        mapping.register(hm)
        event = make_group_message_event(text="任意内容")
        assert mapping.resolve(event) == []


# ── EventTypeHandlerMapping ───────────────────────────────────────────────────


class TestEventTypeHandlerMapping:
    """EventTypeHandlerMapping：按事件类型/子类型匹配。"""

    def setup_method(self) -> None:
        self.mapping = EventTypeHandlerMapping()
        # 仅按 post_type 过滤
        self.hm_notice = _hm(mapping_type="event_type", event_type="notice")
        # 按 post_type + notice_type 过滤
        self.hm_friend_add = _hm(
            mapping_type="event_type",
            event_type="notice",
            notice_type="friend_add",
        )
        # 按 post_type + notice_type + sub_type 过滤
        self.hm_poke = _hm(
            mapping_type="event_type",
            event_type="notice",
            notice_type="notify",
            sub_type="poke",
        )
        self.mapping.register(self.hm_notice)
        self.mapping.register(self.hm_friend_add)
        self.mapping.register(self.hm_poke)

    def test_hit_post_type(self) -> None:
        """post_type 匹配时命中（宽泛匹配，无 notice_type 限制）。"""
        event = make_notice_event(notice_type="friend_add")
        result = self.mapping.resolve(event)
        handlers = [r.handler for r in result]
        assert self.hm_notice in handlers

    def test_hit_notice_type_filter(self) -> None:
        """notice_type 过滤命中。"""
        event = make_notice_event(notice_type="friend_add")
        result = self.mapping.resolve(event)
        handlers = [r.handler for r in result]
        assert self.hm_friend_add in handlers

    def test_no_hit_wrong_notice_type(self) -> None:
        """notice_type 不匹配时过滤掉。"""
        event = make_notice_event(notice_type="group_ban")
        result = self.mapping.resolve(event)
        handlers = [r.handler for r in result]
        assert self.hm_friend_add not in handlers

    def test_hit_sub_type_filter(self) -> None:
        """sub_type 过滤命中。"""
        event = make_notice_event(notice_type="notify", sub_type="poke")
        result = self.mapping.resolve(event)
        handlers = [r.handler for r in result]
        assert self.hm_poke in handlers

    def test_no_hit_wrong_sub_type(self) -> None:
        """sub_type 不匹配时过滤掉。"""
        event = make_notice_event(notice_type="notify", sub_type="honor")
        result = self.mapping.resolve(event)
        handlers = [r.handler for r in result]
        assert self.hm_poke not in handlers

    def test_no_hit_wrong_post_type(self) -> None:
        """post_type 不匹配时不命中。"""
        event = make_group_message_event(text="hello")
        result = self.mapping.resolve(event)
        assert result == []


# ── CompositeHandlerMapping ───────────────────────────────────────────────────


class TestCompositeHandlerMapping:
    """CompositeHandlerMapping：聚合多个映射，优先级排序、scope 过滤。"""

    def _build_composite(self) -> CompositeHandlerMapping:
        """构造包含 command 和 keyword 映射的 CompositeHandlerMapping。"""
        cmd_mapping = CommandHandlerMapping(command_prefix="/")
        kw_mapping = KeywordHandlerMapping()
        composite = CompositeHandlerMapping([cmd_mapping, kw_mapping])
        return composite

    def test_priority_sort_ascending(self) -> None:
        """优先级较小的 HandlerMethod 排在结果列表前面。"""
        composite = self._build_composite()
        hm_low = _hm(mapping_type="keyword", priority=10, keywords={"测试"})
        hm_high = _hm(mapping_type="keyword", priority=90, keywords={"测试"})
        composite.register(hm_high)
        composite.register(hm_low)

        event = make_group_message_event(text="测试一下")
        result = composite.resolve(event)
        assert len(result) == 2
        assert result[0].handler.priority <= result[1].handler.priority
        assert result[0].handler is hm_low
        assert result[1].handler is hm_high

    def test_scope_filter_group_only(self) -> None:
        """message_scope='group' 的处理器只在群聊事件中出现。"""
        composite = self._build_composite()
        hm_group = _hm(mapping_type="keyword", message_scope="group", keywords={"你好"})
        composite.register(hm_group)

        group_event = make_group_message_event(text="你好")
        private_event = make_private_message_event(text="你好")

        group_result = composite.resolve(group_event)
        private_result = composite.resolve(private_event)

        assert any(r.handler is hm_group for r in group_result)
        assert not any(r.handler is hm_group for r in private_result)

    def test_scope_filter_private_only(self) -> None:
        """message_scope='private' 的处理器只在私聊事件中出现。"""
        composite = self._build_composite()
        hm_private = _hm(mapping_type="keyword", message_scope="private", keywords={"私聊"})
        composite.register(hm_private)

        group_event = make_group_message_event(text="私聊")
        private_event = make_private_message_event(text="私聊")

        group_result = composite.resolve(group_event)
        private_result = composite.resolve(private_event)

        assert not any(r.handler is hm_private for r in group_result)
        assert any(r.handler is hm_private for r in private_result)

    def test_scope_all_appears_everywhere(self) -> None:
        """message_scope='all'（默认）的处理器在群聊和私聊均命中。"""
        composite = self._build_composite()
        hm_all = _hm(mapping_type="keyword", message_scope="all", keywords={"通用"})
        composite.register(hm_all)

        group_event = make_group_message_event(text="通用消息")
        private_event = make_private_message_event(text="通用消息")

        assert any(r.handler is hm_all for r in composite.resolve(group_event))
        assert any(r.handler is hm_all for r in composite.resolve(private_event))

    def test_registered_count(self) -> None:
        """registered_count 返回所有子映射中已注册的处理器总数。"""
        composite = self._build_composite()
        assert composite.registered_count == 0

        composite.register(_hm(mapping_type="command", cmd="ping"))
        assert composite.registered_count == 1

        composite.register(_hm(mapping_type="keyword", keywords={"hello"}))
        assert composite.registered_count == 2

        composite.register(_hm(mapping_type="keyword", keywords={"world"}))
        assert composite.registered_count == 3

    def test_add_mapping_dynamically(self) -> None:
        """add_mapping 后可通过 composite.register 将处理器路由到新映射。"""
        composite = CompositeHandlerMapping()
        fullmatch_mapping = FullMatchHandlerMapping()
        composite.add_mapping(fullmatch_mapping)

        hm = _hm(mapping_type="fullmatch", text="你好")
        composite.register(hm)

        event = make_group_message_event(text="你好")
        result = composite.resolve(event)
        assert len(result) == 1
        assert result[0].handler is hm

    def test_unknown_mapping_type_ignored(self) -> None:
        """未知的 mapping_type 在 register 时被静默忽略，不抛异常。"""
        composite = self._build_composite()
        hm = _hm(mapping_type="nonexistent_type")
        # 不应抛出异常
        composite.register(hm)
        assert composite.registered_count == 0

    def test_scope_filter_not_applied_to_non_message_events(self) -> None:
        """scope 过滤仅对消息事件生效；通知事件的 scope 不被过滤。"""
        event_mapping = EventTypeHandlerMapping()
        composite = CompositeHandlerMapping([event_mapping])
        hm = _hm(
            mapping_type="event_type",
            message_scope="group",  # scope 字段存在，但对通知事件无效
            event_type="notice",
        )
        event_mapping.register(hm)

        event = make_notice_event(notice_type="friend_add")
        result = composite.resolve(event)
        # 通知事件不受 message_scope 过滤影响，应命中
        assert len(result) == 1
        assert result[0].handler is hm
