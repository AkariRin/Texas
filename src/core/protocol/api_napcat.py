"""NapCat 扩展 API (P2) —— 待后续实现的存根。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.core.protocol.models.api import APIResponse


class NapCatAPIMixin:
    """提供 NapCat 独有扩展 API 的混入类。

    设计用于混入 BotAPI。实现在第 8 阶段。
    """

    _call: Any  # 将指向 BotAPI._call 方法

    async def friend_poke(
        self, user_id: int, target_id: int | None = None
    ) -> APIResponse:
        params: dict[str, Any] = {"user_id": user_id}
        if target_id is not None:
            params["target_id"] = target_id
        return await self._call("friend_poke", params)

    async def group_poke(
        self, group_id: int, user_id: int, target_id: int | None = None
    ) -> APIResponse:
        params: dict[str, Any] = {"group_id": group_id, "user_id": user_id}
        if target_id is not None:
            params["target_id"] = target_id
        return await self._call("group_poke", params)

    async def set_msg_emoji_like(
        self,
        message_id: int,
        emoji_id: str,
        is_set: bool = True,
    ) -> APIResponse:
        return await self._call(
            "set_msg_emoji_like", {"message_id": message_id, "emoji_id": emoji_id, "set": is_set}
        )

    async def nc_get_rkey(self) -> APIResponse:
        return await self._call("nc_get_rkey", {})

    async def nc_get_packet_status(self) -> APIResponse:
        return await self._call("nc_get_packet_status", {})

    async def get_friends_with_category(self) -> APIResponse:
        return await self._call("get_friends_with_category", {})

    async def set_self_longnick(self, long_nick: str) -> APIResponse:
        return await self._call("set_self_longnick", {"longNick": long_nick})

    async def get_ai_characters(self, group_id: int, chat_type: int = 1) -> APIResponse:
        return await self._call("get_ai_characters", {"group_id": group_id, "chat_type": chat_type})

    async def get_ai_record(
        self,
        character: str,
        group_id: int,
        text: str,
    ) -> APIResponse:
        return await self._call(
            "get_ai_record",
            {
                "character": character,
                "group_id": group_id,
                "text": text,
            },
        )

    async def send_group_ai_record(
        self,
        group_id: int,
        character: str,
        text: str,
    ) -> APIResponse:
        return await self._call(
            "send_group_ai_record",
            {
                "group_id": group_id,
                "character": character,
                "text": text,
            },
        )

    async def translate_en2zh(self, words: list[str]) -> APIResponse:
        return await self._call("translate_en2zh", {"words": words})

    async def nc_get_user_status(self, user_id: int) -> APIResponse:
        return await self._call("nc_get_user_status", {"user_id": user_id})

    async def set_input_status(self, user_id: int, event_type: int) -> APIResponse:
        return await self._call(
            "set_input_status", {"user_id": user_id, "event_type": event_type}
        )

    async def set_diy_online_status(
        self, face_id: int, face_type: int = 1, wording: str = " "
    ) -> APIResponse:
        return await self._call(
            "set_diy_online_status",
            {"face_id": face_id, "face_type": face_type, "wording": wording},
        )

    async def get_rkey(self) -> APIResponse:
        return await self._call("get_rkey", {})

    async def mark_private_msg_as_read(
        self,
        message_id: int | None = None,
        user_id: int | None = None,
    ) -> APIResponse:
        params: dict[str, Any] = {}
        if message_id is not None:
            params["message_id"] = message_id
        if user_id is not None:
            params["user_id"] = user_id
        return await self._call("mark_private_msg_as_read", params)

    async def mark_group_msg_as_read(
        self,
        message_id: int | None = None,
        group_id: int | None = None,
    ) -> APIResponse:
        params: dict[str, Any] = {}
        if message_id is not None:
            params["message_id"] = message_id
        if group_id is not None:
            params["group_id"] = group_id
        return await self._call("mark_group_msg_as_read", params)

    async def get_friend_msg_history(
        self, user_id: int, count: int = 20, message_seq: int | None = None
    ) -> APIResponse:
        params: dict[str, Any] = {"user_id": user_id, "count": count}
        if message_seq is not None:
            params["message_seq"] = message_seq
        return await self._call("get_friend_msg_history", params)

    async def forward_friend_single_msg(
        self, message_id: int, user_id: int
    ) -> APIResponse:
        return await self._call(
            "forward_friend_single_msg", {"message_id": message_id, "user_id": user_id}
        )

    async def forward_group_single_msg(
        self, message_id: int, group_id: int
    ) -> APIResponse:
        return await self._call(
            "forward_group_single_msg", {"message_id": message_id, "group_id": group_id}
        )

    async def set_friend_remark(self, user_id: int, remark: str) -> APIResponse:
        return await self._call(
            "set_friend_remark", {"user_id": user_id, "remark": remark}
        )

    async def set_group_remark(self, group_id: int, remark: str) -> APIResponse:
        return await self._call(
            "set_group_remark", {"group_id": group_id, "remark": remark}
        )

    async def set_group_sign(self, group_id: int) -> APIResponse:
        return await self._call("set_group_sign", {"group_id": group_id})

    async def get_group_shut_list(self, group_id: int) -> APIResponse:
        return await self._call("get_group_shut_list", {"group_id": group_id})

    async def bot_exit(self) -> APIResponse:
        return await self._call("bot_exit", {})

