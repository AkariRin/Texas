"""会话特殊命令常量 —— 全局取消与确认命令定义。"""

from __future__ import annotations

from typing import Final

# 全局取消命令集合，在所有会话中均生效
CANCEL_COMMANDS: Final[frozenset[str]] = frozenset(("/取消", "/cancel"))

# 全局确认命令集合，仅在等待确认状态时生效
CONFIRM_COMMANDS: Final[frozenset[str]] = frozenset(("/确认", "/confirm"))

# 确认等待状态名称前缀（框架内部保留，不应被会话自定义状态使用）
CONFIRM_STATE_PREFIX: Final[str] = "__confirm__"
