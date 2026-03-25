"""OpenAI 兼容 LLM 客户端封装 —— 维护按 provider_id 缓存的 AsyncOpenAI 实例池。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import structlog
from openai import AsyncOpenAI

if TYPE_CHECKING:
    from openai import AsyncStream
    from openai.types.chat import ChatCompletion, ChatCompletionChunk

logger = structlog.get_logger()


class LLMClient:
    """基于 openai 库的通用 LLM 调用客户端，兼容 OpenAI API 协议。

    内部维护一个按 provider_id 缓存的 AsyncOpenAI 实例池，
    避免重复创建客户端。
    """

    def __init__(self) -> None:
        self._clients: dict[str, AsyncOpenAI] = {}
        # provider_id -> (max_retries, retry_interval)
        self._retry_configs: dict[str, tuple[int, int]] = {}

    def _get_or_create(
        self,
        provider_id: str,
        api_base: str,
        api_key: str,
        max_retries: int = 2,
        timeout: int = 60,
        retry_interval: int = 1,
    ) -> AsyncOpenAI:
        """获取或创建指定提供商的 AsyncOpenAI 客户端。"""
        if provider_id not in self._clients:
            self._clients[provider_id] = AsyncOpenAI(
                base_url=api_base,
                api_key=api_key,
                max_retries=max_retries,
                timeout=float(timeout),
            )
            self._retry_configs[provider_id] = (max_retries, retry_interval)
        return self._clients[provider_id]

    def invalidate(self, provider_id: str) -> None:
        """使指定提供商的缓存客户端失效（提供商配置更新时调用）。"""
        self._clients.pop(provider_id, None)
        self._retry_configs.pop(provider_id, None)

    async def chat_completion(
        self,
        *,
        api_base: str,
        api_key: str,
        provider_id: str,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
        extra_params: dict[str, Any] | None = None,
        max_retries: int = 2,
        timeout: int = 60,
        retry_interval: int = 1,
    ) -> ChatCompletion | AsyncStream[ChatCompletionChunk]:
        """发送 Chat Completion 请求。

        - 当 stream=False 时，返回 ChatCompletion 对象
        - 当 stream=True 时，返回 AsyncStream 异步迭代器
        """
        client = self._get_or_create(
            provider_id,
            api_base,
            api_key,
            max_retries=max_retries,
            timeout=timeout,
            retry_interval=retry_interval,
        )

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }

        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        if extra_params:
            kwargs.update(extra_params)

        logger.debug(
            "LLM 请求",
            provider_id=provider_id,
            model=model,
            stream=stream,
            event_type="llm.request",
        )

        return cast(
            "ChatCompletion | AsyncStream[ChatCompletionChunk]",
            await client.chat.completions.create(**kwargs),
        )

    async def close(self) -> None:
        """关闭所有缓存的客户端实例。"""
        for client in self._clients.values():
            await client.close()
        self._clients.clear()
