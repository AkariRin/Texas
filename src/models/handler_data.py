"""HandlerData —— 每个处理器/作用域的通用键值存储。"""

from __future__ import annotations

from sqlalchemy import BigInteger, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db.base import Base


class HandlerData(Base):
    __tablename__ = "handler_data"
    __table_args__ = (
        UniqueConstraint("handler_name", "key", "scope", "scope_id", name="uq_handler_data"),
    )

    handler_name: Mapped[str] = mapped_column(String(128), index=True)
    key: Mapped[str] = mapped_column(String(256))
    value: Mapped[dict] = mapped_column(JSONB, default=dict)
    scope: Mapped[str] = mapped_column(String(16), default="global")  # global | group | user
    scope_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
