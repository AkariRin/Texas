"""CheckinService 单元测试。"""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import AsyncMock

from sqlalchemy.exc import IntegrityError

from src.services.checkin import CheckinService
from tests.unit.services.conftest import (
    make_cache,
    make_execute_result,
    make_session,
    make_session_factory,
)

# ── 测试常量 ──────────────────────────────────────────────────────────────────

_GROUP_ID = 100
_USER_ID = 10001
_TODAY = date(2024, 1, 15)
_TODAY_STR = "2024-01-15"
_YESTERDAY = date(2024, 1, 14)
_YESTERDAY_STR = "2024-01-14"
_TWO_DAYS_AGO_STR = "2024-01-13"


def _make_svc(
    cache_data: dict[str, Any] | None = None,
    stream_items: list[Any] | None = None,
    execute_side_effects: list[Any] | None = None,
    flush_side_effect: Any = None,
) -> tuple[CheckinService, Any, Any]:
    """快速构造 CheckinService 及其 mock 依赖（cache, session）。

    Returns:
        (svc, cache_mock, session_mock)
    """
    cache = make_cache(get_result=cache_data)
    session = make_session(
        execute_side_effects=execute_side_effects,
        stream_items=stream_items,
    )
    if flush_side_effect is not None:
        session.flush = AsyncMock(side_effect=flush_side_effect)
    factory, _ = make_session_factory(session)
    svc = CheckinService(session_factory=factory, cache=cache)
    return svc, cache, session


# ── TestCheckin ───────────────────────────────────────────────────────────────


class TestCheckin:
    """checkin() 核心业务逻辑测试组。"""

    async def test_duplicate_when_cache_has_today(self) -> None:
        """缓存中 last_date == today → 重复签到，rank=0，streak/total 原值返回。"""
        svc, _, _ = _make_svc(cache_data={"last_date": _TODAY_STR, "streak": 5, "total": 10})

        result = await svc.checkin(group_id=_GROUP_ID, user_id=_USER_ID, today=_TODAY)

        assert result.is_duplicate is True
        assert result.rank == 0
        assert result.streak == 5
        assert result.total == 10

    async def test_consecutive_day_increments_streak(self) -> None:
        """last_date == yesterday → 连续签到，streak+1，total+1。"""
        rank_result = make_execute_result(scalar_one=3)
        svc, cache, _ = _make_svc(
            cache_data={"last_date": _YESTERDAY_STR, "streak": 7, "total": 20},
            execute_side_effects=[rank_result],
        )

        result = await svc.checkin(group_id=_GROUP_ID, user_id=_USER_ID, today=_TODAY)

        assert result.is_duplicate is False
        assert result.streak == 8
        assert result.total == 21
        assert result.rank == 3

    async def test_nonconsecutive_day_resets_streak(self) -> None:
        """last_date != yesterday（断链）→ streak 重置为 1。"""
        rank_result = make_execute_result(scalar_one=1)
        svc, _, _ = _make_svc(
            cache_data={"last_date": _TWO_DAYS_AGO_STR, "streak": 5, "total": 15},
            execute_side_effects=[rank_result],
        )

        result = await svc.checkin(group_id=_GROUP_ID, user_id=_USER_ID, today=_TODAY)

        assert result.streak == 1
        assert result.total == 16
        assert result.is_duplicate is False

    async def test_integrity_error_treated_as_duplicate(self) -> None:
        """flush() 抛 IntegrityError（并发写入冲突）→ 视为重复签到。"""
        svc, _, _ = _make_svc(
            cache_data={"last_date": _YESTERDAY_STR, "streak": 3, "total": 10},
            flush_side_effect=IntegrityError("unique", "params", "orig"),
        )

        result = await svc.checkin(group_id=_GROUP_ID, user_id=_USER_ID, today=_TODAY)

        assert result.is_duplicate is True
        assert result.rank == 0
        assert result.streak == 3
        assert result.total == 10

    async def test_updates_cache_after_successful_checkin(self) -> None:
        """签到成功后应更新 Redis 缓存，写入 today/new_streak/new_total。"""
        rank_result = make_execute_result(scalar_one=2)
        svc, cache, _ = _make_svc(
            cache_data={"last_date": _YESTERDAY_STR, "streak": 4, "total": 9},
            execute_side_effects=[rank_result],
        )

        await svc.checkin(group_id=_GROUP_ID, user_id=_USER_ID, today=_TODAY)

        cache.set.assert_awaited()
        cached_data: dict = cache.set.call_args.args[1]
        assert cached_data["last_date"] == _TODAY_STR
        assert cached_data["streak"] == 5
        assert cached_data["total"] == 10

    async def test_cache_miss_triggers_rebuild_and_continues(self) -> None:
        """cache.get 返回 None → 调用 rebuild_cache，使用重建结果继续签到流程。

        stream 中只有 yesterday → rebuild 后 last_date = yesterday, streak = 1
        checkin 检测到 last_date == yesterday → 连续，new_streak = 2
        """
        total_result = make_execute_result(scalar_one=1)
        rank_result = make_execute_result(scalar_one=1)
        svc, cache, _ = _make_svc(
            cache_data=None,
            stream_items=[_YESTERDAY],
            execute_side_effects=[total_result, rank_result],
        )

        result = await svc.checkin(group_id=_GROUP_ID, user_id=_USER_ID, today=_TODAY)

        assert result.is_duplicate is False
        assert result.streak == 2
        assert result.total == 2
        assert result.rank == 1


