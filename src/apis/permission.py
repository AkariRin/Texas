"""权限管理 REST API —— /api/v1/permissions。"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.core.services.permission import FeaturePermissionService  # noqa: TC001
from src.core.utils.response import ok

logger = structlog.get_logger()

router = APIRouter(prefix="/permissions", tags=["permissions"])


# ─────────────────────── 依赖 ───────────────────────


def get_permission_service(request: Request) -> FeaturePermissionService:
    """获取权限服务。"""
    registry = request.app.state.service_registry
    return registry.get_typed(FeaturePermissionService, "permission_service")  # type: ignore[no-any-return]


# ─────────────────────── Schema ───────────────────────


class FeatureUpdateBody(BaseModel):
    enabled: bool | None = None


class FeatureSetItem(BaseModel):
    feature_name: str
    enabled: bool


class GroupFeatureSetBody(BaseModel):
    features: list[FeatureSetItem]


class PrivateUserBody(BaseModel):
    user_qq: int
    enabled: bool = True


class PrivateUserRemoveBody(BaseModel):
    user_qq: int


class GroupSwitchBody(BaseModel):
    enabled: bool


# ─────────────────────── 功能树 ───────────────────────


@router.get("/features")
async def list_features(
    service: FeaturePermissionService = Depends(get_permission_service),
) -> dict[str, Any]:
    """获取功能树（controller + 子 methods，过滤系统功能）。"""
    features = await service.list_features()
    return ok(features)


@router.post("/features/{name:path}/update")
async def update_feature(
    name: str,
    body: FeatureUpdateBody,
    service: FeaturePermissionService = Depends(get_permission_service),
) -> dict[str, Any]:
    """更新功能全局启用状态（写入全局哨兵行）。"""
    result = await service.update_feature(name, enabled=body.enabled)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Feature '{name}' not found")
    return ok(result)


# ─────────────────────── 群聊权限 ───────────────────────


@router.get("/groups/{group_id}/features")
async def get_group_features(
    group_id: int,
    service: FeaturePermissionService = Depends(get_permission_service),
) -> dict[str, Any]:
    """获取某群所有功能的权限状态。"""
    perms = await service.get_group_permissions(group_id)
    return ok(perms)


@router.post("/groups/{group_id}/features")
async def set_group_features(
    group_id: int,
    body: GroupFeatureSetBody,
    service: FeaturePermissionService = Depends(get_permission_service),
) -> dict[str, Any]:
    """批量设置群功能状态。"""
    await service.batch_set_group_features(group_id, [f.model_dump() for f in body.features])
    return ok(None, message="ok")


@router.post("/groups/{group_id}/switch")
async def set_group_switch(
    group_id: int,
    body: GroupSwitchBody,
    service: FeaturePermissionService = Depends(get_permission_service),
) -> dict[str, Any]:
    """设置群聊 Bot 总开关。"""
    await service.set_group_enabled(group_id, body.enabled)
    return ok({"group_id": group_id, "bot_enabled": body.enabled})


# ─────────────────────── 私聊权限 ───────────────────────


@router.get("/features/{name}/private-users")
async def get_private_users(
    name: str,
    service: FeaturePermissionService = Depends(get_permission_service),
) -> dict[str, Any]:
    """获取私聊用户权限列表（含 enabled 状态）。"""
    users = await service.get_private_permissions(name)
    return ok(users)


@router.post("/features/{name}/private-users")
async def add_private_user(
    name: str,
    body: PrivateUserBody,
    service: FeaturePermissionService = Depends(get_permission_service),
) -> dict[str, Any]:
    """设置用户私聊权限（upsert）。"""
    await service.set_private_permission(name, body.user_qq, body.enabled)
    return ok(None, message="ok")


@router.post("/features/{name}/private-users/remove")
async def remove_private_user(
    name: str,
    body: PrivateUserRemoveBody,
    service: FeaturePermissionService = Depends(get_permission_service),
) -> dict[str, Any]:
    """删除用户私聊权限记录（恢复为全局默认）。"""
    await service.remove_private_user(name, body.user_qq)
    return ok(None, message="ok")


# ─────────────────────── 权限矩阵 ───────────────────────


@router.get("/matrix")
async def get_permission_matrix(
    service: FeaturePermissionService = Depends(get_permission_service),
) -> dict[str, Any]:
    """获取完整权限矩阵（所有活跃群 × 所有活跃功能，过滤系统功能）。"""
    matrix = await service.get_permission_matrix()
    return ok(matrix)
