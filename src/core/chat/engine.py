"""聊天库引擎兼容层 —— 委托给通用引擎工厂。

已弃用：新代码请直接使用 src.core.db.engine.create_engine()。
保留此模块仅为避免现有导入报错。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.db.engine import create_engine, create_session_factory

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

    from src.core.config import Settings


def create_chat_engine(settings: Settings) -> AsyncEngine:
    """创建聊天库异步引擎 —— 委托给通用工厂."""
    return create_engine(
        settings.CHAT_DATABASE_URL,
        pool_size=settings.CHAT_DB_POOL_SIZE,
        max_overflow=settings.CHAT_DB_MAX_OVERFLOW,
    )


def create_chat_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """创建聊天库 session factory —— 委托给通用工厂."""
    return create_session_factory(engine)
