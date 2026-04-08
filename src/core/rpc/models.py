"""Redis RPC 请求/响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RPCRequest(BaseModel):
    """Worker → 主进程的 RPC 请求。"""

    request_id: str
    """UUID 字符串，用于匹配对应的响应通道。"""

    action: str
    """action 名称（业务自定义，如 request_checkin）。"""

    params: dict[str, object] = Field(default_factory=dict)
    """传递给 action 的参数字典。"""

    timeout: float = 30.0
    """调用方期望的超时秒数，Consumer 侧将以此限制 handler 的最大执行时间。"""


class RPCResponse(BaseModel):
    """主进程 → Worker 的 RPC 响应。"""

    request_id: str
    """与 RPCRequest.request_id 匹配。"""

    success: bool
    """True 表示调用成功，False 表示发生错误。"""

    data: dict[str, object] | None = None
    """成功时为 handler 返回的数据字典。"""

    error: str | None = None
    """失败时的错误描述。"""
