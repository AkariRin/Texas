"""Bot 信息 API 端点 —— 业务层，获取 Bot 登录信息。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter()

# 将由 main.py 在启动时设置
_conn_mgr_provider: Any = None
_bot_api_provider: Any = None


def set_bot_providers(conn_mgr: Any, bot_api: Any) -> None:
    global _conn_mgr_provider, _bot_api_provider
    _conn_mgr_provider = conn_mgr
    _bot_api_provider = bot_api


@router.get("/bot/info")
async def bot_info() -> dict[str, Any]:
    """获取 Bot 登录信息（昵称、QQ 号、头像）。"""
    nickname = None
    user_id = None
    avatar_url = None

    connected = _conn_mgr_provider.connected if _conn_mgr_provider else False

    if connected and _bot_api_provider:
        try:
            resp = await _bot_api_provider.get_login_info()
            if resp.ok and isinstance(resp.data, dict):
                nickname = resp.data.get("nickname")
                user_id = resp.data.get("user_id")
                if user_id:
                    avatar_url = f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"
        except Exception:
            pass

    return {
        "code": 0,
        "data": {
            "nickname": nickname,
            "user_id": user_id,
            "avatar_url": avatar_url,
        },
        "message": "ok",
    }
