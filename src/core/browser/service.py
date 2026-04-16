"""通用浏览器渲染服务 —— Playwright Chromium 生命周期管理与 HTML-to-PNG API。"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Final

import structlog

if TYPE_CHECKING:
    from playwright.async_api import Browser, Playwright, Route

logger = structlog.get_logger()

# Chromium 启动参数（容器/CI 环境兼容）
_CHROMIUM_ARGS: Final = (
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--single-process",
)


class BrowserRenderError(Exception):
    """浏览器渲染失败异常。"""


class BrowserService:
    """通用 Playwright Chromium 渲染服务。

    管理无头浏览器生命周期，提供异步 HTML-to-PNG 渲染 API。
    使用前须调用 start()，应用关闭时调用 close()。

    render_html() 默认以 js_enabled=False、block_network=True 运行，
    在 Playwright 浏览器上下文层面禁用 JS 执行并阻断所有 HTTP/HTTPS 网络请求，
    无需调用方对 html 内容进行预净化。如需渲染可信富内容（如 Vuetify 报表），
    可显式传入 js_enabled=True 以放开 JS 限制。

    用法::

        browser = BrowserService()
        await browser.start()
        # 安全渲染（默认）：禁用 JS + 阻断网络
        png_bytes = await browser.render_html("<html>...</html>", selector="#content")
        # 可信渲染：启用 JS，网络仍阻断
        png_bytes = await browser.render_html(trusted_html, js_enabled=True, selector="#app")
        await browser.close()
    """

    def __init__(self, max_concurrent_renders: int = 4) -> None:
        self._max_concurrent = max_concurrent_renders
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._sem: asyncio.Semaphore | None = None
        self._restart_lock: asyncio.Lock | None = None  # 防止并发重启竞态

    async def start(self) -> None:
        """启动 Playwright Chromium 浏览器实例。

        应在应用启动时调用一次。若 Chromium 未安装，
        抛出 BrowserRenderError 并提示执行 playwright install chromium。
        """
        self._sem = asyncio.Semaphore(self._max_concurrent)
        self._restart_lock = asyncio.Lock()
        await self._launch_browser()

    async def close(self) -> None:
        """关闭浏览器实例，释放资源。应在应用关闭时调用。"""
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._pw is not None:
            await self._pw.stop()
            self._pw = None

    async def _launch_browser(self) -> None:
        """启动 Chromium 浏览器进程。"""
        from playwright.async_api import async_playwright

        try:
            # 重启场景下 _pw 仍有效（未调用 close()），直接复用；
            # 仅在首次启动或 close() 后重新 start() 时重建 Playwright 实例。
            if self._pw is None:
                self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.launch(
                headless=True,
                args=list(_CHROMIUM_ARGS),
            )
        except Exception as e:
            msg = str(e)
            if "Executable doesn't exist" in msg or "not found" in msg.lower():
                logger.error(
                    "Chromium 未安装，请执行：playwright install chromium",
                    event_type="browser.not_installed",
                )
                raise BrowserRenderError(
                    "Chromium 未安装，请执行：playwright install chromium"
                ) from e
            detail = msg or type(e).__name__
            logger.error(
                "Chromium 浏览器启动失败",
                error=detail,
                event_type="browser.launch_error",
            )
            raise BrowserRenderError(f"浏览器启动失败：{detail}") from e

    async def _ensure_browser(self) -> None:
        """确保浏览器处于连接状态，断连时自动重启。

        使用 Lock 防止多协程并发触发重启产生双实例竞态。
        """
        if self._browser is not None and self._browser.is_connected():
            return
        if self._restart_lock is None:
            raise RuntimeError("BrowserService 未初始化，请先调用 start()")
        async with self._restart_lock:
            # 二次检查：可能已被先获得锁的协程重启完毕
            if self._browser is not None and self._browser.is_connected():
                return
            logger.warning(
                "Chromium 浏览器断连，正在重启",
                event_type="browser.restart",
            )
            await self._launch_browser()

    @staticmethod
    async def _abort_route(route: Route) -> None:
        """Playwright route handler：中止所有匹配的网络请求。"""
        await route.abort()

    async def render_html(
        self,
        html: str,
        *,
        js_enabled: bool = False,
        block_network: bool = True,
        viewport_width: int = 800,
        viewport_height: int = 1,
        selector: str = "body",
        timeout: int = 10_000,
    ) -> bytes:
        """将完整 HTML 文档渲染为 PNG 图片字节。

        默认以 js_enabled=False、block_network=True 运行，提供渲染层注入防护，
        无需调用方对 html 内容进行预净化。

        Args:
            html: 完整 HTML 文档字符串（应含 <!DOCTYPE html>）。
            js_enabled: 是否允许 JavaScript 执行，默认 False（禁用）。
                设为 True 时可渲染 Vue/Vuetify 等依赖 JS 的可信模板。
            block_network: 是否阻断所有 HTTP/HTTPS 网络请求，默认 True（阻断）。
                阻断范围包括公网、内网及 localhost 其他端口，防止 SSRF。
                data: URI 和 file:// 不经过路由系统，不受影响。
                设为 False 时由调用方自行负责安全。
            viewport_width: 视口宽度（px）。
            viewport_height: 视口高度（px），1 表示自动撑开到元素实际高度。
            selector: 截图目标 CSS 选择器，默认 "body"。
            timeout: 截图超时（ms）。

        Returns:
            PNG 字节数据。

        Raises:
            BrowserRenderError: 浏览器不可用、渲染超时或截图失败时抛出。
        """
        if self._sem is None:
            raise RuntimeError("BrowserService 未初始化，请先调用 start()")

        try:
            await self._ensure_browser()
        except Exception as e:
            raise BrowserRenderError(f"浏览器不可用：{e}") from e

        async with self._sem:
            # 二次检查：_ensure_browser() 与进入 sem 之间存在 await 间隙，
            # 极低概率有其他协程调用 close() 将 _browser 置 None。
            browser = self._browser
            if browser is None:
                raise BrowserRenderError("浏览器实例不可用（内部状态异常）")
            context = None
            try:
                context = await browser.new_context(
                    # height=1：element.screenshot 会自动撑开到元素实际高度，无需预设
                    viewport={"width": viewport_width, "height": viewport_height},
                    java_script_enabled=js_enabled,
                )
                if block_network:
                    await context.route("**/*", BrowserService._abort_route)
                page = await context.new_page()
                await page.set_content(html, wait_until="domcontentloaded")
                element = page.locator(selector)
                png_bytes: bytes = await element.screenshot(type="png", timeout=timeout)
                return png_bytes
            except Exception as e:
                logger.error(
                    "HTML 渲染失败",
                    error=str(e),
                    selector=selector,
                    event_type="browser.render_error",
                )
                raise BrowserRenderError(f"渲染失败：{e}") from e
            finally:
                if context is not None:
                    await context.close()
