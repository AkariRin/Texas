"""用户群签到管理 REST API —— /api/checkin。"""

from __future__ import annotations

from datetime import date  # noqa: TC003
from typing import TYPE_CHECKING, Any, Literal

import structlog
from fastapi import APIRouter, Depends, Query

from src.core.dependencies import get_user_checkin_service
from src.core.utils.helpers import ceil_div
from src.core.utils.response import ok

if TYPE_CHECKING:
    from src.services.checkin import CheckinService

logger = structlog.get_logger()

router = APIRouter(prefix="/checkin", tags=["checkin"])


def _record_to_dict(r: Any) -> dict[str, Any]:
    """将 CheckinRecord ORM 对象转为可序列化字典。"""
    return {
        "id": r.id,
        "group_id": r.group_id,
        "user_id": r.user_id,
        "checkin_date": r.checkin_date.isoformat(),
        "checkin_at": r.checkin_at.isoformat(),
    }


@router.get("/records")
async def list_records(
    group_id: int | None = Query(None, description="群号，不填则查询所有群"),
    user_id: int | None = Query(None),
    record_date: date | None = Query(None, alias="date"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: CheckinService = Depends(get_user_checkin_service),
) -> dict[str, Any]:
    """分页查询签到记录。"""
    records, total = await service.list_records(
        group_id=group_id,
        user_id=user_id,
        record_date=record_date,
        page=page,
        page_size=page_size,
    )
    pages = ceil_div(total, page_size)
    return ok(
        {
            "items": [_record_to_dict(r) for r in records],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
        }
    )


@router.get("/leaderboard")
async def get_leaderboard(
    group_id: int | None = Query(None, description="群号，不填则查询所有群"),
    by: Literal["total", "streak"] = Query("total"),
    limit: int = Query(20, ge=1, le=50),
    service: CheckinService = Depends(get_user_checkin_service),
) -> dict[str, Any]:
    """查询排行榜（累计或连续）。"""
    entries = await service.get_leaderboard(group_id=group_id, by=by, limit=limit)
    return ok(
        [{"rank": i + 1, "user_id": e.user_id, "value": e.value} for i, e in enumerate(entries)]
    )


@router.get("/trend")
async def get_daily_trend(
    group_id: int | None = Query(None, description="群号，不填则查询所有群"),
    days: int = Query(30, ge=7, le=90),
    service: CheckinService = Depends(get_user_checkin_service),
) -> dict[str, Any]:
    """查询最近 N 天每日签到人数趋势。"""
    trend = await service.get_daily_trend(group_id=group_id, days=days)
    return ok([{"date": d.date, "count": d.count} for d in trend])


@router.get("/summary")
async def get_summary(
    group_id: int | None = Query(None, description="群号，不填则查询所有群"),
    service: CheckinService = Depends(get_user_checkin_service),
) -> dict[str, Any]:
    """查询汇总卡片数据。"""
    summary = await service.get_summary(group_id=group_id)
    return ok(
        {
            "total_checkins": summary.total_checkins,
            "today_checkins": summary.today_checkins,
            "active_users": summary.active_users,
        }
    )
