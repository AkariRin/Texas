"""漂流瓶 Bot 处理器 —— 响应「扔漂流瓶」和「捞漂流瓶」关键词。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

import structlog

from src.core.framework.decorators import (
    MessageScope,
    Permission,
    controller,
    on_fullmatch,
    on_startswith,
)
from src.core.protocol.models.base import MessageSegment
from src.core.protocol.models.events import MessageEvent
from src.core.protocol.segment import MessageBuilder

if TYPE_CHECKING:
    from src.core.framework.context import Context
    from src.services.drift_bottle import DriftBottleService

logger = structlog.get_logger()

_TRIGGER_THROW: Final = "扔漂流瓶"
_TRIGGER_PICK: Final = "捞漂流瓶"


def _filter_content(segments: list[Any] | str, trigger: str) -> list[dict[str, Any]]:
    """过滤消息段，保留 text（去除触发词）和 image，其他类型丢弃。"""
    if isinstance(segments, str):
        text = segments.removeprefix(trigger).strip()
        return [{"type": "text", "data": {"text": text}}] if text else []

    result: list[dict[str, Any]] = []
    for seg in segments:
        if seg.type == "image":
            result.append({"type": "image", "data": dict(seg.data)})
        elif seg.type == "text":
            text = str(seg.data.get("text", ""))
            # 仅第一个 text 段可能包含触发词前缀
            if not result and text.startswith(trigger):
                text = text[len(trigger) :].strip()
            if text:
                result.append({"type": "text", "data": {"text": text}})
    return result


@controller(
    name="drift_bottle",
    display_name="漂流瓶",
    description="扔/捞漂流瓶，同池内随机互通，每瓶一次性消耗",
    tags=["fun"],
    default_enabled=True,
)
class DriftBottleHandler:
    """漂流瓶处理器。"""

    @on_startswith(
        _TRIGGER_THROW,
        permission=Permission.ANYONE,
        message_scope=MessageScope.group,
        display_name="扔漂流瓶",
        description="消息以「扔漂流瓶」开头时触发，内容包含文字或图片",
    )
    async def handle_throw(self, ctx: Context) -> bool:
        """处理扔漂流瓶请求。"""
        from src.services.drift_bottle import DriftBottleService

        if not ctx.has_service(DriftBottleService) or ctx.group_id is None:
            return False

        svc: DriftBottleService = ctx.get_service(DriftBottleService)

        if not isinstance(ctx.event, MessageEvent):
            return False
        content = _filter_content(ctx.event.message, _TRIGGER_THROW)
        if not content:
            await ctx.reply("漂流瓶里什么都没有哦~")
            return True

        try:
            pool_id = await svc.get_pool_id(ctx.group_id)
            await svc.throw_bottle(
                pool_id=pool_id,
                sender_id=ctx.user_id,
                sender_group_id=ctx.group_id,
                content=content,
            )
        except Exception:
            logger.exception(
                "扔漂流瓶失败",
                group_id=ctx.group_id,
                user_id=ctx.user_id,
                event_type="drift_bottle.throw_error",
            )
            await ctx.reply("扔漂流瓶失败，请稍后重试")
            return True

        msg = MessageBuilder().at(ctx.user_id).text(" 漂流瓶已扔出，不知道会漂到哪里~").build()
        await ctx.reply(msg)
        return True

    @on_fullmatch(
        _TRIGGER_PICK,
        permission=Permission.ANYONE,
        message_scope=MessageScope.group,
        display_name="捞漂流瓶",
        description="发送「捞漂流瓶」时随机捞取同池内一个瓶",
    )
    async def handle_pick(self, ctx: Context) -> bool:
        """处理捞漂流瓶请求。"""
        from src.services.drift_bottle import DriftBottleService

        if not ctx.has_service(DriftBottleService) or ctx.group_id is None:
            return False

        svc: DriftBottleService = ctx.get_service(DriftBottleService)

        try:
            pool_id = await svc.get_pool_id(ctx.group_id)
            bottle = await svc.pick_bottle(pool_id=pool_id, user_id=ctx.user_id)
        except Exception:
            logger.exception(
                "捞漂流瓶失败",
                group_id=ctx.group_id,
                user_id=ctx.user_id,
                event_type="drift_bottle.pick_error",
            )
            await ctx.reply("捞漂流瓶失败，请稍后重试")
            return True

        if bottle is None:
            await ctx.reply("池子里暂时没有漂流瓶，快去扔一个吧~")
            return True

        # 将 content 组装为 Bot 消息段
        reply_segs = [MessageSegment(type="text", data={"text": "捞到了一个漂流瓶：\n"})]
        for seg in bottle.content:
            reply_segs.append(MessageSegment(type=seg["type"], data=seg["data"]))

        await ctx.reply(reply_segs)
        return True
