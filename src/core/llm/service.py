"""LLM 业务逻辑层 —— 提供商/模型 CRUD 与 LLM 调用编排。"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.core.llm.client import LLMClient
from src.core.llm.models import LLM, LLMProvider
from src.core.llm.schemas import (  # noqa: TC001
    ModelCreate,
    ModelUpdate,
    ProviderCreate,
    ProviderUpdate,
)

if TYPE_CHECKING:
    from src.core.cache.client import CacheClient

logger = structlog.get_logger()


class LLMService:
    """LLM 核心服务 —— 封装提供商/模型 CRUD、调用编排。"""

    def __init__(
        self,
        session_factory: Any,
        cache: CacheClient,
    ) -> None:
        self._session_factory = session_factory
        self._cache = cache
        self._client = LLMClient()

    # ══════════════════════════════════════════════
    #  提供商 CRUD
    # ══════════════════════════════════════════════

    async def list_providers(self) -> list[dict[str, Any]]:
        """列出所有提供商（含模型数量）。"""
        async with self._session_factory() as session:
            stmt = select(LLMProvider).options(selectinload(LLMProvider.models))
            result = await session.execute(stmt)
            providers = result.scalars().all()
            return [self._provider_to_dict(p) for p in providers]

    async def get_provider(self, provider_id: uuid.UUID) -> dict[str, Any] | None:
        """获取单个提供商详情（含旗下模型列表）。"""
        async with self._session_factory() as session:
            stmt = (
                select(LLMProvider)
                .where(LLMProvider.id == provider_id)
                .options(selectinload(LLMProvider.models))
            )
            result = await session.execute(stmt)
            provider = result.scalar_one_or_none()
            if provider is None:
                return None
            data = self._provider_to_dict(provider)
            data["models"] = [self._model_to_dict(m) for m in provider.models]
            return data

    async def create_provider(self, data: ProviderCreate) -> dict[str, Any]:
        """创建提供商。"""
        async with self._session_factory() as session:
            provider = LLMProvider(
                name=data.name,
                api_base=data.api_base,
                api_key=data.api_key,
                max_retries=data.max_retries,
                timeout=data.timeout,
                retry_interval=data.retry_interval,
            )
            session.add(provider)
            await session.commit()
            await session.refresh(provider)
            logger.info("LLM 提供商已创建", name=data.name, event_type="llm.provider_created")
            return self._provider_to_dict(provider)

    async def update_provider(
        self, provider_id: uuid.UUID, data: ProviderUpdate
    ) -> dict[str, Any] | None:
        """更新提供商（字段级部分更新）。"""
        async with self._session_factory() as session:
            stmt = (
                select(LLMProvider)
                .where(LLMProvider.id == provider_id)
                .options(selectinload(LLMProvider.models))
            )
            result = await session.execute(stmt)
            provider = result.scalar_one_or_none()
            if provider is None:
                return None

            update_fields = data.model_dump(exclude_unset=True)
            for field, value in update_fields.items():
                setattr(provider, field, value)

            await session.commit()
            await session.refresh(provider)

            # 配置变更时使客户端缓存失效
            if any(
                k in update_fields
                for k in ("api_base", "api_key", "max_retries", "timeout", "retry_interval")
            ):
                self._client.invalidate(str(provider_id))

            logger.info(
                "LLM 提供商已更新",
                provider_id=str(provider_id),
                fields=list(update_fields.keys()),
                event_type="llm.provider_updated",
            )
            return self._provider_to_dict(provider)

    async def delete_provider(self, provider_id: uuid.UUID) -> bool:
        """删除提供商（级联删除旗下模型）。"""
        async with self._session_factory() as session:
            stmt = select(LLMProvider).where(LLMProvider.id == provider_id)
            result = await session.execute(stmt)
            provider = result.scalar_one_or_none()
            if provider is None:
                return False

            await session.delete(provider)
            await session.commit()
            self._client.invalidate(str(provider_id))

            logger.info(
                "LLM 提供商已删除",
                provider_id=str(provider_id),
                event_type="llm.provider_deleted",
            )
            return True

    # ══════════════════════════════════════════════
    #  模型 CRUD
    # ══════════════════════════════════════════════

    async def list_models(self, provider_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
        """列出模型（可按提供商筛选）。"""
        async with self._session_factory() as session:
            stmt = select(LLM).options(selectinload(LLM.provider))
            if provider_id is not None:
                stmt = stmt.where(LLM.provider_id == provider_id)
            result = await session.execute(stmt)
            models = result.scalars().all()
            return [self._model_to_dict(m) for m in models]

    async def get_model(self, model_id: uuid.UUID) -> dict[str, Any] | None:
        """获取单个模型详情。"""
        async with self._session_factory() as session:
            stmt = select(LLM).where(LLM.id == model_id).options(selectinload(LLM.provider))
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            if model is None:
                return None
            return self._model_to_dict(model)

    async def create_model(self, data: ModelCreate) -> dict[str, Any]:
        """创建模型。"""
        async with self._session_factory() as session:
            model = LLM(
                provider_id=uuid.UUID(data.provider_id),
                model_name=data.model_name,
                display_name=data.display_name,
                input_price=Decimal(str(data.input_price)),
                output_price=Decimal(str(data.output_price)),
                temperature=data.temperature,
                max_tokens=data.max_tokens,
                force_stream=data.force_stream,
                extra_params=data.extra_params,
                is_enabled=data.is_enabled,
            )
            session.add(model)
            await session.commit()
            await session.refresh(model, attribute_names=["provider"])
            logger.info(
                "LLM 模型已创建",
                model_name=data.model_name,
                provider_id=data.provider_id,
                event_type="llm.model_created",
            )
            return self._model_to_dict(model)

    async def update_model(self, model_id: uuid.UUID, data: ModelUpdate) -> dict[str, Any] | None:
        """更新模型（字段级部分更新）。"""
        async with self._session_factory() as session:
            stmt = select(LLM).where(LLM.id == model_id).options(selectinload(LLM.provider))
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            if model is None:
                return None

            update_fields = data.model_dump(exclude_unset=True)
            for field, value in update_fields.items():
                if field in ("input_price", "output_price") and value is not None:
                    value = Decimal(str(value))
                setattr(model, field, value)

            await session.commit()
            await session.refresh(model)
            logger.info(
                "LLM 模型已更新",
                model_id=str(model_id),
                fields=list(update_fields.keys()),
                event_type="llm.model_updated",
            )
            return self._model_to_dict(model)

    async def delete_model(self, model_id: uuid.UUID) -> bool:
        """删除模型。"""
        async with self._session_factory() as session:
            stmt = select(LLM).where(LLM.id == model_id)
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            if model is None:
                return False

            await session.delete(model)
            await session.commit()
            logger.info(
                "LLM 模型已删除",
                model_id=str(model_id),
                event_type="llm.model_deleted",
            )
            return True

    # ══════════════════════════════════════════════
    #  LLM 调用
    # ══════════════════════════════════════════════

    async def chat(
        self,
        model_id: uuid.UUID,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> Any:
        """使用指定模型进行对话。

        Returns:
            stream=False → ChatCompletion 对象
            stream=True  → AsyncStream[ChatCompletionChunk] 异步迭代器
        """
        async with self._session_factory() as session:
            stmt = (
                select(LLM)
                .where(LLM.id == model_id, LLM.is_enabled.is_(True))
                .options(selectinload(LLM.provider))
            )
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()

        if model is None:
            raise ValueError(f"模型不存在或已禁用: {model_id}")

        provider = model.provider

        # 合并参数：模型默认 < 请求覆盖
        final_temp = temperature if temperature is not None else model.temperature
        final_max_tokens = max_tokens if max_tokens is not None else model.max_tokens
        final_stream = stream or model.force_stream

        return await self._client.chat_completion(
            api_base=provider.api_base,
            api_key=provider.api_key,
            provider_id=str(provider.id),
            model=model.model_name,
            messages=messages,
            temperature=final_temp,
            max_tokens=final_max_tokens,
            stream=final_stream,
            extra_params=model.extra_params or None,
            max_retries=provider.max_retries,
            timeout=provider.timeout,
            retry_interval=provider.retry_interval,
        )

    async def chat_by_name(
        self,
        model_name: str,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> Any:
        """按 model_name 查找首个启用模型并调用。"""
        async with self._session_factory() as session:
            stmt = (
                select(LLM)
                .where(LLM.model_name == model_name, LLM.is_enabled.is_(True))
                .options(selectinload(LLM.provider))
                .limit(1)
            )
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()

        if model is None:
            raise ValueError(f"找不到启用的模型: {model_name}")

        return await self.chat(
            model.id,
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
        )

    async def test_provider(self, provider_id: uuid.UUID) -> dict[str, Any]:
        """测试提供商连通性。"""
        async with self._session_factory() as session:
            stmt = select(LLMProvider).where(LLMProvider.id == provider_id)
            result = await session.execute(stmt)
            provider = result.scalar_one_or_none()

        if provider is None:
            raise ValueError(f"提供商不存在: {provider_id}")

        try:
            resp = await self._client.chat_completion(
                api_base=provider.api_base,
                api_key=provider.api_key,
                provider_id=str(provider.id),
                model="gpt-3.5-turbo",  # 使用通用模型名测试连通性
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=5,
                stream=False,
                max_retries=provider.max_retries,
                timeout=provider.timeout,
                retry_interval=provider.retry_interval,
            )
            return {
                "success": True,
                "message": "连接成功",
                "model": resp.model if hasattr(resp, "model") else None,
            }
        except Exception as exc:
            logger.warning(
                "提供商连通性测试失败",
                provider_id=str(provider_id),
                error=str(exc),
                event_type="llm.test_failed",
            )
            return {
                "success": False,
                "message": str(exc),
            }

    async def close(self) -> None:
        """释放内部资源。"""
        await self._client.close()

    # ══════════════════════════════════════════════
    #  内部辅助方法
    # ══════════════════════════════════════════════

    @staticmethod
    def _provider_to_dict(provider: LLMProvider) -> dict[str, Any]:
        """将 LLMProvider ORM 对象转换为响应字典。"""
        from src.core.llm.schemas import ProviderResponse

        return {
            "id": str(provider.id),
            "name": provider.name,
            "api_base": provider.api_base,
            "api_key_masked": ProviderResponse.mask_key(provider.api_key),
            "max_retries": provider.max_retries,
            "timeout": provider.timeout,
            "retry_interval": provider.retry_interval,
            "model_count": len(provider.models) if provider.models else 0,
        }

    @staticmethod
    def _model_to_dict(model: LLM) -> dict[str, Any]:
        """将 LLM ORM 对象转换为响应字典。"""
        return {
            "id": str(model.id),
            "provider_id": str(model.provider_id),
            "provider_name": model.provider.name if model.provider else "",
            "model_name": model.model_name,
            "display_name": model.display_name,
            "input_price": float(model.input_price),
            "output_price": float(model.output_price),
            "temperature": model.temperature,
            "max_tokens": model.max_tokens,
            "force_stream": model.force_stream,
            "extra_params": model.extra_params or {},
            "is_enabled": model.is_enabled,
        }
