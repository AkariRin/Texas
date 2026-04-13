"""每日打卡服务 —— 在已启用群执行 NapCat 签到。

由 Celery Beat 每天零点触发，经 Redis RPC 桥接器调用主进程执行打卡；
同时在 WS 连接建立时触发，通过 Redis 日期键去重防止重复打卡。
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, Any, Final, Literal

import structlog

from src.core.cache.key_registry import cache_key
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

# ── 本模块的 Redis 缓存键定义 ──
checkin_key = cache_key(
    "checkin.daily",
    "texas:checkin:{group_id}:{date_str}",
    ttl_hint=90000,
    description="某群某日的打卡状态（date_str 格式：YYYY-MM-DD）。",
)

# 打卡 Redis 键 TTL：25 小时（覆盖时区漂移，自动清理）
_CHECKIN_TTL: Final[int] = 90_000
# 群间发送延迟（秒），避免 QQ 限流
_SEND_DELAY: Final[float] = 1.5
# 此服务注册到权限系统的功能名
FEATURE_NAME: Final[str] = "daily_checkin"

CheckinSource = Literal["ws_connect", "scheduled"]


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

    由 Celery Beat 每天零点通过 Redis RPC 触发，WS 连接建立时亦可触发，
    均通过 Redis 日期键去重防止重复执行。
    打卡 API 使用 NapCat ``send_group_sign``，不发送文本消息。
    """

    __slots__ = (
        "_bot_api",
        "_conn_mgr",
        "_persistent",
        "_permission_service",
        "_session_factory",
        "_current_task",
    )

    def __init__(
        self,
        *,
        bot_api: BotAPI,
        conn_mgr: ConnectionManager,
        persistent: CacheClient,
        permission_service: FeaturePermissionService,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._bot_api = bot_api
        self._conn_mgr = conn_mgr
        self._persistent = persistent  # 持久存储：打卡去重键不可丢失，否则会重复打卡
        self._permission_service = permission_service
        self._session_factory = session_factory
        self._current_task: asyncio.Task[None] | None = None

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

    # ── 内部实现 ──

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
                already_done = await self._persistent.exists(checkin_key(group_id, today))
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
                    exc_info=True,
                )
                skipped += 1
                continue

            if not enabled:
                skipped += 1
                continue

            # 执行打卡
            try:
                resp = await self._bot_api.send_group_sign(group_id)
                if not resp.ok:
                    logger.warning(
                        "群打卡 API 返回失败",
                        group_id=group_id,
                        retcode=resp.retcode,
                        message=resp.message,
                        event_type="checkin.send_error",
                    )
                    failed += 1
                else:
                    await self._persistent.set(checkin_key(group_id, today), "1", ttl=_CHECKIN_TTL)
                    sent += 1
            except Exception:
                logger.warning(
                    "群打卡异常",
                    group_id=group_id,
                    event_type="checkin.send_error",
                    exc_info=True,
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


# ── 生命周期注册 ──

from src.core.lifecycle import startup  # noqa: E402


@startup(
    name="checkin",
    provides=["checkin_service"],
    requires=[
        "session_factory",
        "persistent_client",
        "bot_api",
        "conn_mgr",
        "permission_service",
        "rpc_consumer",
    ],
)
async def _lifecycle_start(deps: dict[str, Any]) -> dict[str, Any]:
    """打卡模块启动（注册 RPC handler，rpc_consumer.start() 由 lifespan 在此后调用）。"""
    checkin_service = DailyCheckinService(
        bot_api=deps["bot_api"],
        conn_mgr=deps["conn_mgr"],
        persistent=deps["persistent_client"],
        permission_service=deps["permission_service"],
        session_factory=deps["session_factory"],
    )

    async def _rpc_handler(params: dict[str, Any]) -> dict[str, Any]:
        """将 RPC request_checkin 请求路由到 DailyCheckinService。"""
        source = str(params.get("source", "scheduled"))
        checkin_service.request_checkin(source=source)  # type: ignore[arg-type]
        return {"triggered": True}

    deps["rpc_consumer"].register_handler("request_checkin", _rpc_handler)
    return {"checkin_service": checkin_service}
