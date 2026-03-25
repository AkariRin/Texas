"""权限系统 ORM 模型 —— Feature、GroupFeaturePermission、PrivateFeaturePermission。"""

from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db.base import Base


class Feature(Base):
    """功能注册表 —— 记录所有 controller/method 级功能及其默认状态。"""

    __tablename__ = "feature_registry"

    # name 格式：controller 级为 "echo"，method 级为 "echo.handle_echo"
    name: Mapped[str] = mapped_column(String(64), primary_key=True, comment="功能唯一标识")

    # parent 为 None 表示 controller 级；非 None 表示 method 级
    parent: Mapped[str | None] = mapped_column(
        ForeignKey("feature_registry.name", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="父功能（controller 级为 null，method 级指向 controller）",
    )

    display_name: Mapped[str] = mapped_column(
        String(128), default="", comment="显示名称（命令名、描述等）"
    )
    description: Mapped[str] = mapped_column(String(256), default="", comment="功能描述")

    # 装饰器声明的默认值（开发者定义）
    default_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="装饰器声明的默认启用状态"
    )

    # 全局开关（管理员可覆盖）
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="全局开关（管理员可修改）")

    # 私聊模式：blacklist（黑名单）/ whitelist（白名单）；仅 controller 级有效
    private_mode: Mapped[str] = mapped_column(
        String(16), default="blacklist", comment="私聊权限模式: blacklist/whitelist"
    )

    # 标记功能是否仍然活跃（对应代码中仍存在的 controller/method）
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="功能是否仍在代码中存在")

    # 自关联：children 仅在 controller 级有意义
    children: Mapped[list[Feature]] = relationship(
        "Feature",
        foreign_keys=[parent],
        back_populates="parent_feature",
        lazy="select",
    )
    parent_feature: Mapped[Feature | None] = relationship(
        "Feature",
        foreign_keys=[parent],
        back_populates="children",
        remote_side=[name],
        lazy="select",
    )

    group_permissions: Mapped[list[GroupFeaturePermission]] = relationship(
        back_populates="feature", lazy="select"
    )
    private_users: Mapped[list[PrivateFeaturePermission]] = relationship(
        back_populates="feature", lazy="select"
    )

    __table_args__ = (Index("ix_feature_registry_parent", "parent"),)


class GroupFeaturePermission(Base):
    """群聊功能权限表 —— 记录特定群对特定功能的启用/禁用状态。"""

    __tablename__ = "group_feature_permissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)

    group_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("groups.group_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="群号",
    )

    feature_name: Mapped[str] = mapped_column(
        ForeignKey("feature_registry.name", ondelete="CASCADE"),
        nullable=False,
        comment="功能标识（controller 或 method 级）",
    )

    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, comment="是否在该群启用")

    feature: Mapped[Feature] = relationship(back_populates="group_permissions", lazy="select")

    __table_args__ = (UniqueConstraint("group_id", "feature_name", name="uq_group_feature"),)


class PrivateFeaturePermission(Base):
    """私聊功能用户权限表 —— 记录用户在私聊中对某功能的黑/白名单成员。"""

    __tablename__ = "private_feature_permissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)

    # controller 级功能标识
    feature_name: Mapped[str] = mapped_column(
        ForeignKey("feature_registry.name", ondelete="CASCADE"),
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

    feature: Mapped[Feature] = relationship(back_populates="private_users", lazy="select")

    __table_args__ = (UniqueConstraint("feature_name", "user_qq", name="uq_private_feature_user"),)
