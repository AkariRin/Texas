"""权限拦截器 —— 检查用户权限是否满足处理器要求。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from src.core.framework.decorators import Permission
from src.core.framework.interceptor import HandlerInterceptor

if TYPE_CHECKING:
    from src.core.framework.context import Context

logger = structlog.get_logger()


class PermissionInterceptor(HandlerInterceptor):
    """检查用户权限级别是否满足处理器所要求的权限。

    当前使用简单的内存检查。第 2 阶段将与数据库 User 模型集成。
    """

    async def pre_handle(self, ctx: Context) -> bool:
        if ctx.handler_method is None:
            return True

        required = ctx.handler_method.permission
        if required == Permission.ANYONE:
            return True

        user_id = ctx.user_id

        # 群角色检查
        if required == Permission.ADMIN:
            logger.debug(
                "Permission denied: admin required",
                user_id=user_id,
                event_type="interceptor.permission.denied",
            )
            await ctx.reply("Permission denied: admin required.")
            return False

        if ctx.is_group and required in (Permission.GROUP_ADMIN, Permission.GROUP_OWNER):
            sender = getattr(ctx.event, "sender", None)
            role = getattr(sender, "role", "member") if sender else "member"
            if required == Permission.GROUP_OWNER and role != "owner":
                await ctx.reply("Permission denied: group owner required.")
                return False
            if required == Permission.GROUP_ADMIN and role not in ("admin", "owner"):
                await ctx.reply("Permission denied: group admin required.")
                return False

        return True
