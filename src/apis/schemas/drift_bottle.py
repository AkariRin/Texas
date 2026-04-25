"""漂流瓶 API 请求/响应 Schema。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreatePoolRequest(BaseModel):
    """创建漂流瓶池请求体。"""

    name: str = Field(..., min_length=1, max_length=64, description="池名称")


class GroupAssignRequest(BaseModel):
    """群池分配请求体。"""

    group_id: int = Field(..., description="群号")
    pool_id: int = Field(..., ge=0, description="目标池 id，0=移回默认池")


class PoolInfoResponse(BaseModel):
    """漂流瓶池信息响应体。"""

    id: int
    name: str
    available_count: int = Field(description="当前未被捞取的漂流瓶数量")


class PoolGroupsResponse(BaseModel):
    """池下群列表响应体。"""

    pool_id: int
    group_ids: list[int]
