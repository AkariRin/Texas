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
| `llm.md` | LLM 模型配置、上下文窗口管理、调用规范 |

任何代码变更都必须符合上述规则。如有冲突，规则文件优先于本文件中的一般性描述。

## 常用命令

### 后端 (Python / uv)

```bash
# 启动开发服务器
uvicorn src.core.main:app --host 0.0.0.0 --port 8000 --reload

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
- 迁移文件分别位于 `src/core/db/migrations/`（主库）和 `src/core/db/chat_migrations/`（聊天库）
- 统一 CLI 入口：`python -m src.core.db.cli`（详见 `misc/db-migration.md`）

### 事件驱动框架 (`src/core/framework/`)

核心事件分发采用职责链模式：
- `EventDispatcher` → `CompositeHandlerMapping` → 具体 Mapping 策略
- 内置多种路由策略：`CommandHandlerMapping`（`/cmd`）、`RegexHandlerMapping`、`KeywordHandlerMapping`、`EventTypeHandlerMapping` 等
- `ComponentScanner` 自动扫描 `src.handlers` 下的处理器，新处理器放在 `src/handlers/` 下即可自动注册
- 拦截器系统：`LoggingInterceptor`（Structlog 结构化日志）、`MetricsInterceptor`（Prometheus）

### 依赖注入模式

- FastAPI `lifespan` 上下文管理器负责服务初始化/清理
- 全局实例（`DatabaseEngine`、`RedisClient`、各 Service）挂载到 `app.state`
- 路由层通过 `Depends()` 获取依赖，避免全局变量

### 分层架构（Spring-like）

```
src/
├── core/        # 纯框架基础设施（db、cache、framework、protocol、ws、logging、monitoring、utils、config）
├── api/         # HTTP API 控制器层（FastAPI 路由）
├── services/    # 业务逻辑层（PersonnelService、LLMService、ChatHistoryService 等）
├── models/      # ORM 模型层（SQLAlchemy 实体定义，Alembic 注册入口）
├── handlers/    # Bot 事件处理器（ComponentScanner 自动扫描）
└── tasks/       # Celery 业务任务（聊天归档等）
```

### 服务层 (`src/services/`)

| 文件 | 服务 | 职责 |
|------|------|------|
| `chat.py` | `ChatHistoryService` | 聊天记录存储、查询 |
| `chat_archive.py` | `ArchiveService` | 按月分区、S3 归档 |
| `personnel.py` | `PersonnelService` | 用户/群聊 CRUD |
| `personnel_sync.py` | `SyncCoordinator` | 定时从 NapCat 同步用户数据 |
| `llm.py` | `LLMService` | LLM 提供商和模型配置管理 |
| `llm_client.py` | `LLMClient` | OpenAI 兼容客户端封装 |
| `llm_completion.py` | `llm_complete/llm_stream` | 高层 LLM 调用接口 |
| `permission.py` | `FeaturePermissionService` | 功能级权限管理 |

### WebSocket 连接管理 (`src/core/ws/`)

NapCat 主动反向连接 Texas，`ConnectionManager` 管理连接池，`HeartbeatMonitor` 负责心跳检测和自动重连。

### 异步任务 (`src/tasks/`)

Celery + RedBeat（Redis 存储调度状态），当前主要任务为聊天记录归档（`chat_archive.py`）。
用户同步已改为 `SyncCoordinator`（`src/services/personnel_sync.py`）内置 asyncio 调度，不再依赖 Celery。

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

`misc/` 目录包含各模块深入文档：
- `architecture.md` — 框架架构与消息传递路径
- `db-migration.md` — 数据库迁移操作指南
- `chat-history.md` — 聊天记录模块设计
- `llm.md` — LLM 集成说明
- `personnel.md` — 人员模块说明

## 测试

- 当前项目未配置测试框架（无 pytest/vitest），验证改动依赖 `ruff check`、`mypy`、`pnpm type-check`
