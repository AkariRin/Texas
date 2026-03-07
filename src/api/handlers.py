"""处理器管理 API 端点。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter()

# 将由 app.py 在启动时设置
_scanner_provider: Any = None


def set_scanner_provider(provider: Any) -> None:
    global _scanner_provider
    _scanner_provider = provider


@router.get("/handlers")
async def list_handlers() -> dict[str, Any]:
    """列出所有已注册的控制器及其处理器。"""
    controllers = []
    if _scanner_provider:
        controllers = _scanner_provider()
    return {
        "code": 0,
        "data": {"controllers": controllers},
        "message": "ok",
    }

