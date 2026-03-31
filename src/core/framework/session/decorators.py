"""会话装饰器 —— 标记会话类和状态处理方法。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.core.framework.session.enums import SessionScope, TimeoutMode
from src.core.framework.session.timeout import TimeoutConfig

if TYPE_CHECKING:
    from collections.abc import Callable

# ── 元数据键 ──

SESSION_META = "__session_meta__"
STATE_META = "__state_meta__"
INPUT_META = "__input_meta__"
EXIT_META = "__exit_meta__"


def interactive_session(
    cancel_commands: tuple[str, ...] = ("/取消", "/cancel"),
    timeout: TimeoutConfig | int = 300,
    scope: SessionScope = SessionScope.user,
    display_name: str = "",
    description: str = "",
    **kwargs: Any,
) -> Callable[[type], type]:
    """标记内部类为交互式会话。

    Args:
        cancel_commands: 取消会话的命令列表。
        timeout: 超时配置，传入 int 时自动构造 TimeoutConfig。
        scope: 会话隔离作用域。
        display_name: 展示名称。
        description: 功能描述。
    """
    if isinstance(timeout, int):
        timeout = TimeoutConfig(duration=timeout, mode=TimeoutMode.silent)

    def decorator(cls: type) -> type:
        setattr(
            cls,
            SESSION_META,
            {
                "cancel_commands": cancel_commands,
                "timeout": timeout,
                "scope": scope,
                "display_name": display_name,
                "description": description,
                **kwargs,
            },
        )
        return cls

    return decorator


def state(
    name: str,
    *,
    initial: bool = False,
    final: bool = False,
    parent: str | None = None,
    display_name: str = "",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """标记方法为状态入口（on_enter），进入该状态时自动调用。

    Args:
        name: 状态名称。
        initial: 是否为初始状态。
        final: 是否为终止状态。
        parent: 父状态名称（嵌套状态）。
        display_name: 展示名称。
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        setattr(
            func,
            STATE_META,
            {
                "name": name,
                "initial": initial,
                "final": final,
                "parent": parent,
                "display_name": display_name,
            },
        )
        return func

    return decorator


def on_input(
    state_name: str,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """标记方法为状态输入处理器。

    用户在该状态下发送消息时调用此方法。
    方法应返回目标状态名（触发转换）或 None（停留当前状态）。

    Args:
        state_name: 关联的状态名称。
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        setattr(func, INPUT_META, {"state_name": state_name})
        return func

    return decorator


def on_exit(
    state_name: str,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """标记方法为状态退出回调。

    离开该状态时自动调用。

    Args:
        state_name: 关联的状态名称。
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        setattr(func, EXIT_META, {"state_name": state_name})
        return func

    return decorator
