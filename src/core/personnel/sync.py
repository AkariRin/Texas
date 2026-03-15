"""人事数据全量同步编排 —— 主进程采集 + Celery 写入。

将原本内联在 main.py lifespan 中的 ~50 行业务逻辑抽取为独立模块，
职责清晰，便于测试。
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from src.core.config import Settings
    from src.core.protocol.api import BotAPI
    from src.core.ws.connection import ConnectionManager

logger = structlog.get_logger()


async def do_personnel_sync(
    *,
    bot_api: BotAPI,
    conn_mgr: ConnectionManager,
    settings: Settings,
) -> None:
    """全量同步人事数据（主进程采集，Celery 写入）。

    流程：
    1. 等待初始延迟
    2. 获取好友列表
    3. 获取群列表
    4. 逐群获取成员列表（含限流延迟）
    5. 提交 Celery 异步写入任务
    """
    from src.core.monitoring.metrics import personnel_api_errors

    await asyncio.sleep(settings.PERSONNEL_SYNC_INITIAL_DELAY)

    if not conn_mgr.connected:
        logger.warning("连接已断开，取消人事同步", event_type="personnel.sync_aborted")
        return

    logger.info("开始人事数据同步", event_type="personnel.sync_start")

    try:
        # 1. 获取好友列表
        friends_resp = await bot_api.get_friend_list()
        friends_data = friends_resp.data if friends_resp.ok else None

        # 2. 获取群列表
        groups_resp = await bot_api.get_group_list()
        groups_data = groups_resp.data if groups_resp.ok else None

        # 3. 逐群获取成员列表
        members_data: dict[int, list[Any]] = {}
        if groups_data and isinstance(groups_data, list):
            for group in groups_data:
                if not conn_mgr.connected:
                    logger.warning("同步中途连接断开", event_type="personnel.sync_interrupted")
                    break

                group_id = group.get("group_id") if isinstance(group, dict) else None
                if not group_id:
                    continue

                try:
                    member_resp = await bot_api.get_group_member_list(int(group_id))
                    if member_resp.ok and isinstance(member_resp.data, list):
                        members_data[int(group_id)] = member_resp.data
                except Exception as exc:
                    personnel_api_errors.labels(action="get_group_member_list").inc()
                    logger.warning(
                        "获取群成员列表失败",
                        group_id=group_id,
                        error=str(exc),
                        event_type="personnel.api_error",
                    )

                await asyncio.sleep(settings.PERSONNEL_SYNC_API_DELAY)

        # 4. 提交 Celery 写入任务
        from src.core.tasks.personnel import persist_personnel_data

        members_serializable = {str(k): v for k, v in members_data.items()}
        persist_personnel_data.delay(
            friends=friends_data,
            groups=groups_data,
            members=members_serializable,
        )

        logger.info(
            "人事数据采集完成，已提交 Celery 写入任务",
            friends_count=len(friends_data) if friends_data else 0,
            groups_count=len(groups_data) if groups_data else 0,
            members_groups=len(members_data),
            event_type="personnel.sync_submitted",
        )

    except Exception as exc:
        logger.error(
            "人事数据同步失败",
            error=str(exc),
            event_type="personnel.sync_error",
        )

