# 编码风格规则（强制执行）

补充 CLAUDE.md 中的格式化配置，约定代码组织和质量底线。

## 不可变优先

- 优先使用 `tuple` 代替 `list`、`frozenset` 代替 `set`（适用于不需要修改的集合）
- 函数/方法参数**禁止**使用可变默认值：`def f(items: list = [])` → 改用 `None` + 函数体初始化
- 模块级常量使用 `Final` 类型注解：`BASE_URL: Final = "https://..."`
- Pydantic 模型字段能用 `model_config = ConfigDict(frozen=True)` 的尽量冻结

## 文件组织（分层架构）

遵循现有 Spring-like 分层，新文件必须放在正确的层：

| 层 | 目录 | 放什么 |
|----|------|--------|
| 基础设施 | `src/core/` | 框架、协议、DB 引擎、缓存、工具函数 |
| API 控制器 | `src/api/` | FastAPI 路由，只做请求解析和响应组装 |
| 业务逻辑 | `src/services/` | 所有业务规则，可被 API 和 Handler 复用 |
| ORM 模型 | `src/models/` | SQLAlchemy 实体，不含业务逻辑 |
| Bot 处理器 | `src/handlers/` | 事件处理，调用 Service，不直接操作 DB |
| 异步任务 | `src/tasks/` | Celery 任务，调用 Service |

- API 路由禁止直接导入 ORM 模型或执行数据库查询，必须经过 Service 层
- Service 层禁止导入 FastAPI 相关模块（`Request`、`Depends` 等）

## 错误处理

- 业务异常使用自定义异常类（继承自 `src/core/` 中的基础异常），禁止直接 `raise Exception("...")`
- **禁止裸 `except:`**，必须捕获具体异常类型；需要兜底时用 `except Exception as e:` 并记录日志
- API 层所有响应必须通过 `src/core/utils/response.py` 的 `ok()` / `fail()` 包装
- 异步代码中的异常必须被 `await` 捕获或通过 `asyncio.TaskGroup` 传播，不得静默丢失

## 输入校验

- FastAPI 路由的请求体必须有对应的 **Pydantic schema**（不接受裸 `dict` 或 `Any`）
- 路径参数和查询参数使用 FastAPI 类型注解（`id: int`、`q: str = Query(..., min_length=1)`）
- Schema 定义放在 `src/api/schemas/` 或与路由文件同目录的 `schemas.py`

## 命名规范

- **Python**：变量/函数 `snake_case`，类 `PascalCase`，常量 `UPPER_SNAKE_CASE`，私有成员 `_prefix`
- **Vue 组件**：文件名 `PascalCase.vue`，组件内部变量遵循 camelCase
- **API 路由路径**：使用 kebab-case（`/api/chat-history`，非 `/api/chatHistory`）
- **数据库表名**：`snake_case` 复数形式（`chat_messages`，非 `ChatMessage`）

## 导入规范

每个 Python 模块**必须**包含：

```python
from __future__ import annotations
```

重型运行时导入（ORM 模型、Service 类等仅用于类型提示的导入）放在 `TYPE_CHECKING` 块：

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.models.user import User
```

导入顺序：标准库 → 第三方库 → 项目内部（遵循 isort / ruff I 规则）。

## 注释与文档

- 模块首行必须是中文 docstring：`"""模块描述。"""`
- 公共函数/方法必须有中文 docstring 说明用途和关键参数
- 内联注释使用中文，保持代码库语言统一
- 禁止提交 TODO/FIXME 注释，未完成的工作应开 Issue 追踪
