"""会话框架枚举类型。"""

from __future__ import annotations

from enum import StrEnum


class TimeoutMode(StrEnum):
    """会话超时策略。"""

    silent = "silent"
    notify = "notify"
    never = "never"


class SessionScope(StrEnum):
    """会话隔离作用域。

    .. deprecated::
        ``scope`` 参数已废弃。会话互斥现统一采用 user+source 粒度，
        即同一用户在同一群/私聊只能有一个活跃会话，与 scope 值无关。
        保留此枚举仅为向后兼容，未来版本将移除。
    """

    user = "user"
    group = "group"
