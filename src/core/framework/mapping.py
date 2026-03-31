"""HandlerMapping —— 将事件路由到处理器方法。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from src.core.framework.decorators import Permission
from src.core.protocol.models.events import GroupMessageEvent, MessageEvent
from src.core.protocol.utils import extract_plaintext

if TYPE_CHECKING:
    import re
    from collections.abc import Callable

    from src.core.protocol.models.base import OneBotEvent


@dataclass
class HandlerMethod:
    """封装处理器方法及其元数据。"""

    controller: object
    method: Callable[..., Any]
    priority: int = 50
    permission: Permission = Permission.ANYONE
    metadata: dict[str, Any] = field(default_factory=dict)
    controller_name: str = ""
    method_name: str = ""


@dataclass
class ResolvedHandler:
    """resolve() 的结果单元 —— 包含 HandlerMethod 及本次匹配产生的上下文数据。

    之所以不把匹配结果写入 HandlerMethod（全局单例），是为了避免并发竞态：
    多个事件同时 resolve 同一正则 handler 时，写全局元数据会导致数据错乱。
    """

    handler: HandlerMethod
    regex_match: re.Match[str] | None = None


class HandlerMapping(ABC):
    """抽象处理器映射（类似 Spring HandlerMapping）。"""

    @abstractmethod
    def resolve(self, event: OneBotEvent) -> list[ResolvedHandler]: ...

    @abstractmethod
    def register(self, handler_method: HandlerMethod) -> None: ...


# ── 具体映射实现 ──


class CommandHandlerMapping(HandlerMapping):
    """通过命令前缀匹配消息文本（例如 /echo、/help）。"""

    def __init__(self, command_prefix: str = "/") -> None:
        self._prefix = command_prefix
        self._handlers: dict[str, list[HandlerMethod]] = {}  # 命令名 -> 处理器列表

    def register(self, handler_method: HandlerMethod) -> None:
        meta = handler_method.metadata
        cmd = meta.get("cmd", "")
        aliases: set[str] = meta.get("aliases", set())
        for name in {cmd} | aliases:
            # 剥离命令前缀，确保与 resolve() 的查找键一致
            key = name.removeprefix(self._prefix)
            self._handlers.setdefault(key, []).append(handler_method)

    def resolve(self, event: OneBotEvent) -> list[ResolvedHandler]:
        if not isinstance(event, MessageEvent):
            return []
        text = extract_plaintext(event)
        if not text.startswith(self._prefix):
            return []
        cmd_text = text[len(self._prefix) :]
        cmd_name = cmd_text.split()[0] if cmd_text else ""
        return [ResolvedHandler(handler=hm) for hm in self._handlers.get(cmd_name, [])]


class RegexHandlerMapping(HandlerMapping):
    """通过正则表达式匹配消息文本。"""

    def __init__(self) -> None:
        self._handlers: list[tuple[re.Pattern[str], HandlerMethod]] = []

    def register(self, handler_method: HandlerMethod) -> None:
        pattern = handler_method.metadata.get("compiled_pattern")
        if pattern:
            self._handlers.append((pattern, handler_method))

    def resolve(self, event: OneBotEvent) -> list[ResolvedHandler]:
        if not isinstance(event, MessageEvent):
            return []
        text = extract_plaintext(event)
        results: list[ResolvedHandler] = []
        for pattern, hm in self._handlers:
            match = pattern.search(text)
            if match:
                # 将匹配结果存入 ResolvedHandler（每次 resolve 独立创建），
                # 而非写入全局 HandlerMethod 元数据，避免并发竞态
                results.append(ResolvedHandler(handler=hm, regex_match=match))
        return results


class KeywordHandlerMapping(HandlerMapping):
    """匹配包含任意关键词的消息文本。"""

    def __init__(self) -> None:
        self._handlers: list[tuple[set[str], HandlerMethod]] = []

    def register(self, handler_method: HandlerMethod) -> None:
        keywords: set[str] = handler_method.metadata.get("keywords", set())
        if keywords:
            self._handlers.append((keywords, handler_method))

    def resolve(self, event: OneBotEvent) -> list[ResolvedHandler]:
        if not isinstance(event, MessageEvent):
            return []
        text = extract_plaintext(event)
        return [
            ResolvedHandler(handler=hm)
            for keywords, hm in self._handlers
            if any(kw in text for kw in keywords)
        ]


class StartsWithHandlerMapping(HandlerMapping):
    def __init__(self) -> None:
        self._handlers: list[tuple[str, HandlerMethod]] = []

    def register(self, handler_method: HandlerMethod) -> None:
        prefix = handler_method.metadata.get("prefix", "")
        if prefix:
            self._handlers.append((prefix, handler_method))

    def resolve(self, event: OneBotEvent) -> list[ResolvedHandler]:
        if not isinstance(event, MessageEvent):
            return []
        text = extract_plaintext(event)
        return [
            ResolvedHandler(handler=hm) for prefix, hm in self._handlers if text.startswith(prefix)
        ]


class EndsWithHandlerMapping(HandlerMapping):
    def __init__(self) -> None:
        self._handlers: list[tuple[str, HandlerMethod]] = []

    def register(self, handler_method: HandlerMethod) -> None:
        suffix = handler_method.metadata.get("suffix", "")
        if suffix:
            self._handlers.append((suffix, handler_method))

    def resolve(self, event: OneBotEvent) -> list[ResolvedHandler]:
        if not isinstance(event, MessageEvent):
            return []
        text = extract_plaintext(event)
        return [
            ResolvedHandler(handler=hm) for suffix, hm in self._handlers if text.endswith(suffix)
        ]


class FullMatchHandlerMapping(HandlerMapping):
    def __init__(self) -> None:
        self._handlers: dict[str, list[HandlerMethod]] = {}

    def register(self, handler_method: HandlerMethod) -> None:
        text = handler_method.metadata.get("text", "")
        if text:
            self._handlers.setdefault(text, []).append(handler_method)

    def resolve(self, event: OneBotEvent) -> list[ResolvedHandler]:
        if not isinstance(event, MessageEvent):
            return []
        text = extract_plaintext(event)
        return [ResolvedHandler(handler=hm) for hm in self._handlers.get(text, [])]


class EventTypeHandlerMapping(HandlerMapping):
    """按事件 post_type / notice_type / sub_type 匹配。"""

    def __init__(self) -> None:
        self._handlers: list[HandlerMethod] = []

    def register(self, handler_method: HandlerMethod) -> None:
        self._handlers.append(handler_method)

    def resolve(self, event: OneBotEvent) -> list[ResolvedHandler]:
        results: list[ResolvedHandler] = []
        for hm in self._handlers:
            meta = hm.metadata
            target_event_type = meta.get("event_type", "")

            if event.post_type != target_event_type:
                continue

            # 对于通知事件，可选择按 notice_type 和 sub_type 过滤
            target_notice_type = meta.get("notice_type")
            if target_notice_type is not None:
                actual_notice_type = getattr(event, "notice_type", None)
                if actual_notice_type != target_notice_type:
                    continue

            target_sub_type = meta.get("sub_type")
            if target_sub_type is not None:
                actual_sub_type = getattr(event, "sub_type", None)
                if actual_sub_type != target_sub_type:
                    continue

            # 对于请求事件，可选择按 request_type 过滤
            target_request_type = meta.get("request_type")
            if target_request_type is not None:
                actual_request_type = getattr(event, "request_type", None)
                if actual_request_type != target_request_type:
                    continue

            results.append(ResolvedHandler(handler=hm))
        return results


# ── 复合映射 ──

_MAPPING_TYPE_TO_CLASS: dict[str, type[HandlerMapping]] = {
    "command": CommandHandlerMapping,
    "regex": RegexHandlerMapping,
    "keyword": KeywordHandlerMapping,
    "startswith": StartsWithHandlerMapping,
    "endswith": EndsWithHandlerMapping,
    "fullmatch": FullMatchHandlerMapping,
    "event_type": EventTypeHandlerMapping,
}


class CompositeHandlerMapping(HandlerMapping):
    """聚合多个 HandlerMapping，合并结果并按优先级排序。"""

    def __init__(self, mappings: list[HandlerMapping] | None = None) -> None:
        self._mappings: list[HandlerMapping] = mappings or []
        # 同时维护一个类型 -> 映射的索引，用于注册
        self._type_index: dict[str, HandlerMapping] = {}
        for m in self._mappings:
            for mt, cls in _MAPPING_TYPE_TO_CLASS.items():
                if isinstance(m, cls):
                    self._type_index[mt] = m

    def add_mapping(self, mapping: HandlerMapping) -> None:
        self._mappings.append(mapping)
        for mt, cls in _MAPPING_TYPE_TO_CLASS.items():
            if isinstance(mapping, cls):
                self._type_index[mt] = mapping

    def register(self, handler_method: HandlerMethod) -> None:
        mapping_type = handler_method.metadata.get("mapping_type", "")
        target = self._type_index.get(mapping_type)
        if target:
            target.register(handler_method)

    def resolve(self, event: OneBotEvent) -> list[ResolvedHandler]:
        resolved: list[ResolvedHandler] = []
        for mapping in self._mappings:
            resolved.extend(mapping.resolve(event))

        # message_scope 过滤：仅对消息事件生效
        if isinstance(event, MessageEvent):
            is_group = isinstance(event, GroupMessageEvent)
            resolved = [
                r
                for r in resolved
                if (scope := r.handler.metadata.get("message_scope", "all")) == "all"
                or (scope == "group" and is_group)
                or (scope == "private" and not is_group)
            ]

        resolved.sort(key=lambda r: r.handler.priority)
        return resolved

    @property
    def registered_count(self) -> int:
        """所有映射中已注册的处理器方法总数。"""
        count = 0
        for m in self._mappings:
            if isinstance(m, CommandHandlerMapping):
                count += sum(len(v) for v in m._handlers.values())
            elif isinstance(
                m,
                (
                    RegexHandlerMapping,
                    KeywordHandlerMapping,
                    StartsWithHandlerMapping,
                    EndsWithHandlerMapping,
                ),
            ):
                count += len(m._handlers)
            elif isinstance(m, FullMatchHandlerMapping):
                count += sum(len(v) for v in m._handlers.values())
            elif isinstance(m, EventTypeHandlerMapping):
                count += len(m._handlers)
        return count
