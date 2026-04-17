# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目简介

Texas 是基于 NapCat / OneBot 11 协议的 QQ 机器人框架，采用 Python 后端 + Vue 3 前端的全栈架构。

## 团队规则（必读）

本项目强制遵守 `.claude/rules/` 下的团队规则，这些规则会自动加载到每次 Claude Code 会话中：

| 规则文件 | 覆盖范围 |
|----------|----------|
| `security.md` | Secrets 管理、输入校验、注入/XSS/CSRF 防护 |
| `coding-style.md` | 不可变优先、文件组织、错误处理、命名规范 |
| `git-workflow.md` | 提交格式、PR 流程、变更范围控制 |
| `performance.md` | 查询优化、异步并发、排障节奏 |

任何代码变更都必须符合上述规则。如有冲突，规则文件优先于本文件中的一般性描述。

## 常用命令

### 后端 (Python / uv)

```bash
# 启动开发服务器（--loop none 防止 Windows 上 reload 模式覆盖为 SelectorEventLoop，Playwright 需要 ProactorEventLoop）
uvicorn src.core.main:app --host 0.0.0.0 --port 8000 --reload --loop none

# Lint 和格式化
ruff check src --fix
ruff format src

# 类型检查
mypy src

# 数据库迁移
python -m src.core.db.cli migrate            # 升级所有库到 head
python -m src.core.db.cli migrate --target main   # 仅升级主库
python -m src.core.db.cli migrate --target chat   # 仅升级聊天库

# Celery (聊天归档异步任务)
celery -A src.core.tasks.celery_app worker --loglevel=info
celery -A src.core.tasks.celery_app beat -S redbeat.RedBeatScheduler --loglevel=info
```

### 前端 (Vue 3 / pnpm)

```bash
cd frontend

pnpm dev          # 开发服务器（代理 /api 到后端）
pnpm build        # 类型检查 + 生产构建
pnpm type-check   # vue-tsc 类型检查
pnpm lint         # 运行全部 lint（Oxlint + ESLint）
pnpm format       # Prettier 格式化
```

### 本地中间件

```bash
docker-compose -f compose.yaml up -d   # 启动 PostgreSQL + Redis + NapCat
```

### 生产镜像

```bash
docker build -t texas:latest .
# 通过环境变量 ROLE 控制启动角色: bot(默认) | worker | beat
# worker/beat 仅用于聊天归档 Celery 任务；人员同步由主进程内 SyncCoordinator 管理
```

### 快捷命令（Claude Code Slash Commands）

| 命令 | 说明 |
|------|------|
| `/project:lint` | 后端 ruff + 前端 pnpm lint，一键全栈 lint |
| `/project:typecheck` | mypy + vue-tsc 全栈类型检查 |
| `/project:dev` | 检查中间件 → 启动后端 + 前端 |
| `/project:new-handler` | 创建 Bot 事件处理器（带模板和约定提示）|
| `/project:new-api` | 创建 API 端点（后端路由 + 前端 API 层 8 步检查清单）|
| `/project:db-migrate` | 数据库迁移工作流（autogenerate → 检查 → 执行 → 验证）|

## 架构概览

### 双数据库设计

- **主库** (`DATABASE_URL`): 用户、群聊、LLM 配置、管理员等核心业务数据
- **聊天库** (`CHAT_DATABASE_URL`): 独立 PostgreSQL 存储聊天记录，按月自动分区
- 注册表驱动的迁移系统：`src/core/db/migration_registry.py` 统一管理所有库迁移目标
- 迁移文件统一位于 `src/core/db/migrations/{库名}/`：主库 `migrations/main/`，聊天库 `migrations/chat/`
- 统一 CLI 入口：`python -m src.core.db.cli`

### 事件驱动框架 (`src/core/framework/`)

