# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目简介

Texas 是基于 NapCat / OneBot 11 协议的 QQ 机器人框架，采用 Python 后端 + Vue 3 前端的全栈架构。

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
alembic -c alembic.ini upgrade head          # 主库
alembic -c alembic_chat.ini upgrade head     # 聊天库

# Celery (异步任务)
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
```

## 架构概览

### 双数据库设计

- **主库** (`DATABASE_URL`): 用户、群聊、LLM 配置、管理员等核心业务数据
- **聊天库** (`CHAT_DATABASE_URL`): 独立 PostgreSQL 存储聊天记录，按月自动分区
- 两套独立的 Alembic 迁移配置：`alembic.ini` 和 `alembic_chat.ini`
- 迁移文件分别位于 `src/core/db/migrations/` 和 `src/core/chat/migrations/`

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

### 服务层 (`src/core/*/service.py`)

| 模块 | 服务 | 职责 |
|------|------|------|
| `chat/` | `ChatHistoryService`、`ArchiveService` | 聊天记录存储、按月分区、S3 归档 |
| `personnel/` | `PersonnelService`、`SyncCoordinator` | 用户/群聊 CRUD、定时从 NapCat 同步 |
| `llm/` | `LLMService` | LLM 提供商和模型配置管理 |

### WebSocket 连接管理 (`src/core/ws/`)

NapCat 主动反向连接 Texas，`ConnectionManager` 管理连接池，`HeartbeatMonitor` 负责心跳检测和自动重连。

### 异步任务 (`src/core/tasks/`)

Celery + RedBeat（Redis 存储调度状态），当前主要任务为定时同步用户/群聊数据。

### 前端架构

- **Pinia** 分模块状态管理（`stores/`），使用 `pinia-plugin-persistedstate` 做 localStorage 持久化
- **API 层** (`apis/`) 封装所有 HTTP 请求，通过 Axios + Vite 代理访问后端
- **Vuetify 4** 作为 UI 框架，路由对应关系见 `frontend/src/router/index.ts`

## 关键配置

- 环境变量参考 `.env` 文件，必须设置 `NAPCAT_ACCESS_TOKEN`
- 配置中心：`src/core/config.py`（Pydantic Settings，支持从环境变量或 `.env` 读取）
- 前端开发代理：Vite 将 `/api` 代理到本地后端，配置见 `frontend/vite.config.ts`
