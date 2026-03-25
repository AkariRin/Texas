"""用户数据全量同步编排 —— 主进程采集 + 写入 + 定时调度。

通过 ``SyncCoordinator`` 集中管理同步任务的生命周期，
所有触发入口（WS 连接、API 手动触发、内置定时调度）
统一调用 ``coordinator.request_sync()``, 从结构上杜绝重复触发。
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, Literal

import structlog

if TYPE_CHECKING:
    from src.core.config import Settings
    from src.core.protocol.api import BotAPI
    from src.core.ws.connection import ConnectionManager
    from src.services.personnel import PersonnelService

logger = structlog.get_logger()

SyncSource = Literal["ws_connect", "manual", "scheduled"]


class SyncCoordinator:
    """用户数据同步协调器 —— 确保同一时刻最多只有一个同步任务运行。

    所有同步触发入口（WS 首连、手动 API、内置定时调度）均通过
    ``request_sync()`` 统一调度，不再由调用方自行 ``create_task``。

    防重机制（两层）：
    1. **任务去重**：``_current_task`` 未完成时，新请求直接跳过。
    2. **冷却窗口**：定时触发（``source="scheduled"``）在最近一次同步
       启动后的 ``min_sync_gap`` 秒内会被静默忽略，避免定时调度
       与 WS 首连触发产生时间窗口重叠。
    """

    __slots__ = (
        "_bot_api",
        "_conn_mgr",
        "_personnel_service",
        "_settings",
        "_current_task",
        "_last_sync_start",
        "_min_sync_gap",
        "_scheduler_task",
    )

    def __init__(
        self,
        *,
        bot_api: BotAPI,
        conn_mgr: ConnectionManager,
        personnel_service: PersonnelService,
        settings: Settings,
    ) -> None:
        self._bot_api = bot_api
        self._conn_mgr = conn_mgr
        self._personnel_service = personnel_service
        self._settings = settings
        self._current_task: asyncio.Task[None] | None = None
        self._last_sync_start: float = 0.0  # monotonic 时间戳
        # 冷却窗口：同步间隔的一半，至少 30 秒
        self._min_sync_gap: float = max(settings.PERSONNEL_SYNC_INTERVAL / 2, 30.0)
        self._scheduler_task: asyncio.Task[None] | None = None

    # ── 公共接口 ──

    @property
    def is_running(self) -> bool:
        """是否有同步任务正在执行."""
        return self._current_task is not None and not self._current_task.done()

    def request_sync(self, *, source: SyncSource = "manual") -> asyncio.Task[None] | None:
        """请求一次全量同步。

        Args:
            source: 触发来源。
                - ``"ws_connect"``  — WS 首连触发（仅在无任务运行时生效）
                - ``"manual"``      — 用户手动触发（仅在无任务运行时生效）
                - ``"scheduled"``   — 定时调度触发（额外受冷却窗口约束）

        Returns:
            新创建的 Task —— 如果成功发起同步。
            ``None`` —— 如果本次请求被跳过。
        """
        # 层 1：任务去重 —— 正在执行则直接跳过
        if self.is_running:
            logger.debug(
                "同步正在执行，跳过触发",
                source=source,
                event_type="personnel.sync_skipped",
            )
            return None

        # 层 2：冷却窗口 —— 仅约束定时触发
        if source == "scheduled":
            elapsed = time.monotonic() - self._last_sync_start
            if elapsed < self._min_sync_gap:
                logger.debug(
                    "距上次同步间隔不足，跳过定时触发",
                    source=source,
                    elapsed=round(elapsed, 1),
                    min_gap=self._min_sync_gap,
                    event_type="personnel.sync_cooldown",
                )
                return None

        self._last_sync_start = time.monotonic()
        self._current_task = asyncio.create_task(self._run_sync(), name="personnel-sync")
        logger.info(
            "同步任务已创建",
            source=source,
            event_type="personnel.sync_requested",
        )
        return self._current_task

    def start_scheduler(self) -> None:
        """启动内置定时调度（asyncio 周期任务）。"""
        if self._scheduler_task is not None and not self._scheduler_task.done():
            return
        self._scheduler_task = asyncio.create_task(
            self._scheduler_loop(), name="personnel-sync-scheduler"
        )
        logger.info(
            "用户同步定时调度已启动",
            interval=self._settings.PERSONNEL_SYNC_INTERVAL,
            event_type="personnel.scheduler_started",
        )

    def stop_scheduler(self) -> None:
        """停止内置定时调度。"""
        if self._scheduler_task is not None and not self._scheduler_task.done():
            self._scheduler_task.cancel()
            logger.info("用户同步定时调度已停止", event_type="personnel.scheduler_stopped")
        self._scheduler_task = None

    # ── 内部实现 ──

    async def _scheduler_loop(self) -> None:
        """asyncio 周期任务：按 PERSONNEL_SYNC_INTERVAL 间隔触发同步。"""
        interval = self._settings.PERSONNEL_SYNC_INTERVAL
        try:
            while True:
                await asyncio.sleep(interval)
                self.request_sync(source="scheduled")
        except asyncio.CancelledError:
            return

    async def _run_sync(self) -> None:
        """全量同步用户数据（主进程采集 + 写入）。

        流程：
        1. 等待初始延迟
        2. 获取好友列表
        3. 获取群列表
        4. 逐群获取成员列表（含限流延迟）
        5. 直接持久化到数据库
        """
        from src.core.monitoring.metrics import personnel_api_errors

        await asyncio.sleep(self._settings.PERSONNEL_SYNC_INITIAL_DELAY)

        if not self._conn_mgr.connected:
            logger.warning("连接已断开，取消用户同步", event_type="personnel.sync_aborted")
            return

        logger.info("开始用户数据同步", event_type="personnel.sync_start")

        try:
            # 1. 获取好友列表
            friends_resp = await self._bot_api.get_friend_list()
            friends_data = friends_resp.data if friends_resp.ok else None

            # 2. 获取群列表
            groups_resp = await self._bot_api.get_group_list()
            groups_data = groups_resp.data if groups_resp.ok else None

            # 3. 逐群获取成员列表
            members_data: dict[int, list[Any]] = {}
            if groups_data and isinstance(groups_data, list):
                for group in groups_data:
                    if not self._conn_mgr.connected:
                        logger.warning("同步中途连接断开", event_type="personnel.sync_interrupted")
                        break

                    group_id = group.get("group_id") if isinstance(group, dict) else None
                    if not group_id:
                        continue

                    try:
                        member_resp = await self._bot_api.get_group_member_list(int(group_id))
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

                    await asyncio.sleep(self._settings.PERSONNEL_SYNC_API_DELAY)

            # 4. 直接持久化到数据库
            await self._personnel_service.persist_sync_data(
                friends=friends_data,
                groups=groups_data,
                members=members_data,
            )

        except Exception as exc:
            logger.error(
                "用户数据同步失败",
                error=str(exc),
                event_type="personnel.sync_error",
            )
