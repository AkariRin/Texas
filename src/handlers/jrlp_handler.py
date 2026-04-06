"""今日老婆 Bot 处理器 —— 响应群聊抽取指令。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import structlog

from src.core.framework.decorators import MessageScope, controller, on_fullmatch
from src.core.protocol.segment import MessageBuilder

if TYPE_CHECKING:
    from src.core.framework.context import Context
    from src.services.jrlp import JrlpService

logger = structlog.get_logger()

_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")

# QQ 头像 URL 模板（与前端保持一致）
_AVATAR_URL = "https://q1.qlogo.cn/g?b=qq&nk={qq}&s=100"


@controller(
    name="jrlp",
    display_name="今日老婆",
    description="每日群内随机抽取群老婆，每人每群每天一次",
    tags=["fun"],
    default_enabled=True,
)
class JrlpHandler:
    """今日老婆处理器。"""

    @on_fullmatch("jrlp", message_scope=MessageScope.group)
    @on_fullmatch("今日老婆", message_scope=MessageScope.group)
    @on_fullmatch("抽老婆", message_scope=MessageScope.group)
    @on_fullmatch("群老婆", message_scope=MessageScope.group)
    async def draw_wife(self, ctx: Context) -> bool:
        """随机抽取今日群老婆。"""
        from src.services.jrlp import JrlpService

        if not ctx.has_service(JrlpService) or ctx.group_id is None:
            return False

        jrlp_service: JrlpService = ctx.get_service(JrlpService)
        today = datetime.now(_SHANGHAI_TZ).date()

        try:
            record, is_new = await jrlp_service.get_or_draw(
                group_id=ctx.group_id,
                user_id=ctx.user_id,
                today=today,
            )
        except ValueError:
            await ctx.reply("该群暂无可抽取的成员，请等待群成员同步后重试")
            return True
        except Exception:
            logger.exception(
                "抽取今日老婆失败",
                group_id=ctx.group_id,
                user_id=ctx.user_id,
                event_type="jrlp.draw_error",
            )
            await ctx.reply("抽取失败，请稍后重试")
            return True

        avatar_url = _AVATAR_URL.format(qq=record.wife_qq)

        if is_new:
            text = f"你今天的群老婆是：{record.wife_name}({record.wife_qq})"
        else:
            text = f"你今天已经有群老婆{record.wife_name}({record.wife_qq})了，要好好对待她哦~"

        msg = MessageBuilder().at(ctx.user_id).image(avatar_url).text(f" {text}").build()
        await ctx.reply(msg)
        return True
