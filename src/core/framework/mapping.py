"""HandlerMapping —— 将事件路由到处理器方法。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from src.core.framework.decorators import Permission
from src.core.protocol.models.events import (
    MessageEvent,
)

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


class HandlerMapping(ABC):
    """抽象处理器映射（类似 Spring HandlerMapping）。"""

    @abstractmethod
    def resolve(self, event: OneBotEvent) -> list[HandlerMethod]: ...

    @abstractmethod
    def register(self, handler_method: HandlerMethod) -> None: ...


def _get_plaintext(event: OneBotEvent) -> str:
    """从消息事件中提取纯文本。"""
    if not isinstance(event, MessageEvent):
        return ""
    msg = event.message
    if isinstance(msg, str):
        return msg
    parts: list[str] = []
    for seg in msg:
        if seg.type == "text":
            parts.append(str(seg.data.get("text", "")))
    return "".join(parts).strip()


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
            self._handlers.setdefault(name, []).append(handler_method)

    def resolve(self, event: OneBotEvent) -> list[HandlerMethod]:
        if not isinstance(event, MessageEvent):
            return []
        text = _get_plaintext(event)
        if not text.startswith(self._prefix):
            return []
        cmd_text = text[len(self._prefix) :]
        cmd_name = cmd_text.split()[0] if cmd_text else ""
        return list(self._handlers.get(cmd_name, []))


class RegexHandlerMapping(HandlerMapping):
    """通过正则表达式匹配消息文本。"""

    def __init__(self) -> None:
        self._handlers: list[tuple[re.Pattern[str], HandlerMethod]] = []

    def register(self, handler_method: HandlerMethod) -> None:
        pattern = handler_method.metadata.get("compiled_pattern")
        if pattern:
            self._handlers.append((pattern, handler_method))

    def resolve(self, event: OneBotEvent) -> list[HandlerMethod]:
        if not isinstance(event, MessageEvent):
            return []
        text = _get_plaintext(event)
        results: list[HandlerMethod] = []
        for pattern, hm in self._handlers:
            match = pattern.search(text)
            if match:
                # 将匹配结果存入元数据，供 ctx.get_regex_match() 使用
                hm.metadata["_last_match"] = match
                results.append(hm)
        return results


class KeywordHandlerMapping(HandlerMapping):
    """匹配包含任意关键词的消息文本。"""

    def __init__(self) -> None:
        self._handlers: list[tuple[set[str], HandlerMethod]] = []

    def register(self, handler_method: HandlerMethod) -> None:
        keywords: set[str] = handler_method.metadata.get("keywords", set())
        if keywords:
            self._handlers.append((keywords, handler_method))

    def resolve(self, event: OneBotEvent) -> list[HandlerMethod]:
        if not isinstance(event, MessageEvent):
            return []
        text = _get_plaintext(event)
        results: list[HandlerMethod] = []
        for keywords, hm in self._handlers:
            if any(kw in text for kw in keywords):
                results.append(hm)
        return results


class StartsWithHandlerMapping(HandlerMapping):
    def __init__(self) -> None:
        self._handlers: list[tuple[str, HandlerMethod]] = []

    def register(self, handler_method: HandlerMethod) -> None:
        prefix = handler_method.metadata.get("prefix", "")
        if prefix:
            self._handlers.append((prefix, handler_method))

    def resolve(self, event: OneBotEvent) -> list[HandlerMethod]:
        if not isinstance(event, MessageEvent):
            return []
        text = _get_plaintext(event)
        return [hm for prefix, hm in self._handlers if text.startswith(prefix)]


class EndsWithHandlerMapping(HandlerMapping):
    def __init__(self) -> None:
        self._handlers: list[tuple[str, HandlerMethod]] = []

    def register(self, handler_method: HandlerMethod) -> None:
        suffix = handler_method.metadata.get("suffix", "")
        if suffix:
            self._handlers.append((suffix, handler_method))

    def resolve(self, event: OneBotEvent) -> list[HandlerMethod]:
        if not isinstance(event, MessageEvent):
            return []
        text = _get_plaintext(event)
        return [hm for suffix, hm in self._handlers if text.endswith(suffix)]


class FullMatchHandlerMapping(HandlerMapping):
    def __init__(self) -> None:
        self._handlers: dict[str, list[HandlerMethod]] = {}

    def register(self, handler_method: HandlerMethod) -> None:
        text = handler_method.metadata.get("text", "")
        if text:
            self._handlers.setdefault(text, []).append(handler_method)

    def resolve(self, event: OneBotEvent) -> list[HandlerMethod]:
        if not isinstance(event, MessageEvent):
            return []
        text = _get_plaintext(event)
        return list(self._handlers.get(text, []))


class EventTypeHandlerMapping(HandlerMapping):
    """按事件 post_type / notice_type / sub_type 匹配。"""

    def __init__(self) -> None:
        self._handlers: list[HandlerMethod] = []

    def register(self, handler_method: HandlerMethod) -> None:
        self._handlers.append(handler_method)

    def resolve(self, event: OneBotEvent) -> list[HandlerMethod]:
        results: list[HandlerMethod] = []
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

            results.append(hm)
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

    def resolve(self, event: OneBotEvent) -> list[HandlerMethod]:
        handlers: list[HandlerMethod] = []
        for mapping in self._mappings:
            handlers.extend(mapping.resolve(event))
        handlers.sort(key=lambda h: h.priority)
        return handlers

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
