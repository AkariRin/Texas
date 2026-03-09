"""Celery 应用实例 —— 异步任务队列基础设施。"""

from __future__ import annotations

from celery import Celery

from src.core.config import Settings

settings = Settings()

celery_app = Celery(
    "texas",
    broker=settings.CELERY_BROKER_URL,
    include=["src.core.tasks.personnel"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

