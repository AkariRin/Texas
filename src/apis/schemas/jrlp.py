"""今日老婆 API 请求/响应 Schema。"""

from __future__ import annotations

from datetime import date as date_
from datetime import datetime

from pydantic import BaseModel, Field


class WifeRecordResponse(BaseModel):
    """单条记录响应体。"""

    id: int
    group_id: int
    user_id: int
    user_nickname: str
    wife_qq: int
    wife_nickname: str
    date: date_
    drawn_at: datetime | None


class PaginatedRecordsResponse(BaseModel):
    """分页记录响应体。"""

    items: list[WifeRecordResponse]
    total: int
    page: int
    page_size: int
    pages: int


class SetWifeRequest(BaseModel):
    """手动设置老婆请求体（创建预设）。"""

    group_id: int = Field(..., description="群号")
    user_id: int = Field(..., description="抽取者 QQ")
    wife_qq: int = Field(..., description="老婆 QQ")
    date: date_ = Field(..., description="日期（北京时间自然日）")


class UpdateRecordRequest(BaseModel):
    """修改记录请求体。"""

    id: int = Field(..., description="记录 ID")
    wife_qq: int = Field(..., description="新老婆 QQ")


class DeleteRecordRequest(BaseModel):
    """删除记录请求体。"""

    id: int = Field(..., description="记录 ID")
