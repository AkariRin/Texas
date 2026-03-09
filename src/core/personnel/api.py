"""人事管理 REST API 路由 —— /api/v1/personnel。"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, TypeVar

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

if TYPE_CHECKING:
    from src.core.personnel.service import PersonnelService

logger = structlog.get_logger()

router = APIRouter(prefix="/v1/personnel", tags=["personnel"])
internal_router = APIRouter(prefix="/internal/personnel", tags=["personnel-internal"])

# ── 响应模型 ──

T = TypeVar("T")


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


# ── 依赖注入 ──


_personnel_service: PersonnelService | None = None
_sync_trigger_callback: Any = None  # 主进程同步触发回调


def set_personnel_api_deps(
    service: PersonnelService,
    sync_trigger: Any = None,
) -> None:
    global _personnel_service, _sync_trigger_callback
    _personnel_service = service
    _sync_trigger_callback = sync_trigger


def _get_service() -> PersonnelService:
    if _personnel_service is None:
        raise HTTPException(status_code=503, detail="Personnel service not initialized")
    return _personnel_service


# ── 用户管理 API (7.1) ──


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    relation: str | None = None,
    qq: int | None = None,
    nickname: str | None = None,
) -> dict[str, Any]:
    """分页查询用户列表。"""
    service = _get_service()
    result = await service.list_users(
        page=page, page_size=page_size, relation=relation, qq=qq, nickname=nickname
    )
    return {"code": 0, "data": result, "message": "ok"}


@router.get("/users/{qq}")
async def get_user(qq: int) -> dict[str, Any]:
    """获取单个用户详情。"""
    service = _get_service()
    user = await service.get_user(qq)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"code": 0, "data": user, "message": "ok"}


@router.get("/users/{qq}/groups")
async def get_user_groups(qq: int) -> dict[str, Any]:
    """获取用户所属的所有群聊。"""
    service = _get_service()
    groups = await service.get_user_groups(qq)
    return {"code": 0, "data": groups, "message": "ok"}


# ── 群聊管理 API (7.2) ──


@router.get("/groups")
async def list_groups(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    group_name: str | None = None,
    is_active: bool | None = None,
) -> dict[str, Any]:
    """分页查询群列表。"""
    service = _get_service()
    result = await service.list_groups(
        page=page, page_size=page_size, group_name=group_name, is_active=is_active
    )
    return {"code": 0, "data": result, "message": "ok"}


@router.get("/groups/{group_id}")
async def get_group(group_id: int) -> dict[str, Any]:
    """获取单个群聊详情。"""
    service = _get_service()
    group = await service.get_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return {"code": 0, "data": group, "message": "ok"}


@router.get("/groups/{group_id}/members")
async def list_group_members(
    group_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: str | None = None,
    nickname: str | None = None,
) -> dict[str, Any]:
    """分页获取群成员列表。"""
    service = _get_service()
    result = await service.list_group_members(
        group_id=group_id, page=page, page_size=page_size, role=role, nickname=nickname
    )
    return {"code": 0, "data": result, "message": "ok"}


# ── 同步管理 API (7.3) ──


@router.post("/sync")
async def trigger_sync() -> dict[str, Any]:
    """手动触发一次全量同步。"""
    if _sync_trigger_callback is None:
        raise HTTPException(status_code=503, detail="Sync trigger not configured")

    try:
        asyncio.create_task(_sync_trigger_callback())
        return {"code": 0, "data": None, "message": "Sync triggered"}
    except Exception as exc:
        logger.error("手动触发同步失败", error=str(exc), event_type="personnel.manual_sync_error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/sync/status")
async def get_sync_status() -> dict[str, Any]:
    """获取最近一次同步的状态。"""
    service = _get_service()
    status = await service.get_sync_status()
    return {"code": 0, "data": status, "message": "ok"}


# ── 管理员管理 API (7.4) ──


@router.get("/admins")
async def list_admins() -> dict[str, Any]:
    """获取所有管理员列表。"""
    service = _get_service()
    admins = await service.get_admins()
    return {"code": 0, "data": admins, "message": "ok"}


@router.post("/admins/{qq}/add")
async def add_admin(qq: int) -> dict[str, Any]:
    """添加管理员。"""
    service = _get_service()
    success = await service.set_admin(qq)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"code": 0, "data": None, "message": "Admin set successfully"}


@router.post("/admins/{qq}/delete")
async def remove_admin(qq: int) -> dict[str, Any]:
    """移除管理员。"""
    service = _get_service()
    success = await service.remove_admin(qq)
    if not success:
        raise HTTPException(status_code=404, detail="User not found or not an admin")
    return {"code": 0, "data": None, "message": "Admin removed successfully"}


# ── 内部 API (7.5) ──


@internal_router.post("/trigger-sync")
async def internal_trigger_sync() -> dict[str, Any]:
    """内部端点：触发主进程数据采集（供 Celery Beat 调用）。"""
    if _sync_trigger_callback is None:
        raise HTTPException(status_code=503, detail="Sync trigger not configured")

    try:
        asyncio.create_task(_sync_trigger_callback())
        return {"code": 0, "data": None, "message": "Sync triggered"}
    except Exception as exc:
        logger.error("内部触发同步失败", error=str(exc), event_type="personnel.internal_sync_error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
