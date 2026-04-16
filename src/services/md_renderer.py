"""Markdown 渲染器服务 —— 生命周期注册（启动 / 关闭 Playwright Chromium）。"""

from __future__ import annotations

from typing import Any

from src.core.lifecycle import shutdown, startup
from src.core.utils.md2img import MarkdownRenderer


@startup(
    name="md_renderer",
    provides=["md_renderer"],
    requires=[],
    dispatcher_services=["md_renderer"],
)
async def _lifecycle_start(deps: dict[str, Any]) -> dict[str, Any]:
    """Markdown 渲染器启动（启动 Playwright Chromium）。"""
    renderer = MarkdownRenderer()
    await renderer.start()
    return {"md_renderer": renderer}


@shutdown(name="md_renderer")
async def _lifecycle_stop(services: dict[str, Any]) -> None:
    """Markdown 渲染器关闭（释放 Playwright 资源）。"""
    renderer: MarkdownRenderer = services["md_renderer"]
    await renderer.close()
