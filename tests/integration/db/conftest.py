"""集成测试容器 fixtures —— PostgreSQL 17 + Redis 7。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio

# Docker 可用性检测：未启动 Docker 时跳过整个 db 集成测试目录
try:
    import docker as _docker

    _docker.from_env().ping()
except Exception:
    pytest.skip("Docker 不可用，跳过 DB 集成测试", allow_module_level=True)

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

# 导入所有 ORM 模型，确保 Base.metadata 注册完整
import src.models.checkin  # noqa: F401
import src.models.drift_bottle  # noqa: F401
import src.models.feedback  # noqa: F401
import src.models.jrlp  # noqa: F401
import src.models.like  # noqa: F401
import src.models.llm  # noqa: F401
import src.models.permission  # noqa: F401
import src.models.personnel  # noqa: F401
from src.core.cache.client import CacheClient
from src.core.db.base import Base

# ── 容器生命周期（session 级）─────────────────────────────────────────────────


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer]:
    """启动 PostgreSQL 17 容器，整个 pytest session 只启动一次。"""
    with PostgresContainer("postgres:17-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def redis_container() -> Generator[RedisContainer]:
    """启动 Redis 7 容器，整个 pytest session 只启动一次。"""
    with RedisContainer("redis:7-alpine") as r:
        yield r


# ── 数据库引擎（session 级）──────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_engine(postgres_container: PostgresContainer) -> AsyncGenerator[AsyncEngine]:
    """创建 asyncpg 引擎，执行 metadata.create_all() 建所有表。

    loop_scope="session" 确保 session-scoped async fixture 与 pytest-asyncio >= 0.23 兼容。
    使用 metadata.create_all() 而非 Alembic，避免测试依赖完整 Settings 配置。
    """
    sync_url = postgres_container.get_connection_url()
    async_url = sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")

    engine = create_async_engine(async_url, pool_pre_ping=True, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield engine
    finally:
        await engine.dispose()


# ── 事务隔离（function 级）──────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    """每个测试独立的 AsyncSession，通过 SAVEPOINT 实现 rollback 隔离。

    join_transaction_mode="create_savepoint" 使得 session.commit() 只提交 SAVEPOINT，
    外层 conn.rollback() 撤销全部变更，保证测试间隔离。
    """
    conn = await db_engine.connect()
    await conn.begin()
    session = AsyncSession(connection=conn, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        try:
            await session.close()
        finally:
            try:
                await conn.rollback()
            finally:
                await conn.close()


@pytest.fixture
def session_factory(db_session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    """将已有 session 包装为 Service 可注入的 session_factory。

    asynccontextmanager 包装器在运行时与 async_sessionmaker 行为一致：
    调用方均通过 `async with factory() as session:` 获取 session。
    cast 在不引入运行时开销的前提下满足 mypy strict 模式的类型约束。
    """

    @asynccontextmanager
    async def _factory() -> AsyncGenerator[AsyncSession]:
        yield db_session

    return cast("async_sessionmaker[AsyncSession]", _factory)


# ── Redis 客户端（function 级）──────────────────────────────────────────────


@pytest_asyncio.fixture
async def cache_client(redis_container: RedisContainer) -> AsyncGenerator[CacheClient]:
    """创建连接到测试 Redis 容器的 CacheClient，测试结束后关闭连接。"""
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    client = CacheClient(url=f"redis://{host}:{port}", default_ttl=300)
    try:
        yield client
    finally:
        await client.close()


# ── 测试数据工厂（通用）────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def seed_user_group(db_session: AsyncSession) -> dict[str, int]:
    """插入测试用 User + Group 记录，供依赖 FK 约束的测试使用。

    Group 字段 group_name（非 name），其余字段有 default 可省略。
    """
    from src.models.enums import UserRelation
    from src.models.personnel import Group, User

    user = User(qq=10001, nickname="测试用户", relation=UserRelation.group_member)
    group = Group(group_id=100, group_name="测试群")
    db_session.add_all([user, group])
    await db_session.flush()
    return {"user_id": 10001, "group_id": 100}
