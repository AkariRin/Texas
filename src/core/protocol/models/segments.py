"""消息段类型定义（标准 + NapCat 扩展）。"""

from __future__ import annotations

from pydantic import BaseModel


class SegmentData(BaseModel):
    """消息段特定数据的基类。"""

    class Config:
        extra = "allow"


class TextData(SegmentData):
    text: str


class FaceData(SegmentData):
    id: int
    raw: str | None = None
    result_id: str | None = None
    chain_count: int | None = None


class ImageData(SegmentData):
    file: str
    name: str | None = None
    summary: str | None = None
    sub_type: int | None = None
    file_id: str | None = None
    url: str | None = None
    path: str | None = None
    file_size: int | None = None
    file_unique: str | None = None


class RecordData(SegmentData):
    file: str
    name: str | None = None
    file_id: str | None = None
    url: str | None = None
    path: str | None = None
    file_size: int | None = None
    file_unique: str | None = None


class VideoData(SegmentData):
    file: str
    name: str | None = None
    thumb: str | None = None
    file_id: str | None = None
    url: str | None = None
    path: str | None = None
    file_size: int | None = None
    file_unique: str | None = None


class AtData(SegmentData):
    qq: str  # numeric QQ or "all"


class ReplyData(SegmentData):
    id: int


class ForwardData(SegmentData):
    id: str
    content: list[object] | None = None


class MFaceData(SegmentData):
    """商城表情（NapCat 扩展）。"""

    emoji_id: str | None = None
    emoji_package_id: str | None = None
    key: str | None = None
    summary: str | None = None


class DiceData(SegmentData):
    result: int | None = None


class RpsData(SegmentData):
    result: int | None = None


class PokeData(SegmentData):
    type: str
    id: str


class FileData(SegmentData):
    file: str
    name: str | None = None
    file_id: str | None = None
    file_size: int | None = None
    file_unique: str | None = None
    path: str | None = None
    url: str | None = None


class JsonData(SegmentData):
    data: str | dict[str, object]


class MusicData(SegmentData):
    type: str  # qq | 163 | kugou | kuwo | migu | custom
    id: str | None = None
    url: str | None = None
    image: str | None = None
    singer: str | None = None
    title: str | None = None


class NodeData(SegmentData):
    """转发消息节点。"""

    id: int | None = None
    content: list[object] | None = None
    user_id: int | None = None
    nickname: str | None = None


class ContactData(SegmentData):
    type: str  # qq | group
    id: str


class MarkdownData(SegmentData):
    content: str | None = None


class ShareData(SegmentData):
    url: str | None = None
    title: str | None = None
    content: str | None = None
    image: str | None = None


class LocationData(SegmentData):
    lat: float | None = None
    lon: float | None = None
    title: str | None = None
    content: str | None = None

