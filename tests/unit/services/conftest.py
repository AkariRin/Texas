"""Service 层单元测试 fixtures —— async session factory / cache / bot_api mock。"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock


class _AsyncIterator:
    """将普通列表包装为异步迭代器，模拟 session.stream_scalars() 返回值。

    async for 语义与真实 SQLAlchemy streaming result 一致。
    """

    def __init__(self, items: list[Any]) -> None:
        self._iter = iter(items)

    def __aiter__(self) -> _AsyncIterator:
        return self

    async def __anext__(self) -> Any:
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration from None

    async def close(self) -> None:
        pass


def make_execute_result(
    scalar_one: int = 0,
    scalars_all: list[Any] | None = None,
    scalar_one_or_none: Any = None,
) -> MagicMock:
    """构造 session.execute() 返回值 mock。

    Args:
        scalar_one: result.scalar_one() 返回值（用于 COUNT 查询）。
        scalars_all: result.scalars().all() 返回值（用于列表查询）。
        scalar_one_or_none: result.scalar_one_or_none() 返回值（用于单条查询）。
    """
    result = MagicMock()
    result.scalar = MagicMock(return_value=scalar_one)
    result.scalar_one = MagicMock(return_value=scalar_one)
    result.scalar_one_or_none = MagicMock(return_value=scalar_one_or_none)
    result.scalars.return_value.all.return_value = scalars_all or []
    result.scalars.return_value.first.return_value = scalars_all[0] if scalars_all else None
    return result


def make_session(
    execute_side_effects: list[Any] | None = None,
    get_result: Any = None,
    stream_items: list[Any] | None = None,
) -> MagicMock:
    """构造 AsyncSession mock，正确实现 async with 和 begin() 的上下文管理器协议。

    Args:
        execute_side_effects: 按调用顺序依次返回的 execute() 结果列表。
        get_result: session.get() 的返回值（模拟 primary key 查找）。
        stream_items: session.stream_scalars() 的异步迭代元素列表。
    """
    session = MagicMock()

    # async with session: 协议
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    # async with session.begin(): 协议
    begin_cm = MagicMock()
    begin_cm.__aenter__ = AsyncMock(return_value=None)
    begin_cm.__aexit__ = AsyncMock(return_value=False)
    session.begin = MagicMock(return_value=begin_cm)

    # execute() 按顺序返回
    if execute_side_effects:
        session.execute = AsyncMock(side_effect=execute_side_effects)
    else:
        session.execute = AsyncMock(return_value=make_execute_result())

    # get() 返回单个对象（按 primary key 查找）
    session.get = AsyncMock(return_value=get_result)

    # stream_scalars() 返回异步迭代器
    session.stream_scalars = AsyncMock(return_value=_AsyncIterator(stream_items or []))

    # 写操作（无返回值，仅需 await）
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    return session


def make_session_factory(
    session: MagicMock | None = None,
) -> tuple[MagicMock, MagicMock]:
    """构造 async_sessionmaker mock 及其底层 session。

    每次调用 factory() 返回同一个 async context manager，__aenter__ 返回 session。
    所有 session 操作共享同一个 mock 对象，可统一断言。

    Returns:
        (factory, session)：factory 传入 Service.__init__，session 用于断言。
    """
    if session is None:
        session = make_session()

    factory_cm = MagicMock()
    factory_cm.__aenter__ = AsyncMock(return_value=session)
    factory_cm.__aexit__ = AsyncMock(return_value=False)

    factory = MagicMock(return_value=factory_cm)
    return factory, session


def make_cache(get_result: Any = None) -> MagicMock:
    """构造 CacheClient mock。

    Args:
        get_result: cache.get() 的返回值（None 表示缓存未命中）。
    """
    cache = MagicMock()
    cache.get = AsyncMock(return_value=get_result)
    cache.set = AsyncMock()
    cache.delete = AsyncMock()
    return cache


def make_bot_api() -> MagicMock:
    """构造 BotAPI mock。"""
    bot = MagicMock()
    bot.send_private_msg = AsyncMock(return_value={"message_id": 100})
    bot.send_group_msg = AsyncMock(return_value={"message_id": 101})
    return bot
