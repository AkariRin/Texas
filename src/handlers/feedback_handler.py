"""用户反馈处理器 —— 反馈提交与查询命令。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from src.core.framework.decorators import controller, on_command, on_event
from src.models.feedback import FeedbackSource, FeedbackType

if TYPE_CHECKING:
    from src.core.framework.context import Context

from src.services.feedback import FeedbackService

logger = structlog.get_logger()


@controller(
    name="feedback",
    display_name="用户反馈",
    description="用户反馈提交与查询功能",
    tags=["user", "feedback"],
    version="1.0.0",
    default_enabled=True,
)
class FeedbackHandler:
    """用户反馈处理器 —— 支持简单模式和交互式模式。"""

    @on_command(
        cmd="/取消",
        aliases={"/cancel"},
        display_name="取消操作",
        description="取消当前交互式会话",
    )
    async def cancel_session(self, ctx: Context) -> bool:
        """取消交互式会话。"""
        if not ctx.has_service(FeedbackService):
            return False

        feedback_service = ctx.get_service(FeedbackService)
        session = await feedback_service.get_session(ctx.user_id)

        if session:
            await feedback_service.clear_session(ctx.user_id)
            await ctx.reply("已取消当前操作")
            return True

        return False

    @on_event(
        event_type="message",
        priority=10,
        display_name="交互式会话处理",
        description="处理反馈交互式会话的后续消息",
    )
    async def handle_interactive_session(self, ctx: Context) -> bool:
        """处理交互式会话的后续消息。"""
        if not ctx.has_service(FeedbackService):
            return False

        feedback_service = ctx.get_service(FeedbackService)
        session = await feedback_service.get_session(ctx.user_id)

        if not session:
            return False

        text = ctx.get_plaintext().strip()

        # 处理类型选择步骤
        if session.get("step") == "select_type":
            feedback_type = self._parse_type_selection(text)
            if not feedback_type:
                await ctx.reply("无效的选择，请重新输入或发送 /取消 退出")
                return True

            session["feedback_type"] = feedback_type.value
            session["step"] = "input_content"
            await feedback_service.set_session(ctx.user_id, session)
            await ctx.reply("请输入反馈内容：")
            return True

        # 处理内容输入步骤
        if session.get("step") == "input_content":
            if not text:
                await ctx.reply("内容不能为空，请重新输入")
                return True

            try:
                source = FeedbackSource.GROUP if session.get("source") else FeedbackSource.PRIVATE
                feedback_type_str = session.get("feedback_type")
                feedback_type = FeedbackType(feedback_type_str) if feedback_type_str else None

                feedback = await feedback_service.create_feedback(
                    user_id=ctx.user_id,
                    content=text,
                    source=source,
                    group_id=session.get("group_id"),
                    feedback_type=feedback_type,
                )

                await feedback_service.clear_session(ctx.user_id)
                await ctx.reply(f"反馈已提交，编号：{str(feedback.id)[:8]}")
            except Exception as exc:
                logger.error(
                    "创建反馈失败",
                    user_id=ctx.user_id,
                    error=str(exc),
                    event_type="feedback.create_error",
                )
                await ctx.reply("反馈提交失败，请稍后重试")
                await feedback_service.clear_session(ctx.user_id)

            return True

        return False

    @on_command(
        cmd="/反馈",
        aliases={"/feedback"},
        display_name="提交反馈",
        description="提交用户反馈，支持简单模式和交互式模式",
    )
    async def submit_feedback(self, ctx: Context) -> bool:
        """提交反馈命令 —— 支持简单模式和交互式模式。"""
        if not ctx.has_service(FeedbackService):
            return False

        feedback_service = ctx.get_service(FeedbackService)
        arg_str = ctx.get_arg_str().strip()

        # 交互式模式：无参数
        if not arg_str:
            await self._start_interactive_mode(ctx, feedback_service)
            return True

        # 简单模式：解析类型和内容
        feedback_type = self._parse_type_from_text(arg_str)
        content = arg_str

        # 如果识别到类型关键词，移除关键词部分
        if feedback_type:
            for keyword in ["bug", "建议", "投诉"]:
                if arg_str.lower().startswith(keyword):
                    content = arg_str[len(keyword) :].strip()
                    break

        # 创建反馈
        try:
            source = FeedbackSource.GROUP if ctx.is_group else FeedbackSource.PRIVATE
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
                fb_type = fb.feedback_type.value if fb.feedback_type else "未分类"
                fb_status = "已处理" if fb.status.value == "processed" else "待处理"
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

    # ════════════════════════════════════════════
    #  内部辅助方法
    # ════════════════════════════════════════════

    async def _start_interactive_mode(
        self, ctx: Context, feedback_service: FeedbackService
    ) -> None:
        """启动交互式反馈模式。"""
        await ctx.reply(
            "请选择反馈类型：\n1. bug（问题反馈）\n2. 建议\n3. 投诉\n\n"
            "请回复数字或类型名称，或发送 /取消 退出"
        )
        await feedback_service.set_session(
            ctx.user_id, {"step": "select_type", "source": ctx.is_group, "group_id": ctx.group_id}
        )

    @staticmethod
    def _parse_type_from_text(text: str) -> FeedbackType | None:
        """从文本中解析反馈类型关键词。"""
        text_lower = text.lower()
        if text_lower.startswith("bug") or text_lower.startswith("问题"):
            return FeedbackType.BUG
        if text_lower.startswith("建议") or text_lower.startswith("suggestion"):
            return FeedbackType.SUGGESTION
        if text_lower.startswith("投诉") or text_lower.startswith("complaint"):
            return FeedbackType.COMPLAINT
        return None

    @staticmethod
    def _parse_type_selection(text: str) -> FeedbackType | None:
        """解析用户在交互式模式中的类型选择。"""
        text = text.strip().lower()
        if text in ("1", "bug", "问题"):
            return FeedbackType.BUG
        if text in ("2", "建议", "suggestion"):
            return FeedbackType.SUGGESTION
        if text in ("3", "投诉", "complaint"):
            return FeedbackType.COMPLAINT
        return None
