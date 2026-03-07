"""控制器与处理器注册装饰器（替代 Java 注解）。"""

from __future__ import annotations

import re
from enum import IntEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


class Permission(IntEnum):
    ANYONE = 0
    GROUP_MEMBER = 10
    GROUP_ADMIN = 20
    GROUP_OWNER = 30
    SUPERUSER = 100


# ── 存储在被装饰对象上的元数据键 ──

CONTROLLER_META = "__controller_meta__"
HANDLER_META = "__handler_meta__"


# ── 类装饰器 ──


def controller(
    name: str,
    description: str = "",
    version: str = "0.0.0",
    default_priority: int = 50,
) -> Callable[[type], type]:
    """将类标记为控制器（类似 Spring @Controller）。"""

    def decorator(cls: type) -> type:
        setattr(
            cls,
            CONTROLLER_META,
            {
                "name": name,
                "description": description,
                "version": version,
                "default_priority": default_priority,
            },
        )
        return cls

    return decorator


# ── 方法装饰器 ──


def _handler_decorator(
    mapping_type: str,
    priority: int | None = None,
    permission: Permission = Permission.ANYONE,
    **kwargs: Any,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """内部辅助函数，用于将处理器元数据附加到方法上。"""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        meta = {
            "mapping_type": mapping_type,
            "priority": priority,
            "permission": permission,
            **kwargs,
        }
        # 允许叠加多个装饰器
        existing: list[dict[str, Any]] = getattr(func, HANDLER_META, [])
        existing.append(meta)
        setattr(func, HANDLER_META, existing)
        return func

    return decorator


def on_command(
    cmd: str,
    aliases: set[str] | None = None,
    priority: int | None = None,
    permission: Permission = Permission.ANYONE,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """通过命令前缀匹配消息（例如 /echo）。"""
    return _handler_decorator(
        "command",
        priority=priority,
        permission=permission,
        cmd=cmd,
        aliases=aliases or set(),
    )


def on_regex(
    pattern: str,
    flags: int = 0,
    priority: int | None = None,
    permission: Permission = Permission.ANYONE,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """通过正则表达式匹配消息。"""
    compiled = re.compile(pattern, flags)
    return _handler_decorator(
        "regex",
        priority=priority,
        permission=permission,
        pattern=pattern,
        compiled_pattern=compiled,
    )


def on_keyword(
    keywords: set[str],
    priority: int | None = None,
    permission: Permission = Permission.ANYONE,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """匹配包含任意关键词的消息。"""
    return _handler_decorator(
        "keyword",
        priority=priority,
        permission=permission,
        keywords=keywords,
    )


def on_startswith(
    prefix: str,
    priority: int | None = None,
    permission: Permission = Permission.ANYONE,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """匹配以指定前缀开头的消息。"""
    return _handler_decorator(
        "startswith",
        priority=priority,
        permission=permission,
        prefix=prefix,
    )


def on_endswith(
    suffix: str,
    priority: int | None = None,
    permission: Permission = Permission.ANYONE,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """匹配以指定后缀结尾的消息。"""
    return _handler_decorator(
        "endswith",
        priority=priority,
        permission=permission,
        suffix=suffix,
    )


def on_fullmatch(
    text: str,
    priority: int | None = None,
    permission: Permission = Permission.ANYONE,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """完全匹配消息文本。"""
    return _handler_decorator(
        "fullmatch",
        priority=priority,
        permission=permission,
        text=text,
    )


def on_event(
    event_type: str,
    priority: int | None = None,
    permission: Permission = Permission.ANYONE,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """按事件 post_type 匹配。"""
    return _handler_decorator(
        "event_type",
        priority=priority,
        permission=permission,
        event_type=event_type,
    )


def on_notice(
    notice_type: str | None = None,
    sub_type: str | None = None,
    priority: int | None = None,
    permission: Permission = Permission.ANYONE,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """匹配通知事件。"""
    return _handler_decorator(
        "event_type",
        priority=priority,
        permission=permission,
        event_type="notice",
        notice_type=notice_type,
        sub_type=sub_type,
    )


def on_request(
    request_type: str | None = None,
    priority: int | None = None,
    permission: Permission = Permission.ANYONE,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """匹配请求事件。"""
    return _handler_decorator(
        "event_type",
        priority=priority,
        permission=permission,
        event_type="request",
        request_type=request_type,
    )


def on_message_sent(
    priority: int | None = None,
    permission: Permission = Permission.ANYONE,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """匹配 message_sent 事件（NapCat 扩展）。"""
    return _handler_decorator(
        "event_type",
        priority=priority,
        permission=permission,
        event_type="message_sent",
    )


def on_poke(
    priority: int | None = None,
    permission: Permission = Permission.ANYONE,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """匹配戳一戳通知事件。"""
    return _handler_decorator(
        "event_type",
        priority=priority,
        permission=permission,
        event_type="notice",
        notice_type="notify",
        sub_type="poke",
    )


def on_essence(
    sub_type: str | None = None,
    priority: int | None = None,
    permission: Permission = Permission.ANYONE,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """匹配精华消息通知事件。"""
    return _handler_decorator(
        "event_type",
        priority=priority,
        permission=permission,
        event_type="notice",
        notice_type="essence",
        sub_type=sub_type,
    )


def on_bot_offline(
    priority: int | None = None,
    permission: Permission = Permission.ANYONE,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """匹配 bot_offline 通知事件。"""
    return _handler_decorator(
        "event_type",
        priority=priority,
        permission=permission,
        event_type="notice",
        notice_type="bot_offline",
    )
