"""LLM ORM 模型 —— LLMProvider, LLM。"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db.base import Base


class LLMProvider(Base):
    """LLM 提供商表 —— 管理多个 OpenAI 兼容提供商。"""

    __tablename__ = "llm_providers"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="提供商名称")
    api_base: Mapped[str] = mapped_column(String(512), nullable=False, comment="API 基础地址")
    api_key: Mapped[str] = mapped_column(String(512), nullable=False, comment="API 密钥")
    max_retries: Mapped[int] = mapped_column(Integer, default=2, comment="最大重试次数")
    timeout: Mapped[int] = mapped_column(Integer, default=60, comment="请求超时 (秒)")
    retry_interval: Mapped[int] = mapped_column(Integer, default=1, comment="重试间隔 (秒)")

    # 关联
    models: Mapped[list[LLM]] = relationship(
        back_populates="provider",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class LLM(Base):
    """LLM 模型表 —— 提供商下的具体模型配置。"""

    __tablename__ = "llms"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("llm_providers.id"), nullable=False, index=True, comment="所属提供商"
    )
    model_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="模型标识")
    display_name: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="展示名称"
    )
    input_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), default=Decimal("0"), comment="输入价格 (每百万 token, USD)"
    )
    output_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), default=Decimal("0"), comment="输出价格 (每百万 token, USD)"
    )
    temperature: Mapped[float] = mapped_column(Float, default=0.7, comment="默认温度")
    max_tokens: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="最大输出 token 数"
    )
    force_stream: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否强制流式输出"
    )
    extra_params: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, comment="额外请求参数"
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")

    __table_args__ = (
        UniqueConstraint("provider_id", "model_name", name="uq_provider_model"),
    )

    # 关联
    provider: Mapped[LLMProvider] = relationship(back_populates="models")

