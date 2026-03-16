"""后端管理 API 路由 —— /api。"""

from __future__ import annotations

from fastapi import APIRouter

from src.api.bot import router as bot_router
from src.api.handlers import router as handlers_router
from src.api.logs import router as logs_router
from src.api.queue import router as queue_router
from src.core.chat.api import router as chat_router
from src.core.llm.api import router as llm_router
from src.core.personnel.api import router as personnel_router

api_router = APIRouter()
api_router.include_router(handlers_router, tags=["handlers"])
api_router.include_router(bot_router, tags=["bot"])
api_router.include_router(queue_router)
api_router.include_router(personnel_router)
api_router.include_router(logs_router, tags=["logs"])
api_router.include_router(llm_router)
api_router.include_router(chat_router)
