"""全局测试 fixtures —— 事件工厂函数、BotAPI mock、Context 工厂。"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# ── OneBot 事件工厂函数（普通函数，非 fixture，可在模块顶层直接调用）──────────


def make_group_message_event(
    user_id: int = 10001,
    group_id: int = 100,
    text: str = "",
    role: str = "member",
) -> Any:
    """构造群聊消息事件（GroupMessageEvent）。"""
    from src.core.protocol.models.events import GroupMessageEvent

    raw: dict[str, Any] = {
        "post_type": "message",
        "message_type": "group",
        "sub_type": "normal",
        "message_id": 1,
        "user_id": user_id,
        "group_id": group_id,
        "message": [{"type": "text", "data": {"text": text}}],
        "raw_message": text,
        "sender": {
            "user_id": user_id,
            "nickname": "TestUser",
            "role": role,
        },
        "time": 1700000000,
        "self_id": 88888,
    }
    return GroupMessageEvent.model_validate(raw)


def make_private_message_event(
    user_id: int = 10001,
    text: str = "",
) -> Any:
    """构造私聊消息事件（PrivateMessageEvent）。"""
    from src.core.protocol.models.events import PrivateMessageEvent

    raw: dict[str, Any] = {
        "post_type": "message",
        "message_type": "private",
        "sub_type": "friend",
        "message_id": 2,
        "user_id": user_id,
        "message": [{"type": "text", "data": {"text": text}}],
        "raw_message": text,
        "sender": {
            "user_id": user_id,
            "nickname": "TestUser",
        },
        "time": 1700000000,
        "self_id": 88888,
    }
    return PrivateMessageEvent.model_validate(raw)


def make_notice_event(
    notice_type: str,
    sub_type: str | None = None,
    user_id: int = 10001,
    group_id: int | None = None,
) -> Any:
    """构造通知事件（NoticeEvent）。"""
    from src.core.protocol.models.events import NoticeEvent

    raw: dict[str, Any] = {
        "post_type": "notice",
        "notice_type": notice_type,
        "user_id": user_id,
        "time": 1700000000,
        "self_id": 88888,
    }
    if sub_type is not None:
        raw["sub_type"] = sub_type
    if group_id is not None:
        raw["group_id"] = group_id
    return NoticeEvent.model_validate(raw)


# ── Context 工厂（带 reply Mock）────────────────────────────────────────────


def make_context(
    event: Any,
    services: dict[type, Any] | None = None,
) -> Any:
    """创建 Context 对象，reply/send/finish 均预置为 AsyncMock。

    Handler 测试断言应针对 ctx.reply，而非底层 bot.send_group_msg，
    因为 handler 只调用 ctx.reply()，不直接操作 BotAPI。

    ctx.finish 会抛出 FinishError（与真实行为一致），调用方需 try/except 捕获。
    """
    from src.core.framework.context import Context, FinishError

    bot = MagicMock()
    bot.send_group_msg = AsyncMock(return_value={"message_id": 999})
    bot.send_private_msg = AsyncMock(return_value={"message_id": 998})

    ctx = Context(event=event, bot=bot, services=services or {})
    # 覆盖 reply/send 为 AsyncMock，捕获 handler 的输出
    ctx.reply = AsyncMock()
    ctx.send = ctx.reply

    # finish 保持语义：发完消息后抛出 FinishError 中止执行
    async def _finish(message: Any = None) -> None:  # noqa: ANN401
        if message is not None:
            await ctx.reply(message)
        raise FinishError()

    ctx.finish = _finish  # type: ignore[method-assign]
    return ctx


# ── pytest fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def group_event_factory():
    """返回 make_group_message_event 工厂函数。"""
    return make_group_message_event


@pytest.fixture
def private_event_factory():
    """返回 make_private_message_event 工厂函数。"""
    return make_private_message_event
