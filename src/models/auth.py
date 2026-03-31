"""鉴权 ORM 模型 —— AdminCredential, WebAuthnCredential。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.core.db.base import Base


class AdminCredential(Base):
    """管理员凭据表 —— 全局唯一一条记录（单管理员模型）。"""

    __tablename__ = "admin_credentials"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="bcrypt 哈希后的静态令牌"
    )
    totp_secret: Mapped[str | None] = mapped_column(
        String(64), nullable=True, default=None, comment="base32 TOTP secret，NULL 表示未启用"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )


class WebAuthnCredential(Base):
    """WebAuthn Passkey 凭据表 —— 可注册多个设备。"""

    __tablename__ = "webauthn_credentials"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    credential_id: Mapped[bytes] = mapped_column(
        LargeBinary, unique=True, nullable=False, comment="WebAuthn Credential ID"
    )
    public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, comment="COSE 格式公钥")
    sign_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="防重放签名计数器"
    )
    device_name: Mapped[str] = mapped_column(
        String(64), default="", nullable=False, comment="用户自定义设备名称"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="注册时间"
    )
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="最后使用时间"
    )
