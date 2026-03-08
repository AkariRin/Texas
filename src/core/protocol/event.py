"""事件解析 —— 将 JSON 字典转换为对应类型的 OneBotEvent 子类。"""

from __future__ import annotations

import structlog

from .models.base import OneBotEvent
from .models.events import (
    BotOfflineNotice,
    EssenceNotice,
    FriendAddNotice,
    FriendRecallNotice,
    FriendRequestEvent,
    GrayTipNotify,
    GroupAdminNotice,
    GroupBanNotice,
    GroupCardNotice,
    GroupDecreaseNotice,
    GroupIncreaseNotice,
    GroupMessageEvent,
    GroupMsgEmojiLikeNotice,
    GroupNameNotify,
    GroupRecallNotice,
    GroupRequestEvent,
    GroupUploadNotice,
    HeartbeatEvent,
    InputStatusNotify,
    LifecycleEvent,
    MessageSentEvent,
    NoticeEvent,
    NotifyEvent,
    PokeNotify,
    PrivateMessageEvent,
    ProfileLikeNotify,
    RequestEvent,
    TitleNotify,
)

logger = structlog.get_logger()

# 映射表：(notice_type, sub_type?) -> 模型类
_NOTICE_MAP: dict[str, type[NoticeEvent]] = {
    "friend_add": FriendAddNotice,
    "friend_recall": FriendRecallNotice,
    "group_upload": GroupUploadNotice,
    "group_admin": GroupAdminNotice,
    "group_decrease": GroupDecreaseNotice,
    "group_increase": GroupIncreaseNotice,
    "group_ban": GroupBanNotice,
    "group_recall": GroupRecallNotice,
    "group_card": GroupCardNotice,
    "essence": EssenceNotice,
    "group_msg_emoji_like": GroupMsgEmojiLikeNotice,
    "bot_offline": BotOfflineNotice,
}

_NOTIFY_SUBTYPE_MAP: dict[str, type[NotifyEvent]] = {
    "poke": PokeNotify,
    "group_name": GroupNameNotify,
    "title": TitleNotify,
    "profile_like": ProfileLikeNotify,
    "input_status": InputStatusNotify,
    "gray_tip": GrayTipNotify,
}


def parse_event(data: dict[str, object]) -> OneBotEvent:
    """将原始 JSON 字典解析为对应的 OneBotEvent 子类。"""
    post_type = data.get("post_type", "")

    if post_type == "message":
        return _parse_message(data)
    elif post_type == "message_sent":
        return MessageSentEvent.model_validate(data)
    elif post_type == "meta_event":
        return _parse_meta(data)
    elif post_type == "notice":
        return _parse_notice(data)
    elif post_type == "request":
        return _parse_request(data)
    else:
        logger.warning("Unknown post_type", post_type=post_type, event_type="protocol.unknown")
        return OneBotEvent.model_validate(data)


def _parse_message(data: dict[str, object]) -> OneBotEvent:
    msg_type = data.get("message_type", "")
    if msg_type == "private":
        return PrivateMessageEvent.model_validate(data)
    elif msg_type == "group":
        return GroupMessageEvent.model_validate(data)
    else:
        logger.warning("Unknown message_type", message_type=msg_type)
        return PrivateMessageEvent.model_validate(data)


def _parse_meta(data: dict[str, object]) -> OneBotEvent:
    meta_type = data.get("meta_event_type", "")
    if meta_type == "lifecycle":
        return LifecycleEvent.model_validate(data)
    elif meta_type == "heartbeat":
        return HeartbeatEvent.model_validate(data)
    else:
        logger.warning("Unknown meta_event_type", meta_event_type=meta_type)
        return OneBotEvent.model_validate(data)


def _parse_notice(data: dict[str, object]) -> OneBotEvent:
    notice_type = str(data.get("notice_type", ""))

    if notice_type == "notify":
        sub_type = str(data.get("sub_type", ""))
        notify_cls = _NOTIFY_SUBTYPE_MAP.get(sub_type, NotifyEvent)
        return notify_cls.model_validate(data)

    notice_cls = _NOTICE_MAP.get(notice_type, NoticeEvent)
    return notice_cls.model_validate(data)


def _parse_request(data: dict[str, object]) -> OneBotEvent:
    req_type = data.get("request_type", "")
    if req_type == "friend":
        return FriendRequestEvent.model_validate(data)
    elif req_type == "group":
        return GroupRequestEvent.model_validate(data)
    else:
        return RequestEvent.model_validate(data)
