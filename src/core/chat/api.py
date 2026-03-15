"""聊天记录 REST API 路由 —— /api/v1/chat。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.core.dependencies import get_archive_service, get_chat_service
from src.core.utils.response import ok

if TYPE_CHECKING:
    from src.core.chat.archive_service import ArchiveService
    from src.core.chat.service import ChatHistoryService

logger = structlog.get_logger()

router = APIRouter(prefix="/v1/chat", tags=["chat"])

# ── 请求模型 ──


class TriggerArchiveRequest(BaseModel):
    partition_name: str | None = None


# ════════════════════════════════════════════
#  概览 & 统计
# ════════════════════════════════════════════


@router.get("/overview")
async def get_overview(
    group_id: int | None = Query(default=None),
    svc: ChatHistoryService = Depends(get_chat_service),
) -> dict[str, Any]:
    """获取消息统计概览。"""
    result = await svc.get_overview_stats(group_id=group_id)
    return ok(result)


@router.get("/trend")
async def get_trend(
    group_id: int | None = Query(default=None),
    granularity: str = Query(default="day"),
    days: int = Query(default=30, ge=1, le=365),
    svc: ChatHistoryService = Depends(get_chat_service),
) -> dict[str, Any]:
    """获取消息趋势数据。"""
    result = await svc.get_trend_data(group_id=group_id, granularity=granularity, days=days)
    return ok(result)


@router.get("/heatmap")
async def get_heatmap(
    group_id: int | None = Query(default=None),
    svc: ChatHistoryService = Depends(get_chat_service),
) -> dict[str, Any]:
    """获取时段热力图数据。"""
    result = await svc.get_heatmap_data(group_id=group_id)
    return ok(result)


@router.get("/rankings/groups")
async def get_group_ranking(
    limit: int = Query(default=10, ge=1, le=100),
    svc: ChatHistoryService = Depends(get_chat_service),
) -> dict[str, Any]:
    """获取群消息量排行。"""
    result = await svc.get_group_ranking(limit=limit)
    return ok(result)


@router.get("/rankings/users")
async def get_user_ranking(
    group_id: int | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=100),
    svc: ChatHistoryService = Depends(get_chat_service),
) -> dict[str, Any]:
    """获取用户消息量排行。"""
    result = await svc.get_user_ranking(group_id=group_id, limit=limit)
    return ok(result)


@router.get("/stats")
async def get_stats(
    group_id: int | None = Query(default=None),
    svc: ChatHistoryService = Depends(get_chat_service),
) -> dict[str, Any]:
    """获取消息统计详情。"""
    result = await svc.get_message_stats(group_id=group_id)
    return ok(result)


# ════════════════════════════════════════════
#  消息查询
# ════════════════════════════════════════════


@router.get("/messages/group/{group_id}")
async def get_group_messages(
    group_id: int,
    before: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    keyword: str | None = Query(default=None),
    user_id: int | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    svc: ChatHistoryService = Depends(get_chat_service),
) -> dict[str, Any]:
    """获取群聊消息列表（游标分页）。"""
    before_dt = datetime.fromisoformat(before) if before else None
    start_dt = datetime.fromisoformat(start_date) if start_date else None
    end_dt = datetime.fromisoformat(end_date) if end_date else None

    result = await svc.get_group_messages(
        group_id=group_id,
        before=before_dt,
        limit=limit,
        keyword=keyword,
        user_id=user_id,
        start_date=start_dt,
        end_date=end_dt,
    )
    return ok(result)


@router.get("/messages/private/{user_id}")
async def get_private_messages(
    user_id: int,
    before: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    svc: ChatHistoryService = Depends(get_chat_service),
) -> dict[str, Any]:
    """获取私聊消息列表。"""
    before_dt = datetime.fromisoformat(before) if before else None
    result = await svc.get_private_messages(
        user_id=user_id,
        before=before_dt,
        limit=limit,
    )
    return ok(result)


@router.get("/messages/{message_id}/context")
async def get_message_context(
    message_id: int,
    created_at: str = Query(...),
    context: int = Query(default=5, ge=1, le=50),
    svc: ChatHistoryService = Depends(get_chat_service),
) -> dict[str, Any]:
    """获取消息上下文（前后 N 条）。"""
    created_at_dt = datetime.fromisoformat(created_at)
    result = await svc.get_message_context(
        message_id=message_id,
        created_at=created_at_dt,
        context_size=context,
    )
    return ok(result)


# ════════════════════════════════════════════
#  归档管理
# ════════════════════════════════════════════


@router.get("/archives")
async def get_archives(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: ArchiveService = Depends(get_archive_service),
) -> dict[str, Any]:
    """获取归档列表。"""
    result = await svc.get_archive_logs(page=page, page_size=page_size)
    return ok(result)


@router.post("/archives/trigger")
async def trigger_archive(
    body: TriggerArchiveRequest | None = None,
) -> dict[str, Any]:
    """手动触发归档任务。"""
    from src.core.tasks.chat_archive import archive_chat_history

    partition_name = body.partition_name if body else None
    task = archive_chat_history.delay(partition_name)
    return ok({"task_id": task.id}, message="Archive task queued")


@router.get("/archives/query")
async def query_archive(
    period_start: str = Query(...),
    group_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    svc: ArchiveService = Depends(get_archive_service),
) -> dict[str, Any]:
    """查询归档数据。"""
    result = await svc.query_archived_messages(
        period_start=period_start,
        group_id=group_id,
        limit=limit,
    )
    return ok(result)
