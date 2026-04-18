"""点赞服务 —— 手动点赞、定时任务注册/取消/查询、批量定时执行。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any, Final

import structlog

from src.core.framework.decorators import feature
from src.core.lifecycle import startup
from src.models.enums import LikeSource
from src.models.like import LikeHistory, LikeTask

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from src.core.protocol.api import BotAPI

logger = structlog.get_logger()

# 每次点赞的默认次数（定时点赞固定使用此值，不可由用户修改）
DEFAULT_LIKE_TIMES: Final[int] = 10
# 批量定时点赞时各用户之间的发送延迟（秒），避免 QQ 限流
_SEND_DELAY: Final[float] = 1.0


# ── 返回值数据类 ──


@dataclass(frozen=True)
class RegisterResult:
    """注册定时任务的结果。"""

    already_exists: bool


@dataclass(frozen=True)
class LikeStatus:
    """用户点赞状态查询结果。"""

    has_task: bool
    total_times: int
    last_triggered_at: datetime | None


@feature(
    name="like_service",
    display_name="点赞",
    description="手动点赞与每日定时自动点赞",
    tags=["automation"],
    default_enabled=True,
)
class LikeService:
    """点赞服务 —— 提供手动点赞和每日定时点赞能力。

    通过 @startup 注册到生命周期，向 RPC Consumer 注册 request_like handler。
    run_scheduled_likes() 通过 is_running + asyncio Task 防止并发重入。
    """

    __slots__ = ("_bot_api", "_session_factory", "_current_task")

    def __init__(
        self,
        *,
        bot_api: BotAPI,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._bot_api = bot_api
        self._session_factory = session_factory
        self._current_task: asyncio.Task[None] | None = None

    # ── 公共接口 ──

    @property
    def is_running(self) -> bool:
        """是否有定时点赞任务正在执行。"""
        return self._current_task is not None and not self._current_task.done()

    async def send_like_now(
        self,
        qq: int,
        times: int,
        source: LikeSource,
    ) -> bool:
        """立即调用 send_like API 点赞，并写入历史记录。

        Args:
            qq: 被点赞用户 QQ。
            times: 点赞次数。
            source: 触发来源（manual / scheduled）。

        Returns:
            是否成功。
        """
        success = False
        try:
            resp = await self._bot_api.send_like(user_id=qq, times=times)
            success = resp.ok
            if not success:
                logger.warning(
                    "send_like API 返回失败",
                    qq=qq,
                    times=times,
                    retcode=resp.retcode,
                    message=resp.message,
                    event_type="like.send_error",
                )
        except Exception:
            logger.warning(
                "send_like 异常",
                qq=qq,
                times=times,
                event_type="like.send_exception",
                exc_info=True,
            )

        async with self._session_factory() as session:
            session.add(
                LikeHistory(
                    qq=qq,
                    times=times,
                    triggered_at=datetime.now(UTC),
                    source=source,
                    success=success,
                )
            )
            await session.commit()

        return success

    async def register_task(
        self,
        qq: int,
        group_id: int | None,
    ) -> RegisterResult:
        """注册定时点赞任务。

        Args:
            qq: 用户 QQ。
            group_id: 注册时所在群（私聊注册为 None）。

        Returns:
            RegisterResult.already_exists=True 表示任务已存在。
        """
        from sqlalchemy import select
        from sqlalchemy.exc import IntegrityError

        async with self._session_factory() as session:
            exists = await session.scalar(select(LikeTask.id).where(LikeTask.qq == qq).limit(1))
            if exists is not None:
                return RegisterResult(already_exists=True)

            session.add(
                LikeTask(
                    qq=qq,
                    registered_at=datetime.now(UTC),
                    registered_group_id=group_id,
                )
            )
            try:
                await session.commit()
            except IntegrityError:
                # 极小概率并发竞争
                await session.rollback()
                return RegisterResult(already_exists=True)

        logger.info(
            "定时点赞任务已注册",
            qq=qq,
            group_id=group_id,
            event_type="like.task_registered",
        )
        return RegisterResult(already_exists=False)

    async def cancel_task(self, qq: int) -> bool:
        """取消定时点赞任务。

        Returns:
            True 表示删除成功，False 表示任务不存在。
        """
        from sqlalchemy import delete, select

        async with self._session_factory() as session:
            row = await session.scalar(select(LikeTask.id).where(LikeTask.qq == qq).limit(1))
            if row is None:
                return False
            await session.execute(delete(LikeTask).where(LikeTask.qq == qq))
            await session.commit()

        logger.info("定时点赞任务已取消", qq=qq, event_type="like.task_cancelled")
        return True

    async def get_status(self, qq: int) -> LikeStatus:
        """查询用户点赞状态与历史统计。

        Returns:
            LikeStatus 包含是否有任务、总点赞次数、最近触发时间。
        """
        from sqlalchemy import func, select

        async with self._session_factory() as session:
            has_task = (
                await session.scalar(select(LikeTask.id).where(LikeTask.qq == qq).limit(1))
            ) is not None

            total_times: int = (
                await session.scalar(
                    select(func.sum(LikeHistory.times)).where(
                        LikeHistory.qq == qq,
                        LikeHistory.success.is_(True),
                    )
                )
            ) or 0

            last_triggered_at: datetime | None = await session.scalar(
                select(LikeHistory.triggered_at)
                .where(LikeHistory.qq == qq)
                .order_by(LikeHistory.triggered_at.desc())
                .limit(1)
            )

        return LikeStatus(
            has_task=has_task,
            total_times=total_times,
            last_triggered_at=last_triggered_at,
        )

    async def list_tasks(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[LikeTask], int]:
        """分页查询所有定时点赞任务。

        Returns:
            (任务列表, 总数)
        """
        from sqlalchemy import func, select

        offset = (page - 1) * page_size
        async with self._session_factory() as session:
            total: int = (await session.scalar(select(func.count()).select_from(LikeTask))) or 0
            result = await session.execute(
                select(LikeTask)
                .order_by(LikeTask.registered_at.desc())
                .offset(offset)
                .limit(page_size)
            )
            items = list(result.scalars().all())
        return items, total

    async def list_history(
        self,
        qq: int | None = None,
        source: LikeSource | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[LikeHistory], int]:
        """分页查询点赞历史记录，支持多条件过滤。

        Args:
            qq: 按 QQ 过滤（可选）。
            source: 按触发来源过滤（可选）。
            date_from: 开始日期（date 对象，可选）。
            date_to: 结束日期（date 对象，可选）。
            page: 页码（从 1 开始）。
            page_size: 每页条数。

        Returns:
            (历史记录列表, 总数)
        """
        from sqlalchemy import func, select

        stmt = select(LikeHistory)
        count_stmt = select(func.count()).select_from(LikeHistory)

        if qq is not None:
            stmt = stmt.where(LikeHistory.qq == qq)
            count_stmt = count_stmt.where(LikeHistory.qq == qq)
        if source is not None:
            stmt = stmt.where(LikeHistory.source == source)
            count_stmt = count_stmt.where(LikeHistory.source == source)
        if date_from is not None:
            start = datetime.combine(date_from, datetime.min.time()).replace(tzinfo=UTC)
            stmt = stmt.where(LikeHistory.triggered_at >= start)
            count_stmt = count_stmt.where(LikeHistory.triggered_at >= start)
        if date_to is not None:
            end = datetime.combine(date_to, datetime.max.time()).replace(tzinfo=UTC)
            stmt = stmt.where(LikeHistory.triggered_at <= end)
            count_stmt = count_stmt.where(LikeHistory.triggered_at <= end)

        offset = (page - 1) * page_size
        stmt = stmt.order_by(LikeHistory.triggered_at.desc()).offset(offset).limit(page_size)

        async with self._session_factory() as session:
            total: int = (await session.scalar(count_stmt)) or 0
            result = await session.execute(stmt)
            items = list(result.scalars().all())
        return items, total

    def request_scheduled_likes(self) -> asyncio.Task[None] | None:
        """请求执行一轮定时点赞（防并发重入）。

        Returns:
            新建的 Task，或 None（已有任务运行中，跳过本次触发）。
        """
        if self.is_running:
            logger.debug("定时点赞任务正在执行，跳过本次触发", event_type="like.skipped")
            return None

        self._current_task = asyncio.create_task(
            self._run_scheduled_likes(), name="daily-like-scheduled"
        )
        logger.info("定时点赞任务已创建", event_type="like.requested")
        return self._current_task

    # ── 内部实现 ──

    async def _run_scheduled_likes(self) -> None:
        """遍历所有注册任务，依次执行定时点赞，结果写日志。"""
        from sqlalchemy import select

        async with self._session_factory() as session:
            result = await session.execute(select(LikeTask.qq))
            qq_list = list(result.scalars().all())

        total = len(qq_list)
        success_count = failed_count = 0

        for i, qq in enumerate(qq_list):
            try:
                ok = await self.send_like_now(qq, DEFAULT_LIKE_TIMES, LikeSource.scheduled)
            except Exception:
                logger.warning(
                    "定时点赞执行异常",
                    qq=qq,
                    exc_info=True,
                    event_type="like.send_exception",
                )
                ok = False
            if ok:
                success_count += 1
            else:
                failed_count += 1
            if i < total - 1:
                await asyncio.sleep(_SEND_DELAY)

        logger.info(
            "本轮定时点赞完成",
            total=total,
            success=success_count,
            failed=failed_count,
            event_type="like.round_done",
        )


@startup(
    name="like",
    provides=["like_service"],
    requires=["session_factory", "bot_api", "rpc_consumer"],
    dispatcher_services=["like_service"],
)
async def _lifecycle_start(deps: dict[str, Any]) -> dict[str, Any]:
    """点赞模块启动（注册 RPC handler）。"""
    like_service = LikeService(
        bot_api=deps["bot_api"],
        session_factory=deps["session_factory"],
    )

    async def _rpc_handler(params: dict[str, Any]) -> dict[str, Any]:
        """将 RPC request_like 请求路由到 LikeService。request_like 不需要 params。"""
        task = like_service.request_scheduled_likes()
        return {"triggered": task is not None}

    deps["rpc_consumer"].register_handler("request_like", _rpc_handler)
    return {"like_service": like_service}
