"""Redis RPC 请求/响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RPCRequest(BaseModel):
    """Worker → 主进程的 RPC 请求。"""

    request_id: str
    """UUID 字符串，用于匹配对应的响应通道。"""

    action: str
    """OneBot 11 action 名称（如 send_group_msg）或自定义 action（如 request_checkin）。"""

    params: dict[str, object] = Field(default_factory=dict)
    """传递给 action 的参数字典。"""

    timeout: float = 30.0
    """调用方期望的超时秒数，RPCConsumer 会以此作为 BotAPI._call() 的超时。"""


class RPCResponse(BaseModel):
    """主进程 → Worker 的 RPC 响应。"""

    request_id: str
    """与 RPCRequest.request_id 匹配。"""

    success: bool
    """True 表示调用成功，False 表示发生错误。"""

    data: dict[str, object] | None = None
    """成功时为 APIResponse.model_dump() 序列化结果。"""

    error: str | None = None
    """失败时的错误描述。"""
