"""后端管理 API 路由 —— 自动发现 src.core.apis 和 src.apis 下的所有 router 模块。"""

from __future__ import annotations

import importlib
import pkgutil

from fastapi import APIRouter


def build_main_router() -> APIRouter:
    """扫描两个 API 包，自动注册所有含 router 属性的模块。"""
    main = APIRouter()
    for pkg_name in ("src.core.apis", "src.apis"):
        try:
            pkg = importlib.import_module(pkg_name)
        except ImportError:
            continue
        for module_info in pkgutil.iter_modules(pkg.__path__):
            if module_info.name in ("router", "__init__"):
                continue
            mod = importlib.import_module(f"{pkg_name}.{module_info.name}")
            if hasattr(mod, "router"):
                main.include_router(mod.router)
    return main


api_router = build_main_router()
