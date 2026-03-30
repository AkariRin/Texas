"""会话框架枚举类型。"""

from __future__ import annotations

from enum import StrEnum


class TimeoutMode(StrEnum):
    """会话超时策略。"""

    SILENT = "silent"
    NOTIFY = "notify"
    NEVER = "never"


class SessionScope(StrEnum):
    """会话隔离作用域。"""

    USER = "user"
    GROUP = "group"
