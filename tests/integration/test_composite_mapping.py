"""集成测试：CompositeHandlerMapping 多种策略联合工作。

与单元测试（test_mapping.py）的区别：本文件测试多个子映射同时存在时的联合行为，
验证 command + keyword + regex + event_type 四种策略在同一 CompositeHandlerMapping
中的协同路由、scope 过滤、优先级排序等端到端场景。
"""

from __future__ import annotations

import re
from unittest.mock import MagicMock

from src.core.framework.decorators import Permission
from src.core.framework.mapping import (
    CommandHandlerMapping,
    CompositeHandlerMapping,
    EventTypeHandlerMapping,
    HandlerMethod,
    KeywordHandlerMapping,
    RegexHandlerMapping,
)
from tests.conftest import make_group_message_event, make_notice_event, make_private_message_event

# ── 辅助函数 ──────────────────────────────────────────────────────────────────


def _hm(
    mapping_type: str = "command",
    priority: int = 50,
    message_scope: str = "all",
    **meta: object,
) -> HandlerMethod:
    """构造最小可注册的 HandlerMethod，用于集成场景。"""
    return HandlerMethod(
        component=MagicMock(),
        method=MagicMock(),
        priority=priority,
        permission=Permission.ANYONE,
        metadata={"mapping_type": mapping_type, "message_scope": message_scope, **meta},
        component_name="test_component",
        method_name="test_method",
    )


def _build_composite() -> CompositeHandlerMapping:
    """构造包含四种子映射的 CompositeHandlerMapping，模拟真实生产环境。"""
    cm = CompositeHandlerMapping()
    cm.add_mapping(CommandHandlerMapping(command_prefix="/"))
    cm.add_mapping(KeywordHandlerMapping())
    cm.add_mapping(RegexHandlerMapping())
    cm.add_mapping(EventTypeHandlerMapping())
    return cm


# ── 集成测试用例 ──────────────────────────────────────────────────────────────


