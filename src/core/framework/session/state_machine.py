"""状态机引擎 —— 管理状态图和转换逻辑。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from src.core.framework.session.commands import CONFIRM_COMMANDS, CONFIRM_STATE_PREFIX
from src.core.framework.session.state import State, Transition  # noqa: TC001

if TYPE_CHECKING:
    from collections.abc import Iterator

    from src.core.framework.session.context import SessionContext

logger = structlog.get_logger()


class StateMachineError(Exception):
    """状态机异常基类。"""


class InvalidTransitionError(StateMachineError):
    """无效的状态转换。"""


class StateMachine:
    """有限状态机引擎。

    支持条件转换、嵌套状态、并行状态和历史状态。
    """

    def __init__(self, states: list[State], initial_state: str | None = None) -> None:
        self._states: dict[str, State] = {}
        self._initial_state: str | None = initial_state
        self._current_state: str | None = None
        self._history: dict[str, str] = {}  # 父状态 → 最后激活的子状态
        self._state_stack: list[str] = []  # 状态路径栈（嵌套状态用）

        for s in states:
            self.add_state(s)

        # 自动检测初始状态
        if self._initial_state is None and self._states:
            # 取第一个状态作为初始状态
            self._initial_state = next(iter(self._states))

    @property
    def current_state(self) -> str | None:
        """当前状态名称。"""
        return self._current_state

    @property
    def initial_state(self) -> str | None:
        """初始状态名称。"""
        return self._initial_state

    @property
    def is_finished(self) -> bool:
        """状态机是否已到达终止状态。"""
        if self._current_state is None:
            return False
        state = self._states.get(self._current_state)
        return state is not None and state.is_final

    def add_state(self, state: State) -> None:
        """注册状态。"""
        self._states[state.name] = state

    def add_transition(self, from_state: str, transition: Transition) -> None:
        """为状态添加转换规则。"""
        state = self._states.get(from_state)
        if state is None:
            raise StateMachineError(f"状态 '{from_state}' 不存在")
        event_key = transition.event or f"_auto_{len(state.transitions)}"
        state.transitions[event_key] = transition

    def get_state(self, name: str) -> State | None:
        """按名称获取状态。"""
        return self._states.get(name)

    def iter_states(self) -> Iterator[State]:
        """遍历所有已注册的状态。"""
        return iter(self._states.values())

    async def start(self, ctx: SessionContext) -> None:
        """启动状态机，进入初始状态。"""
        if self._initial_state is None:
            raise StateMachineError("未设置初始状态")
        await self._enter_state(self._initial_state, ctx)

    async def process_input(self, ctx: SessionContext) -> str | None:
        """处理用户输入，返回新状态名称或 None（停留当前状态）。"""
        if self._current_state is None:
            raise StateMachineError("状态机未启动")

        state = self._states.get(self._current_state)
        if state is None:
            raise StateMachineError(f"当前状态 '{self._current_state}' 不存在")

        if state.is_final:
            return None

        # 优先使用 on_input 处理函数
        if state.on_input is not None:
            target = await state.on_input(ctx)
            if target is not None:
                await self.transition_to(target, ctx)
                return target
            return None

        # 然后尝试匹配转换规则
        user_input = ctx.input or ""
        for _event, transition in state.transitions.items():
            if transition.event is not None and transition.event != user_input:
                continue
            if transition.guard is not None and not await transition.guard(ctx):
                continue
            await self._execute_transition(transition, ctx)
            return transition.target

        return None

    async def transition_to(self, target: str, ctx: SessionContext) -> None:
        """显式转换到目标状态。"""
        # 目标为确认等待状态且尚未注入时，动态构建并注入该状态
        if target not in self._states and target.startswith(CONFIRM_STATE_PREFIX):
            self._inject_confirm_state(ctx)

        if target not in self._states:
            raise InvalidTransitionError(f"目标状态 '{target}' 不存在")

        if self._current_state is not None:
            await self._exit_state(self._current_state, ctx)

        await self._enter_state(target, ctx)

    def _inject_confirm_state(self, ctx: SessionContext) -> None:
        """动态注入确认等待状态。

        由 transition_to 在目标状态为确认状态时自动调用。
        通过 ctx.pop_confirm_config() 读取配置（取出后自动清空，防止重复注入）。
        """
        config = ctx.pop_confirm_config()
        if config is None:
            return

        state_name: str = config["state_name"]
        prompt: str = config["prompt"]
        on_confirm: str = config["on_confirm"]

        async def _on_enter(sctx: SessionContext) -> None:
            await sctx.reply(prompt)

        async def _on_input(sctx: SessionContext) -> str | None:
            text = (sctx.input or "").strip()
            if text in CONFIRM_COMMANDS:
                return on_confirm
            await sctx.reply("请发送 /确认 继续，或 /取消 放弃")
            return None

        self.add_state(State(name=state_name, on_enter=_on_enter, on_input=_on_input))

    async def _enter_state(self, state_name: str, ctx: SessionContext) -> None:
        """进入指定状态。"""
        state = self._states.get(state_name)
        if state is None:
            raise StateMachineError(f"状态 '{state_name}' 不存在")

        self._current_state = state_name
        ctx.current_state = state_name

        # 记录嵌套状态历史
        if state.parent is not None:
            self._history[state.parent] = state_name

        logger.debug(
            "进入状态",
            state=state_name,
            is_final=state.is_final,
            event_type="session.state_enter",
        )

        if state.on_enter is not None:
            await state.on_enter(ctx)

        if state.is_final:
            return

        if state.initial_substate is not None:
            await self._enter_state(state.initial_substate, ctx)

    async def _exit_state(self, state_name: str, ctx: SessionContext) -> None:
        """退出指定状态。"""
        state = self._states.get(state_name)
        if state is None:
            return

        logger.debug(
            "退出状态",
            state=state_name,
            event_type="session.state_exit",
        )

        if state.on_exit is not None:
            await state.on_exit(ctx)

    async def _execute_transition(self, transition: Transition, ctx: SessionContext) -> None:
        """执行状态转换。"""
        if self._current_state is not None:
            await self._exit_state(self._current_state, ctx)

        if transition.action is not None:
            await transition.action(ctx)

        await self._enter_state(transition.target, ctx)

    def serialize(self) -> dict[str, Any]:
        """序列化状态机状态（用于 Redis 持久化）。"""
        return {
            "current_state": self._current_state,
            "initial_state": self._initial_state,
            "history": dict(self._history),
            "state_stack": list(self._state_stack),
        }

    def deserialize(self, data: dict[str, Any]) -> None:
        """从序列化数据恢复状态机状态。"""
        self._current_state = data.get("current_state")
        self._initial_state = data.get("initial_state", self._initial_state)
        self._history = dict(data.get("history", {}))
        self._state_stack = list(data.get("state_stack", []))
