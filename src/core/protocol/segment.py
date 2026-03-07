"""消息段链式构建器 & CQ 码工具。"""

from __future__ import annotations

from .models.base import MessageSegment


class Seg:
    """用于构建 MessageSegment 实例的便捷工厂类（链式风格）。"""

    @staticmethod
    def text(text: str) -> MessageSegment:
        return MessageSegment(type="text", data={"text": text})

    @staticmethod
    def face(face_id: int) -> MessageSegment:
        return MessageSegment(type="face", data={"id": face_id})

    @staticmethod
    def image(file: str, **kw: object) -> MessageSegment:
        return MessageSegment(type="image", data={"file": file, **kw})

    @staticmethod
    def record(file: str, **kw: object) -> MessageSegment:
        return MessageSegment(type="record", data={"file": file, **kw})

    @staticmethod
    def video(file: str, **kw: object) -> MessageSegment:
        return MessageSegment(type="video", data={"file": file, **kw})

    @staticmethod
    def at(qq: str | int) -> MessageSegment:
        return MessageSegment(type="at", data={"qq": str(qq)})

    @staticmethod
    def reply(msg_id: int) -> MessageSegment:
        return MessageSegment(type="reply", data={"id": msg_id})

    @staticmethod
    def forward(forward_id: str) -> MessageSegment:
        return MessageSegment(type="forward", data={"id": forward_id})

    @staticmethod
    def json_msg(data: str | dict[str, object]) -> MessageSegment:
        return MessageSegment(type="json", data={"data": data})

    @staticmethod
    def music(type_: str, music_id: str | None = None, **kw: object) -> MessageSegment:
        d: dict[str, object] = {"type": type_}
        if music_id is not None:
            d["id"] = music_id
        d.update(kw)
        return MessageSegment(type="music", data=d)

    @staticmethod
    def poke(type_: str, poke_id: str) -> MessageSegment:
        return MessageSegment(type="poke", data={"type": type_, "id": poke_id})

    @staticmethod
    def dice() -> MessageSegment:
        return MessageSegment(type="dice", data={})

    @staticmethod
    def rps() -> MessageSegment:
        return MessageSegment(type="rps", data={})

    @staticmethod
    def contact(type_: str, contact_id: str) -> MessageSegment:
        return MessageSegment(type="contact", data={"type": type_, "id": contact_id})

    @staticmethod
    def node(
        node_id: int | None = None,
        content: list[object] | None = None,
        user_id: int | None = None,
        nickname: str | None = None,
    ) -> MessageSegment:
        d: dict[str, object] = {}
        if node_id is not None:
            d["id"] = node_id
        if content is not None:
            d["content"] = content
        if user_id is not None:
            d["user_id"] = user_id
        if nickname is not None:
            d["nickname"] = nickname
        return MessageSegment(type="node", data=d)

    @staticmethod
    def file(file: str, **kw: object) -> MessageSegment:
        return MessageSegment(type="file", data={"file": file, **kw})


class MessageBuilder:
    """链式消息构建器。

    用法：
        msg = MessageBuilder().text("Hello ").at(123456).text(" world!").build()
    """

    def __init__(self) -> None:
        self._segments: list[MessageSegment] = []

    def add(self, seg: MessageSegment) -> MessageBuilder:
        self._segments.append(seg)
        return self

    def text(self, text: str) -> MessageBuilder:
        return self.add(Seg.text(text))

    def face(self, face_id: int) -> MessageBuilder:
        return self.add(Seg.face(face_id))

    def image(self, file: str, **kw: object) -> MessageBuilder:
        return self.add(Seg.image(file, **kw))

    def record(self, file: str, **kw: object) -> MessageBuilder:
        return self.add(Seg.record(file, **kw))

    def at(self, qq: str | int) -> MessageBuilder:
        return self.add(Seg.at(qq))

    def reply(self, msg_id: int) -> MessageBuilder:
        return self.add(Seg.reply(msg_id))

    def build(self) -> list[MessageSegment]:
        return list(self._segments)
