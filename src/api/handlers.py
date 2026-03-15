"""处理器管理 API 端点。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from src.core.dependencies import get_scanner_controllers
from src.core.utils.response import ok

router = APIRouter()


@router.get("/handlers")
async def list_handlers(
    controllers: list[dict[str, Any]] = Depends(get_scanner_controllers),
) -> dict[str, Any]:
    """列出所有已注册的控制器及其处理器。"""
    return ok({"controllers": controllers})
