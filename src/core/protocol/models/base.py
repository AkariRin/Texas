"""OneBot 11 基础事件模型与枚举。"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class EventType(str, Enum):
    MESSAGE = "message"
    MESSAGE_SENT = "message_sent"
    NOTICE = "notice"
    REQUEST = "request"
    META = "meta_event"


class MessageType(str, Enum):
    PRIVATE = "private"
    GROUP = "group"


class NoticeType(str, Enum):
    FRIEND_ADD = "friend_add"
    FRIEND_RECALL = "friend_recall"
    GROUP_UPLOAD = "group_upload"
    GROUP_ADMIN = "group_admin"
    GROUP_DECREASE = "group_decrease"
    GROUP_INCREASE = "group_increase"
    GROUP_BAN = "group_ban"
    GROUP_RECALL = "group_recall"
    GROUP_CARD = "group_card"
    ESSENCE = "essence"
    GROUP_MSG_EMOJI_LIKE = "group_msg_emoji_like"
    NOTIFY = "notify"
    BOT_OFFLINE = "bot_offline"


class RequestType(str, Enum):
    FRIEND = "friend"
    GROUP = "group"


class MetaEventType(str, Enum):
    LIFECYCLE = "lifecycle"
    HEARTBEAT = "heartbeat"


class Role(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


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

