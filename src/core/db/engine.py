"""通用异步 SQLAlchemy 引擎和 session 工厂。

所有数据库（主库、聊天库等）统一使用此模块创建引擎，
不再为每个库维护独立的 engine.py。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine(
    url: str,
    pool_size: int = 10,
    max_overflow: int = 20,
    **kwargs: Any,
) -> AsyncEngine:
    """创建异步引擎（通用工厂）。

    Args:
        url: 数据库连接 URL（asyncpg 格式）。
        pool_size: 连接池大小。
        max_overflow: 连接池最大溢出连接数。
        **kwargs: 传递给 create_async_engine 的额外参数。
    """
    return create_async_engine(
        url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False,
        **kwargs,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """创建绑定到引擎的 session 工厂。"""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
