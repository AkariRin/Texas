"""今日老婆（jrlp）业务逻辑服务。"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from src.models.jrlp import WifeRecord
from src.models.personnel import GroupMembership

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = structlog.get_logger()


class JrlpService:
    """今日老婆服务 —— 封装抽取、预设、查询、修改、删除逻辑。"""

    __slots__ = ("_session_factory",)

    def __init__(self, *, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    # ── 核心抽取 ──

    async def get_or_draw(
        self, group_id: int, user_id: int, today: date
    ) -> tuple[WifeRecord, bool]:
        """查询或抽取今日老婆。

        Returns:
            (record, is_new): is_new=True 表示本次为首次抽取（含预设触发）。

        Raises:
            ValueError: 群内无可抽取的活跃成员。
        """
        async with self._session_factory() as session:
            record = await self._find_record(session, group_id, user_id, today)

            if record is not None:
                if record.drawn_at is not None:
                    return record, False
                # 预设未触发 → 标记为已抽取
                record.drawn_at = datetime.now(UTC)
                await session.commit()
                await session.refresh(record)
                return record, True

            # 无记录 → 随机抽取群成员
            member = await self._random_member(session, group_id)
            if member is None:
                raise ValueError("该群暂无可抽取的活跃成员")

            wife_name = member.card.strip() or member.user.nickname.strip() or str(member.user_id)
            new_record = WifeRecord(
                group_id=group_id,
                user_id=user_id,
                wife_qq=member.user_id,
                wife_name=wife_name,
                date=today,
                drawn_at=datetime.now(UTC),
            )
            session.add(new_record)
            try:
                await session.commit()
                await session.refresh(new_record)
                return new_record, True
            except IntegrityError:
                # 并发冲突：另一请求已先写入，重查返回
                await session.rollback()
                existing = await self._find_record(session, group_id, user_id, today)
                if existing is None:
                    raise RuntimeError("并发写入后仍未找到记录，请重试") from None
                return existing, False

    # ── 管理接口 ──

    async def list_records(
        self,
        *,
        group_id: int | None = None,
        user_id: int | None = None,
        record_date: date | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[WifeRecord], int]:
        """分页查询抽取/预设记录。"""
        async with self._session_factory() as session:
            stmt = select(WifeRecord)
            if group_id is not None:
                stmt = stmt.where(WifeRecord.group_id == group_id)
            if user_id is not None:
                stmt = stmt.where(WifeRecord.user_id == user_id)
            if record_date is not None:
                stmt = stmt.where(WifeRecord.date == record_date)

            count_result = await session.execute(select(func.count()).select_from(stmt.subquery()))
            total = count_result.scalar_one()

            result = await session.execute(
                stmt.order_by(WifeRecord.date.desc(), WifeRecord.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            return list(result.scalars().all()), total

    async def create_preset(
        self,
        *,
        group_id: int,
        user_id: int,
        wife_qq: int,
        wife_name: str,
        record_date: date,
    ) -> WifeRecord:
        """管理员预设今日老婆（drawn_at=null）。

        Raises:
            ValueError: 该用户今日已有记录（已抽或已预设）。
        """
        async with self._session_factory() as session:
            existing = await self._find_record(session, group_id, user_id, record_date)
            if existing is not None:
                raise ValueError(f"用户 {user_id} 在群 {group_id} 于 {record_date} 已有记录")

            record = WifeRecord(
                group_id=group_id,
                user_id=user_id,
                wife_qq=wife_qq,
                wife_name=wife_name,
                date=record_date,
                drawn_at=None,
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return record

    async def update_record(
        self, record_id: int, *, wife_qq: int, wife_name: str
    ) -> WifeRecord | None:
        """修改记录的老婆信息（预设和已抽取均可修改）。"""
        async with self._session_factory() as session:
            result = await session.execute(select(WifeRecord).where(WifeRecord.id == record_id))
            record = result.scalar_one_or_none()
            if record is None:
                return None
            record.wife_qq = wife_qq
            record.wife_name = wife_name
            await session.commit()
            await session.refresh(record)
            return record

    async def delete_preset(self, record_id: int) -> bool:
        """删除预设记录（仅允许删除 drawn_at=null 的记录）。

        Returns:
            True = 删除成功；False = 记录不存在或已抽取（不允许删除）。
        """
        async with self._session_factory() as session:
            result = await session.execute(select(WifeRecord).where(WifeRecord.id == record_id))
            record = result.scalar_one_or_none()
            if record is None or record.drawn_at is not None:
                return False
            await session.delete(record)
            await session.commit()
            return True

    # ── 内部辅助 ──

    @staticmethod
    async def _find_record(
        session: AsyncSession, group_id: int, user_id: int, record_date: date
    ) -> WifeRecord | None:
        result = await session.execute(
            select(WifeRecord).where(
                WifeRecord.group_id == group_id,
                WifeRecord.user_id == user_id,
                WifeRecord.date == record_date,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _random_member(session: AsyncSession, group_id: int) -> GroupMembership | None:
        result = await session.execute(
            select(GroupMembership)
            .where(
                GroupMembership.group_id == group_id,
                GroupMembership.is_active.is_(True),
            )
            .options(selectinload(GroupMembership.user))
            .order_by(func.random())
            .limit(1)
        )
        return result.scalar_one_or_none()
