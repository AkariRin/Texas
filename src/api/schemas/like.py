"""点赞 API 请求/响应 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.models.enums import LikeSource  # noqa: TC001 — Pydantic 字段类型运行时需要


class OrmBaseModel(BaseModel):
    """ORM 对象反序列化基类。"""

    model_config = ConfigDict(from_attributes=True)


class CreateLikeTaskRequest(BaseModel):
    """新增定时点赞任务请求体。"""

    qq: int = Field(..., description="被点赞用户 QQ 号", gt=0)


class LikeTaskResponse(OrmBaseModel):
    """定时点赞任务响应体。"""

    id: int
    qq: int
    registered_at: datetime
    registered_group_id: int | None


class LikeHistoryResponse(OrmBaseModel):
    """点赞历史记录响应体。"""

    id: int
    qq: int
    times: int
    triggered_at: datetime
    source: LikeSource
    success: bool
