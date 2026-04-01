"""SessionInterceptor —— 会话消息路由拦截器。

在所有 handler 之前检查是否有活跃会话，
将消息路由到对应的交互式会话处理。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from src.core.framework.interceptor import HandlerInterceptor

if TYPE_CHECKING:
    from src.core.framework.context import Context
    from src.core.framework.session.manager import SessionManager

logger = structlog.get_logger()


class SessionInterceptor(HandlerInterceptor):
    """会话拦截器 —— 拦截消息事件并路由到活跃会话。"""

    def __init__(self, session_manager: SessionManager) -> None:
        self._session_manager = session_manager

    async def pre_handle(self, ctx: Context) -> bool:
        """在处理器执行前检查会话路由。

        Returns:
            False 表示消息已被会话处理，阻止后续 handler。
            True 表示无活跃会话，正常分发。
        """
        # 仅拦截消息事件
        if getattr(ctx.event, "post_type", None) != "message":
            return True

        # 查找活跃会话
        session_key = self._session_manager.get_active_session_key(ctx.user_id, ctx.group_id)
        if session_key is None:
            return True

        text = ctx.get_plaintext().strip()

        # 检查全局取消命令
        if self._session_manager.is_cancel_command(text):
            cancelled = await self._session_manager.cancel_session(session_key, ctx)
            if cancelled:
                msg = self._session_manager.build_reply(
                    "已取消当前操作。", ctx.user_id, ctx.is_group
                )
                await ctx.reply(msg)
            return False

        # 路由到会话处理
        handled = await self._session_manager.dispatch_input(session_key, ctx)
        return not handled