# ── TestRebuildCache ──────────────────────────────────────────────────────────


class TestRebuildCache:
    """rebuild_cache() 签到 streak 算法测试组。

    算法按降序遍历历史日期，遇到非连续断点立即 break。
    结果的 last_date 是连续 streak 中最老的日期（非最新），
    对生产逻辑安全（缓存 TTL 30 天，超时用户 streak 已断）。
    """

    async def test_empty_user_returns_zeroes(self) -> None:
        """total=0（从未签到）→ 返回全零，不更新缓存。"""
        total_result = make_execute_result(scalar_one=0)
        svc, cache, _ = _make_svc(execute_side_effects=[total_result])

        result = await svc.rebuild_cache(group_id=_GROUP_ID, user_id=_USER_ID)

        assert result == {"last_date": "", "streak": 0, "total": 0}
        cache.set.assert_not_awaited()

    async def test_single_date_returns_streak_1(self) -> None:
        """仅有一条记录 → streak=1，last_date 为该日期。"""
        single_date = date(2024, 1, 13)
        total_result = make_execute_result(scalar_one=1)
        svc, cache, _ = _make_svc(
            execute_side_effects=[total_result],
            stream_items=[single_date],
        )

        result = await svc.rebuild_cache(group_id=_GROUP_ID, user_id=_USER_ID)

        assert result["streak"] == 1
        assert result["last_date"] == "2024-01-13"
        assert result["total"] == 1
        cache.set.assert_awaited_once()

    async def test_consecutive_dates_accumulate_streak(self) -> None:
        """3 个连续日期 → streak=3，last_date 为最老那天（算法设计特性）。"""
        dates = [date(2024, 1, 15), date(2024, 1, 14), date(2024, 1, 13)]
        total_result = make_execute_result(scalar_one=3)
        svc, _, _ = _make_svc(
            execute_side_effects=[total_result],
            stream_items=dates,
        )

        result = await svc.rebuild_cache(group_id=_GROUP_ID, user_id=_USER_ID)

        assert result["streak"] == 3
        assert result["last_date"] == "2024-01-13"
        assert result["total"] == 3

    async def test_gap_in_dates_stops_streak(self) -> None:
        """日期中存在断点 → streak 在断点处停止，只计算最近的连续段。"""
        # 01-15 和 01-13 之间跳过了 01-14（有断点）
        dates = [date(2024, 1, 15), date(2024, 1, 13)]
        total_result = make_execute_result(scalar_one=5)
        svc, _, _ = _make_svc(
            execute_side_effects=[total_result],
            stream_items=dates,
        )

        result = await svc.rebuild_cache(group_id=_GROUP_ID, user_id=_USER_ID)

        assert result["streak"] == 1
        assert result["last_date"] == "2024-01-15"
        assert result["total"] == 5

    async def test_sets_cache_after_rebuild(self) -> None:
        """total>0 时 rebuild_cache 应调用 cache.set 写入结果。"""
        total_result = make_execute_result(scalar_one=2)
        dates = [date(2024, 1, 15), date(2024, 1, 14)]
        svc, cache, _ = _make_svc(
            execute_side_effects=[total_result],
            stream_items=dates,
        )

        result = await svc.rebuild_cache(group_id=_GROUP_ID, user_id=_USER_ID)

        cache.set.assert_awaited_once()
        cached_data: dict = cache.set.call_args.args[1]
        assert cached_data == result
