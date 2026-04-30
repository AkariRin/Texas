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

# 仅下载 Headless Shell 二进制（不含 Chrome for Testing + FFmpeg，节省约 170MB/平台）
# 项目仅用 headless=True 渲染，chromium-headless-shell 完全满足需求
ENV PLAYWRIGHT_BROWSERS_PATH=/build/.playwright-browsers
RUN /build/.venv/bin/playwright install chromium-headless-shell

# 阶段 3：运行时
FROM python:3.14-slim AS runtime
WORKDIR /app

# 消除 apt 交互式 debconf 警告，适用于后续所有 RUN 层
ENV DEBIAN_FRONTEND=noninteractive

# 创建非 root 用户
RUN groupadd -r texas && useradd -r -g texas texas

# 复制 Python 虚拟环境和 Chromium 二进制（均来自 builder，已与 playwright 版本绑定）
COPY --from=backend-builder /build/.venv /app/.venv
COPY --from=backend-builder /build/.playwright-browsers /app/.playwright-browsers

# 安装 Chromium 运行时系统库（libnss3 等，由 playwright 管理与当前版本精确匹配）
# fonts-noto-cjk：Noto CJK SC 字体，HTML 模板中优先级高于 playwright 自带的 WenQuanYi
# fonts-noto-color-emoji 已由 playwright install-deps 自动安装，无需重复声明
RUN /app/.venv/bin/python -m playwright install-deps chromium-headless-shell \
    && apt-get install -y --no-install-recommends fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# 复制业务代码
COPY --from=backend-builder /build/src /app/src
COPY --from=backend-builder /build/pyproject.toml /app/pyproject.toml

# 复制前端构建产物
COPY --from=frontend-builder /build/dist /app/frontend/dist

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/app/.playwright-browsers

# 复制启动脚本
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

USER texas
EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["bot"]
