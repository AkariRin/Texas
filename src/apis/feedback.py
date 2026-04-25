"""用户反馈 REST API 路由 —— /api/v1/feedback。"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from src.core.utils.helpers import ceil_div
from src.core.utils.response import ok
from src.services.feedback import FeedbackService  # noqa: TC001

logger = structlog.get_logger()


def get_feedback_service(request: Request) -> FeedbackService:
    """获取反馈服务。"""
    registry = request.app.state.service_registry
    return registry.get_typed(FeedbackService, "feedback_service")  # type: ignore[no-any-return]


router = APIRouter(prefix="/feedbacks", tags=["feedback"])

# ── 请求/响应模型 ──


class UpdateStatusRequest(BaseModel):
    status: str
    admin_reply: str | None = None


class FeedbackResponse(BaseModel):
    id: str
    user_id: int
    group_id: int | None
    content: str
    status: str
    feedback_type: str | None
    source: str
    admin_reply: str | None
    created_at: str
    updated_at: str
    processed_at: str | None


class PaginatedFeedbackResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int
    pages: int


# ── 反馈管理 API ──


@router.get("")
async def list_feedbacks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    feedback_type: str | None = None,
    user_id: int | None = None,
    source: str | None = None,
    search: str | None = None,
    service: FeedbackService = Depends(get_feedback_service),
) -> dict[str, Any]:
    """分页查询反馈列表。"""
    from src.models.enums import FeedbackSource, FeedbackStatus, FeedbackType

    # 转换字符串参数为枚举（无效值返回 400）
    try:
        status_enum = FeedbackStatus(status) if status else None
        feedback_type_enum = FeedbackType(feedback_type) if feedback_type else None
        source_enum = FeedbackSource(source) if source else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"无效的筛选参数值: {exc}") from exc

    feedbacks, total = await service.list_feedbacks(
        page=page,
        page_size=page_size,
        status=status_enum,
        feedback_type=feedback_type_enum,
        user_id=user_id,
        source=source_enum,
        search=search,
    )

    pages = ceil_div(total, page_size)
    items = [
        {
            "id": str(f.id),
            "user_id": f.user_id,
            "group_id": f.group_id,
            "content": f.content,
            "status": f.status,
            "feedback_type": f.feedback_type if f.feedback_type else None,
            "source": f.source,
            "admin_reply": f.admin_reply,
            "created_at": f.created_at.isoformat(),
            "updated_at": f.updated_at.isoformat(),
            "processed_at": f.processed_at.isoformat() if f.processed_at else None,
        }
        for f in feedbacks
    ]

    result = {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }
    return ok(result)


@router.get("/{feedback_id}")
async def get_feedback(
    feedback_id: str,
    service: FeedbackService = Depends(get_feedback_service),
) -> dict[str, Any]:
    """获取单个反馈详情。"""
    from uuid import UUID

    try:
        fid = UUID(feedback_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="无效的 feedback_id 格式") from exc

    feedback = await service.get_feedback(fid)
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    data = {
        "id": str(feedback.id),
        "user_id": feedback.user_id,
        "group_id": feedback.group_id,
        "content": feedback.content,
        "status": feedback.status,
        "feedback_type": feedback.feedback_type if feedback.feedback_type else None,
        "source": feedback.source,
        "admin_reply": feedback.admin_reply,
        "created_at": feedback.created_at.isoformat(),
        "updated_at": feedback.updated_at.isoformat(),
        "processed_at": feedback.processed_at.isoformat() if feedback.processed_at else None,
    }
    return ok(data)


@router.post("/{feedback_id}/status")
async def update_feedback_status(
    feedback_id: str,
    body: UpdateStatusRequest,
    service: FeedbackService = Depends(get_feedback_service),
) -> dict[str, Any]:
    """更新反馈状态。"""
    from uuid import UUID

    from src.models.enums import FeedbackStatus

    try:
        fid = UUID(feedback_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="无效的 feedback_id 格式") from exc

    try:
        status_enum = FeedbackStatus(body.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"无效的状态值: {body.status}") from exc

    feedback = await service.update_status(fid, status_enum, body.admin_reply)
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return ok(None, message="Status updated successfully")
