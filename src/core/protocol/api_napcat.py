"""NapCat 扩展 API (P2) —— 待后续实现的存根。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from src.core.protocol.models.api import APIResponse


class NapCatAPIMixin:
    """提供 NapCat 独有扩展 API 的混入类。

    设计用于混入 BotAPI。实现在第 8 阶段。
    """

    _call: Callable[..., Coroutine[Any, Any, APIResponse]]

    async def friend_poke(self, user_id: int, target_id: int | None = None) -> APIResponse:
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
        return await self._call("set_input_status", {"user_id": user_id, "event_type": event_type})

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

    async def forward_friend_single_msg(self, message_id: int, user_id: int) -> APIResponse:
        return await self._call(
            "forward_friend_single_msg", {"message_id": message_id, "user_id": user_id}
        )

    async def forward_group_single_msg(self, message_id: int, group_id: int) -> APIResponse:
        return await self._call(
            "forward_group_single_msg", {"message_id": message_id, "group_id": group_id}
        )

    async def set_friend_remark(self, user_id: int, remark: str) -> APIResponse:
        return await self._call("set_friend_remark", {"user_id": user_id, "remark": remark})

    async def set_group_remark(self, group_id: int, remark: str) -> APIResponse:
        return await self._call("set_group_remark", {"group_id": group_id, "remark": remark})

    async def set_group_sign(self, group_id: int) -> APIResponse:
        return await self._call("set_group_sign", {"group_id": group_id})

    async def get_group_shut_list(self, group_id: int) -> APIResponse:
        return await self._call("get_group_shut_list", {"group_id": group_id})

    async def bot_exit(self) -> APIResponse:
        return await self._call("bot_exit", {})

    async def set_online_status(
        self, status: int, ext_status: int, battery_status: int
    ) -> APIResponse:
        """设置账号在线状态（含电量）。"""
        return await self._call(
            "set_online_status",
            {"status": status, "ext_status": ext_status, "battery_status": battery_status},
        )

    async def set_qq_avatar(self, file: str) -> APIResponse:
        """设置 QQ 头像，file 为 URL 或本地路径。"""
        return await self._call("set_qq_avatar", {"file": file})

    async def get_clientkey(self) -> APIResponse:
        """获取 clientkey（用于某些 API 鉴权）。"""
        return await self._call("get_clientkey", {})

    async def get_unidirectional_friend_list(self) -> APIResponse:
        """获取单向好友列表（仅关注了本账号的用户）。"""
        return await self._call("get_unidirectional_friend_list", {})

    async def get_profile_like(self) -> APIResponse:
        """获取点赞自己的用户列表。"""
        return await self._call("get_profile_like", {})

    async def fetch_emoji_like(
        self,
        message_id: int,
        emoji_id: str,
        emoji_type: str | None = None,
        count: int | None = None,
    ) -> APIResponse:
        """获取消息表情点赞详情。"""
        params: dict[str, Any] = {"message_id": message_id, "emoji_id": emoji_id}
        if emoji_type is not None:
            params["emoji_type"] = emoji_type
        if count is not None:
            params["count"] = count
        return await self._call("fetch_emoji_like", params)

    async def get_doubt_friends_add_request(self) -> APIResponse:
        """获取可疑好友添加请求列表。"""
        return await self._call("get_doubt_friends_add_request", {})

    async def set_doubt_friends_add_request(
        self,
        user_id: int,
        approve: bool = True,
        remark: str = "",
    ) -> APIResponse:
        """处理可疑好友添加请求。"""
        params: dict[str, Any] = {"user_id": user_id, "approve": approve}
        if remark:
            params["remark"] = remark
        return await self._call("set_doubt_friends_add_request", params)

    async def send_poke(self, user_id: int, group_id: int | None = None) -> APIResponse:
        """发送戳一戳（私聊或群内）。"""
        params: dict[str, Any] = {"user_id": user_id}
        if group_id is not None:
            params["group_id"] = group_id
        return await self._call("send_poke", params)

    async def _mark_all_as_read(self) -> APIResponse:
        """将所有消息标记为已读。"""
        return await self._call("_mark_all_as_read", {})

    async def get_recent_contact(self, count: int = 10) -> APIResponse:
        """获取最近联系人列表。"""
        return await self._call("get_recent_contact", {"count": count})

    async def get_group_info_ex(self, group_id: int) -> APIResponse:
        """获取群扩展信息（比 get_group_info 更详细）。"""
        return await self._call("get_group_info_ex", {"group_id": group_id})

    async def set_group_portrait(self, group_id: int, file: str) -> APIResponse:
        """设置群头像，file 为 URL 或本地路径。"""
        return await self._call("set_group_portrait", {"group_id": group_id, "file": file})

    async def get_group_ignore_add_request(self) -> APIResponse:
        """获取被忽略的加群请求列表。"""
        return await self._call("get_group_ignore_add_request", {})

    async def get_group_ignored_notifies(self) -> APIResponse:
        """获取被忽略的群通知列表。"""
        return await self._call("get_group_ignored_notifies", {})

    async def send_group_sign(self, group_id: int) -> APIResponse:
        """发送群打卡。"""
        return await self._call("send_group_sign", {"group_id": group_id})

    async def ark_share_peer(
        self,
        user_id: int | None = None,
        phone_number: str | None = None,
        group_id: int | None = None,
    ) -> APIResponse:
        """获取好友/群分享 Ark 卡片数据（私聊）。"""
        params: dict[str, Any] = {}
        if user_id is not None:
            params["user_id"] = user_id
        if phone_number is not None:
            params["phone_number"] = phone_number
        if group_id is not None:
            params["group_id"] = group_id
        return await self._call("ArkSharePeer", params)

    async def ark_share_group(self, group_id: int) -> APIResponse:
        """获取群分享 Ark 卡片数据。"""
        return await self._call("ArkShareGroup", {"group_id": group_id})

    async def get_mini_app_ark(
        self,
        app_type: str,
        title: str,
        desc: str,
        pic_url: str,
        jump_url: str,
    ) -> APIResponse:
        """获取小程序 Ark 卡片数据，app_type 对应 NapCat 的 type 字段。"""
        return await self._call(
            "get_mini_app_ark",
            {
                "type": app_type,
                "title": title,
                "desc": desc,
                "pic_url": pic_url,
                "jump_url": jump_url,
            },
        )

    async def click_inline_keyboard_button(
        self,
        group_id: int,
        bot_appid: str,
        button_id: str,
        callback_data: str,
        msg_seq: int,
    ) -> APIResponse:
        """点击群消息内嵌键盘按钮。"""
        return await self._call(
            "click_inline_keyboard_button",
            {
                "group_id": group_id,
                "bot_appid": bot_appid,
                "button_id": button_id,
                "callback_data": callback_data,
                "msg_seq": msg_seq,
            },
        )

    async def create_collection(self, raw_data: str, brief: str) -> APIResponse:
        """创建收藏内容。"""
        return await self._call("create_collection", {"raw_data": raw_data, "brief": brief})

    async def get_collection_list(
        self, category: int | None = None, count: int | None = None
    ) -> APIResponse:
        """获取收藏列表。"""
        params: dict[str, Any] = {}
        if category is not None:
            params["category"] = category
        if count is not None:
            params["count"] = count
        return await self._call("get_collection_list", params)

    async def fetch_custom_face(self, count: int = 48) -> APIResponse:
        """获取自定义表情列表。"""
        return await self._call("fetch_custom_face", {"count": count})

    async def get_robot_uin_range(self) -> APIResponse:
        """获取机器人 QQ 号段范围。"""
        return await self._call("get_robot_uin_range", {})

    async def send_packet(self, cmd: str, body: str) -> APIResponse:
        """发送原始数据包（高级调试用途）。"""
        return await self._call("send_packet", {"cmd": cmd, "body": body})

    async def get_guild_list(self) -> APIResponse:
        """获取频道列表。"""
        return await self._call("get_guild_list", {})

    async def get_guild_service_profile(self) -> APIResponse:
        """获取频道服务资料。"""
        return await self._call("get_guild_service_profile", {})

    async def _get_model_show(self) -> APIResponse:
        """获取账号挂件展示信息。"""
        return await self._call("_get_model_show", {})

    async def _set_model_show(
        self,
        model: str,
        model_show: str | None = None,
    ) -> APIResponse:
        """设置账号挂件展示。"""
        params: dict[str, Any] = {"model": model}
        if model_show is not None:
            params["model_show"] = model_show
        return await self._call("_set_model_show", params)
