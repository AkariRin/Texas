"""统一 API 响应格式。

所有 REST API 端点均使用此模块的 ok() / fail() 构造响应，
确保前端收到一致的 {code, data, message} 结构。
"""

from __future__ import annotations

from typing import Any


def ok(data: Any = None, message: str = "ok") -> dict[str, Any]:
    """构造成功响应。"""
    return {"code": 0, "data": data, "message": message}


def fail(message: str, code: int = -1, data: Any = None) -> dict[str, Any]:
    """构造失败响应。"""
    return {"code": code, "data": data, "message": message}
