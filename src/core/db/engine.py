"""Async SQLAlchemy engine and session factory."""

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


def create_engine(settings: Settings) -> AsyncEngine:
    """Create an async engine with connection pooling."""
    return create_async_engine(
        settings.DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=settings.LOG_LEVEL == "DEBUG",
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create a session factory bound to the engine."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
