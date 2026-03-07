"""Bot 状态 API 端点。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter()

# 将由 app.py 在启动时设置
_status_provider: Any = None


def set_status_provider(provider: Any) -> None:
    global _status_provider
    _status_provider = provider


@router.get("/status")
async def get_status() -> dict[str, Any]:
    """获取 Bot 运行状态。"""
    if _status_provider:
        return _status_provider()
    return {
        "code": 0,
        "data": {
            "status": "running",
            "ws_connected": False,
            "handlers_registered": 0,
        },
        "message": "ok",
    }

