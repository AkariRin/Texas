"""CacheClient 集成测试 —— 连接真实 Redis 7 容器。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from src.core.cache.client import CacheClient


@pytest.mark.integration
async def test_set_and_get_string(cache_client: CacheClient) -> None:
    """set/get 字符串值，序列化/反序列化应透明。"""
    await cache_client.set("test:str", "hello")
    result = await cache_client.get("test:str")
    assert result == "hello"


@pytest.mark.integration
async def test_set_and_get_dict(cache_client: CacheClient) -> None:
    """set/get dict 值，应通过 JSON 序列化后还原。"""
    payload = {"user_id": 42, "streak": 7, "last_date": "2026-04-01"}
    await cache_client.set("test:dict", payload)
    result = await cache_client.get("test:dict")
    assert result == payload


@pytest.mark.integration
async def test_get_returns_none_for_missing_key(cache_client: CacheClient) -> None:
    """不存在的键应返回 None，不抛出异常。"""
    result = await cache_client.get("test:nonexistent:key:xyz")
    assert result is None


@pytest.mark.integration
async def test_delete_removes_key(cache_client: CacheClient) -> None:
    """delete 后 get 应返回 None，exists 应返回 False。"""
    await cache_client.set("test:del", "value")
    assert await cache_client.exists("test:del") is True

    await cache_client.delete("test:del")

    assert await cache_client.get("test:del") is None
    assert await cache_client.exists("test:del") is False


@pytest.mark.integration
async def test_exists_returns_true_for_present_key(cache_client: CacheClient) -> None:
    """exists 对已存在的键应返回 True。"""
    await cache_client.set("test:exists:yes", "1")
    assert await cache_client.exists("test:exists:yes") is True


@pytest.mark.integration
async def test_exists_returns_false_for_missing_key(cache_client: CacheClient) -> None:
    """exists 对不存在的键应返回 False。"""
    assert await cache_client.exists("test:exists:no:such:key:xyz") is False


@pytest.mark.integration
async def test_incr_increments_counter(cache_client: CacheClient) -> None:
    """incr 应从 1 开始递增计数器。"""
    key = "test:counter"
    await cache_client.delete(key)  # 确保干净起点

    v1 = await cache_client.incr(key)
    v2 = await cache_client.incr(key)
    v3 = await cache_client.incr(key)

    assert v1 == 1
    assert v2 == 2
    assert v3 == 3


@pytest.mark.integration
async def test_get_or_set_calls_factory_on_miss(cache_client: CacheClient) -> None:
    """get_or_set：缓存 miss 时调用 factory，命中时直接返回缓存值（不再调用 factory）。"""
    key = "test:get_or_set"
    await cache_client.delete(key)

    call_count = 0

    async def factory() -> str:
        nonlocal call_count
        call_count += 1
        return "computed"

    # 首次调用：factory 被执行
    val1 = await cache_client.get_or_set(key, factory)
    assert val1 == "computed"
    assert call_count == 1

    # 二次调用：缓存命中，factory 不再执行
    val2 = await cache_client.get_or_set(key, factory)
    assert val2 == "computed"
    assert call_count == 1  # 未增加


@pytest.mark.integration
async def test_delete_by_pattern_removes_matching_keys(cache_client: CacheClient) -> None:
    """delete_by_pattern 按 glob 模式批量删除，只删除匹配键，不影响其他键。"""
    await cache_client.set("test:batch:a", "1")
    await cache_client.set("test:batch:b", "2")
    await cache_client.set("test:other:x", "3")

    await cache_client.delete_by_pattern("test:batch:*")

    assert await cache_client.exists("test:batch:a") is False
    assert await cache_client.exists("test:batch:b") is False
    # 非匹配键不受影响
    assert await cache_client.exists("test:other:x") is True
