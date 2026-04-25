"""帮助处理器 —— 响应 /help 等指令，返回图片格式的功能帮助。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

import structlog

from src.core.framework.decorators import MessageScope, controller, on_command
from src.core.utils.helpers import ceil_div
from src.core.utils.md2img import MarkdownRenderError

if TYPE_CHECKING:
    from src.core.framework.context import Context
    from src.core.services.permission import FeaturePermissionService
    from src.core.utils.md2img import MarkdownRenderer

logger = structlog.get_logger()

# ── 公开常量（修改此值即可调整分页条数） ──
HELP_PAGE_SIZE: Final = 8

# ── 内部常量 ──
_RENDER_WIDTH: Final = 680
_ADMIN_CATEGORY_TAG: Final = "管理员专属"
_UNCATEGORIZED_TAG: Final = "其他"


@dataclass(frozen=True)
class _HelpItem:
    """帮助列表中的单个功能条目。"""

    display_name: str
    description: str
    trigger: str
    admin: bool
    tag: str  # 展平时携带，切片后用于重建分组


@dataclass(frozen=True)
class _HelpCategory:
    """按 tag 分组的功能分类。"""

    tag: str
    items: tuple[_HelpItem, ...]


def _parse_categories(raw: list[dict[str, Any]], is_admin: bool) -> list[_HelpCategory]:
    """将 FeaturePermissionService 返回的原始 dict 列表转换为分类 DTO。

    注意：raw 已由 service 层按 is_admin 完成过滤，此函数不重复过滤。
    is_admin 仅用于控制管理员专属分类是否追加到末尾。

    admin=True 的 controller 统一归入 _ADMIN_CATEGORY_TAG，其余按 tag 分组。
    tag 为空字符串的 controller 归入 _UNCATEGORIZED_TAG。
    """
    normal: dict[str, list[_HelpItem]] = {}
    admin_items: list[_HelpItem] = []

    for entry in raw:
        tag: str = entry["tag"] or _UNCATEGORIZED_TAG
        is_entry_admin: bool = entry["admin"]

        for method in entry["methods"]:
            item = _HelpItem(
                display_name=method["display_name"],
                description=method["description"],
                trigger=method["trigger"],
                admin=is_entry_admin,
                tag=_ADMIN_CATEGORY_TAG if is_entry_admin else tag,
            )
            if is_entry_admin:
                admin_items.append(item)
            else:
                normal.setdefault(tag, []).append(item)

    categories: list[_HelpCategory] = [
        _HelpCategory(tag=t, items=tuple(items)) for t, items in normal.items()
    ]
    if is_admin and admin_items:
        categories.append(_HelpCategory(tag=_ADMIN_CATEGORY_TAG, items=tuple(admin_items)))

    return categories


def _flatten(categories: list[_HelpCategory]) -> list[_HelpItem]:
    """将分类列表展平为单一列表，每个 item 携带 tag 信息。"""
    return [item for cat in categories for item in cat.items]


def _paginate(items: list[_HelpItem], page: int) -> tuple[list[_HelpCategory], int]:
    """切片并重新分组。

    Args:
        items: 展平后的完整列表。
        page: 1-based 页码。

    Returns:
        (当前页的分类列表, 总页数)
    """
    total = len(items)
    total_pages = max(1, ceil_div(total, HELP_PAGE_SIZE))
    start = (page - 1) * HELP_PAGE_SIZE
    page_items = items[start : start + HELP_PAGE_SIZE]

    # 按 item.tag 重新分组（保留跨页后的正确分组顺序）
    grouped: dict[str, list[_HelpItem]] = {}
    for item in page_items:
        grouped.setdefault(item.tag, []).append(item)

    categories = [_HelpCategory(tag=t, items=tuple(its)) for t, its in grouped.items()]
    return categories, total_pages


def _fmt_trigger(trigger: str) -> str:
    """格式化触发方式：转义 Markdown 表格分隔符，为空时返回占位符。"""
    return trigger.replace("|", r"\|") if trigger else "—"


def _build_list_markdown(
    categories: list[_HelpCategory],
    page: int,
    total_pages: int,
) -> str:
    """构建帮助列表页的 Markdown 字符串。"""
    lines: list[str] = ["# Texas Bot 功能帮助", ""]

    for cat in categories:
        lines.append(f"## {cat.tag}")
        lines.append("| 功能 | 说明 | 触发方式 |")
        lines.append("|------|------|----------|")
        for item in cat.items:
            desc = item.description or "—"
            lines.append(f"| {item.display_name} | {desc} | {_fmt_trigger(item.trigger)} |")
        lines.append("")

    lines.append("---")
    if total_pages > 1:
        nav_parts = [f"第 {page} 页 / 共 {total_pages} 页"]
        if page < total_pages:
            nav_parts.append(f"发送 `/help {page + 1}` 查看下一页")
        nav_parts.append("`/help <功能名>` 查看详情")
        lines.append(" · ".join(nav_parts))
    else:
        lines.append("发送 `/help <功能名>` 查看详情")

    return "\n".join(lines)


def _build_detail_markdown(
    display_name: str,
    description: str,
    methods: list[dict[str, Any]],
) -> str:
    """构建功能详情页的 Markdown 字符串。"""
    lines: list[str] = [
        f"# {display_name}",
        "",
        description or "",
        "",
        "## 子命令",
        "| 命令 | 说明 | 触发方式 |",
        "|------|------|----------|",
    ]
    for m in methods:
        desc = m.get("description") or "—"
        lines.append(f"| {m['display_name']} | {desc} | {_fmt_trigger(m.get('trigger', ''))} |")

    return "\n".join(lines)


@controller(
    name="help",
    display_name="帮助",
    description="查看当前可用功能列表",
    tags=[],
    default_enabled=True,
    system=True,
    # system=True：FeaturePermissionChecker 跳过权限检查（始终可用），
    # 且不出现在帮助列表自身中（non_system_tree 过滤）。
)
class HelpHandler:
    """帮助处理器 —— 渲染当前上下文已启用功能列表为 PNG 图片。"""

    @on_command(
        cmd="/help",
        aliases={"/帮助", "/？"},
        display_name="功能帮助",
        description="查看当前可用功能列表，发送 /help <功能名> 查看子命令详情",
        message_scope=MessageScope.all,
    )
    async def show_help(self, ctx: Context) -> bool:
        """处理 /help 指令。"""
        from src.core.services.permission import FeaturePermissionService
        from src.core.services.personnel import PersonnelService
        from src.core.utils.md2img import MarkdownRenderer

        if not ctx.has_service(FeaturePermissionService):
            return False
        if not ctx.has_service(MarkdownRenderer):
            return False

        perm_svc = ctx.get_service(FeaturePermissionService)
        renderer = ctx.get_service(MarkdownRenderer)

        # ── 超管身份判断（PersonnelService 不可用时降级为 False） ──
        is_admin = False
        if ctx.has_service(PersonnelService):
            admin_set = await ctx.get_service(PersonnelService).get_admin_qq_set()
            is_admin = ctx.user_id in admin_set

        # ── 参数解析 ──
        arg = ctx.get_arg_str().strip()

        if not arg:
            await self._handle_list(
                ctx, page=1, is_admin=is_admin, perm_svc=perm_svc, renderer=renderer
            )
        elif arg.isdigit():
            await self._handle_list(
                ctx, page=int(arg), is_admin=is_admin, perm_svc=perm_svc, renderer=renderer
            )
        else:
            await self._handle_detail(
                ctx, feature_query=arg, is_admin=is_admin, perm_svc=perm_svc, renderer=renderer
            )

        return True

    async def _handle_list(
        self,
        ctx: Context,
        page: int,
        is_admin: bool,
        perm_svc: FeaturePermissionService,
        renderer: MarkdownRenderer,
    ) -> None:
        """列表模式：渲染当前页功能列表为图片。"""
        if ctx.is_group and ctx.group_id is not None:
            raw = await perm_svc.get_help_features_for_group(ctx.group_id, is_admin)
        else:
            raw = await perm_svc.get_help_features_for_private(ctx.user_id, is_admin)

        categories = _parse_categories(raw, is_admin)
        flat = _flatten(categories)

        if not flat:
            await ctx.reply("当前暂无可用功能")
            return

        page_categories, total_pages = _paginate(flat, page)
        if page < 1 or page > total_pages:
            await ctx.reply(f"共 {total_pages} 页，请输入有效页码")
            return
        md = _build_list_markdown(page_categories, page, total_pages)

        try:
            seg = await renderer.render_to_seg(md, width=_RENDER_WIDTH)
            await ctx.reply([seg])
        except MarkdownRenderError:
            logger.exception(
                "帮助列表渲染失败",
                page=page,
                user_id=ctx.user_id,
                event_type="help.render_error",
            )
            await ctx.reply("帮助图片生成失败，请稍后重试")

    async def _handle_detail(
        self,
        ctx: Context,
        feature_query: str,
        is_admin: bool,
        perm_svc: FeaturePermissionService,
        renderer: MarkdownRenderer,
    ) -> None:
        """详情模式：渲染指定功能的子命令详情为图片。"""
        registry = perm_svc.registry

        # 先按 name 精确匹配，再按 display_name 精确匹配
        meta = registry.get(feature_query)
        if meta is None or meta.parent is not None or meta.system or (not is_admin and meta.admin):
            # 尝试 display_name 精确匹配（区分大小写）
            # 使用 non_system_names() 避免遍历系统级和 method 级条目
            meta = next(
                (
                    m
                    for n in registry.non_system_names()
                    if (m := registry.get(n)) is not None
                    and m.parent is None
                    and m.display_name == feature_query
                    and (is_admin or not m.admin)
                ),
                None,
            )

        if meta is None:
            await ctx.reply("未找到该功能或功能未启用")
            return

        # 权限检查
        if ctx.is_group and ctx.group_id is not None:
            enabled = await perm_svc.is_group_feature_enabled(ctx.group_id, meta.name, meta.name)
        else:
            enabled = await perm_svc.is_private_feature_allowed(meta.name, meta.name, ctx.user_id)

        if not enabled:
            await ctx.reply("未找到该功能或功能未启用")
            return

        # 详情页展示全部子命令，不按 message_scope 二次过滤
        methods = [
            {
                "display_name": child.display_name,
                "description": child.description,
                "trigger": child.trigger,
            }
            for child_name in meta.children
            if (child := registry.get(child_name)) is not None
        ]

        md = _build_detail_markdown(meta.display_name, meta.description, methods)

        try:
            seg = await renderer.render_to_seg(md, width=_RENDER_WIDTH)
            await ctx.reply([seg])
        except MarkdownRenderError:
            logger.exception(
                "帮助详情渲染失败",
                feature=meta.name,
                user_id=ctx.user_id,
                event_type="help.detail_render_error",
            )
            await ctx.reply("帮助图片生成失败，请稍后重试")
