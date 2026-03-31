"""每日打卡服务 —— 定时在已启用群执行 NapCat 签到。

每天零点（Asia/Shanghai）及 WS 连接建立时触发，
通过 Redis 日期键去重，防止重启后重复打卡。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Final, Literal

import structlog

from src.core.cache.keys import checkin_key
from src.core.framework.decorators import feature
from src.core.utils import SHANGHAI_TZ
from src.models.personnel import Group

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from src.core.cache.client import CacheClient
    from src.core.protocol.api import BotAPI
    from src.core.ws.connection import ConnectionManager
    from src.services.permission import FeaturePermissionService

logger = structlog.get_logger()

# 打卡 Redis 键 TTL：25 小时（覆盖时区漂移，自动清理）
_CHECKIN_TTL: Final[int] = 90_000
# 群间发送延迟（秒），避免 QQ 限流
_SEND_DELAY: Final[float] = 1.5
# 此服务注册到权限系统的功能名
FEATURE_NAME: Final[str] = "daily_checkin"

CheckinSource = Literal["ws_connect", "scheduled"]


def _seconds_until_next_midnight() -> float:
    """计算距下一个 Asia/Shanghai 零点的秒数。"""
    now = datetime.now(SHANGHAI_TZ)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return (tomorrow - now).total_seconds()


@feature(
    name=FEATURE_NAME,
    display_name="每日打卡",
    description="每日零点自动在已启用群执行打卡签到",
    tags=["automation"],
    default_enabled=True,
    system=False,
)
class DailyCheckinService:
    """每日自动打卡协调器。

    调度模式与 ``SyncCoordinator`` 一致：asyncio 内进程调度 + 任务去重。
    打卡 API 使用 NapCat ``send_group_sign``，不发送文本消息。
    """

    __slots__ = (
        "_bot_api",
        "_conn_mgr",
        "_cache",
        "_permission_service",
        "_session_factory",
        "_current_task",
        "_scheduler_task",
    )

    def __init__(
        self,
        *,
        bot_api: BotAPI,
        conn_mgr: ConnectionManager,
        cache: CacheClient,
        permission_service: FeaturePermissionService,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._bot_api = bot_api
        self._conn_mgr = conn_mgr
        self._cache = cache
        self._permission_service = permission_service
        self._session_factory = session_factory
        self._current_task: asyncio.Task[None] | None = None
        self._scheduler_task: asyncio.Task[None] | None = None

    # ── 公共接口 ──

    @property
    def is_running(self) -> bool:
        """是否有打卡任务正在执行。"""
        return self._current_task is not None and not self._current_task.done()

    def request_checkin(self, *, source: CheckinSource = "ws_connect") -> asyncio.Task[None] | None:
        """请求执行一轮打卡。

        Args:
            source: 触发来源（``ws_connect`` 或 ``scheduled``）。

        Returns:
            新建的 Task，或 ``None``（已有任务运行中，跳过本次触发）。
        """
        if self.is_running:
            logger.debug(
                "打卡任务正在执行，跳过本次触发",
                source=source,
                event_type="checkin.skipped",
            )
            return None

        self._current_task = asyncio.create_task(
            self._run_checkin(), name=f"daily-checkin-{source}"
        )
        logger.info("打卡任务已创建", source=source, event_type="checkin.requested")
        return self._current_task

    def start_scheduler(self) -> None:
        """启动零点定时调度。"""
        if self._scheduler_task is not None and not self._scheduler_task.done():
            return
        self._scheduler_task = asyncio.create_task(
            self._scheduler_loop(), name="daily-checkin-scheduler"
        )
        logger.info("每日打卡定时调度已启动", event_type="checkin.scheduler_started")

    def stop_scheduler(self) -> None:
        """停止定时调度。"""
        if self._scheduler_task is not None and not self._scheduler_task.done():
            self._scheduler_task.cancel()
            logger.info("每日打卡定时调度已停止", event_type="checkin.scheduler_stopped")
        self._scheduler_task = None

    # ── 内部实现 ──

    async def _scheduler_loop(self) -> None:
        """asyncio 定时循环：每天零点（Asia/Shanghai）触发打卡。"""
        try:
            while True:
                wait_secs = _seconds_until_next_midnight()
                logger.debug(
                    "等待下次零点打卡",
                    wait_seconds=round(wait_secs),
                    event_type="checkin.scheduler_wait",
                )
                await asyncio.sleep(wait_secs)
                self.request_checkin(source="scheduled")
        except asyncio.CancelledError:
            return

    async def _run_checkin(self) -> None:
        """遍历所有符合条件的群，执行打卡。"""
        if not self._conn_mgr.connected:
            logger.warning("WS 未连接，跳过本轮打卡", event_type="checkin.aborted_no_ws")
            return

        today = datetime.now(SHANGHAI_TZ).strftime("%Y-%m-%d")
        group_ids = await self._get_eligible_group_ids()

        sent = skipped = failed = 0

        for group_id in group_ids:
            # Redis 去重：今日已打卡则跳过
            try:
                already_done = await self._cache.exists(checkin_key(group_id, today))
            except Exception:
                logger.warning(
                    "Redis 查询失败，跳过该群",
                    group_id=group_id,
                    event_type="checkin.redis_error",
                )
                skipped += 1
                continue

            if already_done:
                skipped += 1
                continue

            # 权限检查：群级功能开关
            try:
                enabled = await self._permission_service.is_group_feature_enabled(
                    group_id, FEATURE_NAME, FEATURE_NAME
                )
            except Exception:
                logger.warning(
                    "权限查询失败，跳过该群",
                    group_id=group_id,
                    event_type="checkin.perm_error",
                )
                skipped += 1
                continue

            if not enabled:
                skipped += 1
                continue

            # 执行打卡
            try:
                await self._bot_api.send_group_sign(group_id)
                await self._cache.set(checkin_key(group_id, today), "1", ttl=_CHECKIN_TTL)
                sent += 1
            except Exception:
                logger.warning(
                    "群打卡失败",
                    group_id=group_id,
                    event_type="checkin.send_error",
                )
                failed += 1

            await asyncio.sleep(_SEND_DELAY)

        logger.info(
            "本轮打卡完成",
            total=len(group_ids),
            sent=sent,
            skipped=skipped,
            failed=failed,
            event_type="checkin.round_done",
        )

    async def _get_eligible_group_ids(self) -> list[int]:
        """查询所有活跃且已开启 bot 的群 ID。"""
        from sqlalchemy import select

        async with self._session_factory() as session:
            result = await session.execute(
                select(Group.group_id).where(
                    Group.is_active.is_(True),
                    Group.bot_enabled.is_(True),
                )
            )
            return list(result.scalars().all())
