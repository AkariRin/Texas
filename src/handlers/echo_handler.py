"""回显处理器 —— 用于测试的简单消息回显。"""

from __future__ import annotations

from src.core.framework.context import Context
from src.core.framework.decorators import controller, on_command, on_regex


@controller(name="echo", description="消息回显处理器", version="1.0.0")
class EchoHandler:
    """回显消息。演示 @on_command 和 @on_regex 的用法。"""

    @on_command("echo", aliases={"回显"}, priority=10)
    async def handle_echo(self, ctx: Context) -> bool:
        """处理 /echo <text> —— 将参数文本回显。"""
        text = ctx.get_arg_str()
        if text:
            await ctx.reply(text)
        else:
            await ctx.reply("Usage: /echo <text>")
        return True

    @on_command("ping", priority=10)
    async def handle_ping(self, ctx: Context) -> bool:
        """处理 /ping —— 简单存活检查。"""
        await ctx.reply("pong!")
        return True

    @on_regex(r"^hello\s+(\w+)$", priority=20)
    async def handle_hello(self, ctx: Context) -> bool:
        """正则匹配：hello <name>。"""
        match = ctx.get_regex_match()
        if match:
            name = match.group(1)
            await ctx.reply(f"Hello, {name}!")
            return True
        return False

