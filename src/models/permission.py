"""权限系统 ORM 模型 —— GroupFeaturePermission、PrivateFeaturePermission。

feature_registry 表已移除，功能元数据现由内存不可变注册表（FeatureRegistry）维护。
group_id=0 为哨兵行，代表功能的全局默认启用状态（替代原 Feature.enabled 字段）。
"""

from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db.base import Base


class GroupFeaturePermission(Base):
    """群聊功能权限表 —— 全量记录每个群对每个功能的启用状态。

    group_id=0 为哨兵行，代表功能的全局默认启用开关。
    正常群号行代表该群的显式权限配置（无需回退逻辑）。
    """

    __tablename__ = "permission_group"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)

    group_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
        comment="群号（0 为全局哨兵行）",
    )

    feature_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="功能标识（controller 或 method 级）",
    )

    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, comment="是否在该群启用")

    __table_args__ = (UniqueConstraint("group_id", "feature_name", name="uq_group_feature"),)


class PrivateFeaturePermission(Base):
    """私聊功能用户权限表 —— 全量记录用户在私聊中对某功能的启用状态。

    显式存储 enabled 布尔值，移除黑/白名单概念。
    未在此表记录的用户私聊权限，回退到全局默认值（group_id=0 哨兵行）。
    """

    __tablename__ = "permission_private"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)

    # controller 级功能标识
    feature_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="功能标识（controller 级）",
    )

    user_qq: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.qq", ondelete="CASCADE"),
        nullable=False,
        comment="用户 QQ 号",
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否允许该用户私聊使用此功能"
    )

    __table_args__ = (
        UniqueConstraint("feature_name", "user_qq", name="uq_private_feature_user"),
        Index("ix_permission_private_feature_name", "feature_name"),
    )
