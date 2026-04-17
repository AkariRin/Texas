"""漂流瓶业务逻辑服务 —— 扔/捞漂流瓶、漂流瓶池管理。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from src.models.drift_bottle import (
    DRIFT_BOTTLE_DEFAULT_POOL_ID,
    DriftBottleGroupPool,
    DriftBottleItem,
    DriftBottlePool,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = structlog.get_logger()


@dataclass(frozen=True)
class BottleItem:
    """捞到的漂流瓶数据。"""

    id: int
    sender_id: int
    sender_group_id: int
    content: list[dict[str, Any]]


@dataclass(frozen=True)
class PoolInfo:
    """漂流瓶池信息（含统计）。"""

    id: int
    name: str
    available_count: int


class DriftBottleService:
    """漂流瓶核心服务 —— 封装扔/捞/池管理逻辑。"""

    __slots__ = ("_session_factory",)

    def __init__(self, *, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    # ── 工具方法 ──

    async def get_pool_id(self, group_id: int) -> int:
        """查询群所属池 id，无记录返回默认池 id。"""
        async with self._session_factory() as session:
            row = await session.get(DriftBottleGroupPool, group_id)
            return row.pool_id if row is not None else DRIFT_BOTTLE_DEFAULT_POOL_ID

    # ── Bot 核心功能 ──

    async def throw_bottle(
        self,
        *,
        pool_id: int,
        sender_id: int,
        sender_group_id: int,
        content: list[dict[str, Any]],
    ) -> DriftBottleItem:
        """投入一个漂流瓶。"""
        async with self._session_factory() as session:
            item = DriftBottleItem(
                pool_id=pool_id,
                sender_id=sender_id,
                sender_group_id=sender_group_id,
                content=content,
            )
            session.add(item)
            await session.commit()
            await session.refresh(item)
            return item

    async def pick_bottle(self, *, pool_id: int, user_id: int) -> BottleItem | None:
        """原子性捞取一个漂流瓶，返回瓶内容；池内无可用瓶返回 None。"""
        async with self._session_factory() as session:
            # 子查询：随机选一个 available 且非本人的瓶
            subq = (
                select(DriftBottleItem.id)
                .where(
                    DriftBottleItem.pool_id == pool_id,
                    DriftBottleItem.is_picked.is_(False),
                    DriftBottleItem.sender_id != user_id,
                )
                .order_by(func.random())
                .limit(1)
                .scalar_subquery()
            )
            # 原子 UPDATE + RETURNING（双重 is_picked 检查防并发重捞）
            stmt = (
                update(DriftBottleItem)
                .where(
                    DriftBottleItem.id == subq,
                    DriftBottleItem.is_picked.is_(False),
                )
                .values(
                    is_picked=True,
                    picked_by=user_id,
                    picked_at=datetime.now(UTC),
                )
                .returning(
                    DriftBottleItem.id,
                    DriftBottleItem.sender_id,
                    DriftBottleItem.sender_group_id,
                    DriftBottleItem.content,
                )
            )
            result = await session.execute(stmt)
            row = result.fetchone()
            await session.commit()
            if row is None:
                return None
            return BottleItem(
                id=row.id,
                sender_id=row.sender_id,
                sender_group_id=row.sender_group_id,
                content=row.content,
            )

    # ── 后台池管理 ──

    async def list_pools(self) -> list[PoolInfo]:
        """列出所有池，含各池未捞取瓶数统计。"""
        async with self._session_factory() as session:
            # LEFT JOIN 统计 available 瓶数
            stmt = (
                select(
                    DriftBottlePool.id,
                    DriftBottlePool.name,
                    func.count(DriftBottleItem.id).label("available_count"),
                )
                .outerjoin(
                    DriftBottleItem,
                    (DriftBottleItem.pool_id == DriftBottlePool.id)
                    & (DriftBottleItem.is_picked.is_(False)),
                )
                .group_by(DriftBottlePool.id, DriftBottlePool.name)
                .order_by(DriftBottlePool.id)
            )
            rows = (await session.execute(stmt)).fetchall()
            return [PoolInfo(id=r.id, name=r.name, available_count=r.available_count) for r in rows]

    async def create_pool(self, name: str) -> DriftBottlePool:
        """创建新漂流瓶池。

        Raises:
            ValueError: 名称重复。
        """
        async with self._session_factory() as session:
            pool = DriftBottlePool(name=name)
            session.add(pool)
            try:
                await session.commit()
                await session.refresh(pool)
                return pool
            except IntegrityError as exc:
                await session.rollback()
                raise ValueError(f"漂流瓶池名称已存在：{name}") from exc

    async def delete_pool(self, pool_id: int) -> None:
        """删除漂流瓶池。

        Raises:
            ValueError: 尝试删除默认池（id=0）或池不存在。
            RuntimeError: 池下仍有群归属（RESTRICT 约束触发 IntegrityError）。
        """
        if pool_id == DRIFT_BOTTLE_DEFAULT_POOL_ID:
            raise ValueError("默认漂流瓶池不可删除")
        async with self._session_factory() as session:
            pool = await session.get(DriftBottlePool, pool_id)
            if pool is None:
                raise ValueError(f"漂流瓶池不存在：{pool_id}")
            try:
                await session.delete(pool)
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise RuntimeError("该池下仍有群归属，无法删除") from exc

    async def list_pool_groups(self, pool_id: int) -> list[int]:
        """列出某池下所有群号。"""
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(DriftBottleGroupPool.group_id).where(DriftBottleGroupPool.pool_id == pool_id)
            )
            return list(rows)

    async def assign_group_pool(self, group_id: int, pool_id: int) -> None:
        """将群分配到指定池（pool_id=0 = 移回默认池，即删除映射记录）。

        Raises:
            ValueError: pool_id 不存在（非 0）。
        """
        async with self._session_factory() as session:
            if pool_id != DRIFT_BOTTLE_DEFAULT_POOL_ID:
                pool = await session.get(DriftBottlePool, pool_id)
                if pool is None:
                    raise ValueError(f"漂流瓶池不存在：{pool_id}")

            existing = await session.get(DriftBottleGroupPool, group_id)

            if pool_id == DRIFT_BOTTLE_DEFAULT_POOL_ID:
                # 移回默认池 = 删除映射记录
                if existing is not None:
                    await session.delete(existing)
            else:
                if existing is None:
                    session.add(DriftBottleGroupPool(group_id=group_id, pool_id=pool_id))
                else:
                    existing.pool_id = pool_id
            await session.commit()


# ── 生命周期注册 ──

from src.core.lifecycle import startup  # noqa: E402


@startup(
    name="drift_bottle_service",
    provides=["drift_bottle_service"],
    requires=["session_factory"],
    dispatcher_services=["drift_bottle_service"],
)
async def _lifecycle_start(deps: dict[str, Any]) -> dict[str, Any]:
    """漂流瓶服务模块启动。"""
    return {"drift_bottle_service": DriftBottleService(session_factory=deps["session_factory"])}
