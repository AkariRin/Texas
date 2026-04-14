"""Celery 应用实例 —— 异步任务队列基础设施。"""

from __future__ import annotations

from celery import Celery

from src.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "texas",
    broker=settings.CELERY_BROKER_URL,
    include=["src.core.tasks.chat_archive", "src.core.tasks.daily_checkin"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # 使用命名空间前缀区分 Broker 队列，支持与应用键共存于同一 Redis DB
    task_default_queue="texas:queue",
    # RedBeat：使用 Redis 作为 Beat 调度器存储
    beat_scheduler="redbeat.RedBeatScheduler",
    redbeat_redis_url=settings.CELERY_REDBEAT_URL,
    redbeat_key_prefix="texas:beat:",
)
