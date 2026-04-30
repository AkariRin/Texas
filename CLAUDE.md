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
| `/texas:audit` | 全量代码审计（bug、性能、规则违反检查）|
| `/texas:bump` | 版本号更新与打 Tag（解析参数 → 检查 → 执行）|
| `/texas:commit` | 生成 Conventional Commit 提交信息（支持拆分建议）|
| `/texas:db-migrate` | 数据库迁移工作流（autogenerate → 检查 → 执行 → 验证）|

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
- `ComponentScanner` 自动扫描 `src.handlers` 和 `src.core.handlers` 下的处理器，新 Bot 事件处理器放在 `src/handlers/` 下即可自动注册；系统级处理器（如 `personnel`）放在 `src/core/handlers/`
- 拦截器系统：`LoggingInterceptor`（Structlog 结构化日志）、`MetricsInterceptor`（Prometheus）

### Handler 开发约定

新 handler 通过装饰器注册到框架：

```python
from src.core.framework.decorators import (
    component, on_command, Permission, MessageScope
)

@component(
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

- `@component` 同时在 `FeatureRegistry` 中注册功能元数据（用于权限管理页面）
- `default_enabled=False`（默认值）意味着管理员需在前端手动开启该功能
- `system=True` 的功能强制启用且不暴露给前端
- 交互式多轮会话见 `src/core/framework/session/`

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
├── core/        # 框架基础设施（db、cache、framework、protocol、ws、logging、monitoring、utils、config）
│   ├── chat/        # 聊天领域包（archive、exporter、s3、main）
│   ├── llm/         # LLM 领域包（api、client、completion、schemas、main）
│   ├── personnel/   # 人员领域包（api、events、query、sync、main）
│   ├── permission/  # 权限领域包（checker、main）
│   ├── handlers/    # 系统级 Handler（如 personnel）
│   ├── registries/  # 注册表（feature、permission、service、config）
│   └── tasks/       # Celery 基础设施（celery_app、chat 归档调度）
├── apis/        # HTTP API 控制器层（FastAPI 路由，对应前端 apis/）
├── services/    # 功能业务服务（checkin、drift_bottle、jrlp、like 等）
├── models/      # ORM 模型层（SQLAlchemy 实体定义，Alembic 注册入口）
├── handlers/    # Bot 事件处理器（ComponentScanner 自动扫描）
└── tasks/       # 业务 Celery 任务（daily_checkin、daily_like、scheduled）
```

### 核心领域包 (`src/core/<domain>/`)

infra 重构后，基础设施服务按领域拆分为独立子包，被 `src/services/` 和 `src/handlers/` 复用：

**`src/core/chat/`** — 聊天领域

| 文件 | 服务/职责 |
|------|-----------|
| `main.py` | `ChatHistoryService`：聊天记录存储、查询 |
| `archive.py` | `ArchiveService`：按月分区、S3 归档（含 Celery 任务）|
| `exporter.py` | `ArchiveExporter`：Parquet 流式导出 |
| `s3.py` | `ArchiveS3`：S3 归档上传 |

**`src/core/llm/`** — LLM 领域

| 文件 | 服务/职责 |
|------|-----------|
| `main.py` | `LLMService`：LLM 提供商和模型配置管理 |
| `client.py` | `LLMClient`：OpenAI 兼容客户端封装 |
| `completion.py` | `llm_complete/llm_stream`：高层 LLM 调用接口 |
| `schemas.py` | Pydantic schemas：LLM 配置相关请求/响应模型 |
| `api.py` | FastAPI 路由：LLM 提供商/模型 CRUD |

**`src/core/personnel/`** — 人员领域

| 文件 | 服务/职责 |
|------|-----------|
| `main.py` | `PersonnelService`：用户/群聊写操作（upsert、管理员管理）|
| `query.py` | `PersonnelQueryService`：用户/群聊只读查询（SRP 拆分）|
| `events.py` | `PersonnelEventsService`：好友/群成员增量事件处理 |
| `sync.py` | `SyncCoordinator`：定时从 NapCat 同步用户数据 |
| `api.py` | FastAPI 路由：人员查询 API |

**`src/core/permission/`** — 权限领域

