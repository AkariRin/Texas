"""用户群签到业务逻辑服务。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any, Final, Literal

import structlog
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from src.core.cache.key_registry import cache_key
from src.core.utils import SHANGHAI_TZ
from src.models.checkin import CheckinRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from src.core.cache.client import CacheClient

logger = structlog.get_logger()

# ── Redis 缓存键注册 ──
_CACHE_TTL: Final[int] = 2_592_000  # 30 天（秒）

checkin_stats_key = cache_key(
    "checkin.user_stats",
    "texas:checkin:stats:{group_id}:{user_id}",
    ttl_hint=_CACHE_TTL,
    description="用户在某群的签到统计缓存（last_date / streak / total）",
)


# ── 返回值数据类 ──


@dataclass(frozen=True)
class CheckinResult:
    """签到操作结果。"""

    is_duplicate: bool
    rank: int  # 今日本群第几个（重复签到时为 0）
    streak: int  # 当前连续签到天数
    total: int  # 累计签到天数


@dataclass(frozen=True)
class LeaderEntry:
    """排行榜条目。"""

    user_id: int
    value: int  # total 或 streak，由 by 参数决定


@dataclass(frozen=True)
class DayCount:
    """每日签到人数数据点。"""

    date: str  # YYYY-MM-DD
    count: int


@dataclass(frozen=True)
class SummaryData:
    """汇总卡片数据。"""

    total_checkins: int  # 历史签到总人次
    today_checkins: int  # 今日签到人数
    active_users: int  # 过去 30 天至少签到一次的去重用户数


class CheckinService:
    """用户群签到核心服务。"""

    __slots__ = ("_session_factory", "_cache")

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        cache: CacheClient,
    ) -> None:
        self._session_factory = session_factory
        self._cache = cache

    # ── 核心签到 ──

    async def checkin(self, group_id: int, user_id: int, today: date) -> CheckinResult:
        """执行签到，返回 rank / streak / total / is_duplicate。

        Args:
            group_id: 群号。
            user_id: 用户 QQ。
            today: 北京时间当天日期。

        Returns:
            CheckinResult，重复签到时 rank=0。
        """
        today_str = today.isoformat()
        key = checkin_stats_key(group_id, user_id)

        # 1. 读缓存
        cached: dict[str, Any] | None = await self._cache.get(key)
        if cached is None:
            cached = await self.rebuild_cache(group_id, user_id)

        last_date_str: str = cached.get("last_date", "")
        streak: int = int(cached.get("streak", 0))
        total: int = int(cached.get("total", 0))

        # 2. 重复签到检测
        if last_date_str == today_str:
            return CheckinResult(is_duplicate=True, rank=0, streak=streak, total=total)

        # 3. 计算新 streak / total
        yesterday_str = (today - timedelta(days=1)).isoformat()
        new_streak = streak + 1 if last_date_str == yesterday_str else 1
        new_total = total + 1

        # 4. 插入 DB
        async with self._session_factory() as session:
            record = CheckinRecord(
                group_id=group_id,
                user_id=user_id,
                checkin_date=today,
                checkin_at=datetime.now(UTC),
            )
            session.add(record)
            try:
                await session.flush()
                # 5. 查今日排名（含本次插入）
                count_result = await session.execute(
                    select(func.count())
                    .select_from(CheckinRecord)
                    .where(
                        CheckinRecord.group_id == group_id,
                        CheckinRecord.checkin_date == today,
                    )
                )
                rank = count_result.scalar_one()
                await session.commit()
            except IntegrityError:
                # 并发冲突：已被其他请求先写入
                await session.rollback()
                logger.warning(
                    "签到并发冲突，视为重复",
                    group_id=group_id,
                    user_id=user_id,
                    event_type="checkin.concurrent_duplicate",
                )
                return CheckinResult(is_duplicate=True, rank=0, streak=streak, total=total)

        # 6. 更新缓存
        new_cache: dict[str, Any] = {
            "last_date": today_str,
            "streak": new_streak,
            "total": new_total,
        }
        await self._cache.set(key, new_cache, ttl=_CACHE_TTL)

        logger.info(
            "用户签到成功",
            group_id=group_id,
            user_id=user_id,
            rank=rank,
            streak=new_streak,
            total=new_total,
            event_type="checkin.success",
        )
        return CheckinResult(is_duplicate=False, rank=rank, streak=new_streak, total=new_total)

    async def rebuild_cache(self, group_id: int, user_id: int) -> dict[str, Any]:
        """从 DB 重建用户在某群的签到缓存。

        先 COUNT 获取总数，再流式扫描最近日期遇到第一个断点即停（early-exit），
        避免将全量历史记录加载到内存。

        Returns:
            包含 last_date / streak / total 的 dict。
        """
        base_where = (
            CheckinRecord.group_id == group_id,
            CheckinRecord.user_id == user_id,
        )
        async with self._session_factory() as session:
            total: int = (
                await session.execute(select(func.count()).where(*base_where))
            ).scalar_one()

            if total == 0:
                return {"last_date": "", "streak": 0, "total": 0}

            last_date: date | None = None
            streak = 0
            stream = await session.stream_scalars(
                select(CheckinRecord.checkin_date)
                .where(*base_where)
                .order_by(CheckinRecord.checkin_date.desc())
            )
            try:
                async for d in stream:
                    if last_date is None:
                        last_date = d
                        streak = 1
                    elif (last_date - d).days == 1:
                        streak += 1
                        last_date = d
                    else:
                        break
            finally:
                await stream.close()

        cache_data: dict[str, Any] = {
            "last_date": last_date.isoformat() if last_date else "",
            "streak": streak,
            "total": total,
        }
        key = checkin_stats_key(group_id, user_id)
        await self._cache.set(key, cache_data, ttl=_CACHE_TTL)
        return cache_data

    # ── 管理 / 统计接口 ──

    async def list_records(
        self,
        *,
        group_id: int | None = None,
        user_id: int | None = None,
        record_date: date | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[CheckinRecord], int]:
        """分页查询签到记录。group_id 为 None 时查询所有群。"""
        async with self._session_factory() as session:
            stmt = select(CheckinRecord)
            if group_id is not None:
                stmt = stmt.where(CheckinRecord.group_id == group_id)
            if user_id is not None:
                stmt = stmt.where(CheckinRecord.user_id == user_id)
            if record_date is not None:
                stmt = stmt.where(CheckinRecord.checkin_date == record_date)

            count_result = await session.execute(select(func.count()).select_from(stmt.subquery()))
            total = count_result.scalar_one()

            result = await session.execute(
                stmt.order_by(CheckinRecord.checkin_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            return list(result.scalars().all()), total

    async def get_leaderboard(
        self,
        group_id: int | None = None,
        by: Literal["total", "streak"] = "total",
        limit: int = 20,
    ) -> list[LeaderEntry]:
        """查询排行榜。group_id 为 None 时统计所有群。

        Args:
            group_id: 群号，None 表示全局。
            by: "total"（累计签到天数）或 "streak"（当前连续天数）。
            limit: 返回条数，最大 50。
        """
        limit = min(limit, 50)
        async with self._session_factory() as session:
            if by == "total":
                stmt = select(CheckinRecord.user_id, func.count().label("value"))
                if group_id is not None:
                    stmt = stmt.where(CheckinRecord.group_id == group_id)
                result = await session.execute(
                    stmt.group_by(CheckinRecord.user_id).order_by(func.count().desc()).limit(limit)
                )
                return [LeaderEntry(user_id=row[0], value=row[1]) for row in result.all()]

            # by == "streak"：使用窗口函数计算当前连续天数
            # 跨群时先 DISTINCT 去重同一用户同一天多群签到，避免重复计数
            group_filter = "WHERE group_id = :group_id" if group_id is not None else ""
            streak_sql = text(f"""
                WITH distinct_dates AS (
                    SELECT DISTINCT user_id, checkin_date FROM checkin {group_filter}
                ),
                gaps AS (
                    SELECT user_id, checkin_date,
                           CASE WHEN LAG(checkin_date)
                                         OVER (PARTITION BY user_id ORDER BY checkin_date)
                                     = checkin_date - INTERVAL '1 day'
                                THEN 0 ELSE 1 END AS new_streak
                    FROM distinct_dates
                ),
                streak_groups AS (
                    SELECT user_id, checkin_date,
                           SUM(new_streak) OVER (PARTITION BY user_id ORDER BY checkin_date) AS grp
                    FROM gaps
                ),
                streak_lengths AS (
                    SELECT user_id, grp, COUNT(*) AS len, MAX(checkin_date) AS last_day
                    FROM streak_groups GROUP BY user_id, grp
                ),
                current_streaks AS (
                    SELECT DISTINCT ON (user_id) user_id, len AS streak
                    FROM streak_lengths ORDER BY user_id, last_day DESC
                )
                SELECT user_id, streak FROM current_streaks ORDER BY streak DESC LIMIT :limit
            """)  # nosec — group_filter 为硬编码结构，:group_id/:limit 均为参数化绑定
            params: dict[str, Any] = {"limit": limit}
            if group_id is not None:
                params["group_id"] = group_id
            result = await session.execute(streak_sql, params)
            return [LeaderEntry(user_id=row[0], value=row[1]) for row in result.all()]

    async def get_daily_trend(self, group_id: int | None = None, days: int = 30) -> list[DayCount]:
        """查询最近 N 天每日签到人数。group_id 为 None 时统计所有群。"""
        days = min(days, 90)
        cutoff = datetime.now(SHANGHAI_TZ).date() - timedelta(days=days)
        async with self._session_factory() as session:
            stmt = select(
                CheckinRecord.checkin_date,
                func.count().label("cnt"),
            ).where(CheckinRecord.checkin_date >= cutoff)
            if group_id is not None:
                stmt = stmt.where(CheckinRecord.group_id == group_id)
            result = await session.execute(
                stmt.group_by(CheckinRecord.checkin_date).order_by(CheckinRecord.checkin_date)
            )
            return [DayCount(date=row[0].isoformat(), count=row[1]) for row in result.all()]

    async def get_summary(self, group_id: int | None = None) -> SummaryData:
        """查询汇总卡片数据。group_id 为 None 时统计所有群。"""
        today = datetime.now(SHANGHAI_TZ).date()
        cutoff = today - timedelta(days=30)

        async with self._session_factory() as session:
            # 三个聚合合并为一次 SQL 查询，避免多次 round-trip
            stmt = select(
                func.count().label("total"),
                func.count().filter(CheckinRecord.checkin_date == today).label("today_count"),
                func.count(CheckinRecord.user_id.distinct())
                .filter(CheckinRecord.checkin_date >= cutoff)
                .label("active"),
            )
            if group_id is not None:
                stmt = stmt.where(CheckinRecord.group_id == group_id)
            row = (await session.execute(stmt)).one()

        return SummaryData(
            total_checkins=row.total,
            today_checkins=row.today_count,
            active_users=row.active,
        )


# ── 生命周期注册 ──

from src.core.lifecycle import startup  # noqa: E402


@startup(
    name="user_checkin",
    provides=["user_checkin_service"],
    requires=["session_factory", "cache_client"],
    dispatcher_services=["user_checkin_service"],
)
async def _lifecycle_start(deps: dict[str, Any]) -> dict[str, Any]:
    """用户签到模块启动。"""
    return {
        "user_checkin_service": CheckinService(
            session_factory=deps["session_factory"],
            cache=deps["cache_client"],
        )
    }
