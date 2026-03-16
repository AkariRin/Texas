"""用户管理 REST API 路由 —— /api/v1/personnel。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.core.dependencies import get_personnel_service, get_sync_coordinator
from src.core.utils.response import ok

if TYPE_CHECKING:
    from src.core.personnel.service import PersonnelService
    from src.core.personnel.sync import SyncCoordinator

logger = structlog.get_logger()

router = APIRouter(prefix="/v1/personnel", tags=["personnel"])

# ── 响应模型 ──


class UserResponse(BaseModel):
    qq: int
    nickname: str
    relation: str
    group_count: int
    last_synced: str | None


class GroupResponse(BaseModel):
    group_id: int
    group_name: str
    member_count: int
    max_member_count: int
    is_active: bool
    last_synced: str | None


class GroupMemberResponse(BaseModel):
    qq: int
    nickname: str
    card: str
    role: str
    relation: str
    join_time: int
    last_active_time: int
    title: str


class SyncStatusResponse(BaseModel):
    last_sync_time: str | None
    duration_seconds: float | None
    status: str
    users_synced: int
    groups_synced: int
    memberships_synced: int


class PaginatedResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int
    pages: int


class AdminActionRequest(BaseModel):
    qq: int


# ── 用户管理 API (7.1) ──


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    relation: str | None = None,
    qq: int | None = None,
    nickname: str | None = None,
    service: PersonnelService = Depends(get_personnel_service),
) -> dict[str, Any]:
    """分页查询用户列表。"""
    result = await service.list_users(
        page=page, page_size=page_size, relation=relation, qq=qq, nickname=nickname
    )
    return ok(result)


@router.get("/users/{qq}")
async def get_user(
    qq: int,
    service: PersonnelService = Depends(get_personnel_service),
) -> dict[str, Any]:
    """获取单个用户详情。"""
    user = await service.get_user(qq)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return ok(user)


@router.get("/users/{qq}/groups")
async def get_user_groups(
    qq: int,
    service: PersonnelService = Depends(get_personnel_service),
) -> dict[str, Any]:
    """获取用户所属的所有群聊。"""
    groups = await service.get_user_groups(qq)
    return ok(groups)


# ── 群聊管理 API (7.2) ──


@router.get("/groups")
async def list_groups(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    group_name: str | None = None,
    is_active: bool | None = None,
    service: PersonnelService = Depends(get_personnel_service),
) -> dict[str, Any]:
    """分页查询群列表。"""
    result = await service.list_groups(
        page=page, page_size=page_size, group_name=group_name, is_active=is_active
    )
    return ok(result)


@router.get("/groups/{group_id}")
async def get_group(
    group_id: int,
    service: PersonnelService = Depends(get_personnel_service),
) -> dict[str, Any]:
    """获取单个群聊详情。"""
    group = await service.get_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return ok(group)


@router.get("/groups/{group_id}/members")
async def list_group_members(
    group_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: str | None = None,
    nickname: str | None = None,
    service: PersonnelService = Depends(get_personnel_service),
) -> dict[str, Any]:
    """分页获取群成员列表。"""
    result = await service.list_group_members(
        group_id=group_id, page=page, page_size=page_size, role=role, nickname=nickname
    )
    return ok(result)


# ── 同步管理 API (7.3) ──


@router.post("/sync")
async def trigger_sync(
    coordinator: SyncCoordinator = Depends(get_sync_coordinator),
) -> dict[str, Any]:
    """手动触发一次全量同步。"""
    try:
        task = coordinator.request_sync(source="manual")
        if task is None:
            return ok(None, message="Sync already in progress, skipped")
        return ok(None, message="Sync triggered")
    except Exception as exc:
        logger.error("手动触发同步失败", error=str(exc), event_type="personnel.manual_sync_error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/sync/status")
async def get_sync_status(
    service: PersonnelService = Depends(get_personnel_service),
) -> dict[str, Any]:
    """获取最近一次同步的状态。"""
    status = await service.get_sync_status()
    return ok(status)


# ── 管理员管理 API (7.4) ──


@router.get("/admins")
async def list_admins(
    service: PersonnelService = Depends(get_personnel_service),
) -> dict[str, Any]:
    """获取所有管理员列表。"""
    admins = await service.get_admins()
    return ok(admins)


@router.post("/admins/{qq}/add")
async def add_admin(
    qq: int,
    service: PersonnelService = Depends(get_personnel_service),
) -> dict[str, Any]:
    """添加管理员。"""
    success = await service.set_admin(qq)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return ok(None, message="Admin set successfully")


@router.post("/admins/{qq}/delete")
async def remove_admin(
    qq: int,
    service: PersonnelService = Depends(get_personnel_service),
) -> dict[str, Any]:
    """移除管理员。"""
    success = await service.remove_admin(qq)
    if not success:
        raise HTTPException(status_code=404, detail="User not found or not an admin")
    return ok(None, message="Admin removed successfully")


