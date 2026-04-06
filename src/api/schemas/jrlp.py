"""今日老婆 API 请求/响应 Schema。"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class WifeRecordResponse(BaseModel):
    """单条记录响应体。"""

    id: int
    group_id: int
    user_id: int
    wife_qq: int
    wife_name: str
    date: date
    drawn_at: datetime | None


class PaginatedRecordsResponse(BaseModel):
    """分页记录响应体。"""

    items: list[WifeRecordResponse]
    total: int
    page: int
    page_size: int
    pages: int


class CreatePresetRequest(BaseModel):
    """创建预设请求体。"""

    group_id: int = Field(..., description="群号")
    user_id: int = Field(..., description="抽取者 QQ")
    wife_qq: int = Field(..., description="老婆 QQ")
    wife_name: str = Field(..., min_length=1, max_length=64, description="老婆昵称")
    date: date = Field(..., description="预设日期（北京时间自然日）")


class UpdateRecordRequest(BaseModel):
    """修改记录请求体。"""

    id: int = Field(..., description="记录 ID")
    wife_qq: int = Field(..., description="新老婆 QQ")
    wife_name: str = Field(..., min_length=1, max_length=64, description="新老婆昵称")


class DeleteRecordRequest(BaseModel):
    """删除预设请求体。"""

    id: int = Field(..., description="记录 ID（仅限 drawn_at=null 的预设记录）")
