"""人员管理 API 请求体 Schema。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ResolveRequest(BaseModel):
    """批量解析用户和群 ID 到基本展示信息的请求体。"""

    user_ids: list[int] = Field(default_factory=list, max_length=200)
    group_ids: list[int] = Field(default_factory=list, max_length=200)
