"""OneBot 11 基础事件模型与枚举。"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class EventType(StrEnum):
    message = "message"
    message_sent = "message_sent"
    notice = "notice"
    request = "request"
    meta_event = "meta_event"


class MessageType(StrEnum):
    private = "private"
    group = "group"


class NoticeType(StrEnum):
    friend_add = "friend_add"
    friend_recall = "friend_recall"
    group_upload = "group_upload"
    group_admin = "group_admin"
    group_decrease = "group_decrease"
    group_increase = "group_increase"
    group_ban = "group_ban"
    group_recall = "group_recall"
    group_card = "group_card"
    essence = "essence"
    group_msg_emoji_like = "group_msg_emoji_like"
    notify = "notify"
    bot_offline = "bot_offline"


class RequestType(StrEnum):
    friend = "friend"
    group = "group"


class MetaEventType(StrEnum):
    lifecycle = "lifecycle"
    heartbeat = "heartbeat"


class Role(StrEnum):
    owner = "owner"
    admin = "admin"
    member = "member"


class OneBotEvent(BaseModel):
    """所有 OneBot 11 事件的基础模型。"""

    time: int
    self_id: int
    post_type: str

    class Config:
        extra = "allow"


class Sender(BaseModel):
    """消息发送者信息。"""

    user_id: int | None = None
    nickname: str | None = None
    sex: str | None = None
    age: int | None = None
    card: str | None = None
    role: str | None = None
    title: str | None = None
    level: str | None = None
    area: str | None = None
    group_id: int | None = None

    class Config:
        extra = "allow"


class Anonymous(BaseModel):
    """匿名发送者信息。"""

    id: int
    name: str
    flag: str

    class Config:
        extra = "allow"


class HeartbeatStatus(BaseModel):
    """心跳事件中的状态信息。"""

    online: bool | None = None
    good: bool = True

    class Config:
        extra = "allow"


class MessageSegment(BaseModel):
    """A single message segment in array format."""

    type: str
    data: dict[str, object] = Field(default_factory=dict)

    class Config:
        extra = "allow"
