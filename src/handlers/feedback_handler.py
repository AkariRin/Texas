"""用户反馈处理器 —— 反馈提交与查询命令。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel

from src.core.framework.decorators import controller, on_command
from src.core.framework.session import (
    InteractiveSession,
    SessionScope,
    TimeoutConfig,
    TimeoutMode,
    interactive_session,
    on_input,
    state,
)
from src.models.enums import FeedbackSource, FeedbackStatus, FeedbackType
from src.services.feedback import FeedbackService

if TYPE_CHECKING:
    from src.core.framework.context import Context
    from src.core.framework.session.context import SessionContext

logger = structlog.get_logger()


class FeedbackSessionData(BaseModel):
    """反馈交互式会话数据模型。"""

    feedback_type: FeedbackType | None = None
    content: str | None = None
    source: FeedbackSource = FeedbackSource.private
    group_id: int | None = None


@controller(
    name="feedback",
    display_name="用户反馈",
    description="用户反馈提交与查询功能",
    tags=["user", "feedback"],
    default_enabled=True,
)
class FeedbackHandler:
    """用户反馈处理器 —— 支持简单模式和交互式模式。"""

    @on_command(
        cmd="/反馈",
        aliases={"/feedback"},
        display_name="提交反馈",
        description="提交用户反馈，支持简单模式和交互式模式",
    )
    async def submit_feedback(self, ctx: Context) -> bool:
        """提交反馈命令 —— 有参数时直接提交，无参数时启动交互式会话。"""
        if not ctx.has_service(FeedbackService):
            return False

        arg_str = ctx.get_arg_str().strip()

        # 交互式模式：无参数
        if not arg_str:
            initial_data = {
                "source": FeedbackSource.group if ctx.is_group else FeedbackSource.private,
                "group_id": ctx.group_id,
            }
            await ctx.start_session(self.FeedbackSession, initial_data=initial_data)
            return True

        # 简单模式：解析类型和内容
        feedback_type, content = self._parse_quick_feedback(arg_str)

        try:
            feedback_service = ctx.get_service(FeedbackService)
            source = FeedbackSource.group if ctx.is_group else FeedbackSource.private
            feedback = await feedback_service.create_feedback(
                user_id=ctx.user_id,
                content=content,
                source=source,
                group_id=ctx.group_id,
                feedback_type=feedback_type,
            )
            await ctx.reply(f"反馈已提交，编号：{str(feedback.id)[:8]}")
        except Exception as exc:
            logger.error(
                "创建反馈失败",
                user_id=ctx.user_id,
                error=str(exc),
                event_type="feedback.create_error",
            )
            await ctx.reply("反馈提交失败，请稍后重试")

        return True

    @on_command(
        cmd="/我的反馈",
        aliases={"/myfeedback"},
        display_name="查询我的反馈",
        description="查询用户自己的反馈列表",
    )
    async def my_feedbacks(self, ctx: Context) -> bool:
        """查询用户最近 5 条反馈。"""
        if not ctx.has_service(FeedbackService):
            return False

        feedback_service = ctx.get_service(FeedbackService)

        try:
            feedbacks = await feedback_service.get_user_feedbacks(ctx.user_id, limit=5)

            if not feedbacks:
                await ctx.reply("您还没有提交过反馈")
                return True

            lines = ["您的反馈列表："]
            for fb in feedbacks:
                fb_id = str(fb.id)[:8]
                fb_type = str(fb.feedback_type) if fb.feedback_type else "未分类"
                fb_status = "已处理" if fb.status == FeedbackStatus.done else "待处理"
                created = fb.created_at.strftime("%Y-%m-%d %H:%M")

                line = f"\n[{fb_id}] {fb_type} | {fb_status} | {created}"
                if fb.admin_reply:
                    line += f"\n回复：{fb.admin_reply}"
                lines.append(line)

            await ctx.reply("\n".join(lines))
        except Exception as exc:
            logger.error(
                "查询反馈失败",
                user_id=ctx.user_id,
                error=str(exc),
                event_type="feedback.query_error",
            )
            await ctx.reply("查询失败，请稍后重试")

        return True

    # ── 交互式会话定义 ──

    @interactive_session(
        cancel_commands=("/取消", "/cancel"),
        timeout=TimeoutConfig(
            duration=300,
            mode=TimeoutMode.notify,
            warning_before=60,
        ),
        scope=SessionScope.user,
    )
    class FeedbackSession(InteractiveSession[FeedbackSessionData]):
        """反馈收集交互式会话。"""

        @state("select_type", initial=True)
        async def prompt_type(self, ctx: SessionContext) -> None:
            """进入时提示用户选择反馈类型。"""
            await ctx.reply(
                "请选择反馈类型：\n"
                "1. bug（问题反馈）\n"
                "2. 建议\n"
                "3. 投诉\n\n"
                "请回复数字或类型名称，或发送 /取消 退出"
            )

        @on_input("select_type")
        async def process_type(self, ctx: SessionContext) -> str | None:
            """处理用户在 select_type 状态下的输入。"""
            feedback_type = _parse_type_selection(ctx.input or "")
            if feedback_type is None:
                await ctx.reply("无效的选择，请重新输入或发送 /取消 退出")
                return None
            ctx.data.feedback_type = feedback_type
            return "input_content"

        @state("input_content")
        async def prompt_content(self, ctx: SessionContext) -> None:
            """进入时提示用户输入反馈内容。"""
            await ctx.reply("请输入反馈内容：")

        @on_input("input_content")
        async def process_content(self, ctx: SessionContext) -> str | None:
            """处理用户在 input_content 状态下的输入。"""
            content = (ctx.input or "").strip()
            if not content:
                await ctx.reply("内容不能为空，请重新输入")
                return None
            ctx.data.content = content
            return "submit"

        @state("submit", final=True)
        async def do_submit(self, ctx: SessionContext) -> None:
            """终止状态 —— 提交反馈。"""
            feedback_service = ctx.get_service(FeedbackService)
            try:
                feedback = await feedback_service.create_feedback(
                    user_id=ctx.user_id,
                    content=ctx.data.content or "",
                    source=ctx.data.source,
                    group_id=ctx.data.group_id,
                    feedback_type=ctx.data.feedback_type,
                )
                await ctx.reply(f"反馈已提交，编号：{str(feedback.id)[:8]}")
            except Exception as exc:
                logger.error(
                    "创建反馈失败",
                    user_id=ctx.user_id,
                    error=str(exc),
                    event_type="feedback.create_error",
                )
                await ctx.reply("反馈提交失败，请稍后重试")

        async def on_cancel(self, ctx: SessionContext) -> None:
            """用户取消会话时的回调。"""

        async def on_timeout(self, ctx: SessionContext | None) -> None:
            """会话超时时的回调。"""

    # ── 内部辅助方法 ──

    @staticmethod
    def _parse_quick_feedback(args: str) -> tuple[FeedbackType | None, str]:
        """解析快捷反馈参数。"""
        text_lower = args.lower()
        type_keywords: tuple[tuple[str, FeedbackType], ...] = (
            ("bug", FeedbackType.bug),
            ("问题", FeedbackType.bug),
            ("建议", FeedbackType.suggestion),
            ("suggestion", FeedbackType.suggestion),
            ("投诉", FeedbackType.complaint),
            ("complaint", FeedbackType.complaint),
        )
        for keyword, ftype in type_keywords:
            if text_lower.startswith(keyword):
                return ftype, args[len(keyword) :].strip() or args
        return None, args


def _parse_type_selection(text: str) -> FeedbackType | None:
    """解析用户在交互式模式中的类型选择。"""
    text = text.strip().lower()
    if text in ("1", "bug", "问题"):
        return FeedbackType.bug
    if text in ("2", "建议", "suggestion"):
        return FeedbackType.suggestion
    if text in ("3", "投诉", "complaint"):
        return FeedbackType.complaint
    return None
