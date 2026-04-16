"""浏览器渲染服务 —— 生命周期注册（启动 / 关闭 Playwright Chromium）。"""

from __future__ import annotations

from typing import Any

from src.core.browser import BrowserService
from src.core.lifecycle import shutdown, startup


@startup(
    name="browser",
    provides=["browser"],
    requires=[],
    dispatcher_services=["browser"],
)
async def _lifecycle_start(deps: dict[str, Any]) -> dict[str, Any]:
    """浏览器渲染服务启动（启动 Playwright Chromium）。"""
    browser = BrowserService()
    await browser.start()
    return {"browser": browser}


@shutdown(name="browser")
async def _lifecycle_stop(services: dict[str, Any]) -> None:
    """浏览器渲染服务关闭（释放 Playwright 资源）。"""
    browser: BrowserService = services["browser"]
    await browser.close()
