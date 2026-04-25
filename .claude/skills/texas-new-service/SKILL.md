---
name: texas-new-service
description: Use when adding a new service class in the Texas project. Covers @startup/@shutdown lifecycle registration, provides/requires dependency declaration, app.state injection, AppState dataclass extension, and optional @feature decorator for permission-aware services.
---

# Texas: 创建新 Service

## 概述

Texas 服务通过 `@startup` / `@shutdown` 声明式注册到生命周期系统。`LifecycleOrchestrator` 根据 `requires` 拓扑排序后按序启动，无需手动管理顺序。

## 5 步流程

```
1. 创建 Service 类（src/services/<name>.py）
2. 在同文件末尾注册 @startup / @shutdown
3. 扩展 AppState dataclass（src/core/dependencies.py）
4. 添加 get_xxx_service() Depends 函数（同上文件）
5. 在 API 路由或 Context 中使用
```

## Service 类 + 生命周期模板

```python
"""Xxx 服务 —— <功能描述>。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from src.core.lifecycle import shutdown, startup

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import async_sessionmaker

logger = structlog.get_logger()


class XxxService:
    """Xxx 服务 —— 提供 <功能> 能力。"""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def do_something(self, param: str) -> str:
        """执行某项操作。"""
        async with self._session_factory() as session:
            # ... 业务逻辑 ...
            return "result"


# ── 生命周期注册（文件末尾）──

@startup(
    name="xxx_service",
    provides=["xxx_service"],          # 向注册表暴露的键名 → app.state 属性名
    requires=["db"],                   # 依赖的服务键名（基础设施或其他 Service）
    # dispatcher_services=["xxx_service"],  # 若需向 EventDispatcher 注入，取消注释
)
async def _lifecycle_start(deps: dict[str, Any]) -> dict[str, Any]:
    """启动 Xxx 服务。"""
    session_factory = deps["db"]       # deps key 对应 requires 中声明的键
    svc = XxxService(session_factory=session_factory)
    return {"xxx_service": svc}        # 返回 key 必须与 provides 一致


@shutdown(name="xxx_service")
async def _lifecycle_stop(services: dict[str, Any]) -> None:
    """关闭 Xxx 服务（释放资源）。"""
    svc: XxxService = services["xxx_service"]
    # await svc.close()  # 若有需要关闭的资源
```

## 扩展 AppState（`src/core/dependencies.py`）

```python
# 1. 导入类型
if TYPE_CHECKING:
    ...
    from src.services.xxx import XxxService   # ← 新增

# 2. AppState dataclass 新增字段
@dataclass
class AppState:
    ...
    xxx_service: XxxService   # ← 新增，字段名必须与 @startup provides 键一致

# 3. 新增 Depends 函数
def get_xxx_service(request: Request) -> XxxService:
    """获取 Xxx 服务。"""
    return _state(request).xxx_service
```

## 常用 `requires` 依赖键参考

| 键名 | 说明 |
|------|------|
| `db` | 主库 `async_sessionmaker` |
| `chat_db` | 聊天库 `async_sessionmaker` |
| `cache` | Redis 缓存客户端 |
| `persistent_cache` | Redis 持久化客户端 |
| `bot_api` | OneBot API 客户端 |
| `browser` | Playwright 浏览器实例 |
| `personnel` | PersonnelService |
| `personnel_query` | PersonnelQueryService |

## 带权限感知的 Service（@feature）

若 Service 本身需要在前端权限管理页面显示：

```python
from src.core.framework.decorators import feature

@feature(
    name="xxx_service",
    display_name="Xxx 功能",
    description="功能简要描述",
    tags=["fun"],
    default_enabled=True,
)
class XxxService:
    ...
```

`@feature` 与 `@controller`（Handler 用）类似，但用于独立于 Handler 的 Service 级功能元数据。

## 在 Handler 中使用 Service

```python
# Handler 方法中（延迟导入避免循环）
async def handle(self, ctx: Context) -> bool:
    from src.services.xxx import XxxService
    if not ctx.has_service(XxxService):
        return False
    svc: XxxService = ctx.get_service(XxxService)
```

> `ctx.get_service()` 内部通过类型匹配在 `dispatcher_services` 中查找，
> 因此 **`@startup` 中 `dispatcher_services` 必须包含该服务键名**，否则 Handler 无法获取。

## 常见错误

| 错误 | 修复 |
|------|------|
| `AttributeError: 'AppState' object has no attribute 'xxx_service'` | `AppState` dataclass 未添加字段 |
| `KeyError: 'xxx_service'` in lifespan | `@startup provides` 键名与 `AppState` 字段名不一致 |
| Handler `ctx.get_service(XxxService)` 返回 None | `@startup` 未设置 `dispatcher_services=["xxx_service"]` |
| 服务未启动 | `src/services/xxx.py` 未被 import（`ComponentScanner` 扫描 `src.services.*`，确保文件在该目录）|
| 循环导入 | Service 类不要在模块级导入其他 Service；在方法体内延迟导入 |
