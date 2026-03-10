"""LLM 高层调用接口 —— 供项目其他模块直接使用。

使用方式：
    from src.core.llm.completion import llm_complete, llm_stream

    # 一次性获取完整回复
    reply = await llm_complete("deepseek-chat", [
        {"role": "user", "content": "你好"}
    ])
    print(reply)  # "你好！有什么可以帮你的吗？"

    # 流式获取回复
    async for chunk in llm_stream("gpt-4o", messages):
        print(chunk, end="", flush=True)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from src.core.llm.service import LLMService

_service: LLMService | None = None


def init_completion(service: LLMService) -> None:
    """由 lifespan() 在启动时调用，注入 LLMService 实例。"""
    global _service
    _service = service


def _get_service() -> LLMService:
    if _service is None:
        raise RuntimeError("LLMService 未初始化，请确保 init_completion() 已在 lifespan 中调用")
    return _service


async def llm_complete(
    model_name: str,
    messages: list[dict[str, str]],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    extra_params: dict[str, Any] | None = None,
) -> str:
    """一次性调用 LLM 并返回完整文本回复。

    Args:
        model_name: 模型标识 (如 "gpt-4o"、"deepseek-chat")，
                    在 llms 表中按 model_name 查找首个启用的匹配项。
        messages:   OpenAI 格式的消息列表。
        temperature: 覆盖模型默认温度（可选）。
        max_tokens:  覆盖模型默认 max_tokens（可选）。
        extra_params: 合并到请求的额外参数（可选）。

    Returns:
        模型回复的文本内容。

    Raises:
        ValueError: 找不到匹配的启用模型。
        RuntimeError: LLMService 未初始化。
    """
    service = _get_service()
    result = await service.chat_by_name(
        model_name=model_name,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=False,
    )
    if result.choices:
        return result.choices[0].message.content or ""
    return ""


async def llm_stream(
    model_name: str,
    messages: list[dict[str, str]],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    extra_params: dict[str, Any] | None = None,
) -> AsyncIterator[str]:
    """流式调用 LLM，逐块 yield 文本内容。

    用法:
        async for chunk in llm_stream("gpt-4o", messages):
            print(chunk, end="")
    """
    service = _get_service()
    stream = await service.chat_by_name(
        model_name=model_name,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
