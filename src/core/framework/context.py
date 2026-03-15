"""事件上下文 —— 封装事件、Bot API 及便捷方法。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from src.core.protocol.models.events import GroupMessageEvent, MessageEvent
from src.core.protocol.segment import Seg

if TYPE_CHECKING:
    import re

    from src.core.protocol.api import BotAPI
    from src.core.protocol.models.base import MessageSegment, OneBotEvent

_T = TypeVar("_T")


class FinishError(Exception):
    """由 ctx.finish() 抛出，用于中止后续处理器的执行。"""


class Context:
    """事件处理上下文 —— 传递给拦截器和处理器。"""

    def __init__(
        self,
        event: OneBotEvent,
        bot: BotAPI,
        services: dict[type, Any] | None = None,
    ) -> None:
        self.event = event
        self.bot = bot
        self.handler_method: Any = None  # 在调用处理器前由调度器设置
        self._attributes: dict[str, Any] = {}
        self._regex_match: re.Match[str] | None = None
        self._services: dict[type, Any] = services or {}

    # ── 服务注册表（Handler DI） ──

    def get_service(self, service_type: type[_T]) -> _T:
        """从上下文获取服务实例（类型安全）。

        用法::

            personnel = ctx.get_service(PersonnelService)
        """
        service = self._services.get(service_type)
        if service is None:
            raise RuntimeError(
                f"Service {service_type.__name__} not registered in context. "
                f"Available: {[t.__name__ for t in self._services]}"
            )
        return service  # type: ignore[no-any-return]

    def has_service(self, service_type: type) -> bool:
        """检查服务是否已注册。"""
        return service_type in self._services

    # ── 属性存储（拦截器 <-> 处理器数据传递） ──

    def set_attribute(self, key: str, value: Any) -> None:
        self._attributes[key] = value

    def get_attribute(self, key: str, default: Any = None) -> Any:
        return self._attributes.get(key, default)

    # ── 正则匹配（由调度器在 @on_regex 时设置） ──

    def set_regex_match(self, match: re.Match[str]) -> None:
        self._regex_match = match

    def get_regex_match(self) -> re.Match[str] | None:
        return self._regex_match

    # ── 消息辅助方法 ──

    def get_plaintext(self) -> str:
        """从消息中提取纯文本。"""
        if not isinstance(self.event, MessageEvent):
            return ""
        msg = self.event.message
        if isinstance(msg, str):
            return msg
        parts: list[str] = []
        for seg in msg:
            if seg.type == "text":
                parts.append(str(seg.data.get("text", "")))
        return "".join(parts).strip()

    def get_args(self) -> list[str]:
        """提取命令参数（命令名之后的文本）。"""
        text = self.get_plaintext()
        parts = text.split(maxsplit=1)
        if len(parts) <= 1:
            return []
        return parts[1].split()

    def get_arg_str(self) -> str:
        """以单个字符串形式获取命令名之后的所有内容。"""
        text = self.get_plaintext()
        parts = text.split(maxsplit=1)
        return parts[1] if len(parts) > 1 else ""

    # ── 回复 / 发送快捷方法 ──

    async def reply(self, message: str | list[MessageSegment]) -> None:
        """向当前会话发送回复。"""
        if isinstance(message, str):
            message = [Seg.text(message)]
        if isinstance(self.event, GroupMessageEvent):
            await self.bot.send_group_msg(self.event.group_id, message)
        elif isinstance(self.event, MessageEvent):
            await self.bot.send_private_msg(self.event.user_id, message)

    async def send(self, message: str | list[MessageSegment]) -> None:
        """reply 的别名。"""
        await self.reply(message)

    async def finish(self, message: str | list[MessageSegment] | None = None) -> None:
        """发送消息并中止后续处理器的执行。"""
        if message is not None:
            await self.reply(message)
        raise FinishError()

    async def recall(self) -> None:
        """撤回当前消息。"""
        if isinstance(self.event, MessageEvent):
            await self.bot.delete_msg(self.event.message_id)

    # ── 便捷属性 ──

    @property
    def user_id(self) -> int:
        return getattr(self.event, "user_id", 0)

    @property
    def group_id(self) -> int | None:
        return getattr(self.event, "group_id", None)

    @property
    def message_id(self) -> int:
        return getattr(self.event, "message_id", 0)

    @property
    def is_group(self) -> bool:
        return isinstance(self.event, GroupMessageEvent)
