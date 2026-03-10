"""Celery Beat 定时任务调度配置（基于 RedBeat 持久化到 Redis）。"""

from __future__ import annotations

from celery.schedules import schedule
from redbeat import RedBeatSchedulerEntry

from src.core.config import Settings
from src.core.tasks.celery_app import celery_app as celery_app

settings = Settings()


def setup_periodic_tasks() -> None:
    """将周期性任务注册到 RedBeat（Redis），实现多实例安全的调度存储。"""
    interval = settings.PERSONNEL_SYNC_INTERVAL

    entry = RedBeatSchedulerEntry(
        name="schedule-personnel-sync",
        task="src.core.tasks.personnel.schedule_personnel_sync",
        schedule=schedule(run_every=interval),
        app=celery_app,
        options={"expires": interval - 60},
    )
    entry.save()


# 模块加载时自动注册
setup_periodic_tasks()
