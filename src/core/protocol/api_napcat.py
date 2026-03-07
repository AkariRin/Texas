"""NapCat 扩展 API (P2) —— 待后续实现的存根。"""

from __future__ import annotations

from typing import Any

from src.core.protocol.models.api import APIResponse


class NapCatAPIMixin:
    """提供 NapCat 独有扩展 API 的混入类。

    设计用于混入 BotAPI。实现在第 8 阶段。
    """

    _call: Any  # 将指向 BotAPI._call 方法

    async def friend_poke(self, user_id: int) -> APIResponse:
        return await self._call("friend_poke", {"user_id": user_id})

    async def group_poke(self, group_id: int, user_id: int) -> APIResponse:
        return await self._call("group_poke", {"group_id": group_id, "user_id": user_id})

    async def set_msg_emoji_like(
        self, message_id: int, emoji_id: str, set: bool = True,
    ) -> APIResponse:
        return await self._call(
            "set_msg_emoji_like", {"message_id": message_id, "emoji_id": emoji_id, "set": set}
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

    async def send_group_ai_record(
        self, group_id: int, character: str, text: str,
    ) -> APIResponse:
        return await self._call("send_group_ai_record", {
            "group_id": group_id, "character": character, "text": text,
        })

    async def translate_en2zh(self, words: list[str]) -> APIResponse:
        return await self._call("translate_en2zh", {"words": words})

