"""Markdown 转 PNG 图片渲染器。"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Final

import structlog
from markdown_it import MarkdownIt

from src.core.protocol.segment import Seg
from src.core.utils.resource import base64_encode

if TYPE_CHECKING:
    from playwright.async_api import Browser, Playwright

    from src.core.protocol.models.base import MessageSegment

logger = structlog.get_logger()

# HTML 页面模板（使用 str.replace 注入变量，避免 CSS 花括号转义问题）
# 占位符：__PADDING__（内边距px）、__WIDTH__（宽度px）、__HTML_CONTENT__（HTML正文）
_HTML_TEMPLATE: Final = """\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body { margin: 0; background: #fff; }
    #content {
      padding: __PADDING__px;
      max-width: __WIDTH__px;
      font-family: system-ui, -apple-system, "Noto Sans CJK SC", "WenQuanYi Micro Hei", sans-serif;
      font-size: 15px;
      line-height: 1.6;
      color: #24292e;
    }
    h1, h2, h3, h4, h5, h6 { margin-top: 1em; margin-bottom: .5em; font-weight: 600; }
    h1 { font-size: 1.8em; border-bottom: 1px solid #eaecef; padding-bottom: .3em; }
    h2 { font-size: 1.4em; border-bottom: 1px solid #eaecef; padding-bottom: .3em; }
    pre { background: #f6f8fa; border-radius: 6px; padding: 12px 16px; overflow-x: auto; }
    code { font-family: "SFMono-Regular", Consolas, monospace; font-size: 0.9em; }
    :not(pre) > code { background: #f0f2f4; padding: 2px 5px; border-radius: 3px; }
    blockquote { border-left: 4px solid #0969da; margin: 0; padding: 0 1em; color: #57606a; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #d0d7de; padding: 6px 13px; }
    th { background: #f6f8fa; font-weight: 600; }
    tr:nth-child(even) { background: #f6f8fa; }
    img { max-width: 100%; }
    hr { border: none; border-top: 1px solid #eaecef; }
  </style>
</head>
<body>
  <div id="content">__HTML_CONTENT__</div>
</body>
</html>"""


class MarkdownRenderError(Exception):
    """Markdown 渲染失败异常。"""


class MarkdownRenderer:
    """Markdown 转 PNG 图片渲染器。

    通过 Playwright 无头 Chromium 将 Markdown 渲染为 PNG 图片。
    使用前须调用 start()，应用关闭时调用 close()。

    用法::

        renderer = MarkdownRenderer()
        await renderer.start()
        seg = await renderer.render_to_seg("# Hello")
        await ctx.reply([seg])
    """

    def __init__(
        self,
        default_width: int = 800,
        padding: int = 24,
        max_concurrent_renders: int = 4,
    ) -> None:
        self._default_width = default_width
        self._padding = padding
        self._max_concurrent = max_concurrent_renders
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._sem: asyncio.Semaphore | None = None
        self._restart_lock: asyncio.Lock | None = None  # 防止并发重启竞态
        # 禁用 HTML 内联/块，防止恶意脚本在 Chromium 中执行
        # 注意：不要启用 linkify 插件，否则 javascript: URL 可能绕过此防护
        self._md = MarkdownIt().disable("html_inline").disable("html_block")
        # 预替换 padding（实例生命周期内固定），减少每次 render() 中的重复替换
        self._partial_template = _HTML_TEMPLATE.replace("__PADDING__", str(padding))

    async def start(self) -> None:
        """启动 Playwright Chromium 浏览器实例。

        应在应用启动时调用一次。若 Chromium 未安装，
        抛出 RuntimeError 并提示执行 playwright install chromium。
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
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--single-process",
                ],
            )
        except Exception as e:
            msg = str(e)
            if "Executable doesn't exist" in msg or "not found" in msg.lower():
                logger.error(
                    "Chromium 未安装，请执行：playwright install chromium",
                    event_type="md2img.browser_not_installed",
                )
                raise MarkdownRenderError(
                    "Chromium 未安装，请执行：playwright install chromium"
                ) from e
            detail = msg or type(e).__name__
            logger.error(
                "Chromium 浏览器启动失败",
                error=detail,
                event_type="md2img.browser_launch_error",
            )
            raise MarkdownRenderError(f"浏览器启动失败：{detail}") from e

    async def _ensure_browser(self) -> None:
        """确保浏览器处于连接状态，断连时自动重启。

        使用 Lock 防止多协程并发触发重启产生双实例竞态。
        """
        if self._browser is not None and self._browser.is_connected():
            return
        if self._restart_lock is None:
            raise RuntimeError("MarkdownRenderer 未初始化，请先调用 start()")
        async with self._restart_lock:
            # 二次检查：可能已被先获得锁的协程重启完毕
            if self._browser is not None and self._browser.is_connected():
                return
            logger.warning(
                "Chromium 浏览器断连，正在重启",
                event_type="md2img.browser_restart",
            )
            await self._launch_browser()

    async def render(self, md: str, *, width: int | None = None) -> bytes:
        """将 Markdown 渲染为 PNG 图片字节。

        Args:
            md: Markdown 格式字符串。
            width: 图片宽度（px），None 时使用 default_width。

        Returns:
            PNG 字节数据（典型大小 200-500KB）。

        Raises:
            MarkdownRenderError: 内容为空、渲染超时、浏览器崩溃或重启失败时抛出。
        """
        if not md.strip():
            raise MarkdownRenderError("Markdown 内容不能为空")

        if self._sem is None:
            raise RuntimeError("MarkdownRenderer 未初始化，请先调用 start()")

        w = width if width is not None else self._default_width

        try:
            await self._ensure_browser()
        except Exception as e:
            raise MarkdownRenderError(f"浏览器不可用：{e}") from e

        # markdown 渲染是 CPU bound（纯 Python），放在 sem 外不占用浏览器并发槽位
        html_fragment = self._md.render(md)
        html = self._partial_template.replace("__WIDTH__", str(w)).replace(
            "__HTML_CONTENT__", html_fragment
        )

        async with self._sem:
            # 二次检查：_ensure_browser() 与进入 sem 之间存在 await 间隙，
            # 极低概率有其他协程调用 close() 将 _browser 置 None。
            browser = self._browser
            if browser is None:
                raise MarkdownRenderError("浏览器实例不可用（内部状态异常）")
            context = await browser.new_context(
                # height=1：element.screenshot 会自动撑开到元素实际高度，无需预设
                viewport={"width": w + self._padding * 2, "height": 1}
            )
            try:
                page = await context.new_page()
                await page.set_content(html, wait_until="domcontentloaded")
                element = page.locator("#content")
                png_bytes: bytes = await element.screenshot(type="png", timeout=10_000)
                return png_bytes
            except Exception as e:
                logger.error(
                    "Markdown 渲染失败",
                    error=str(e),
                    event_type="md2img.render_error",
                )
                raise MarkdownRenderError(f"渲染失败：{e}") from e
            finally:
                await context.close()

    async def render_to_seg(self, md: str, *, width: int | None = None) -> MessageSegment:
        """将 Markdown 渲染为可直接发送的图片消息段。

        内部调用 render()，将结果 base64 编码后封装为 Seg.image()。

        Args:
            md: Markdown 格式字符串。
            width: 图片宽度（px），None 时使用 default_width。

        Returns:
            可直接传给 ctx.reply() 的图片消息段。

        Raises:
            MarkdownRenderError: 渲染失败时透传。
        """
        png_bytes = await self.render(md, width=width)
        return Seg.image(base64_encode(png_bytes))
