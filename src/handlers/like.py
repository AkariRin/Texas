"""点赞 Bot 处理器 —— 响应 /like 或 /点赞 命令。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from src.core.framework.decorators import (
    MessageScope,
    Permission,
    controller,
    on_command,
)
from src.models.enums import LikeSource
from src.services.like import DEFAULT_LIKE_TIMES

if TYPE_CHECKING:
    from src.core.framework.context import Context
    from src.services.like import LikeService

logger = structlog.get_logger()

_USAGE = (
    "用法：\n"
    "  /like [n]       立即点赞 n 次（默认 10）\n"
    "  /like schedule  注册每日定时点赞\n"
    "  /like cancel    取消定时点赞\n"
    "  /like status    查看状态与统计"
)


@controller(
    name="like",
    display_name="点赞",
    description="给自己 QQ 主页点赞，支持手动和每日定时自动点赞",
    tags=["fun"],
    default_enabled=True,
)
class LikeHandler:
    """点赞处理器。"""

    @on_command(
        "like",
        aliases={"点赞"},
        permission=Permission.ANYONE,
        message_scope=MessageScope.all,
        display_name="点赞",
        description="/like [n|schedule|cancel|status]",
    )
    async def handle(self, ctx: Context) -> None:
        """解析参数并分发到对应子命令。"""
        from src.services.like import LikeService

        if not ctx.has_service(LikeService):
            return

        svc: LikeService = ctx.get_service(LikeService)
        qq = ctx.user_id
        args = ctx.get_args()
        sub = args[0].lower() if args else ""

        if sub in ("schedule", "定时"):
            await self._handle_schedule(ctx, svc, qq)
        elif sub in ("cancel", "取消"):
            await self._handle_cancel(ctx, svc, qq)
        elif sub in ("status", "状态"):
            await self._handle_status(ctx, svc, qq)
        elif sub == "" or sub.isdigit():
            await self._handle_send(ctx, svc, qq, sub)
        else:
            await ctx.reply(_USAGE)

    async def _handle_send(self, ctx: Context, svc: LikeService, qq: int, sub: str) -> None:
        """执行立即点赞。"""
        times = DEFAULT_LIKE_TIMES
        if sub.isdigit():
            n = int(sub)
            if n < 1 or n > 20:
                await ctx.reply("点赞次数范围为 1~20")
                return
            times = n

        success = await svc.send_like_now(qq, times, LikeSource.manual)
        if success:
            await ctx.reply(f"已给你点赞 {times} 次 👍")
        else:
            await ctx.reply("点赞失败，请稍后重试")

    async def _handle_schedule(self, ctx: Context, svc: LikeService, qq: int) -> None:
        """注册定时点赞任务。"""
        result = await svc.register_task(qq, ctx.group_id)
        if result.already_exists:
            await ctx.reply("你已经注册过每日定时点赞了～")
        else:
            await ctx.reply(f"已注册每日定时点赞！每天零点自动给你点赞 {DEFAULT_LIKE_TIMES} 次")

    async def _handle_cancel(self, ctx: Context, svc: LikeService, qq: int) -> None:
        """取消定时点赞任务。"""
        deleted = await svc.cancel_task(qq)
        if deleted:
            await ctx.reply("已取消每日定时点赞")
        else:
            await ctx.reply("你还没有注册定时点赞哦")

    async def _handle_status(self, ctx: Context, svc: LikeService, qq: int) -> None:
        """查询点赞状态与统计。"""
        status = await svc.get_status(qq)
        task_info = "✅ 已开启每日定时点赞" if status.has_task else "❌ 未开启定时点赞"
        last_time = (
            status.last_triggered_at.strftime("%Y-%m-%d %H:%M")
            if status.last_triggered_at
            else "暂无"
        )
        await ctx.reply(
            f"点赞状态\n{task_info}\n累计已点赞：{status.total_times} 次\n最近点赞：{last_time}"
        )
