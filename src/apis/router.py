"""后端管理 API 路由 —— 自动发现平台组件包和 src.apis 下的所有 router 模块。"""

from __future__ import annotations

import importlib
import pkgutil

from fastapi import APIRouter

# 平台组件包：各包内的 api.py 提供 HTTP 路由
_CORE_API_PACKAGES = ("src.core.personnel", "src.core.llm")


def build_main_router() -> APIRouter:
    """扫描平台组件包和业务 API 包，自动注册所有含 router 属性的模块。"""
    main = APIRouter()
    for pkg_name in (*_CORE_API_PACKAGES, "src.apis"):
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
