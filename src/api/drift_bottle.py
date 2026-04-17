"""漂流瓶管理 REST API —— /api/drift-bottle-pools。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path

from src.api.schemas.drift_bottle import (
    CreatePoolRequest,
    GroupAssignRequest,
    PoolGroupsResponse,
    PoolInfoResponse,
)
from src.core.dependencies import get_drift_bottle_service
from src.core.utils.response import ok

if TYPE_CHECKING:
    from src.services.drift_bottle import DriftBottleService

logger = structlog.get_logger()

router = APIRouter(prefix="/drift-bottle-pools", tags=["drift-bottle"])


@router.get("")
async def list_pools(
    service: DriftBottleService = Depends(get_drift_bottle_service),
) -> dict[str, Any]:
    """列出所有漂流瓶池，含各池未捞取瓶数统计。"""
    pools = await service.list_pools()
    return ok(
        [
            PoolInfoResponse(id=p.id, name=p.name, available_count=p.available_count).model_dump()
            for p in pools
        ]
    )


@router.post("")
async def create_pool(
    body: CreatePoolRequest,
    service: DriftBottleService = Depends(get_drift_bottle_service),
) -> dict[str, Any]:
    """创建新漂流瓶池。"""
    try:
        pool = await service.create_pool(body.name)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ok({"id": pool.id, "name": pool.name})


@router.post("/{pool_id}/delete")
async def delete_pool(
    pool_id: int = Path(..., description="池 id，0=默认池（不可删除）"),
    service: DriftBottleService = Depends(get_drift_bottle_service),
) -> dict[str, Any]:
    """删除漂流瓶池（id=0 的默认池不可删除）。"""
    try:
        await service.delete_pool(pool_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ok(None)


@router.get("/{pool_id}/groups")
async def list_pool_groups(
    pool_id: int = Path(..., description="池 id"),
    service: DriftBottleService = Depends(get_drift_bottle_service),
) -> dict[str, Any]:
    """列出指定池下所有群号。"""
    group_ids = await service.list_pool_groups(pool_id)
    return ok(PoolGroupsResponse(pool_id=pool_id, group_ids=group_ids).model_dump())


@router.post("/group-assign")
async def assign_group_pool(
    body: GroupAssignRequest,
    service: DriftBottleService = Depends(get_drift_bottle_service),
) -> dict[str, Any]:
    """将群分配到指定池；pool_id=0 表示移回默认池。"""
    try:
        await service.assign_group_pool(group_id=body.group_id, pool_id=body.pool_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(None)
