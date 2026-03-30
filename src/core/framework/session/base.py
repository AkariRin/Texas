"""InteractiveSession 基类 —— 会话实例的核心抽象。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, TypeVar, get_args

import structlog
from pydantic import BaseModel

from src.core.framework.session.decorators import EXIT_META, INPUT_META, STATE_META
from src.core.framework.session.state import State  # noqa: TC001

if TYPE_CHECKING:
    from src.core.framework.session.context import SessionContext
    from src.core.framework.session.manager import SessionManager
    from src.core.framework.session.state_machine import StateMachine

logger = structlog.get_logger()

TData = TypeVar("TData", bound=BaseModel)


class InteractiveSession(Generic[TData]):  # noqa: UP046
    """交互式会话基类。

    子类通过泛型参数指定会话数据模型::

        class FeedbackSession(InteractiveSession[FeedbackSessionData]):
            ...

    状态定义支持两种方式：
    1. 装饰器 DSL: 使用 @state / @on_input / @on_exit 装饰方法
    2. 配置式: 重写 build_states() 方法返回 State 列表
    """

    def __init__(self) -> None:
        self.data: Any = None  # 由 SessionManager 初始化为 TData 实例
        # 以下字段由 SessionManager.start_session() 在使用前赋值
        self.state_machine: StateMachine = None  # type: ignore[assignment]
        self.manager: SessionManager = None  # type: ignore[assignment]
        self.controller: Any = None
        self._session_key: str = ""

    # ── 生命周期钩子 ──

    async def on_start(self, ctx: SessionContext) -> None:
        """会话启动时调用，可用于初始化数据。"""

    async def on_finish(self, ctx: SessionContext) -> None:
        """会话正常结束时调用（到达 final 状态）。"""

    async def on_cancel(self, ctx: SessionContext) -> None:
        """用户取消会话时调用。"""

    async def on_timeout(self, ctx: SessionContext | None) -> None:
        """会话超时时调用，ctx 可能为 None（静默超时无法获取上下文）。"""

    async def on_error(self, ctx: SessionContext, exc: Exception) -> None:
        """会话处理异常时调用。"""

    # ── 动态状态机构建 ──

    async def build_states(self) -> list[State] | None:
        """子类可重写此方法动态构建状态。

        返回 None 则使用装饰器定义的状态。
        """
        return None

    # ── 内部工具方法 ──

    @classmethod
    def _resolve_data_cls(cls) -> type[BaseModel]:
        """解析泛型参数中的数据模型类。"""
        for base in getattr(cls, "__orig_bases__", ()):
            args = get_args(base)
            if args and isinstance(args[0], type) and issubclass(args[0], BaseModel):
                return args[0]
        raise TypeError(
            f"{cls.__name__} 必须指定泛型参数，"
            f"例如: class {cls.__name__}(InteractiveSession[MyData])"
        )

    @classmethod
    def _build_states_from_decorators(cls) -> tuple[list[State], str | None]:
        """从装饰器元数据构建状态列表。

        Returns:
            (状态列表, 初始状态名称)
        """
        state_defs: dict[str, dict[str, Any]] = {}
        input_handlers: dict[str, Any] = {}  # state_name → bound method
        exit_handlers: dict[str, Any] = {}
        initial_state: str | None = None

        # 扫描类方法上的装饰器元数据
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name, None)
            if attr is None or not callable(attr):
                continue

            # @state 装饰器
            smeta = getattr(attr, STATE_META, None)
            if smeta is not None:
                name = smeta["name"]
                state_defs[name] = {
                    "on_enter": attr,
                    "is_final": smeta.get("final", False),
                    "parent": smeta.get("parent"),
                }
                if smeta.get("initial", False):
                    if initial_state is not None:
                        raise ValueError(
                            f"会话 {cls.__name__} 定义了多个初始状态: '{initial_state}' 和 '{name}'"
                        )
                    initial_state = name

            # @on_input 装饰器
            imeta = getattr(attr, INPUT_META, None)
            if imeta is not None:
                input_handlers[imeta["state_name"]] = attr

            # @on_exit 装饰器
            emeta = getattr(attr, EXIT_META, None)
            if emeta is not None:
                exit_handlers[emeta["state_name"]] = attr

        if not state_defs:
            raise ValueError(f"会话 {cls.__name__} 未定义任何状态（使用 @state 装饰器）")

        if initial_state is None:
            # 默认取第一个定义的状态
            initial_state = next(iter(state_defs))

        # 组装 State 对象
        states: list[State] = []
        for name, sdef in state_defs.items():
            states.append(
                State(
                    name=name,
                    on_enter=sdef.get("on_enter"),
                    on_exit=exit_handlers.get(name),
                    on_input=input_handlers.get(name),
                    is_final=sdef.get("is_final", False),
                    parent=sdef.get("parent"),
                )
            )

        return states, initial_state
