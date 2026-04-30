"""CheckinService 集成测试。"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import pytest

from src.models.checkin import CheckinRecord
from src.models.personnel import User, UserRelation
from src.services.checkin import CheckinService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from src.core.cache.client import CacheClient

# 缓存键模板，与 CheckinService 内部保持一致
_CACHE_KEY_TPL = "texas:checkin:stats:{group_id}:{user_id}"


# ── 辅助工具 ────────────────────────────────────────────────────────────────


def _make_service(
    session_factory: async_sessionmaker[AsyncSession],
    cache_client: CacheClient,
) -> CheckinService:
    """快速构造 CheckinService 实例。"""
    return CheckinService(session_factory=session_factory, cache=cache_client)


# ── 测试 ─────────────────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_checkin_first_time(
    session_factory: async_sessionmaker[AsyncSession],
    cache_client: CacheClient,
    seed_user_group: dict[str, int],
) -> None:
    """首次签到应返回 is_duplicate=False，rank=1，streak=1，total=1。"""
    svc = _make_service(session_factory, cache_client)
    user_id: int = seed_user_group["user_id"]
    group_id: int = seed_user_group["group_id"]
    today = date(2026, 4, 1)

    result = await svc.checkin(group_id, user_id, today)

    assert result.is_duplicate is False
    assert result.rank == 1
    assert result.streak == 1
    assert result.total == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_checkin_duplicate_via_cache(
    session_factory: async_sessionmaker[AsyncSession],
    cache_client: CacheClient,
    seed_user_group: dict[str, int],
) -> None:
    """缓存命中路径：同一天签到两次，第二次应返回 is_duplicate=True，rank=0。"""
    svc = _make_service(session_factory, cache_client)
    user_id: int = seed_user_group["user_id"]
    group_id: int = seed_user_group["group_id"]
    today = date(2026, 4, 1)

    first = await svc.checkin(group_id, user_id, today)
    assert first.is_duplicate is False

    second = await svc.checkin(group_id, user_id, today)
    assert second.is_duplicate is True
    assert second.rank == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_checkin_duplicate_via_rebuild(
    session_factory: async_sessionmaker[AsyncSession],
    cache_client: CacheClient,
    seed_user_group: dict[str, int],
) -> None:
    """Cache miss → rebuild_cache 路径：删除 Redis 键后再次签到仍应返回 is_duplicate=True。"""
    svc = _make_service(session_factory, cache_client)
    user_id: int = seed_user_group["user_id"]
    group_id: int = seed_user_group["group_id"]
    today = date(2026, 4, 1)

    first = await svc.checkin(group_id, user_id, today)
    assert first.is_duplicate is False

    # 手动删除 Redis 缓存键，模拟 cache miss 场景
    cache_key = _CACHE_KEY_TPL.format(group_id=group_id, user_id=user_id)
    await cache_client.delete(cache_key)

    # rebuild_cache 路径：从 DB 重建后发现当天已签到
    second = await svc.checkin(group_id, user_id, today)
    assert second.is_duplicate is True
    assert second.rank == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_streak_consecutive_days(
    session_factory: async_sessionmaker[AsyncSession],
    cache_client: CacheClient,
    seed_user_group: dict[str, int],
) -> None:
    """连续两天签到：第1天 streak=1，第2天 streak=2。"""
    svc = _make_service(session_factory, cache_client)
    user_id: int = seed_user_group["user_id"]
    group_id: int = seed_user_group["group_id"]

    day1 = date(2026, 4, 1)
    day2 = date(2026, 4, 2)

    result1 = await svc.checkin(group_id, user_id, day1)
    assert result1.streak == 1
    assert result1.total == 1

    result2 = await svc.checkin(group_id, user_id, day2)
    assert result2.streak == 2
    assert result2.total == 2
    assert result2.is_duplicate is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_streak_resets_after_gap(
    session_factory: async_sessionmaker[AsyncSession],
    cache_client: CacheClient,
    seed_user_group: dict[str, int],
) -> None:
    """第1天签到、跳过第2天、第3天签到：streak 应重置为 1。"""
    svc = _make_service(session_factory, cache_client)
    user_id: int = seed_user_group["user_id"]
    group_id: int = seed_user_group["group_id"]

    day1 = date(2026, 4, 1)
    day3 = date(2026, 4, 3)  # 跳过 4 月 2 日

    result1 = await svc.checkin(group_id, user_id, day1)
    assert result1.streak == 1

    # 清除缓存，确保第3天会重新读取 last_date（可选，但保持测试确定性）
    cache_key = _CACHE_KEY_TPL.format(group_id=group_id, user_id=user_id)
    await cache_client.delete(cache_key)

    result3 = await svc.checkin(group_id, user_id, day3)
    assert result3.is_duplicate is False
    assert result3.streak == 1  # 连续中断后重置
    assert result3.total == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_leaderboard_streak_window_function(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    cache_client: CacheClient,
    seed_user_group: dict[str, int],
) -> None:
    """验证 get_leaderboard(by='streak') 使用 PostgreSQL LAG 窗口函数正确排序。

    插入三个用户，连续签到天数各不同：
      - user_id=10002：连续 3 天（streak=3）
      - user_id=10001：连续 2 天（streak=2，由 seed_user_group 提供）
      - user_id=10003：连续 1 天（streak=1）

    预期排行榜顺序：10002 > 10001 > 10003。
    """
    group_id: int = seed_user_group["group_id"]
    # seed_user_group 已创建 user_id=10001，无需重复创建

    # 额外创建两个测试用户
    user2 = User(qq=10002, nickname="用户2", relation=UserRelation.group_member)
    user3 = User(qq=10003, nickname="用户3", relation=UserRelation.group_member)
    db_session.add_all([user2, user3])
    await db_session.flush()

    # 构造签到记录：各用户连续签到天数不同
    now_utc = datetime.now(UTC)

    # user_id=10002：连续 3 天（streak=3）—— Apr 1~3
    records_u2 = [
        CheckinRecord(
            group_id=group_id,
            user_id=10002,
            checkin_date=date(2026, 4, d),
            checkin_at=now_utc,
        )
        for d in (1, 2, 3)
    ]

    # user_id=10001：连续 2 天（streak=2）—— Apr 1~2
    records_u1 = [
        CheckinRecord(
            group_id=group_id,
            user_id=10001,
            checkin_date=date(2026, 4, d),
            checkin_at=now_utc,
        )
        for d in (1, 2)
    ]

    # user_id=10003：只签到 1 天（streak=1）—— Apr 1
    records_u3 = [
        CheckinRecord(
            group_id=group_id,
            user_id=10003,
            checkin_date=date(2026, 4, 1),
            checkin_at=now_utc,
        )
    ]

    db_session.add_all([*records_u2, *records_u1, *records_u3])
    await db_session.flush()

    svc = _make_service(session_factory, cache_client)
    leaderboard = await svc.get_leaderboard(group_id=group_id, by="streak", limit=10)

    assert len(leaderboard) == 3

    # 排行榜按 streak 降序：10002(3) > 10001(2) > 10003(1)
    assert leaderboard[0].user_id == 10002
    assert leaderboard[0].value == 3

    assert leaderboard[1].user_id == 10001
    assert leaderboard[1].value == 2

    assert leaderboard[2].user_id == 10003
    assert leaderboard[2].value == 1
