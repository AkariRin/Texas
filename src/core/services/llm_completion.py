"""LLM 高层调用接口 —— 供 Handler 通过 Context DI 或直接传入 LLMService 使用。

使用方式（Handler 中推荐）：
    from src.core.services.llm import LLMService
    from src.core.services.llm_completion import llm_complete, llm_stream

    # 通过 ctx.get_service() 获取 LLMService
    llm = ctx.get_service(LLMService)

    # 一次性获取完整回复
    reply = await llm_complete(llm, "deepseek-chat", [
        {"role": "user", "content": "你好"}
    ])

    # 流式获取回复
    async for chunk in llm_stream(llm, "gpt-4o", messages):
        print(chunk, end="", flush=True)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from src.core.services.llm import LLMService


async def llm_complete(
    service: LLMService,
    model_name: str,
    messages: list[dict[str, str]],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str:
    """一次性调用 LLM 并返回完整文本回复。

    Args:
        service:    LLMService 实例，通过 ctx.get_service(LLMService) 或 Depends 获取。
        model_name: 模型标识 (如 "gpt-4o"、"deepseek-chat")，
                    在 llms 表中按 model_name 查找首个启用的匹配项。
        messages:   OpenAI 格式的消息列表。
        temperature: 覆盖模型默认温度（可选）。
        max_tokens:  覆盖模型默认 max_tokens（可选）。

    Returns:
        模型回复的文本内容。

    Raises:
        ValueError: 找不到匹配的启用模型。
    """
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
    service: LLMService,
    model_name: str,
    messages: list[dict[str, str]],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> AsyncIterator[str]:
    """流式调用 LLM，逐块 yield 文本内容。

    用法:
        llm = ctx.get_service(LLMService)
        async for chunk in llm_stream(llm, "gpt-4o", messages):
            print(chunk, end="")
    """
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
