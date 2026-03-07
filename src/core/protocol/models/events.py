"""所有 OneBot 11 事件类型模型（含 NapCat 扩展）。"""

from __future__ import annotations

from pydantic import Field

from .base import (
    Anonymous,
    HeartbeatStatus,
    MessageSegment,
    OneBotEvent,
    Sender,
)

# ── 消息事件 ──


class MessageEvent(OneBotEvent):
    """消息事件基类。"""

    post_type: str = "message"
    message_type: str
    sub_type: str = ""
    message_id: int = 0
    user_id: int = 0
    message: list[MessageSegment] | str = Field(default_factory=list)
    raw_message: str = ""
    font: int = 0
    sender: Sender = Field(default_factory=Sender)


class PrivateMessageEvent(MessageEvent):
    """私聊（好友）消息事件。"""

    message_type: str = "private"
    sub_type: str = "friend"  # friend | group | other
    target_id: int | None = None
    temp_source: int | None = None


class GroupMessageEvent(MessageEvent):
    """群消息事件。"""

    message_type: str = "group"
    sub_type: str = "normal"  # normal | anonymous | notice
    group_id: int = 0
    anonymous: Anonymous | None = None


class MessageSentEvent(MessageEvent):
    """机器人自发消息事件（NapCat 扩展，post_type=message_sent）。"""

    post_type: str = "message_sent"
    target_id: int = 0


# ── 元事件 ──


class MetaEvent(OneBotEvent):
    """元事件基类。"""

    post_type: str = "meta_event"
    meta_event_type: str


class LifecycleEvent(MetaEvent):
    """生命周期事件（NapCat 中仅有 connect）。"""

    meta_event_type: str = "lifecycle"
    sub_type: str = "connect"


class HeartbeatEvent(MetaEvent):
    """心跳事件。"""

    meta_event_type: str = "heartbeat"
    status: HeartbeatStatus = Field(default_factory=HeartbeatStatus)
    interval: int = 30000


# ── 通知事件 ──


class NoticeEvent(OneBotEvent):
    """通知事件基类。"""

    post_type: str = "notice"
    notice_type: str
    sub_type: str = ""


class FriendAddNotice(NoticeEvent):
    notice_type: str = "friend_add"
    user_id: int = 0


class FriendRecallNotice(NoticeEvent):
    notice_type: str = "friend_recall"
    user_id: int = 0
    message_id: int = 0


class GroupUploadNotice(NoticeEvent):
    notice_type: str = "group_upload"
    group_id: int = 0
    user_id: int = 0
    file: dict[str, object] = Field(default_factory=dict)


class GroupAdminNotice(NoticeEvent):
    notice_type: str = "group_admin"
    sub_type: str = ""  # set | unset
    group_id: int = 0
    user_id: int = 0


class GroupDecreaseNotice(NoticeEvent):
    notice_type: str = "group_decrease"
    sub_type: str = ""  # leave | kick | kick_me | disband
    group_id: int = 0
    user_id: int = 0
    operator_id: int = 0


class GroupIncreaseNotice(NoticeEvent):
    notice_type: str = "group_increase"
    sub_type: str = ""  # approve | invite
    group_id: int = 0
    user_id: int = 0
    operator_id: int = 0


class GroupBanNotice(NoticeEvent):
    notice_type: str = "group_ban"
    sub_type: str = ""  # ban | lift_ban
    group_id: int = 0
    user_id: int = 0
    operator_id: int = 0
    duration: int = 0


class GroupRecallNotice(NoticeEvent):
    notice_type: str = "group_recall"
    group_id: int = 0
    user_id: int = 0
    operator_id: int = 0
    message_id: int = 0


class GroupCardNotice(NoticeEvent):
    notice_type: str = "group_card"
    group_id: int = 0
    user_id: int = 0
    card_new: str = ""
    card_old: str = ""


class EssenceNotice(NoticeEvent):
    notice_type: str = "essence"
    sub_type: str = ""  # add | delete
    group_id: int = 0
    message_id: int = 0
    sender_id: int = 0
    operator_id: int = 0


class GroupMsgEmojiLikeNotice(NoticeEvent):
    notice_type: str = "group_msg_emoji_like"
    group_id: int = 0
    user_id: int = 0
    message_id: int = 0
    likes: list[dict[str, object]] = Field(default_factory=list)


class NotifyEvent(NoticeEvent):
    """通知子类型事件（戳一戳、群名称、头衔等）。"""

    notice_type: str = "notify"
    sub_type: str = ""
    group_id: int | None = None
    user_id: int = 0
    target_id: int | None = None


class PokeNotify(NotifyEvent):
    sub_type: str = "poke"
    raw_info: dict[str, object] | None = None


class GroupNameNotify(NotifyEvent):
    sub_type: str = "group_name"
    name_new: str = ""


class TitleNotify(NotifyEvent):
    sub_type: str = "title"
    title: str = ""


class ProfileLikeNotify(NotifyEvent):
    sub_type: str = "profile_like"
    operator_id: int = 0
    operator_nick: str = ""
    times: int = 0


class InputStatusNotify(NotifyEvent):
    sub_type: str = "input_status"
    status_text: str = ""
    event_type: int = 0


class BotOfflineNotice(NoticeEvent):
    notice_type: str = "bot_offline"
    user_id: int = 0
    tag: str = ""
    message: str = ""


# ── 请求事件 ──


class RequestEvent(OneBotEvent):
    """请求事件基类。"""

    post_type: str = "request"
    request_type: str
    user_id: int = 0
    comment: str = ""
    flag: str = ""


class FriendRequestEvent(RequestEvent):
    request_type: str = "friend"


class GroupRequestEvent(RequestEvent):
    request_type: str = "group"
    sub_type: str = ""  # add | invite
    group_id: int = 0
