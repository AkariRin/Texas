"""OneBot 11 协议的 API 请求/响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class APIRequest(BaseModel):
    """通过 WebSocket 发送的 OneBot 11 API 请求。"""

    action: str
    params: dict[str, object] = Field(default_factory=dict)
    echo: str = ""


class APIResponse(BaseModel):
    """通过 WebSocket 接收的 OneBot 11 API 响应。"""

    status: str = ""  # ok | failed
    retcode: int = 0
    data: dict[str, object] | list[object] | None = None
    message: str | None = None
    wording: str | None = None
    echo: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "ok" and self.retcode == 0

    class Config:
        extra = "allow"

