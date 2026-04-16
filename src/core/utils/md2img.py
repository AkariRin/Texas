"""Markdown 转 PNG 图片渲染器。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from markdown_it import MarkdownIt

from src.core.browser import BrowserRenderError, BrowserService
from src.core.protocol.segment import Seg
from src.core.utils.resource import base64_encode

if TYPE_CHECKING:
    from src.core.protocol.models.base import MessageSegment

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

    将 Markdown 转为 HTML（注入防护由 BrowserService 层提供），委托 BrowserService 渲染为 PNG 图片。

    用法::

        renderer = MarkdownRenderer(browser=browser_service)
        seg = await renderer.render_to_seg("# Hello")
        await ctx.reply([seg])
    """

    def __init__(
        self,
        browser: BrowserService,
        default_width: int = 800,
        padding: int = 24,
    ) -> None:
        self._browser = browser
        self._default_width = default_width
        self._padding = padding
        self._md = MarkdownIt()
        # 预替换 padding（实例生命周期内固定），减少每次 render() 中的重复替换
        self._partial_template = _HTML_TEMPLATE.replace("__PADDING__", str(padding))

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

        w = width if width is not None else self._default_width

        # markdown 渲染是 CPU bound（纯 Python），在委托给浏览器之前完成
        html_fragment = self._md.render(md)
        html = self._partial_template.replace("__WIDTH__", str(w)).replace(
            "__HTML_CONTENT__", html_fragment
        )

        try:
            return await self._browser.render_html(
                html,
                viewport_width=w + self._padding * 2,
                selector="#content",
            )
        except BrowserRenderError as e:
            raise MarkdownRenderError(f"渲染失败：{e}") from e

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
