"""go-cqhttp 兼容 API 扩展 (P1)。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.core.protocol.models.api import APIResponse

    pass


class GoCQHTTPAPIMixin:
    """提供 go-cqhttp 兼容扩展 API 的混入类。

    设计用于混入 BotAPI 或作为独立扩展使用。
    """

    _call: Any  # 将指向 BotAPI._call 方法

    async def set_qq_profile(
        self,
        nickname: str,
        company: str = "",
        email: str = "",
        college: str = "",
        personal_note: str = "",
    ) -> APIResponse:
        return await self._call(
            "set_qq_profile",
            {
                "nickname": nickname,
                "company": company,
                "email": email,
                "college": college,
                "personal_note": personal_note,
            },
        )

    async def mark_msg_as_read(self, message_id: int) -> APIResponse:
        return await self._call("mark_msg_as_read", {"message_id": message_id})

    async def send_group_forward_msg(
        self,
        group_id: int,
        messages: list[dict[str, Any]],
    ) -> APIResponse:
        return await self._call(
            "send_group_forward_msg", {"group_id": group_id, "messages": messages}
        )

    async def send_private_forward_msg(
        self,
        user_id: int,
        messages: list[dict[str, Any]],
    ) -> APIResponse:
        return await self._call(
            "send_private_forward_msg", {"user_id": user_id, "messages": messages}
        )

    async def get_group_msg_history(
        self,
        group_id: int,
        message_seq: int | None = None,
        count: int = 20,
    ) -> APIResponse:
        params: dict[str, Any] = {"group_id": group_id, "count": count}
        if message_seq is not None:
            params["message_seq"] = message_seq
        return await self._call("get_group_msg_history", params)

    async def set_essence_msg(self, message_id: int) -> APIResponse:
        return await self._call("set_essence_msg", {"message_id": message_id})

    async def delete_essence_msg(self, message_id: int) -> APIResponse:
        return await self._call("delete_essence_msg", {"message_id": message_id})

    async def get_essence_msg_list(self, group_id: int) -> APIResponse:
        return await self._call("get_essence_msg_list", {"group_id": group_id})

    async def ocr_image(self, image: str) -> APIResponse:
        return await self._call("ocr_image", {"image": image})

    async def upload_group_file(
        self,
        group_id: int,
        file: str,
        name: str,
        folder: str = "",
    ) -> APIResponse:
        return await self._call(
            "upload_group_file",
            {
                "group_id": group_id,
                "file": file,
                "name": name,
                "folder": folder,
            },
        )

    async def upload_private_file(self, user_id: int, file: str, name: str) -> APIResponse:
        return await self._call(
            "upload_private_file", {"user_id": user_id, "file": file, "name": name}
        )

    async def get_group_file_system_info(self, group_id: int) -> APIResponse:
        return await self._call("get_group_file_system_info", {"group_id": group_id})

    async def get_group_root_files(self, group_id: int) -> APIResponse:
        return await self._call("get_group_root_files", {"group_id": group_id})

    async def get_group_file_url(self, group_id: int, file_id: str, busid: int) -> APIResponse:
        return await self._call(
            "get_group_file_url",
            {
                "group_id": group_id,
                "file_id": file_id,
                "busid": busid,
            },
        )

    async def download_file(
        self, url: str, thread_count: int = 1, headers: str = ""
    ) -> APIResponse:
        return await self._call(
            "download_file",
            {
                "url": url,
                "thread_count": thread_count,
                "headers": headers,
            },
        )

    async def delete_friend(self, user_id: int) -> APIResponse:
        return await self._call("delete_friend", {"user_id": user_id})
