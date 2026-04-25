"""点赞管理 REST API —— /api/like。"""

from __future__ import annotations

from datetime import date  # noqa: TC003 — FastAPI Query 参数运行时需要
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request

from src.apis.schemas.like import (  # noqa: TC001 — FastAPI Body 参数运行时需要
    CreateLikeTaskRequest,
    LikeHistoryResponse,
    LikeTaskResponse,
)
from src.core.utils.helpers import ceil_div
from src.core.utils.response import ok
from src.models.enums import LikeSource  # noqa: TC001 — FastAPI Query 枚举参数运行时需要
from src.services.like import LikeService  # noqa: TC001


def get_like_service(request: Request) -> LikeService:
    """获取点赞服务。"""
    registry = request.app.state.service_registry
    return registry.get_typed(LikeService, "like_service")  # type: ignore[no-any-return]


router = APIRouter(prefix="/like", tags=["like"])


@router.get("/tasks")
async def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: LikeService = Depends(get_like_service),
) -> dict[str, Any]:
    """分页查询已注册的定时点赞任务列表。"""
    items, total = await service.list_tasks(page=page, page_size=page_size)
    return ok(
        {
            "items": [LikeTaskResponse.model_validate(t).model_dump(mode="json") for t in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": ceil_div(total, page_size),
        }
    )


@router.post("/tasks")
async def create_task(
    body: CreateLikeTaskRequest,
    service: LikeService = Depends(get_like_service),
) -> dict[str, Any]:
    """新增定时点赞任务。"""
    result = await service.register_task(body.qq, group_id=None)
    if result.already_exists:
        raise HTTPException(status_code=409, detail="该用户已存在定时点赞任务")
    return ok({"qq": body.qq})


@router.post("/tasks/{qq}/cancel")
async def cancel_task(
    qq: int = Path(..., description="用户 QQ 号", gt=0),
    service: LikeService = Depends(get_like_service),
) -> dict[str, Any]:
    """取消指定用户的定时点赞任务。"""
    deleted = await service.cancel_task(qq)
    if not deleted:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ok({"qq": qq})


@router.get("/history")
async def list_history(
    qq: int | None = Query(None, description="按 QQ 过滤"),
    source: LikeSource | None = Query(None, description="按来源过滤：manual / scheduled"),
    date_from: date | None = Query(None, alias="date_from"),
    date_to: date | None = Query(None, alias="date_to"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: LikeService = Depends(get_like_service),
) -> dict[str, Any]:
    """分页查询点赞执行历史。"""
    items, total = await service.list_history(
        qq=qq,
        source=source,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return ok(
        {
            "items": [LikeHistoryResponse.model_validate(h).model_dump(mode="json") for h in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": ceil_div(total, page_size),
        }
    )