核心事件分发采用职责链模式：
- `EventDispatcher` → `CompositeHandlerMapping` → 具体 Mapping 策略
- 内置多种路由策略：`CommandHandlerMapping`（`/cmd`）、`RegexHandlerMapping`、`KeywordHandlerMapping`、`EventTypeHandlerMapping` 等
- `ComponentScanner` 自动扫描 `src.handlers` 下的处理器，新处理器放在 `src/handlers/` 下即可自动注册
- 拦截器系统：`LoggingInterceptor`（Structlog 结构化日志）、`MetricsInterceptor`（Prometheus）

### Handler 开发约定

新 handler 通过装饰器注册到框架：

```python
from src.core.framework.decorators import (
    controller, on_command, Permission, MessageScope
)

@controller(
    name="echo",
    display_name="回声",
    description="复读用户消息",
    default_enabled=True,
)
class EchoHandler:
    @on_command("echo", permission=Permission.ANYONE, scope=MessageScope.group)
    async def handle(self, ctx: Context) -> None:
        ...
```

- `@controller` 同时在 `FeatureRegistry` 中注册功能元数据（用于权限管理页面）
- `default_enabled=False`（默认值）意味着管理员需在前端手动开启该功能
- `system=True` 的功能强制启用且不暴露给前端
- 交互式多轮会话见 `misc/interactive-session.md` 和 `src/core/framework/session/`

### 依赖注入模式

- FastAPI `lifespan` 上下文管理器负责服务初始化/清理
- 全局实例（`DatabaseEngine`、`RedisClient`、各 Service）挂载到 `app.state`
- 路由层通过 `Depends()` 获取依赖，避免全局变量

### 生命周期编排（`src/core/lifecycle/`）

新服务通过装饰器声明式注册，`LifecycleOrchestrator` 负责拓扑排序后按序启动/关闭：

```python
@startup(name="my_svc", provides=["my_svc"], requires=["browser"])
async def _start(deps: dict[str, Any]) -> dict[str, Any]:
    svc = MyService(deps["browser"])
    return {"my_svc": svc}

@shutdown(name="my_svc")
async def _stop(services: dict[str, Any]) -> None:
    await services["my_svc"].close()
```

`ComponentScanner` 扫描 `src.services` 时触发模块 import，装饰器自动注册到注册表。

### 浏览器渲染（`src/core/browser/`）

`BrowserService` 封装 Playwright Chromium 实例，通过 `LifecycleOrchestrator` 管理生命周期。
`MarkdownRenderer`（`src/core/utils/md2img.py`）基于 `BrowserService` 将 Markdown 渲染为 PNG 图片。

### 分层架构（Spring-like）

```
src/
├── core/        # 纯框架基础设施（db、cache、framework、protocol、ws、logging、monitoring、utils、config）
├── api/         # HTTP API 控制器层（FastAPI 路由）
├── services/    # 业务逻辑层（PersonnelService、LLMService、ChatHistoryService 等）
├── models/      # ORM 模型层（SQLAlchemy 实体定义，Alembic 注册入口）
├── handlers/    # Bot 事件处理器（ComponentScanner 自动扫描）
└── tasks/       # 空占位层（实际任务在 src/core/tasks/）
```

### 服务层 (`src/services/`)

