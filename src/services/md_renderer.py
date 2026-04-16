"""Markdown 渲染器服务 —— 生命周期注册。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.core.lifecycle import shutdown, startup
from src.core.utils.md2img import MarkdownRenderer

if TYPE_CHECKING:
    from src.core.browser import BrowserService


@startup(
    name="md_renderer",
    provides=["md_renderer"],
    requires=["browser"],
    dispatcher_services=["md_renderer"],
)
async def _lifecycle_start(deps: dict[str, Any]) -> dict[str, Any]:
    """Markdown 渲染器启动。"""
    browser: BrowserService = deps["browser"]
    renderer = MarkdownRenderer(browser=browser)
    return {"md_renderer": renderer}


@shutdown(name="md_renderer")
async def _lifecycle_stop(services: dict[str, Any]) -> None:
    """Markdown 渲染器关闭（无资源需释放）。"""
