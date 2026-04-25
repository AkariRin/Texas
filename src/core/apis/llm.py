"""LLM REST API 路由 —— /api/v1/llm。"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import StreamingResponse

from src.core.services.llm import LLMService  # noqa: TC001
from src.core.services.llm_schemas import (  # noqa: TC001
    ChatRequest,
    ModelCreate,
    ModelUpdate,
    ProviderCreate,
    ProviderUpdate,
)
from src.core.utils.response import ok

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = structlog.get_logger()


def get_llm_service(request: Request) -> LLMService:
    """获取 LLM 服务。"""
    registry = request.app.state.service_registry
    return registry.get_typed(LLMService, "llm_service")  # type: ignore[no-any-return]


router = APIRouter(prefix="/llm", tags=["llm"])


def _parse_uuid(value: str, name: str = "ID") -> uuid.UUID:
    """解析 UUID 字符串，无效时抛出 400。"""
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {name}: {value}") from exc


# ══════════════════════════════════════════════
#  提供商 CRUD (6.1)
# ══════════════════════════════════════════════


@router.get("/providers")
async def list_providers(service: LLMService = Depends(get_llm_service)) -> dict[str, Any]:
    """列出所有提供商。"""
    providers = await service.list_providers()
    return ok(providers)


@router.get("/providers/{provider_id}")
async def get_provider(
    provider_id: str,
    service: LLMService = Depends(get_llm_service),
) -> dict[str, Any]:
    """获取单个提供商详情（含旗下模型列表）。"""
    pid = _parse_uuid(provider_id, "provider_id")
    provider = await service.get_provider(pid)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    return ok(provider)


@router.post("/providers")
async def create_provider(
    data: ProviderCreate,
    service: LLMService = Depends(get_llm_service),
) -> dict[str, Any]:
    """创建提供商。"""
    provider = await service.create_provider(data)
    return ok(provider)


@router.post("/providers/{provider_id}")
async def update_provider(
    provider_id: str,
    data: ProviderUpdate,
    service: LLMService = Depends(get_llm_service),
) -> dict[str, Any]:
    """更新提供商（字段级部分更新）。"""
    pid = _parse_uuid(provider_id, "provider_id")
    provider = await service.update_provider(pid, data)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    return ok(provider)


@router.post("/providers/{provider_id}/delete")
async def delete_provider(
    provider_id: str,
    service: LLMService = Depends(get_llm_service),
) -> dict[str, Any]:
    """删除提供商（级联删除旗下模型）。"""
    pid = _parse_uuid(provider_id, "provider_id")
    success = await service.delete_provider(pid)
    if not success:
        raise HTTPException(status_code=404, detail="Provider not found")
    return ok(None, message="Provider deleted")


@router.post("/providers/{provider_id}/test")
async def test_provider(
    provider_id: str,
    service: LLMService = Depends(get_llm_service),
) -> dict[str, Any]:
    """测试提供商连通性。"""
    pid = _parse_uuid(provider_id, "provider_id")
    try:
        result = await service.test_provider(pid)
        return ok(result)
    except ValueError as exc:
        logger.warning(
            "测试提供商失败",
            error=str(exc),
            provider_id=provider_id,
            event_type="llm.test_provider_error",
        )
        raise HTTPException(status_code=404, detail="提供商不存在") from exc


# ══════════════════════════════════════════════
#  模型 CRUD (6.2)
# ══════════════════════════════════════════════


@router.get("/models")
async def list_models(
    provider_id: str | None = None,
    service: LLMService = Depends(get_llm_service),
) -> dict[str, Any]:
    """列出所有模型（支持按提供商筛选）。"""
    pid = _parse_uuid(provider_id, "provider_id") if provider_id else None
    models = await service.list_models(pid)
    return ok(models)


@router.get("/models/{model_id}")
async def get_model(
    model_id: str,
    service: LLMService = Depends(get_llm_service),
) -> dict[str, Any]:
    """获取单个模型详情。"""
    mid = _parse_uuid(model_id, "model_id")
    model = await service.get_model(mid)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return ok(model)


@router.post("/models")
async def create_model(
    data: ModelCreate,
    service: LLMService = Depends(get_llm_service),
) -> dict[str, Any]:
    """创建模型。"""
    model = await service.create_model(data)
    return ok(model)


@router.post("/models/{model_id}")
async def update_model(
    model_id: str,
    data: ModelUpdate,
    service: LLMService = Depends(get_llm_service),
) -> dict[str, Any]:
    """更新模型（字段级部分更新）。"""
    mid = _parse_uuid(model_id, "model_id")
    model = await service.update_model(mid, data)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return ok(model)


@router.post("/models/{model_id}/delete")
async def delete_model(
    model_id: str,
    service: LLMService = Depends(get_llm_service),
) -> dict[str, Any]:
    """删除模型。"""
    mid = _parse_uuid(model_id, "model_id")
    success = await service.delete_model(mid)
    if not success:
        raise HTTPException(status_code=404, detail="Model not found")
    return ok(None, message="Model deleted")


# ══════════════════════════════════════════════
#  功能端点 (6.3)
# ══════════════════════════════════════════════


@router.post("/chat")
async def chat(
    req: ChatRequest,
    service: LLMService = Depends(get_llm_service),
) -> Any:
    """使用指定模型进行一次对话（支持流式 SSE 响应）。"""
    mid = _parse_uuid(req.model_id, "model_id")

    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    try:
        result = await service.chat(
            model_id=mid,
            messages=messages,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            stream=req.stream,
        )
    except ValueError as exc:
        logger.warning(
            "LLM 对话请求参数错误",
            error=str(exc),
            model_id=req.model_id,
            event_type="llm.chat_value_error",
        )
        raise HTTPException(
            status_code=400, detail="请求参数无效，请检查模型 ID 或消息格式"
        ) from exc

    # 非流式：直接返回完整结果
    if not req.stream:
        content = result.choices[0].message.content if result.choices else ""
        return ok(
            {
                "content": content,
                "model": result.model,
                "usage": {
                    "prompt_tokens": result.usage.prompt_tokens if result.usage else 0,
                    "completion_tokens": result.usage.completion_tokens if result.usage else 0,
                    "total_tokens": result.usage.total_tokens if result.usage else 0,
                },
            }
        )

    # 流式：SSE 响应
    async def _stream_generator() -> AsyncIterator[str]:
        try:
            async for chunk in result:
                if chunk.choices and chunk.choices[0].delta.content:
                    data = json.dumps(
                        {"content": chunk.choices[0].delta.content},
                        ensure_ascii=False,
                    )
                    yield f"data: {data}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.error(
                "LLM 流式响应异常",
                error=str(exc),
                model_id=str(mid),
                event_type="llm.stream_error",
            )
            error_data = json.dumps({"error": "流式响应中断，请稍后重试"}, ensure_ascii=False)
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        _stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
