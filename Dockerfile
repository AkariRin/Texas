# 阶段 1：前端构建
FROM node:22-slim AS frontend-builder
RUN corepack enable
WORKDIR /build
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ .
RUN pnpm build

# 阶段 2：后端构建
FROM python:3.14-slim AS backend-builder
WORKDIR /build
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable
COPY src/ src/

# 阶段 3：运行时
FROM python:3.14-slim AS runtime
WORKDIR /app

# 创建非 root 用户
RUN groupadd -r texas && useradd -r -g texas texas

# 复制后端文件
COPY --from=backend-builder /build/.venv /app/.venv
COPY --from=backend-builder /build/src /app/src
COPY --from=backend-builder /build/pyproject.toml /app/pyproject.toml

# 复制前端构建产物
COPY --from=frontend-builder /build/dist /app/frontend/dist

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# 复制启动脚本
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

USER texas
EXPOSE 8000

# 通过子命令参数控制启动角色：bot（默认）| worker | beat
# 用法：docker run texas:latest [bot|worker|beat] [额外参数...]
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["bot"]
