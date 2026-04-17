"""用户管理只读查询服务 —— 分页列表、详情查询，SRP 分离自 PersonnelService。

PersonnelService 负责写操作（upsert、增量事件、管理员管理），
PersonnelQueryService 负责读操作（列表、详情），两者共享同一 session_factory / cache。
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import ColumnElement, func, select

from src.core.db.utils import escape_like
from src.core.utils.helpers import ceil_div
from src.models.personnel import Group, GroupMembership, User

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from src.core.cache.client import CacheClient

logger = structlog.get_logger()


class PersonnelQueryService:
    """用户管理只读查询服务。"""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        cache: CacheClient,
    ) -> None:
        self._session_factory = session_factory
        self._cache = cache

    # ── 用户查询 ──

    async def get_user(self, qq: int) -> dict[str, Any] | None:
        """获取单个用户详情（含活跃群聊数）。"""
        async with self._session_factory() as session:
            user = await session.get(User, qq)
            if not user:
                return None

            # 使用 COUNT 而非加载全部行
            count_result = await session.execute(
                select(func.count())
                .select_from(GroupMembership)
                .where(GroupMembership.user_id == qq, GroupMembership.is_active.is_(True))
            )
            group_count = count_result.scalar() or 0

            return {
                "qq": user.qq,
                "nickname": user.nickname,
                "relation": user.relation,
                "group_count": group_count,
                "last_synced": user.last_synced.isoformat() if user.last_synced else None,
            }

    async def list_users(
        self,
        page: int = 1,
        page_size: int = 20,
        relation: str | None = None,
        qq: int | None = None,
        nickname: str | None = None,
    ) -> dict[str, Any]:
        """分页查询用户列表（修复 N+1：批量查 group_count，COUNT 计总数）。"""
        async with self._session_factory() as session:
            # 构建过滤条件
            conditions = []
            if relation:
                conditions.append(User.relation == relation)
            if qq:
                conditions.append(User.qq == qq)
            if nickname:
                conditions.append(User.nickname.ilike(f"%{escape_like(nickname)}%", escape="\\"))

            # 总数：使用 COUNT(*) 而非 len(result.all())
            count_stmt = select(func.count()).select_from(User)
            if conditions:
                count_stmt = count_stmt.where(*conditions)
            total = (await session.execute(count_stmt)).scalar() or 0

            if total == 0:
                pages = 0
                return {
                    "items": [],
                    "total": 0,
                    "page": page,
                    "page_size": page_size,
                    "pages": pages,
                }

            # 分页查询
            offset = (page - 1) * page_size
            stmt = select(User).order_by(User.qq).offset(offset).limit(page_size)
            if conditions:
                stmt = stmt.where(*conditions)
            users = (await session.execute(stmt)).scalars().all()

            # 批量查询 group_count，避免 N+1
            user_ids = [u.qq for u in users]
            gc_rows = await session.execute(
                select(GroupMembership.user_id, func.count().label("cnt"))
                .where(
                    GroupMembership.user_id.in_(user_ids),
                    GroupMembership.is_active.is_(True),
                )
                .group_by(GroupMembership.user_id)
            )
            group_counts: dict[int, int] = {row.user_id: row.cnt for row in gc_rows.all()}

            items = [
                {
                    "qq": u.qq,
                    "nickname": u.nickname,
                    "relation": u.relation,
                    "group_count": group_counts.get(u.qq, 0),
                    "last_synced": u.last_synced.isoformat() if u.last_synced else None,
                }
                for u in users
            ]

            pages = ceil_div(total, page_size)
            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "pages": pages,
            }

    async def get_user_groups(self, qq: int) -> list[dict[str, Any]]:
        """获取用户所属的所有群聊。"""
        async with self._session_factory() as session:
            result = await session.execute(
                select(GroupMembership, Group)
                .join(Group, GroupMembership.group_id == Group.group_id)
                .where(GroupMembership.user_id == qq, GroupMembership.is_active.is_(True))
            )
            rows = result.all()
            return [
                {
                    "group_id": group.group_id,
                    "group_name": group.group_name,
                    "member_count": group.member_count,
                    "max_member_count": group.max_member_count,
                    "is_active": group.is_active,
                    "last_synced": group.last_synced.isoformat() if group.last_synced else None,
                    "card": membership.card,
                    "role": membership.role,
                    "join_time": membership.join_time,
                }
                for membership, group in rows
            ]

    # ── 群查询 ──

    async def list_groups(
        self,
        page: int = 1,
        page_size: int = 20,
        group_name: str | None = None,
        is_active: bool | None = None,
    ) -> dict[str, Any]:
        """分页查询群列表。"""
        async with self._session_factory() as session:
            conditions: list[ColumnElement[bool]] = []
            if group_name:
                conditions.append(
                    Group.group_name.ilike(f"%{escape_like(group_name)}%", escape="\\")
                )
            if is_active is not None:
                conditions.append(Group.is_active == is_active)

            count_stmt = select(func.count()).select_from(Group)
            if conditions:
                count_stmt = count_stmt.where(*conditions)
            total = (await session.execute(count_stmt)).scalar() or 0

            if total == 0:
                return {"items": [], "total": 0, "page": page, "page_size": page_size, "pages": 0}

            offset = (page - 1) * page_size
            stmt = select(Group).order_by(Group.group_id).offset(offset).limit(page_size)
            if conditions:
                stmt = stmt.where(*conditions)
            groups = (await session.execute(stmt)).scalars().all()

            items = [
                {
                    "group_id": g.group_id,
                    "group_name": g.group_name,
                    "member_count": g.member_count,
                    "max_member_count": g.max_member_count,
                    "is_active": g.is_active,
                    "last_synced": g.last_synced.isoformat() if g.last_synced else None,
                }
                for g in groups
            ]

            pages = ceil_div(total, page_size)
            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "pages": pages,
            }

    async def get_group(self, group_id: int) -> dict[str, Any] | None:
        """获取单个群聊详情。"""
        async with self._session_factory() as session:
            group = await session.get(Group, group_id)
            if not group:
                return None
            return {
                "group_id": group.group_id,
                "group_name": group.group_name,
                "member_count": group.member_count,
                "max_member_count": group.max_member_count,
                "is_active": group.is_active,
                "last_synced": group.last_synced.isoformat() if group.last_synced else None,
            }

    async def resolve_batch(
        self,
        user_ids: list[int],
        group_ids: list[int],
    ) -> dict[str, Any]:
        """批量解析用户和群 ID 到基本展示信息。

        Args:
            user_ids: 需要解析的 QQ 号列表，最多 200 个。
            group_ids: 需要解析的群号列表，最多 200 个。

        Returns:
            ``{"users": {str(qq): {"nickname", "relation"}}, "groups": {str(gid): {"group_name"}}}``
        """

        async def _query_users() -> dict[str, dict[str, str]]:
            if not user_ids:
                return {}
            async with self._session_factory() as session:
                rows = await session.execute(
                    select(User.qq, User.nickname, User.relation).where(User.qq.in_(user_ids))
                )
                return {
                    str(r.qq): {"nickname": r.nickname, "relation": r.relation} for r in rows.all()
                }

        async def _query_groups() -> dict[str, dict[str, str]]:
            if not group_ids:
                return {}
            async with self._session_factory() as session:
                rows = await session.execute(
                    select(Group.group_id, Group.group_name).where(Group.group_id.in_(group_ids))
                )
                return {str(r.group_id): {"group_name": r.group_name} for r in rows.all()}

        users, groups = await asyncio.gather(_query_users(), _query_groups())
        return {"users": users, "groups": groups}

    async def list_group_members(
        self,
        group_id: int,
        page: int = 1,
        page_size: int = 20,
        role: str | None = None,
        nickname: str | None = None,
        qq: int | None = None,
    ) -> dict[str, Any]:
        """分页获取群成员列表。"""
        async with self._session_factory() as session:
            base_conditions = [
                GroupMembership.group_id == group_id,
                GroupMembership.is_active.is_(True),
            ]
            if role:
                base_conditions.append(GroupMembership.role == role)
            if qq:
                base_conditions.append(GroupMembership.user_id == qq)

            # 构建带 User JOIN 的查询
            join_cond = GroupMembership.user_id == User.qq
            if nickname:
                base_conditions.append(
                    User.nickname.ilike(f"%{escape_like(nickname)}%", escape="\\")
                )

            count_stmt = (
                select(func.count())
                .select_from(GroupMembership)
                .join(User, join_cond)
                .where(*base_conditions)
            )
            total = (await session.execute(count_stmt)).scalar() or 0

            if total == 0:
                return {"items": [], "total": 0, "page": page, "page_size": page_size, "pages": 0}

            offset = (page - 1) * page_size
            stmt = (
                select(GroupMembership, User)
                .join(User, join_cond)
                .where(*base_conditions)
                .order_by(GroupMembership.user_id)
                .offset(offset)
                .limit(page_size)
            )
            rows = (await session.execute(stmt)).all()

            items = [
                {
                    "qq": user.qq,
                    "nickname": user.nickname,
                    "card": membership.card,
                    "role": membership.role,
                    "relation": user.relation,
                    "join_time": membership.join_time,
                    "last_active_time": membership.last_active_time,
                    "title": membership.title,
                }
                for membership, user in rows
            ]

            pages = ceil_div(total, page_size)
            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "pages": pages,
            }
