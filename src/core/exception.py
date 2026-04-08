"""全局异常处理器 —— 统一响应格式为 {code, data, message}。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from src.core.utils.response import fail

if TYPE_CHECKING:
    from fastapi import FastAPI
    from starlette.requests import Request

logger = structlog.get_logger()


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器到 FastAPI 应用。"""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=fail(str(exc.detail), code=exc.status_code),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=fail("请求参数校验失败", code=422, data=exc.errors()),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "未处理的异常",
            path=request.url.path,
            event_type="app.unhandled_exception",
        )
        return JSONResponse(status_code=500, content=fail("服务器内部错误"))
