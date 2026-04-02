"""会话上下文 —— 封装会话内的交互信息。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from src.core.framework.session.commands import CONFIRM_STATE_PREFIX

if TYPE_CHECKING:
    from src.core.framework.context import Context
    from src.core.framework.session.base import InteractiveSession
    from src.core.protocol.models.base import MessageSegment

_T = TypeVar("_T")


class SessionContext:
    """会话上下文 —— 代理原始 Context 并提供会话专属方法。

    每次会话内消息到达时创建一个新的 SessionContext，
    包含原始事件上下文和当前会话的状态信息。
    """

    def __init__(
        self,
        ctx: Context,
        session: InteractiveSession[Any],
        current_state: str,
        user_input: str | None,
    ) -> None:
        self._ctx = ctx
        self.session = session
        self.current_state = current_state
        self.input = user_input

    # ── 会话数据快捷访问 ──

    @property
    def data(self) -> Any:
        """会话数据访问，运行时类型由 InteractiveSession 泛型参数决定。

        由于 Python 泛型限制，静态类型标注为 Any。
        业务处理方法中如需类型推断，可在方法签名处使用 cast：

        .. code-block:: python

            from typing import cast

            @on_input("some_state")
            async def handle(self, ctx: SessionContext) -> str | None:
                data = cast(MySessionData, ctx.data)
                ...
        """
        return self.session.data

    # ── 代理 Context 属性 ──

    @property
    def user_id(self) -> int:
        return self._ctx.user_id

    @property
    def group_id(self) -> int | None:
        return self._ctx.group_id

    @property
    def is_group(self) -> bool:
        return self._ctx.is_group

    @property
    def message_id(self) -> int:
        return self._ctx.message_id

    @property
    def event(self) -> Any:
        """原始事件对象。"""
        return self._ctx.event

    @property
    def bot(self) -> Any:
        """Bot API 实例。"""
        return self._ctx.bot

    @property
    def original_context(self) -> Context:
        """获取原始事件上下文（需要访问完整 Context API 时使用）。"""
        return self._ctx

    # ── 代理 Context 方法 ──

    async def reply(self, message: str | list[MessageSegment]) -> None:
        """向当前会话发送回复。

        群聊时自动在消息头部插入 @创建者（session._creator_user_id），
        以区分同一群内多个用户的并发会话。注意：始终 @ 会话创建者，
        而非当前消息的发送者（二者在一般情况下相同，但特殊流程中可能不同）。
        """
        from src.core.protocol.segment import Seg

        if isinstance(message, str):
            message = [Seg.text(message)]
        if self.is_group:
            message = [Seg.at(self.session._creator_user_id), Seg.text(" "), *message]
        await self._ctx.reply(message)

    async def send(self, message: str | list[MessageSegment]) -> None:
        """reply 的别名（含 @创建者 行为一致）。"""
        await self.reply(message)

    def get_service(self, service_type: type[_T]) -> _T:
        """从上下文获取服务实例（类型安全）。"""
        return self._ctx.get_service(service_type)

    def has_service(self, service_type: type) -> bool:
        """检查服务是否已注册。"""
        return self._ctx.has_service(service_type)

    def get_plaintext(self) -> str:
        """获取消息纯文本。"""
        return self._ctx.get_plaintext()

    def pop_confirm_config(self) -> dict[str, Any] | None:
        """取出并清空待注入的确认状态配置（供框架内部使用）。

        Returns:
            确认配置字典，若未设置则返回 None。
        """
        config = self.session._confirm_config
        self.session._confirm_config = None
        return config

    def confirm_transition(self, prompt: str, on_confirm: str) -> str:
        """请求用户二次确认后再转换到目标状态。

        在 on_input 处理方法中调用并直接返回其结果，框架会自动注入
        确认等待状态，向用户展示提示并等待 /确认 或 /取消 输入。

        Args:
            prompt: 展示给用户的确认提示文本（通常包含操作摘要）。
            on_confirm: 用户发送 /确认 后转换到的目标状态名。

        Returns:
            内部确认状态名，可直接作为 on_input 方法的返回值使用。

        示例::

            @on_input("input_content")
            async def process_content(self, ctx: SessionContext) -> str | None:
                ctx.data.content = ctx.input
                return ctx.confirm_transition(
                    prompt=f"确认提交？内容：{ctx.data.content}\\n发送 /确认 继续，/取消 放弃",
                    on_confirm="submit",
                )
        """
        confirm_state_name = f"{CONFIRM_STATE_PREFIX}_{on_confirm}"
        self.session._confirm_config = {
            "prompt": prompt,
            "on_confirm": on_confirm,
            "state_name": confirm_state_name,
        }
        return confirm_state_name
