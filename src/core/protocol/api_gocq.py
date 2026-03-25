"""go-cqhttp 兼容 API 扩展 (P1)。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from src.core.protocol.models.api import APIResponse


class GoCQHTTPAPIMixin:
    """提供 go-cqhttp 兼容扩展 API 的混入类。

    设计用于混入 BotAPI 或作为独立扩展使用。
    """

    _call: Callable[..., Coroutine[Any, Any, APIResponse]]

    async def set_qq_profile(
        self,
        nickname: str,
        personal_note: str = "",
        sex: int | None = None,
    ) -> APIResponse:
        params: dict[str, Any] = {"nickname": nickname}
        if personal_note:
            params["personal_note"] = personal_note
        if sex is not None:
            params["sex"] = sex
        return await self._call("set_qq_profile", params)

    async def mark_msg_as_read(
        self,
        message_id: int | None = None,
        user_id: int | None = None,
        group_id: int | None = None,
    ) -> APIResponse:
        params: dict[str, Any] = {}
        if message_id is not None:
            params["message_id"] = message_id
        if user_id is not None:
            params["user_id"] = user_id
        if group_id is not None:
            params["group_id"] = group_id
        return await self._call("mark_msg_as_read", params)

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

    async def get_group_file_url(
        self, group_id: int, file_id: str, busid: int | None = None
    ) -> APIResponse:
        params: dict[str, Any] = {"group_id": group_id, "file_id": file_id}
        if busid is not None:
            params["busid"] = busid
        return await self._call("get_group_file_url", params)

    async def download_file(
        self,
        url: str = "",
        base64: str = "",
        name: str = "",
        headers: str | list[str] = "",
    ) -> APIResponse:
        params: dict[str, Any] = {}
        if url:
            params["url"] = url
        if base64:
            params["base64"] = base64
        if name:
            params["name"] = name
        if headers:
            params["headers"] = headers
        return await self._call("download_file", params)

    async def delete_friend(self, user_id: int) -> APIResponse:
        return await self._call("delete_friend", {"user_id": user_id})

    async def send_forward_msg(
        self,
        messages: list[dict[str, Any]],
        message_type: str | None = None,
        user_id: int | None = None,
        group_id: int | None = None,
    ) -> APIResponse:
        """发送合并转发消息（通用）。"""
        params: dict[str, Any] = {"messages": messages}
        if message_type is not None:
            params["message_type"] = message_type
        if user_id is not None:
            params["user_id"] = user_id
        if group_id is not None:
            params["group_id"] = group_id
        return await self._call("send_forward_msg", params)

    async def _send_group_notice(self, group_id: int, content: str, image: str = "") -> APIResponse:
        """发布群公告。"""
        params: dict[str, Any] = {"group_id": group_id, "content": content}
        if image:
            params["image"] = image
        return await self._call("_send_group_notice", params)

    async def _get_group_notice(self, group_id: int) -> APIResponse:
        """获取群公告列表。"""
        return await self._call("_get_group_notice", {"group_id": group_id})

    async def _del_group_notice(self, group_id: int, notice_id: str) -> APIResponse:
        """删除群公告。"""
        return await self._call("_del_group_notice", {"group_id": group_id, "notice_id": notice_id})

    async def get_group_at_all_remain(self, group_id: int) -> APIResponse:
        """获取群 @全体成员 的剩余次数。"""
        return await self._call("get_group_at_all_remain", {"group_id": group_id})

    async def get_group_system_msg(self) -> APIResponse:
        """获取群系统消息（加群申请等）。"""
        return await self._call("get_group_system_msg", {})

    async def get_cookies(self, domain: str = "") -> APIResponse:
        """获取 QQ 相关域名的 Cookie。"""
        params: dict[str, Any] = {}
        if domain:
            params["domain"] = domain
        return await self._call("get_cookies", params)

    async def get_csrf_token(self) -> APIResponse:
        """获取 CSRF Token。"""
        return await self._call("get_csrf_token", {})

    async def get_credentials(self, domain: str = "") -> APIResponse:
        """同时获取 Cookie 和 CSRF Token。"""
        params: dict[str, Any] = {}
        if domain:
            params["domain"] = domain
        return await self._call("get_credentials", params)

    async def get_online_clients(self, no_cache: bool = False) -> APIResponse:
        """获取当前账号已登录的设备列表。"""
        return await self._call("get_online_clients", {"no_cache": no_cache})

    async def check_url_safely(self, url: str) -> APIResponse:
        """检查 URL 安全性。"""
        return await self._call("check_url_safely", {"url": url})

    async def handle_quick_operation(
        self, context: dict[str, Any], operation: dict[str, Any]
    ) -> APIResponse:
        """快速操作（对事件快速回复/处理）。"""
        return await self._call(
            ".handle_quick_operation", {"context": context, "operation": operation}
        )

    async def get_word_slices(self, content: str) -> APIResponse:
        """获取中文分词结果。"""
        return await self._call(".get_word_slices", {"content": content})
