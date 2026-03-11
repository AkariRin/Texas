"""人事管理 ORM 模型 —— User, Group, GroupMembership。"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.core.db.base import Base


class User(Base):
    """机器人已知用户表。"""

    __tablename__ = "users"

    qq: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment="QQ 号")
    nickname: Mapped[str] = mapped_column(String(64), default="", comment="QQ 昵称")

    # ── 关系等级（唯一标识，不使用额外布尔字段） ──
    relation: Mapped[str] = mapped_column(
        String(20),
        default="stranger",
        index=True,
        comment="关系等级: stranger/group_member/friend/admin",
    )

    last_synced: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="最后同步时间"
    )

    # 关联
    memberships: Mapped[list[GroupMembership]] = relationship(
        back_populates="user", lazy="selectin"
    )


class Group(Base):
    """机器人群聊表。"""

    __tablename__ = "groups"

    group_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment="群号")
    group_name: Mapped[str] = mapped_column(String(128), default="", comment="群名称")
    member_count: Mapped[int] = mapped_column(Integer, default=0, comment="当前成员数")
    max_member_count: Mapped[int] = mapped_column(Integer, default=0, comment="最大成员数")

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, index=True, comment="群聊是否活跃（机器人是否仍在群中）"
    )

    last_synced: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="最后同步时间"
    )

    # 关联
    memberships: Mapped[list[GroupMembership]] = relationship(
        back_populates="group", lazy="selectin"
    )


class GroupMembership(Base):
    """群聊成员关系表 —— 记录用户在特定群中的身份信息。"""

    __tablename__ = "group_memberships"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.qq"), index=True, comment="关联用户 QQ 号"
    )
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.group_id"), index=True, comment="关联群号"
    )

    card: Mapped[str] = mapped_column(String(64), default="", comment="群名片")
    role: Mapped[str] = mapped_column(
        String(20), default="member", comment="群内角色: owner/admin/member"
    )
    join_time: Mapped[int] = mapped_column(BigInteger, default=0, comment="入群时间戳")
    last_active_time: Mapped[int] = mapped_column(BigInteger, default=0, comment="最后活跃时间戳")
    title: Mapped[str] = mapped_column(String(64), default="", comment="群头衔")
    title_expire_time: Mapped[int] = mapped_column(BigInteger, default=0, comment="头衔过期时间戳")
    level: Mapped[str] = mapped_column(String(10), default="", comment="群等级")

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, index=True, comment="是否仍在群中"
    )

    # 唯一约束：同一用户在同一群中只有一条记录
    __table_args__ = (UniqueConstraint("user_id", "group_id", name="uq_user_group"),)

    # 关联
    user: Mapped[User] = relationship(back_populates="memberships")
    group: Mapped[Group] = relationship(back_populates="memberships")
