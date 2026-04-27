"""用户群签到 Bot 处理器 —— 响应「签到」关键词或「/签到」命令。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import structlog

from src.core.framework.decorators import (
    MessageScope,
    Permission,
    controller,
    on_command,
    on_keyword,
)
from src.core.protocol.segment import MessageBuilder
from src.core.utils import SHANGHAI_TZ

if TYPE_CHECKING:
    from src.core.framework.context import Context
    from src.services.checkin import CheckinService

logger = structlog.get_logger()


@controller(
    name="user_checkin",
    display_name="群签到",
    description="用户手动签到，回复今日本群排名和连续/累计天数",
    tags=["fun"],
    default_enabled=True,
)
class CheckinHandler:
    """群签到处理器。"""

    @on_keyword(
        {"签到"},
        message_scope=MessageScope.group,
        display_name="签到（关键词）",
        description="发送「签到」触发",
    )
    @on_command(
        "签到",
        permission=Permission.ANYONE,
        message_scope=MessageScope.group,
        display_name="签到（命令）",
        description="发送「/签到」触发",
    )
    # 两个装饰器叠加在同一方法上，框架注册为两条独立路由规则
    # 权限管理页面显示为「签到（关键词）」和「签到（命令）」两个可配置条目
    async def handle_checkin(self, ctx: Context) -> bool:
        """处理用户签到请求，回复排名和连续/累计天数。"""
        from src.services.checkin import CheckinService

        if not ctx.has_service(CheckinService) or ctx.group_id is None:
            return False

        svc: CheckinService = ctx.get_service(CheckinService)
        today = datetime.now(SHANGHAI_TZ).date()

        try:
            result = await svc.checkin(
                group_id=ctx.group_id,
                user_id=ctx.user_id,
                today=today,
            )
        except Exception:
            logger.exception(
                "用户签到异常",
                group_id=ctx.group_id,
                user_id=ctx.user_id,
                event_type="checkin.handler_error",
            )
            await ctx.reply("签到失败，请稍后重试")
            return True

        if result.is_duplicate:
            msg = (
                MessageBuilder()
                .at(ctx.user_id)
                .text(f" 今天已经签到过啦~（连续 {result.streak} 天，累计 {result.total} 天）")
                .build()
            )
        else:
            msg = (
                MessageBuilder()
                .at(ctx.user_id)
                .text(
                    f" 签到成功！今日本群第 {result.rank} 个签到\n"
                    f"连续签到 {result.streak} 天，累计签到 {result.total} 天"
                )
                .build()
            )

        await ctx.reply(msg)
        return True
