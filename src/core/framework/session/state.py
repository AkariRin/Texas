"""状态与转换定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from src.core.framework.session.context import SessionContext


@dataclass
class Transition:
    """状态转换。

    Attributes:
        target: 目标状态名称。
        guard: 转换守卫条件，返回 False 则不执行转换。
        action: 转换过程中执行的动作。
        event: 触发事件名称（配置式定义使用）。
    """

    target: str
    guard: Callable[[SessionContext], Awaitable[bool]] | None = None
    action: Callable[[SessionContext], Awaitable[None]] | None = None
    event: str | None = None


@dataclass
class State:
    """状态定义。

    Attributes:
        name: 状态名称。
        on_enter: 进入状态时的回调。
        on_exit: 退出状态时的回调。
        on_input: 接收用户输入的处理函数，返回目标状态名或 None（停留）。
        transitions: 按事件名索引的转换字典（配置式定义使用）。
        parent: 父状态名称（嵌套状态）。
        initial_substate: 默认子状态（嵌套状态）。
        is_final: 是否为终止状态。
        metadata: 自定义元数据。
    """

    name: str
    on_enter: Callable[[SessionContext], Awaitable[None]] | None = None
    on_exit: Callable[[SessionContext], Awaitable[None]] | None = None
    on_input: Callable[[SessionContext], Awaitable[str | None]] | None = None
    transitions: dict[str, Transition] = field(default_factory=dict)
    parent: str | None = None
    initial_substate: str | None = None
    is_final: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
