"""交互式会话框架 —— 基于状态机的多轮对话抽象层。"""

from __future__ import annotations

from src.core.framework.session.base import InteractiveSession
from src.core.framework.session.commands import CANCEL_COMMANDS, CONFIRM_COMMANDS
from src.core.framework.session.context import SessionContext
from src.core.framework.session.decorators import (
    SESSION_META,
    interactive_session,
    on_exit,
    on_input,
    state,
)
from src.core.framework.session.enums import SessionScope, TimeoutMode
from src.core.framework.session.manager import SessionManager
from src.core.framework.session.state import State, Transition
from src.core.framework.session.state_machine import StateMachine
from src.core.framework.session.timeout import TimeoutConfig

__all__ = [
    "CANCEL_COMMANDS",
    "CONFIRM_COMMANDS",
    "SESSION_META",
    "InteractiveSession",
    "SessionContext",
    "SessionManager",
    "SessionScope",
    "State",
    "StateMachine",
    "TimeoutConfig",
    "TimeoutMode",
    "Transition",
    "interactive_session",
    "on_exit",
    "on_input",
    "state",
]
