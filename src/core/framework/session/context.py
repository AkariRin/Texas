"""会话上下文 —— 封装会话内的交互信息。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

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
        """类型安全的会话数据访问（由 InteractiveSession 泛型参数决定类型）。"""
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
        """向当前会话发送回复。"""
        await self._ctx.reply(message)

    async def send(self, message: str | list[MessageSegment]) -> None:
        """reply 的别名。"""
        await self._ctx.send(message)

    def get_service(self, service_type: type[_T]) -> _T:
        """从上下文获取服务实例（类型安全）。"""
        return self._ctx.get_service(service_type)

    def has_service(self, service_type: type) -> bool:
        """检查服务是否已注册。"""
        return self._ctx.has_service(service_type)

    def get_plaintext(self) -> str:
        """获取消息纯文本。"""
        return self._ctx.get_plaintext()
