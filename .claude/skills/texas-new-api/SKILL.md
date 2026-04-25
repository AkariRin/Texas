---
name: texas-new-api
description: Use when creating a new full-stack API endpoint in the Texas project. Covers backend FastAPI route, Pydantic schemas, dependency injection, router registration, and matching frontend TypeScript API layer.
---

# Texas: 创建全栈 API 端点

## 概述

Texas API 遵循「后端 `src/api/<module>.py` ↔ 前端 `frontend/src/apis/<module>.ts`」一一对应原则，统一响应格式 `{code, data, message}`。

## 8 步检查清单

- [ ] 1. 创建后端路由文件 `src/api/<module>.py`
- [ ] 2. 定义 Pydantic 请求/响应 Schema
- [ ] 3. 在 `src/core/dependencies.py` 添加 `get_xxx_service()` 函数
- [ ] 4. 在 `src/api/router.py` 注册新路由
- [ ] 5. 创建前端 API 层 `frontend/src/apis/<module>.ts`
- [ ] 6. 所有响应使用 `ok()` / `fail()` 包装
- [ ] 7. 路由路径使用 kebab-case（`/api/my-module`）
- [ ] 8. 验证：`pnpm type-check` + `mypy src`

## 后端路由模板

```python
"""<模块名> REST API 路由 —— /api/v1/<path>。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.core.dependencies import get_xxx_service
from src.core.utils.response import ok

if TYPE_CHECKING:
    from src.services.xxx import XxxService

logger = structlog.get_logger()

router = APIRouter(prefix="/xxx-items", tags=["xxx"])

# ── Schema ──

class CreateXxxRequest(BaseModel):
    name: str
    value: int

class XxxResponse(BaseModel):
    id: str
    name: str
    value: int
    created_at: str

# ── 端点 ──

@router.get("")
async def list_xxx(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: XxxService = Depends(get_xxx_service),
) -> dict[str, Any]:
    """分页查询列表。"""
    items, total = await service.list_items(page=page, page_size=page_size)
    return ok({"items": [i.to_dict() for i in items], "total": total})

@router.post("")
async def create_xxx(
    body: CreateXxxRequest,
    service: XxxService = Depends(get_xxx_service),
) -> dict[str, Any]:
    """创建新条目。"""
    item = await service.create(name=body.name, value=body.value)
    return ok({"id": str(item.id)})

@router.get("/{item_id}")
async def get_xxx(
    item_id: str,
    service: XxxService = Depends(get_xxx_service),
) -> dict[str, Any]:
    """获取单个条目。"""
    item = await service.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    return ok(item.to_dict())
```

## 依赖注入接入（`src/core/dependencies.py`）

```python
# 1. 在 AppState dataclass 新增字段（对应 lifespan 中注入的 key）
@dataclass
class AppState:
    ...
    xxx_service: XxxService   # ← 新增

# 2. 新增 Depends 函数
def get_xxx_service(request: Request) -> XxxService:
    """获取 Xxx 服务。"""
    return _state(request).xxx_service
```

## 路由注册（`src/api/router.py`）

```python
from src.api.xxx import router as xxx_router
...
api_router.include_router(xxx_router)
```

## 前端 API 层模板

```typescript
/**
 * Xxx API 接口层 —— 封装 /api/xxx-items 所有后端接口调用。
 */

import http from './client'
import type { ApiResponse, PaginatedResult } from './types'

// ── 类型 ──

export interface XxxItem {
  id: string
  name: string
  value: number
  created_at: string
}

export interface CreateXxxRequest {
  name: string
  value: number
}

export interface XxxListParams {
  page?: number
  page_size?: number
}

// ── API 调用 ──

const BASE = '/api/xxx-items'

export async function list(params: XxxListParams): Promise<PaginatedResult<XxxItem>> {
  const { data } = await http.get<ApiResponse<PaginatedResult<XxxItem>>>(BASE, {
    params,
  })
  return data.data
}

export async function get(id: string): Promise<XxxItem> {
  const { data } = await http.get<ApiResponse<XxxItem>>(`${BASE}/${id}`)
  return data.data
}

export async function create(body: CreateXxxRequest): Promise<{ id: string }> {
  const { data } = await http.post<ApiResponse<{ id: string }>>(BASE, body)
  return data.data
}
```

## 响应格式约定

```python
from src.core.utils.response import ok, fail

# 成功：code=0
return ok(data)
return ok(data, message="自定义成功消息")

# 失败：code=-1（通过 HTTPException 或 fail()）
raise HTTPException(status_code=400, detail="参数无效")
return fail("操作失败原因")
```

## 常见错误

| 错误 | 修复 |
|------|------|
| 路由不生效 | 检查 `router.py` 是否 `include_router` |
| `AttributeError: app.state.xxx` | `dependencies.py` 的 `AppState` 缺少字段，或 lifespan 未注入 |
| 前端 404 | 检查路径是否与后端 `prefix` + 方法路径一致，以及 Vite 代理配置 |
| 类型检查失败 | Service 仅在 `TYPE_CHECKING` 块导入；`Depends()` 参数类型注解要匹配 |
| 裸 `dict` 响应 | 所有路由返回类型注解为 `dict[str, Any]`，body 用 Pydantic Model |