| 文件 | 服务 | 职责 |
|------|------|------|
| `chat.py` | `ChatHistoryService` | 聊天记录存储、查询 |
| `chat_archive.py` | `ArchiveService` | 按月分区、S3 归档 |
| `archive_exporter.py` | `ArchiveExporter` | Parquet 流式导出 |
| `archive_s3.py` | `ArchiveS3` | S3 归档上传 |
| `personnel.py` | `PersonnelService` | 用户/群聊写操作（upsert、管理员管理）|
| `personnel_query.py` | `PersonnelQueryService` | 用户/群聊只读查询（SRP 拆分）|
| `personnel_events.py` | `PersonnelEventsService` | 好友/群成员增量事件处理 |
| `personnel_sync.py` | `SyncCoordinator` | 定时从 NapCat 同步用户数据 |
| `llm.py` | `LLMService` | LLM 提供商和模型配置管理 |
| `llm_client.py` | `LLMClient` | OpenAI 兼容客户端封装 |
| `llm_completion.py` | `llm_complete/llm_stream` | 高层 LLM 调用接口 |
| `permission.py` | `FeaturePermissionService` | 功能级权限管理 |
| `feedback.py` | `FeedbackService` | 用户反馈创建、查询、状态更新 |
| `jrlp.py` | `JrlpService` | 今日老婆随机抽取与记录 |
| `daily_checkin.py` | `DailyCheckinService` | 群签到（Celery Beat 零点触发，RPC 桥接）|
| `checkin.py` | `CheckinService` | 群签到业务逻辑（积分、排行、汇总统计）|
| `drift_bottle.py` | `DriftBottleService` | 漂流瓶（扔/捞漂流瓶、多池管理）|
| `browser.py` | 生命周期注册 | `BrowserService` 启动/关闭（Playwright Chromium）|
| `md_renderer.py` | 生命周期注册 | `MarkdownRenderer` 启动（Markdown→PNG 渲染）|

### WebSocket 连接管理 (`src/core/ws/`)

NapCat 主动反向连接 Texas，`ConnectionManager` 管理连接池，`HeartbeatMonitor` 负责心跳检测和自动重连。

### 异步任务 (`src/core/tasks/`)

> ⚠️ 注意：Celery 任务实际位于 `src/core/tasks/`（celery_app.py、chat_archive.py、daily_checkin.py）。`src/tasks/` 目前仅有空 `__init__.py`，是历史遗留路径。

Celery + RedBeat（Redis 存储调度状态），当前主要任务为聊天记录归档（`chat_archive.py`）。
用户同步已改为 `SyncCoordinator`（`src/services/personnel_sync.py`）内置 asyncio 调度，不再依赖 Celery。

**跨进程 RPC（`src/core/rpc/`）：** Celery Worker 运行在同步上下文，通过 `RPCBridge` 经 Redis pub/sub 调用主进程功能（如每日打卡）。新增需要调用主进程能力的 Celery 任务，应通过 `RPCBridge` 而非直接实例化 Service。

### 前端架构

- **Pinia** 分模块状态管理（`stores/`），使用 `pinia-plugin-persistedstate` 做 localStorage 持久化
- **API 层** (`apis/`) 封装所有 HTTP 请求，通过 Axios + Vite 代理访问后端
- **Vuetify 4** 作为 UI 框架，路由对应关系见 `frontend/src/router/index.ts`

## 关键配置

- 环境变量参考 `.env` 文件，必须设置 `NAPCAT_ACCESS_TOKEN`
- 配置中心：`src/core/config.py`（Pydantic Settings，支持从环境变量或 `.env` 读取）
- 前端开发代理：Vite 将 `/api` 代理到本地后端，配置见 `frontend/vite.config.ts`

## 代码风格

> 详细规则见 `.claude/rules/coding-style.md`（自动加载）。以下为工具链配置摘要：

- Python 行长限制 100，目标版本 py314，Ruff 规则集: E/F/W/I/N/UP/B/A/SIM/TCH
- 注意: 仓库存在 LF/CRLF 混用，新文件统一使用 LF

## API 约定

- 统一响应格式 `{code: 0, data, message}` / `{code: -1, data, message}`，使用 `src/core/utils/response.py` 的 `ok()` / `fail()`
- 后端 API 路由 `src/api/<module>.py` 与前端 `frontend/src/apis/<module>.ts` 一一对应
- 前端 API 层统一通过 `frontend/src/apis/client.ts` 的 Axios 实例发请求

## 详细文档

`misc/` 目录包含深入文档：
- `interactive-session.md` — 交互式多轮会话系统设计与用法
- `help-command-spec.md` — /help 指令功能规范
- `drift-bottle-design.md` — 漂流瓶功能数据模型与业务规则设计

## 测试

- 当前项目未配置测试框架（无 pytest/vitest），验证改动依赖 `ruff check`、`mypy`、`pnpm type-check`
