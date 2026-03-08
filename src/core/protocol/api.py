"""OneBot 11 标准 API 封装 —— 通过 WebSocket 发送指令。"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING, Any

import structlog

from .models.api import APIRequest, APIResponse

if TYPE_CHECKING:
    from src.core.ws.connection import ConnectionManager

    from .models.base import MessageSegment

logger = structlog.get_logger()

DEFAULT_TIMEOUT = 30.0


class BotAPI:
    """OneBot 11 标准 API (P0) —— 发送指令并等待响应。"""

    def __init__(self, connection_manager: ConnectionManager) -> None:
        self._conn = connection_manager
        self._pending: dict[str, asyncio.Future[APIResponse]] = {}

    # ── 内部方法 ──

    async def _call(
        self, action: str, params: dict[str, Any] | None = None, timeout: float = DEFAULT_TIMEOUT
    ) -> APIResponse:
        echo = uuid.uuid4().hex
        req = APIRequest(action=action, params=params or {}, echo=echo)

        future: asyncio.Future[APIResponse] = asyncio.get_running_loop().create_future()
        self._pending[echo] = future

        try:
            await self._conn.send(req.model_dump())
            return await asyncio.wait_for(future, timeout=timeout)
        except TimeoutError:
            logger.warning("API call timeout", action=action, echo=echo, timeout=timeout)
            return APIResponse(status="failed", retcode=-1, message="timeout", echo=echo)
        finally:
            self._pending.pop(echo, None)

    def handle_response(self, data: dict[str, Any]) -> bool:
        """尝试用 API 响应解析挂起的 Future。

        若为 API 响应（含匹配的 echo），返回 True；否则返回 False。
        """
        echo = data.get("echo", "")
        if not echo:
            return False
        future = self._pending.get(str(echo))
        if future is None or future.done():
            return False
        try:
            resp = APIResponse.model_validate(data)
            future.set_result(resp)
        except Exception as exc:
            future.set_exception(exc)
        return True

    # ── 消息 API ──

    async def send_private_msg(
        self, user_id: int, message: list[MessageSegment] | str, auto_escape: bool = False
    ) -> APIResponse:
        msg = [s.model_dump() for s in message] if isinstance(message, list) else message
        return await self._call(
            "send_private_msg",
            {"user_id": user_id, "message": msg, "auto_escape": auto_escape},
        )

    async def send_group_msg(
        self, group_id: int, message: list[MessageSegment] | str, auto_escape: bool = False
    ) -> APIResponse:
        msg = [s.model_dump() for s in message] if isinstance(message, list) else message
        return await self._call(
            "send_group_msg",
            {"group_id": group_id, "message": msg, "auto_escape": auto_escape},
        )

    async def send_msg(
        self,
        message_type: str | None = None,
        user_id: int | None = None,
        group_id: int | None = None,
        message: list[MessageSegment] | str = "",
        auto_escape: bool = False,
    ) -> APIResponse:
        msg = [s.model_dump() for s in message] if isinstance(message, list) else message
        params: dict[str, Any] = {"message": msg, "auto_escape": auto_escape}
        if message_type:
            params["message_type"] = message_type
        if user_id is not None:
            params["user_id"] = user_id
        if group_id is not None:
            params["group_id"] = group_id
        return await self._call("send_msg", params)

    async def delete_msg(self, message_id: int) -> APIResponse:
        return await self._call("delete_msg", {"message_id": message_id})

    async def get_msg(self, message_id: int) -> APIResponse:
        return await self._call("get_msg", {"message_id": message_id})

    async def get_forward_msg(self, forward_id: str) -> APIResponse:
        return await self._call("get_forward_msg", {"id": forward_id})

    async def send_like(self, user_id: int, times: int = 1) -> APIResponse:
        return await self._call("send_like", {"user_id": user_id, "times": times})

    # ── 群管理 API ──

    async def set_group_kick(
        self, group_id: int, user_id: int, reject_add_request: bool = False
    ) -> APIResponse:
        return await self._call(
            "set_group_kick",
            {"group_id": group_id, "user_id": user_id, "reject_add_request": reject_add_request},
        )

    async def set_group_ban(self, group_id: int, user_id: int, duration: int = 1800) -> APIResponse:
        return await self._call(
            "set_group_ban",
            {"group_id": group_id, "user_id": user_id, "duration": duration},
        )

    async def set_group_whole_ban(self, group_id: int, enable: bool = True) -> APIResponse:
        return await self._call("set_group_whole_ban", {"group_id": group_id, "enable": enable})

    async def set_group_admin(
        self, group_id: int, user_id: int, enable: bool = True
    ) -> APIResponse:
        return await self._call(
            "set_group_admin",
            {"group_id": group_id, "user_id": user_id, "enable": enable},
        )

    async def set_group_card(self, group_id: int, user_id: int, card: str = "") -> APIResponse:
        return await self._call(
            "set_group_card",
            {"group_id": group_id, "user_id": user_id, "card": card},
        )

    async def set_group_name(self, group_id: int, group_name: str) -> APIResponse:
        return await self._call("set_group_name", {"group_id": group_id, "group_name": group_name})

    async def set_group_leave(self, group_id: int, is_dismiss: bool = False) -> APIResponse:
        return await self._call("set_group_leave", {"group_id": group_id, "is_dismiss": is_dismiss})

    async def set_group_special_title(
        self, group_id: int, user_id: int, special_title: str = ""
    ) -> APIResponse:
        return await self._call(
            "set_group_special_title",
            {
                "group_id": group_id,
                "user_id": user_id,
                "special_title": special_title,
            },
        )

    # ── 请求处理 ──

    async def set_friend_add_request(
        self, flag: str, approve: bool = True, remark: str = ""
    ) -> APIResponse:
        return await self._call(
            "set_friend_add_request",
            {"flag": flag, "approve": approve, "remark": remark},
        )

    async def set_group_add_request(
        self, flag: str, sub_type: str, approve: bool = True, reason: str = ""
    ) -> APIResponse:
        return await self._call(
            "set_group_add_request",
            {"flag": flag, "sub_type": sub_type, "approve": approve, "reason": reason},
        )

    # ── 信息获取 ──

    async def get_login_info(self) -> APIResponse:
        return await self._call("get_login_info")

    async def get_stranger_info(self, user_id: int, no_cache: bool = False) -> APIResponse:
        return await self._call("get_stranger_info", {"user_id": user_id, "no_cache": no_cache})

    async def get_friend_list(self) -> APIResponse:
        return await self._call("get_friend_list")

    async def get_group_info(self, group_id: int, no_cache: bool = False) -> APIResponse:
        return await self._call("get_group_info", {"group_id": group_id, "no_cache": no_cache})

    async def get_group_list(self) -> APIResponse:
        return await self._call("get_group_list")

    async def get_group_member_info(
        self, group_id: int, user_id: int, no_cache: bool = False
    ) -> APIResponse:
        return await self._call(
            "get_group_member_info",
            {"group_id": group_id, "user_id": user_id, "no_cache": no_cache},
        )

    async def get_group_member_list(self, group_id: int) -> APIResponse:
        return await self._call("get_group_member_list", {"group_id": group_id})

    async def get_group_honor_info(self, group_id: int, honor_type: str = "all") -> APIResponse:
        return await self._call("get_group_honor_info", {"group_id": group_id, "type": honor_type})

    # ── 媒体 ──

    async def get_image(self, file: str) -> APIResponse:
        return await self._call("get_image", {"file": file})

    async def get_record(self, file: str, out_format: str = "mp3") -> APIResponse:
        return await self._call("get_record", {"file": file, "out_format": out_format})

    async def can_send_image(self) -> APIResponse:
        return await self._call("can_send_image")

    async def can_send_record(self) -> APIResponse:
        return await self._call("can_send_record")

    # ── 系统 ──

    async def get_version_info(self) -> APIResponse:
        return await self._call("get_version_info")

    async def get_status(self) -> APIResponse:
        return await self._call("get_status")

    async def clean_cache(self) -> APIResponse:
        return await self._call("clean_cache")
