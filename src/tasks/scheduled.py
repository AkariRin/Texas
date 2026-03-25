"""Celery Beat 定时任务调度配置（基于 RedBeat 持久化到 Redis）。"""

from __future__ import annotations

from celery.schedules import crontab
from redbeat import RedBeatSchedulerEntry

from src.core.config import get_settings
from src.core.tasks.celery_app import celery_app as celery_app

settings = get_settings()


def setup_periodic_tasks() -> None:
    """将周期性任务注册到 RedBeat（Redis），实现多实例安全的调度存储。"""

    # ── 聊天记录归档（每月 1 号凌晨 3:00） ──
    archive_entry = RedBeatSchedulerEntry(
        name="schedule-chat-archive",
        task="src.tasks.chat_archive.archive_chat_history",
        schedule=crontab(hour=3, minute=0, day_of_month=1),
        app=celery_app,
        options={"expires": 86400},
    )
    archive_entry.save()

    # ── 分区预创建（每月 25 号凌晨 1:00） ──
    partition_entry = RedBeatSchedulerEntry(
        name="schedule-chat-partition-ensure",
        task="src.tasks.chat_archive.ensure_chat_partitions",
        schedule=crontab(hour=1, minute=0, day_of_month=25),
        app=celery_app,
        options={"expires": 86400},
    )
    partition_entry.save()


# 模块加载时自动注册
setup_periodic_tasks()
