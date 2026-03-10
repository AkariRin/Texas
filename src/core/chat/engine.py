"""聊天记录库独立引擎 —— 独立于主库的连接池和 session factory。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    from src.core.config import Settings


def create_chat_engine(settings: Settings) -> AsyncEngine:
    """创建聊天库异步引擎（独立连接池）。"""
    return create_async_engine(
        settings.CHAT_DATABASE_URL,
        pool_size=settings.CHAT_DB_POOL_SIZE,
        max_overflow=settings.CHAT_DB_MAX_OVERFLOW,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False,
    )


def create_chat_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """创建聊天库 session factory。"""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

