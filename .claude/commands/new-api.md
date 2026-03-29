# /texas:new-api — 创建 API 端点

创建全栈 API 端点：后端路由 + 前端 API 层配对。

## 收集信息

若未提供，请询问：
- **模块名称**：英文（snake_case），如 `notification`
- **端点列表**：每个端点的 HTTP 方法、路径、功能描述
- **是否需要新 ORM 模型**：字段定义
- **是否需要新 Service**：方法签名
- **是否需要前端页面**：View + 路由

## 创建顺序（后端优先）

### 后端

**1. ORM 模型**（如需要）`src/models/<module>.py`
```python
"""<模块>数据模型。"""
from __future__ import annotations
from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column
from src.core.db.base import Base  # 或 ChatBase（聊天库）

class XxxModel(Base):
    __tablename__ = "<table_name>"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # ... 字段定义
```
在 `src/models/__init__.py` 中导出（让 Alembic 自动检测到）。

**2. Service 层**（如需要）`src/services/<module>.py`
```python
"""<模块>业务逻辑服务。"""
from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession

class XxxService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_xxx(self) -> list[dict]:
        ...
```

**3. 依赖注入** `src/core/dependencies.py`
- 在 `AppState` dataclass 中添加字段（如需全局状态）
- 添加 `get_xxx_service()` 函数：
```python
async def get_xxx_service(request: Request) -> XxxService:
    session = await get_db_session(request)
    return XxxService(session)
```

**4. API 路由** `src/api/<module>.py`
```python
"""<模块> REST API 路由 —— /api/v1/<module>。"""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.core.dependencies import get_xxx_service
from src.core.utils.response import ok, fail

if TYPE_CHECKING:
    from src.services.<module> import XxxService

router = APIRouter(prefix="/<module>", tags=["<module>"])

class XxxResponse(BaseModel):
    id: int
    # ...

@router.get("/")
async def list_xxx(
    service: XxxService = Depends(get_xxx_service),
) -> dict[str, Any]:
    """获取列表。"""
    result = await service.list_xxx()
    return ok(result)
```

**5. 注册路由** `src/api/router.py`
```python
from src.api.<module> import router as <module>_router
api_router.include_router(<module>_router)
```

### 前端

**6. API 层** `frontend/src/apis/<module>.ts`
```typescript
/**
 * <模块> API 接口层 —— 封装 /api/<module> 所有接口调用。
 */
import http from './client'
import type { ApiResponse } from './types'

export interface XxxItem {
  id: number
  // ...
}

const BASE = '/api/<module>'

export async function fetchXxxList(): Promise<XxxItem[]> {
  const { data } = await http.get<ApiResponse<XxxItem[]>>(`${BASE}/`)
  return data.data
}
```

**7. Store**（如需要）`frontend/src/stores/<module>.ts`
```typescript
import { ref } from 'vue'
import { defineStore } from 'pinia'
import * as api from '@/apis/<module>'

export const useXxxStore = defineStore('<module>', () => {
  const items = ref<api.XxxItem[]>([])
  const loading = ref(false)

  async function loadItems() {
    loading.value = true
    try {
      items.value = await api.fetchXxxList()
    } finally {
      loading.value = false
    }
  }

  return { items, loading, loadItems }
})
```

**8. View**（如需要）`frontend/src/views/<module>/XxxView.vue`
使用 Vuetify 4 组件。

**9. 路由注册**（如需要）`frontend/src/router/index.ts`
```typescript
{
  path: '/<module>',
  name: '<module>',
  component: () => import('@/views/<module>/XxxView.vue'),
  meta: { title: '<标题>', icon: 'mdi-xxx', subtitle: '<副标题>', group: '<分组>' },
}
```

## 参考文件

| 用途 | 文件 |
|------|------|
| 后端路由模板 | `src/api/personnel.py` |
| 依赖注入 | `src/core/dependencies.py` |
| 响应工具 | `src/core/utils/response.py` |
| 前端 API 模板 | `frontend/src/apis/personnel.ts` |
| 前端 Store 模板 | `frontend/src/stores/personnel.ts` |
| API 类型定义 | `frontend/src/apis/types.ts` |
| 路由配置 | `frontend/src/router/index.ts` |
