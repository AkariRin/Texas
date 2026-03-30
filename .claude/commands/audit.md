# /texas:audit — 全量代码审计

对 codebase 进行全面分析，找出潜在 bug、性能问题和违反项目规则的代码。

**用法：**
- `/texas:audit` — 全栈审计（默认）
- `/texas:audit backend` — 仅审计 Python 后端
- `/texas:audit frontend` — 仅审计 Vue 前端

当前范围：$ARGUMENTS（为空则默认 `all`）

## 审计维度

### 后端审计（`backend` 或 `all`）

扫描 `src/` 目录，逐模块检查：

**安全问题（Critical）**
- 硬编码的 secrets、token、密码（违反 `security.md`）
- SQL 字符串拼接（f-string/format/% 构造 SQL）
- `eval()`、`exec()`、`pickle.loads()` 处理外部数据
- API 路由接受裸 `dict` 或 `Any` 而非 Pydantic schema

**性能反模式（Warning）**
- N+1 查询：循环内的 `await session.get()` / `await session.execute()`
- 异步上下文中调用同步阻塞函数（`time.sleep`、同步 IO）
- 并发场景未使用 `asyncio.gather()` 而是串行 await
- 无分页的大表查询（缺少 `limit`/`offset`）

**代码质量（Warning）**
- 裸 `except:` 或 `except Exception:` 无日志记录
- `raise Exception(...)` 而非自定义异常类
- 函数/方法缺失类型注解
- 违反分层架构（API 层直接导入 ORM 模型、Service 层导入 FastAPI）
- 缺少 `from __future__ import annotations`

**规则违反（Info）**
- 可变默认参数 `def f(items=[])` / `def f(d={})`
- 模块缺少中文 docstring
- 公共函数缺少 docstring

### 前端审计（`frontend` 或 `all`）

扫描 `frontend/src/` 目录：

**安全问题（Critical）**
- `v-html` 绑定用户输入
- `localStorage` 存储敏感数据

**代码质量（Warning）**
- API 调用无 loading/error 状态处理
- `any` 类型滥用（非必要的 TypeScript `any`）
- Store 中未捕获的异步异常
- 组件超过 300 行（建议拆分）

**规则违反（Info）**
- `console.log` 遗留调试输出
- 未使用的 import 或变量（依赖 ESLint 结果）

## 输出格式

```
## 审计报告 — [范围] — [日期]

### 🔴 Critical（X 项）
| 文件 | 行号 | 问题 | 建议修复 |
|------|------|------|---------|
| ... | ... | ... | ... |

### 🟡 Warning（X 项）
...

### 🔵 Info（X 项）
...

### ✅ 未发现问题的模块
- src/core/framework/
- ...

---
总计：X Critical / X Warning / X Info
建议优先修复 Critical 项，其余可在独立 commit 中处理。
```

## 执行后行动

报告生成后，询问用户是否需要：
1. **逐项修复** — 从 Critical 开始，每次修复一个问题
2. **生成修复清单** — 保存为待办事项，分批处理
3. **仅查阅** — 不立即修改代码
