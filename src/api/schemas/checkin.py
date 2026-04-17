"""用户群签到 API 请求/响应 Schema。"""

from __future__ import annotations

from datetime import date as date_
from datetime import datetime

from pydantic import BaseModel, Field


class CheckinRecordResponse(BaseModel):
    """单条签到记录响应体。"""

    id: int
    group_id: int
    user_id: int
    checkin_date: date_
    checkin_at: datetime


class PaginatedCheckinsResponse(BaseModel):
    """分页签到记录响应体。"""

    items: list[CheckinRecordResponse]
    total: int
    page: int
    page_size: int
    pages: int


class LeaderEntryResponse(BaseModel):
    """排行榜条目响应体。"""

    rank: int
    user_id: int
    value: int = Field(description="累计天数或连续天数，由请求 by 参数决定")


class DayCountResponse(BaseModel):
    """每日签到人数数据点。"""

    date: str
    count: int


class SummaryResponse(BaseModel):
    """汇总卡片数据响应体。"""

    total_checkins: int
    today_checkins: int
    active_users: int
