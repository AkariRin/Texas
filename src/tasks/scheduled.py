"""业务 Celery Beat 定时任务调度配置（RedBeat）。"""

from __future__ import annotations

from celery.schedules import crontab
from redbeat import RedBeatSchedulerEntry

from src.core.tasks.main import app as celery_app


def setup_periodic_tasks() -> None:
    """注册业务周期任务到 RedBeat。"""

    RedBeatSchedulerEntry(
        name="schedule-daily-checkin",
        task="src.tasks.daily_checkin.trigger_daily_checkin",
        schedule=crontab(hour=0, minute=0),
        app=celery_app,
        options={"expires": 3600},
    ).save()

    RedBeatSchedulerEntry(
        name="schedule-daily-like",
        task="src.tasks.daily_like.trigger_daily_like",
        schedule=crontab(hour=0, minute=0),
        app=celery_app,
        options={"expires": 3600},
    ).save()


setup_periodic_tasks()
