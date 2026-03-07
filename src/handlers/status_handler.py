"""状态处理器 —— 演示依赖注入和 Bot 信息查询。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.framework.decorators import controller, on_command

if TYPE_CHECKING:
    from src.core.framework.context import Context


@controller(name="status", description="Bot 状态查询处理器", version="1.0.0")
class StatusHandler:
    """提供 /status 命令以查询 Bot 信息。"""

    @on_command("status", aliases={"状态"}, priority=10)
    async def handle_status(self, ctx: Context) -> bool:
        """处理 /status —— 显示 Bot 运行状态。"""
        try:
            resp = await ctx.bot.get_login_info()
            if resp.ok and isinstance(resp.data, dict):
                nickname = resp.data.get("nickname", "Unknown")
                user_id = resp.data.get("user_id", "Unknown")
                await ctx.reply(f"Bot: {nickname} ({user_id})\nStatus: Online")
            else:
                await ctx.reply("Bot is running, but couldn't fetch login info.")
        except Exception:
            await ctx.reply("Bot is running.")
        return True

    @on_command("help", aliases={"帮助"}, priority=10)
    async def handle_help(self, ctx: Context) -> bool:
        """处理 /help —— 显示可用命令。"""
        help_text = (
            "Available commands:\n"
            "  /ping — Liveness check\n"
            "  /echo <text> — Echo back text\n"
            "  /status — Show bot status\n"
            "  /help — Show this help"
        )
        await ctx.reply(help_text)
        return True