| 文件 | 服务/职责 |
|------|-----------|
| `main.py` | `FeaturePermissionService`：功能级权限管理 |
| `checker.py` | `PermissionChecker`：功能级权限校验辅助 |

### 功能业务服务层 (`src/services/`)

与功能 Handler 一一对应，通过生命周期装饰器注册：

| 文件 | 服务 | 职责 |
|------|------|------|
| `feedback.py` | `FeedbackService` | 用户反馈创建、查询、状态更新 |
| `jrlp.py` | `JrlpService` | 今日老婆随机抽取与记录 |
| `like.py` | `LikeService` | 点赞（手动点赞、定时任务注册/取消/查询）|
| `daily_checkin.py` | `DailyCheckinService` | 群签到（Celery Beat 零点触发，RPC 桥接）|
| `checkin.py` | `CheckinService` | 群签到业务逻辑（积分、排行、汇总统计）|
| `drift_bottle.py` | `DriftBottleService` | 漂流瓶（扔/捞漂流瓶、多池管理）|
| `browser.py` | 生命周期注册 | `BrowserService` 启动/关闭（Playwright Chromium）|
| `md_renderer.py` | 生命周期注册 | `MarkdownRenderer` 启动（Markdown→PNG 渲染）|

### WebSocket 连接管理 (`src/core/ws/`)

NapCat 主动反向连接 Texas，`ConnectionManager` 管理连接池，`HeartbeatMonitor` 负责心跳检测和自动重连。

### 异步任务

Celery + RedBeat（Redis 存储调度状态），任务分两层：

**基础设施层 `src/core/tasks/`**

| 文件 | 职责 |
|------|------|
| `celery_app.py` | Celery 应用实例定义 |
| `scheduled.py` | 注册 chat 归档周期任务到 RedBeat |
| `utils.py` | 任务工具函数 |

**业务任务层 `src/tasks/`**

| 文件 | 任务 | 触发方式 |
|------|------|---------|
| `daily_checkin.py` | 零点群签到（RPC 桥接主进程）| RedBeat cron |
| `daily_like.py` | 批量定时点赞（RPC 桥接主进程）| RedBeat cron |
| `scheduled.py` | 注册 checkin/like 周期任务到 RedBeat | 模块加载时自动执行 |

Chat 归档任务定义于 `src/core/chat/archive.py`（Celery 任务 ID：`src.core.chat.archive.*`），由 `src/core/tasks/scheduled.py` 调度。

定时调度一览：

| 任务 | 调度时间 | 调度文件 |
|------|---------|---------|
| 聊天归档 | 每月 1 日 03:00 | `src/core/tasks/scheduled.py` |
| 分区预创建 | 每月 25 日 01:00 | `src/core/tasks/scheduled.py` |
| 每日打卡 | 每天 00:00 | `src/tasks/scheduled.py` |
| 每日点赞 | 每天 00:00 | `src/tasks/scheduled.py` |

用户同步已改为 `SyncCoordinator`（`src/core/personnel/sync.py`）内置 asyncio 调度，不再依赖 Celery。

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
- 后端 API 路由 `src/apis/<module>.py` 与前端 `frontend/src/apis/<module>.ts` 一一对应（注意目录名为 `apis` 而非 `api`）
- 核心层 API 路由随领域包内聚：`src/core/llm/api.py`、`src/core/personnel/api.py`
- 前端 API 层统一通过 `frontend/src/apis/client.ts` 的 Axios 实例发请求

## 详细文档

`misc/` 目录当前包含 `NapCatDocs/`（NapCat 协议文档 git submodule）。
功能设计文档（交互式会话、漂流瓶等）已整合到代码注释和本 CLAUDE.md 中。

## 测试

### 后端 (pytest)

```bash
# 运行全部单元测试
uv run pytest tests/unit/

# 运行全部测试（含集成测试，需要数据库连接）
uv run pytest

# 带覆盖率报告
uv run pytest --cov=src --cov-report=term-missing
```

测试分布：`tests/unit/`（单元/框架测试）、`tests/integration/`（集成测试）

### 前端 (Vitest)

```bash
cd frontend
pnpm test        # 单次运行（CI 模式）
pnpm test:watch  # 监听模式（开发时使用）
```

前端测试位于 `frontend/src/__tests__/`（按 `composables/`、`utils/` 分类）。
