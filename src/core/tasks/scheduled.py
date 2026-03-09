"""Celery Beat 定时任务调度配置。"""

from __future__ import annotations

from src.core.config import Settings
from src.core.tasks.celery_app import celery_app

settings = Settings()

# 注册周期性任务
celery_app.conf.beat_schedule = {
    "schedule-personnel-sync": {
        "task": "src.core.tasks.personnel.schedule_personnel_sync",
        "schedule": settings.PERSONNEL_SYNC_INTERVAL,
        "options": {"expires": settings.PERSONNEL_SYNC_INTERVAL - 60},
    },
}

