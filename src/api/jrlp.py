"""今日老婆管理 REST API —— /api/jrlp。"""

from __future__ import annotations

from datetime import date  # noqa: TC003 — FastAPI Query 参数运行时需要
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.schemas.jrlp import (  # noqa: TC001 — FastAPI Body 参数运行时需要
    DeleteRecordRequest,
    SetWifeRequest,
    UpdateRecordRequest,
)
from src.core.dependencies import get_jrlp_service
from src.core.utils.response import fail, ok

if TYPE_CHECKING:
    from src.services.jrlp import JrlpService

logger = structlog.get_logger()

router = APIRouter(prefix="/jrlp", tags=["jrlp"])


def _record_to_dict(r: Any) -> dict[str, Any]:
    """将 WifeRecord 转为可序列化字典（只返回 ID，名称由前端通过公共接口解析）。"""
    return {
        "id": r.id,
        "group_id": r.group_id,
        "user_id": r.user_id,
        "wife_qq": r.wife_qq,
        "date": r.date.isoformat(),
        "drawn_at": r.drawn_at.isoformat() if r.drawn_at else None,
    }


@router.get("/records")
async def list_records(
    group_id: int | None = Query(None),
    user_id: int | None = Query(None),
    record_date: date | None = Query(None, alias="date"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: JrlpService = Depends(get_jrlp_service),
) -> dict[str, Any]:
    """分页查询抽取/预设记录。"""
    records, total = await service.list_records(
        group_id=group_id,
        user_id=user_id,
        record_date=record_date,
        page=page,
        page_size=page_size,
    )
    pages = (total + page_size - 1) // page_size
    return ok(
        {
            "items": [_record_to_dict(r) for r in records],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
        }
    )


@router.post("/records/create")
async def create_preset(
    body: SetWifeRequest,
    service: JrlpService = Depends(get_jrlp_service),
) -> dict[str, Any]:
    """手动设置老婆（创建预设）。"""
    try:
        record = await service.create_preset(
            group_id=body.group_id,
            user_id=body.user_id,
            wife_qq=body.wife_qq,
            record_date=body.date,
        )
    except ValueError as exc:
        logger.warning("创建老婆预设失败", error=str(exc), event_type="jrlp.create_preset_error")
        return fail("设置失败，请检查参数或记录是否已存在")
    return ok(_record_to_dict(record), message="设置成功")


@router.post("/records/update")
async def update_record(
    body: UpdateRecordRequest,
    service: JrlpService = Depends(get_jrlp_service),
) -> dict[str, Any]:
    """修改记录的老婆信息。"""
    record = await service.update_record(body.id, wife_qq=body.wife_qq)
    if record is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return ok(_record_to_dict(record), message="修改成功")


@router.post("/records/delete")
async def delete_record(
    body: DeleteRecordRequest,
    service: JrlpService = Depends(get_jrlp_service),
) -> dict[str, Any]:
    """删除记录。"""
    success = await service.delete_record(body.id)
    if not success:
        return fail("记录不存在")
    return ok(None, message="删除成功")
