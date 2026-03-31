"""Bot 信息 API 端点 —— 业务层，获取和修改 Bot 登录信息。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.core.dependencies import get_bot_api, get_conn_mgr
from src.core.utils.response import fail, ok

if TYPE_CHECKING:
    from src.core.protocol.api import BotAPI
    from src.core.ws.connection import ConnectionManager

router = APIRouter()

logger = structlog.get_logger()


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
        except Exception as exc:
            logger.warning(
                "获取 Bot 登录信息失败", error=str(exc), event_type="bot.login_info_error"
            )

    return ok(
        {
            "nickname": nickname,
            "user_id": user_id,
            "avatar_url": avatar_url,
        }
    )


@router.get("/bot/profile")
async def bot_profile(
    conn_mgr: ConnectionManager = Depends(get_conn_mgr),
    bot_api: BotAPI = Depends(get_bot_api),
) -> dict[str, Any]:
    """获取 Bot 完整信息（昵称、QQ 号、头像、在线状态、版本）。"""
    nickname = None
    user_id = None
    avatar_url = None
    online = conn_mgr.connected
    version: dict[str, Any] = {}

    if conn_mgr.connected:
        try:
            login_resp = await bot_api.get_login_info()
            if login_resp.ok and isinstance(login_resp.data, dict):
                nickname = login_resp.data.get("nickname")
                user_id = login_resp.data.get("user_id")
                if user_id:
                    avatar_url = f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"
        except Exception as exc:
            logger.warning("获取登录信息失败", error=str(exc), event_type="bot.login_info_error")

        try:
            ver_resp = await bot_api.get_version_info()
            if ver_resp.ok and isinstance(ver_resp.data, dict):
                version = {
                    "app_name": ver_resp.data.get("app_name", ""),
                    "app_version": ver_resp.data.get("app_version", ""),
                    "protocol_version": ver_resp.data.get("protocol_version", ""),
                }
        except Exception as exc:
            logger.warning("获取版本信息失败", error=str(exc), event_type="bot.version_info_error")

    return ok(
        {
            "nickname": nickname,
            "user_id": user_id,
            "avatar_url": avatar_url,
            "online": online,
            "version": version,
        }
    )


class BotProfileUpdate(BaseModel):
    """修改 Bot 资料的请求体。"""

    nickname: str | None = None
    personal_note: str | None = None


@router.put("/bot/profile")
async def update_bot_profile(
    body: BotProfileUpdate,
    conn_mgr: ConnectionManager = Depends(get_conn_mgr),
    bot_api: BotAPI = Depends(get_bot_api),
) -> dict[str, Any]:
    """修改 Bot 昵称和个性签名。"""
    if not conn_mgr.connected:
        return fail("Bot 未连接，无法修改资料")

    if body.nickname is None and body.personal_note is None:
        return fail("至少需要提供一个修改字段")

    try:
        # 若只传了 personal_note 而没有 nickname，需先获取当前昵称
        nickname = body.nickname
        if nickname is None:
            login_resp = await bot_api.get_login_info()
            if login_resp.ok and isinstance(login_resp.data, dict):
                nickname = str(login_resp.data.get("nickname") or "")
            else:
                return fail("获取当前昵称失败，无法执行修改")

        kwargs: dict[str, Any] = {"nickname": nickname}
        if body.personal_note is not None:
            kwargs["personal_note"] = body.personal_note

        resp = await bot_api.set_qq_profile(**kwargs)
        if not resp.ok:
            return fail(f"修改失败：{resp.message or '未知错误'}")
    except Exception as exc:
        logger.warning("修改 Bot 资料失败", error=str(exc), event_type="bot.update_profile_error")
        return fail(f"修改失败：{exc!s}")

    return ok({})