class TestCompositeRouting:
    """多策略联合路由的集成场景测试。"""

    def test_command_and_keyword_both_resolve(self) -> None:
        """同一群聊消息可同时命中 command 和 keyword 两个独立 handler。

        消息 "/hello 你好" 既以 "/" 开头命中命令处理器，又包含关键词命中关键词处理器。
        验证 CompositeHandlerMapping 合并两个子映射的结果。
        """
        cm = _build_composite()

        hm_cmd = _hm(mapping_type="command", priority=10, cmd="hello")
        hm_kw = _hm(mapping_type="keyword", priority=20, keywords={"你好"})
        cm.register(hm_cmd)
        cm.register(hm_kw)

        event = make_group_message_event(text="/hello 你好")
        result = cm.resolve(event)

        handlers = [r.handler for r in result]
        assert hm_cmd in handlers, "command handler 应被命中"
        assert hm_kw in handlers, "keyword handler 应被命中"
        assert len(result) == 2

    def test_scope_private_only_not_in_group(self) -> None:
        """scope=private 的 handler 在群聊消息中不触发。

        注册一个 message_scope='private' 的关键词处理器，
        群聊事件触发时该处理器不应出现在结果中。
        """
        cm = _build_composite()

        hm_private = _hm(
            mapping_type="keyword",
            message_scope="private",
            keywords={"私信"},
        )
        cm.register(hm_private)

        group_event = make_group_message_event(text="私信内容")
        result = cm.resolve(group_event)

        assert not any(r.handler is hm_private for r in result), (
            "scope=private 的 handler 不应在群聊中出现"
        )

    def test_scope_group_only_not_in_private(self) -> None:
        """scope=group 的 handler 在私聊消息中不触发。

        注册一个 message_scope='group' 的关键词处理器，
        私聊事件触发时该处理器不应出现在结果中。
        """
        cm = _build_composite()

        hm_group = _hm(
            mapping_type="keyword",
            message_scope="group",
            keywords={"群消息"},
        )
        cm.register(hm_group)

        private_event = make_private_message_event(text="群消息")
        result = cm.resolve(private_event)

        assert not any(r.handler is hm_group for r in result), (
            "scope=group 的 handler 不应在私聊中出现"
        )

    def test_scope_group_resolves_in_group(self) -> None:
        """scope=group 的 handler 在群聊事件中正常触发。"""
        cm = _build_composite()

        hm_group = _hm(
            mapping_type="keyword",
            message_scope="group",
            keywords={"群消息"},
        )
        cm.register(hm_group)

        group_event = make_group_message_event(text="群消息")
        result = cm.resolve(group_event)

        assert any(r.handler is hm_group for r in result), "scope=group 的 handler 应在群聊中出现"

    def test_scope_private_resolves_in_private(self) -> None:
        """scope=private 的 handler 在私聊事件中正常触发。"""
        cm = _build_composite()

        hm_private = _hm(
            mapping_type="keyword",
            message_scope="private",
            keywords={"私信"},
        )
        cm.register(hm_private)

        private_event = make_private_message_event(text="私信内容")
        result = cm.resolve(private_event)

        assert any(r.handler is hm_private for r in result), (
            "scope=private 的 handler 应在私聊中出现"
        )

    def test_notice_event_not_matched_by_message_handlers(self) -> None:
        """通知事件不会被 command / keyword / regex 三种消息映射命中。

        CommandHandlerMapping、KeywordHandlerMapping、RegexHandlerMapping
        的 resolve() 要求事件为 MessageEvent 才处理，通知事件应全部返回空。
        """
        cm = _build_composite()

        hm_cmd = _hm(mapping_type="command", cmd="test")
        hm_kw = _hm(mapping_type="keyword", keywords={"通知"})
        hm_re = _hm(
            mapping_type="regex",
            compiled_pattern=re.compile(r".+"),  # 匹配所有非空文本
        )
        cm.register(hm_cmd)
        cm.register(hm_kw)
        cm.register(hm_re)

        notice_event = make_notice_event(notice_type="friend_add")
        result = cm.resolve(notice_event)

        # 通知事件无任何消息类 handler 命中
        assert result == [], f"通知事件不应命中消息处理器，实际结果：{result}"

    def test_event_handler_resolves_notice(self) -> None:
        """EventTypeHandlerMapping 正确路由通知事件。

        注册仅匹配 notice 类型的 event_type handler，
        发送通知事件时应被命中，发送消息事件时不应命中。
        """
        cm = _build_composite()

        hm_notice = _hm(
            mapping_type="event_type",
            event_type="notice",
            notice_type="friend_add",
        )
        cm.register(hm_notice)

        notice_event = make_notice_event(notice_type="friend_add")
        notice_result = cm.resolve(notice_event)
        assert any(r.handler is hm_notice for r in notice_result), (
            "event_type handler 应命中匹配的通知事件"
        )

        # 消息事件不应触发 event_type=notice 的 handler
        msg_event = make_group_message_event(text="任意消息")
        msg_result = cm.resolve(msg_event)
        assert not any(r.handler is hm_notice for r in msg_result), (
            "event_type=notice 的 handler 不应命中消息事件"
        )

    def test_multiple_regex_sorted_by_priority(self) -> None:
        """多个 regex handler 按 priority 升序排列在结果中。

        注册三个都能匹配同一文本的 regex handler，但优先级不同，
        验证 CompositeHandlerMapping.resolve() 对最终结果按 priority 升序排序。
        """
        cm = _build_composite()

        hm_low = _hm(
            mapping_type="regex",
            priority=10,
            compiled_pattern=re.compile(r"测试"),
        )
        hm_mid = _hm(
            mapping_type="regex",
            priority=50,
            compiled_pattern=re.compile(r"测试"),
        )
        hm_high = _hm(
            mapping_type="regex",
            priority=90,
            compiled_pattern=re.compile(r"测试"),
        )
        # 故意乱序注册，验证排序由框架保证
        cm.register(hm_high)
        cm.register(hm_low)
        cm.register(hm_mid)

        event = make_group_message_event(text="这是测试消息")
        result = cm.resolve(event)

        assert len(result) == 3
        priorities = [r.handler.priority for r in result]
        assert priorities == sorted(priorities), f"结果应按 priority 升序排列，实际：{priorities}"
        assert result[0].handler is hm_low
        assert result[1].handler is hm_mid
        assert result[2].handler is hm_high

    def test_no_handlers_empty_result(self) -> None:
        """CompositeHandlerMapping 中无任何已注册 handler 时，resolve() 返回空列表。"""
        cm = _build_composite()

        group_event = make_group_message_event(text="/echo hello")
        private_event = make_private_message_event(text="任意内容")
        notice_event = make_notice_event(notice_type="friend_add")

        assert cm.resolve(group_event) == []
        assert cm.resolve(private_event) == []
        assert cm.resolve(notice_event) == []

    def test_scope_all_works_in_both_group_and_private(self) -> None:
        """scope=all 的 handler 在群聊和私聊均命中。

        这是跨两种消息场景的联合验证。
        """
        cm = _build_composite()

        hm_all = _hm(
            mapping_type="keyword",
            message_scope="all",
            keywords={"通用"},
        )
        cm.register(hm_all)

        group_event = make_group_message_event(text="通用内容")
        private_event = make_private_message_event(text="通用内容")

        group_result = cm.resolve(group_event)
        private_result = cm.resolve(private_event)

        assert any(r.handler is hm_all for r in group_result), "scope=all 应在群聊命中"
        assert any(r.handler is hm_all for r in private_result), "scope=all 应在私聊命中"

    def test_mixed_scope_handlers_selective_routing(self) -> None:
        """同一文本，不同 scope 的 handler 各自选择性路由。

        注册三个关键词相同但 scope 不同的 handler：
        - hm_all：scope=all，群聊和私聊均命中
        - hm_group：scope=group，只在群聊命中
        - hm_private：scope=private，只在私聊命中

        验证 CompositeHandlerMapping 在两种消息类型下的选择性过滤正确。
        """
        cm = _build_composite()

        keyword = "你好"
        hm_all = _hm(mapping_type="keyword", message_scope="all", priority=10, keywords={keyword})
        hm_group = _hm(
            mapping_type="keyword", message_scope="group", priority=20, keywords={keyword}
        )
        hm_private = _hm(
            mapping_type="keyword", message_scope="private", priority=30, keywords={keyword}
        )
        cm.register(hm_all)
        cm.register(hm_group)
        cm.register(hm_private)

        group_result = cm.resolve(make_group_message_event(text=keyword))
        private_result = cm.resolve(make_private_message_event(text=keyword))

        group_handlers = [r.handler for r in group_result]
        private_handlers = [r.handler for r in private_result]

        # 群聊：all + group，不含 private
        assert hm_all in group_handlers
        assert hm_group in group_handlers
        assert hm_private not in group_handlers

        # 私聊：all + private，不含 group
        assert hm_all in private_handlers
        assert hm_private in private_handlers
        assert hm_group not in private_handlers

    def test_notice_event_scope_filter_not_applied(self) -> None:
        """scope 过滤逻辑仅对消息事件生效，通知事件不受 message_scope 字段影响。

        即使 event_type handler 的 metadata 中有 message_scope='group'，
        对于通知事件也不应被过滤掉。
        """
        cm = _build_composite()

        # 故意加一个 message_scope='group' 的通知 handler，验证不被过滤
        hm_notice = _hm(
            mapping_type="event_type",
            message_scope="group",  # 对通知事件无意义，不应触发过滤
            event_type="notice",
        )
        cm.register(hm_notice)

        notice_event = make_notice_event(notice_type="friend_add")
        result = cm.resolve(notice_event)

        assert any(r.handler is hm_notice for r in result), (
            "通知事件不受 message_scope 过滤影响，应正常命中"
        )

    def test_regex_match_object_carried_in_resolved_handler(self) -> None:
        """regex handler 命中时，ResolvedHandler 中携带正确的 regex_match 对象。

        这是集成验证：通过 CompositeHandlerMapping 路由的 regex handler
        的 match 结果应能正确提取捕获组。
        """
        cm = _build_composite()

        pattern = re.compile(r"点赞\s+(\d+)")
        hm_re = _hm(mapping_type="regex", compiled_pattern=pattern)
        cm.register(hm_re)

        event = make_group_message_event(text="点赞 12345")
        result = cm.resolve(event)

        assert len(result) == 1
        resolved = result[0]
        assert resolved.handler is hm_re
        assert resolved.regex_match is not None, "regex_match 不应为 None"
        assert resolved.regex_match.group(1) == "12345", (
            f"捕获组应为 '12345'，实际：{resolved.regex_match.group(1)}"
        )

    def test_command_and_event_type_independent_routing(self) -> None:
        """command 映射和 event_type 映射完全独立，互不干扰。

        发送消息事件只触发 command handler，发送通知事件只触发 event_type handler。
        """
        cm = _build_composite()

        hm_cmd = _hm(mapping_type="command", cmd="ping")
        hm_notice = _hm(mapping_type="event_type", event_type="notice")
        cm.register(hm_cmd)
        cm.register(hm_notice)

        # 消息事件：只有 command handler 可能命中（通知 handler 对消息事件 post_type 不匹配）
        msg_event = make_group_message_event(text="/ping")
        msg_result = cm.resolve(msg_event)
        msg_handlers = [r.handler for r in msg_result]
        assert hm_cmd in msg_handlers
        assert hm_notice not in msg_handlers

        # 通知事件：只有 event_type handler 命中
        notice_event = make_notice_event(notice_type="friend_add")
        notice_result = cm.resolve(notice_event)
        notice_handlers = [r.handler for r in notice_result]
        assert hm_notice in notice_handlers
        assert hm_cmd not in notice_handlers
