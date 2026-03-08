"""用户 ORM 模型。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger, Boolean, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db.base import Base


class User(Base):
    __tablename__ = "users"

    qq_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    nickname: Mapped[str | None] = mapped_column(String(64), nullable=True)
    permission_level: Mapped[int] = mapped_column(Integer, default=0)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
