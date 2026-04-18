"""点赞 API 请求/响应 Schema。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateLikeTaskRequest(BaseModel):
    """新增定时点赞任务请求体。"""

    qq: int = Field(..., description="被点赞用户 QQ 号", gt=0)
