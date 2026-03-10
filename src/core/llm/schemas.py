"""LLM Pydantic 请求/响应模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ── 提供商 ──


class ProviderCreate(BaseModel):
    name: str = Field(..., max_length=64, description="提供商名称")
    api_base: str = Field(..., max_length=512, description="API 基础地址")
    api_key: str = Field(..., max_length=512, description="API 密钥")
    max_retries: int = Field(2, ge=0, le=10, description="最大重试次数")
    timeout: int = Field(60, ge=1, le=600, description="请求超时 (秒)")
    retry_interval: int = Field(1, ge=0, le=60, description="重试间隔 (秒)")


class ProviderUpdate(BaseModel):
    name: str | None = Field(None, max_length=64)
    api_base: str | None = Field(None, max_length=512)
    api_key: str | None = Field(None, max_length=512)
    max_retries: int | None = Field(None, ge=0, le=10)
    timeout: int | None = Field(None, ge=1, le=600)
    retry_interval: int | None = Field(None, ge=0, le=60)


class ProviderResponse(BaseModel):
    id: str
    name: str
    api_base: str
    api_key_masked: str
    max_retries: int
    timeout: int
    retry_interval: int
    model_count: int

    @staticmethod
    def mask_key(key: str) -> str:
        """将 API Key 掩码为 sk-****abcd 格式。"""
        if len(key) <= 8:
            return "****"
        return f"{key[:3]}****{key[-4:]}"


# ── 模型 ──


class ModelCreate(BaseModel):
    provider_id: str
    model_name: str = Field(..., max_length=128)
    display_name: str | None = None
    input_price: float = 0.0
    output_price: float = 0.0
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int | None = None
    force_stream: bool = False
    extra_params: dict[str, Any] = Field(default_factory=dict)
    is_enabled: bool = True


class ModelUpdate(BaseModel):
    display_name: str | None = None
    input_price: float | None = None
    output_price: float | None = None
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = None
    force_stream: bool | None = None
    extra_params: dict[str, Any] | None = None
    is_enabled: bool | None = None


class ModelResponse(BaseModel):
    id: str
    provider_id: str
    provider_name: str
    model_name: str
    display_name: str | None
    input_price: float
    output_price: float
    temperature: float
    max_tokens: int | None
    force_stream: bool
    extra_params: dict[str, Any]
    is_enabled: bool


# ── Chat ──


class ChatMessage(BaseModel):
    role: str = Field(..., description="消息角色: system / user / assistant")
    content: str = Field(..., description="消息内容")


class ChatRequest(BaseModel):
    model_id: str = Field(..., description="模型 ID")
    messages: list[ChatMessage] = Field(..., min_length=1, description="消息列表")
    temperature: float | None = Field(None, ge=0.0, le=2.0, description="覆盖温度")
    max_tokens: int | None = Field(None, description="覆盖最大 token 数")
    stream: bool = Field(False, description="是否流式输出")
