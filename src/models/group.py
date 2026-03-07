"""群组 ORM 模型。"""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db.base import Base


class Group(Base):
    __tablename__ = "groups"

    group_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    group_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
