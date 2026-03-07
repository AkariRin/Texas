# ── Stage 1: Frontend Builder ──
FROM node:22-slim AS frontend-builder
RUN corepack enable
WORKDIR /build
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ .
RUN pnpm build

# ── Stage 2: Backend Builder ──
FROM python:3.14-slim AS backend-builder
WORKDIR /build
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable
COPY src/ src/
COPY main.py .

# ── Stage 3: Runtime ──
FROM python:3.14-slim AS runtime
WORKDIR /app

# Create non-root user
RUN groupadd -r texas && useradd -r -g texas texas

# Copy backend
COPY --from=backend-builder /build/.venv /app/.venv
COPY --from=backend-builder /build/src /app/src
COPY --from=backend-builder /build/main.py /app/main.py
COPY --from=backend-builder /build/pyproject.toml /app/pyproject.toml

# Copy frontend dist
COPY --from=frontend-builder /build/dist /app/frontend/dist

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

USER texas
EXPOSE 8000

# Default: bot-core. Override with ROLE=worker or ROLE=beat
ENV ROLE=bot
CMD if [ "$ROLE" = "worker" ]; then \
      celery -A src.core.tasks.celery_app worker --loglevel=info; \
    elif [ "$ROLE" = "beat" ]; then \
      celery -A src.core.tasks.celery_app beat --loglevel=info; \
    else \
      uvicorn src.core.app:app --host 0.0.0.0 --port 8000; \
    fi

