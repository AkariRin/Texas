"""后端管理 API 路由 —— /api。"""

from __future__ import annotations

from fastapi import APIRouter

from src.api.bot import router as bot_router
from src.api.handlers import router as handlers_router

api_router = APIRouter()
api_router.include_router(handlers_router, tags=["handlers"])
api_router.include_router(bot_router, tags=["bot"])
