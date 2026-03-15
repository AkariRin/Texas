"""Bot 信息 API 端点 —— 业务层，获取 Bot 登录信息。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends

from src.core.dependencies import get_bot_api, get_conn_mgr
from src.core.utils.response import ok

if TYPE_CHECKING:
    from src.core.protocol.api import BotAPI
    from src.core.ws.connection import ConnectionManager

router = APIRouter()


@router.get("/bot/info")
async def bot_info(
    conn_mgr: ConnectionManager = Depends(get_conn_mgr),
    bot_api: BotAPI = Depends(get_bot_api),
) -> dict[str, Any]:
    """获取 Bot 登录信息（昵称、QQ 号、头像）。"""
    nickname = None
    user_id = None
    avatar_url = None

    if conn_mgr.connected:
        try:
            resp = await bot_api.get_login_info()
            if resp.ok and isinstance(resp.data, dict):
                nickname = resp.data.get("nickname")
                user_id = resp.data.get("user_id")
                if user_id:
                    avatar_url = f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"
        except Exception:
            pass

    return ok(
        {
            "nickname": nickname,
            "user_id": user_id,
            "avatar_url": avatar_url,
        }
    )
