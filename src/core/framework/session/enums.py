"""会话框架枚举类型。"""

from __future__ import annotations

from enum import StrEnum


class TimeoutMode(StrEnum):
    """会话超时策略。"""

    silent = "silent"
    notify = "notify"
    never = "never"
