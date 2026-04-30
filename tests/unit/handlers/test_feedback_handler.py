"""FeedbackHandler 单元测试。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.handlers.feedback import FeedbackHandler
from src.models.feedback import FeedbackSource, FeedbackStatus, FeedbackType
from tests.conftest import make_context, make_group_message_event, make_private_message_event

# ── 辅助函数 ──────────────────────────────────────────────────────────────────


def _make_feedback(
    feedback_id: str | None = None,
    feedback_type: FeedbackType | None = FeedbackType.bug,
    status: FeedbackStatus = FeedbackStatus.pending,
    admin_reply: str | None = None,
) -> Any:
    """构造模拟 Feedback 对象。"""
    fb = MagicMock()
    fb.id = uuid.UUID(feedback_id) if feedback_id else uuid.uuid4()
    fb.feedback_type = feedback_type
    fb.status = status
    fb.admin_reply = admin_reply
    fb.created_at = datetime(2024, 1, 15, 12, 30, 0)
    return fb


def _make_feedback_service(
    create_result: Any = None,
    get_user_feedbacks_result: list[Any] | None = None,
) -> Any:
    """构造 FeedbackService mock。"""
    svc = MagicMock()
    if create_result is None:
        create_result = _make_feedback()
    svc.create_feedback = AsyncMock(return_value=create_result)
    svc.get_user_feedbacks = AsyncMock(return_value=get_user_feedbacks_result or [])
    return svc


# ── FeedbackHandler.submit_feedback 测试 ─────────────────────────────────────


class TestSubmitFeedback:
    """submit_feedback 命令测试组。"""

    @pytest.fixture
    def handler(self) -> FeedbackHandler:
        return FeedbackHandler()

    async def test_no_service_returns_false(self, handler: FeedbackHandler) -> None:
        """缺少 FeedbackService 时应返回 False。"""
        event = make_group_message_event(text="/反馈 bug 崩溃了")
        ctx = make_context(event)  # 不传入任何 services

        result = await handler.submit_feedback(ctx)

        assert result is False
        ctx.reply.assert_not_called()

    async def test_bug_prefix_calls_create_feedback(self, handler: FeedbackHandler) -> None:
        """有 bug 前缀参数时应调用 create_feedback，类型为 bug。"""
        feedback_svc = _make_feedback_service()
        event = make_group_message_event(text="/反馈 bug 登录时崩溃")
        from src.services.feedback import FeedbackService

        ctx = make_context(event, services={FeedbackService: feedback_svc})

        result = await handler.submit_feedback(ctx)

        assert result is True
        feedback_svc.create_feedback.assert_awaited_once()
        call_kwargs = feedback_svc.create_feedback.call_args.kwargs
        assert call_kwargs["feedback_type"] == FeedbackType.bug
        assert call_kwargs["content"] == "登录时崩溃"

    async def test_reply_contains_feedback_id(self, handler: FeedbackHandler) -> None:
        """提交成功后回复应包含反馈 ID 的前 8 个字符。"""
        fixed_id = uuid.UUID("12345678-abcd-ef12-3456-789012345678")
        feedback_obj = _make_feedback(feedback_id=str(fixed_id))
        feedback_svc = _make_feedback_service(create_result=feedback_obj)

        event = make_group_message_event(text="/反馈 bug 登录时崩溃")
        from src.services.feedback import FeedbackService

        ctx = make_context(event, services={FeedbackService: feedback_svc})

        await handler.submit_feedback(ctx)

        ctx.reply.assert_awaited_once()
        reply_text: str = ctx.reply.call_args.args[0]
        assert "12345678" in reply_text

    async def test_no_args_starts_session(self, handler: FeedbackHandler) -> None:
        """无参数时应启动交互式会话，不调用 create_feedback。"""
        feedback_svc = _make_feedback_service()
        event = make_group_message_event(text="/反馈")
        from src.services.feedback import FeedbackService

        ctx = make_context(event, services={FeedbackService: feedback_svc})
        ctx.start_session = AsyncMock(return_value=True)

        result = await handler.submit_feedback(ctx)

        assert result is True
        ctx.start_session.assert_awaited_once()
        feedback_svc.create_feedback.assert_not_awaited()

    async def test_no_args_whitespace_starts_session(self, handler: FeedbackHandler) -> None:
        """参数仅含空白字符时也应启动交互式会话。"""
        feedback_svc = _make_feedback_service()
        event = make_group_message_event(text="/反馈   ")
        from src.services.feedback import FeedbackService

        ctx = make_context(event, services={FeedbackService: feedback_svc})
        ctx.start_session = AsyncMock(return_value=True)

        await handler.submit_feedback(ctx)

        ctx.start_session.assert_awaited_once()

    async def test_suggestion_prefix(self, handler: FeedbackHandler) -> None:
        """建议前缀时 create_feedback 应收到 suggestion 类型。"""
        feedback_svc = _make_feedback_service()
        event = make_group_message_event(text="/反馈 建议 增加黑暗模式")
        from src.services.feedback import FeedbackService

        ctx = make_context(event, services={FeedbackService: feedback_svc})

        await handler.submit_feedback(ctx)

        call_kwargs = feedback_svc.create_feedback.call_args.kwargs
        assert call_kwargs["feedback_type"] == FeedbackType.suggestion
        assert call_kwargs["content"] == "增加黑暗模式"

    async def test_complaint_prefix(self, handler: FeedbackHandler) -> None:
        """投诉前缀时 create_feedback 应收到 complaint 类型。"""
        feedback_svc = _make_feedback_service()
        event = make_group_message_event(text="/反馈 投诉 管理员乱用权力")
        from src.services.feedback import FeedbackService

        ctx = make_context(event, services={FeedbackService: feedback_svc})

        await handler.submit_feedback(ctx)

        call_kwargs = feedback_svc.create_feedback.call_args.kwargs
        assert call_kwargs["feedback_type"] == FeedbackType.complaint
        assert call_kwargs["content"] == "管理员乱用权力"

    async def test_no_keyword_feedback_type_is_none(self, handler: FeedbackHandler) -> None:
        """无关键词前缀时 create_feedback 应收到 None 类型，内容为原始参数。"""
        feedback_svc = _make_feedback_service()
        event = make_group_message_event(text="/反馈 系统有点慢")
        from src.services.feedback import FeedbackService

        ctx = make_context(event, services={FeedbackService: feedback_svc})

        await handler.submit_feedback(ctx)

        call_kwargs = feedback_svc.create_feedback.call_args.kwargs
        assert call_kwargs["feedback_type"] is None
        assert call_kwargs["content"] == "系统有点慢"

    async def test_group_source_when_group_event(self, handler: FeedbackHandler) -> None:
        """群聊事件时 source 应为 group。"""
        feedback_svc = _make_feedback_service()
        event = make_group_message_event(group_id=200, text="/反馈 bug 测试")
        from src.services.feedback import FeedbackService

        ctx = make_context(event, services={FeedbackService: feedback_svc})

        await handler.submit_feedback(ctx)

        call_kwargs = feedback_svc.create_feedback.call_args.kwargs
        assert call_kwargs["source"] == FeedbackSource.group
        assert call_kwargs["group_id"] == 200

    async def test_private_source_when_private_event(self, handler: FeedbackHandler) -> None:
        """私聊事件时 source 应为 private，group_id 为 None。"""
        feedback_svc = _make_feedback_service()
        event = make_private_message_event(text="/反馈 bug 测试")
        from src.services.feedback import FeedbackService

        ctx = make_context(event, services={FeedbackService: feedback_svc})

        await handler.submit_feedback(ctx)

        call_kwargs = feedback_svc.create_feedback.call_args.kwargs
        assert call_kwargs["source"] == FeedbackSource.private
        assert call_kwargs["group_id"] is None

    async def test_create_feedback_exception_replies_error(self, handler: FeedbackHandler) -> None:
        """create_feedback 抛出异常时应回复错误提示，仍返回 True。"""
        feedback_svc = _make_feedback_service()
        feedback_svc.create_feedback = AsyncMock(side_effect=RuntimeError("DB error"))
        event = make_group_message_event(text="/反馈 bug 崩溃")
        from src.services.feedback import FeedbackService

        ctx = make_context(event, services={FeedbackService: feedback_svc})

        result = await handler.submit_feedback(ctx)

        assert result is True
        ctx.reply.assert_awaited_once()
        reply_text: str = ctx.reply.call_args.args[0]
        assert "失败" in reply_text


# ── FeedbackHandler.my_feedbacks 测试 ────────────────────────────────────────


class TestMyFeedbacks:
    """my_feedbacks 命令测试组。"""

    @pytest.fixture
    def handler(self) -> FeedbackHandler:
        return FeedbackHandler()

    async def test_no_service_returns_false(self, handler: FeedbackHandler) -> None:
        """缺少 FeedbackService 时应返回 False。"""
        event = make_group_message_event(text="/我的反馈")
        ctx = make_context(event)

        result = await handler.my_feedbacks(ctx)

        assert result is False
        ctx.reply.assert_not_called()

    async def test_empty_feedbacks_replies_none_message(self, handler: FeedbackHandler) -> None:
        """空反馈列表时应回复"没有"相关提示。"""
        feedback_svc = _make_feedback_service(get_user_feedbacks_result=[])
        event = make_group_message_event(user_id=10001, text="/我的反馈")
        from src.services.feedback import FeedbackService

        ctx = make_context(event, services={FeedbackService: feedback_svc})

        result = await handler.my_feedbacks(ctx)

        assert result is True
        ctx.reply.assert_awaited_once()
        reply_text: str = ctx.reply.call_args.args[0]
        assert "没有" in reply_text

    async def test_empty_feedbacks_calls_get_with_correct_user(
        self, handler: FeedbackHandler
    ) -> None:
        """get_user_feedbacks 应使用 ctx.user_id 和 limit=5 调用。"""
        feedback_svc = _make_feedback_service(get_user_feedbacks_result=[])
        event = make_group_message_event(user_id=20002, text="/我的反馈")
        from src.services.feedback import FeedbackService

        ctx = make_context(event, services={FeedbackService: feedback_svc})

        await handler.my_feedbacks(ctx)

        feedback_svc.get_user_feedbacks.assert_awaited_once_with(20002, limit=5)

    async def test_feedbacks_list_is_replied(self, handler: FeedbackHandler) -> None:
        """有反馈时应回复包含反馈列表的消息。"""
        fb1 = _make_feedback(
            feedback_type=FeedbackType.bug,
            status=FeedbackStatus.pending,
        )
        fb2 = _make_feedback(
            feedback_type=FeedbackType.suggestion,
            status=FeedbackStatus.done,
            admin_reply="感谢建议",
        )
        feedback_svc = _make_feedback_service(get_user_feedbacks_result=[fb1, fb2])
        event = make_group_message_event(text="/我的反馈")
        from src.services.feedback import FeedbackService

        ctx = make_context(event, services={FeedbackService: feedback_svc})

        result = await handler.my_feedbacks(ctx)

        assert result is True
        ctx.reply.assert_awaited_once()
        reply_text: str = ctx.reply.call_args.args[0]
        # 应包含列表标题
        assert "反馈列表" in reply_text

    async def test_feedbacks_list_contains_id_prefix(self, handler: FeedbackHandler) -> None:
        """回复的反馈列表应包含反馈 ID 的前 8 个字符。"""
        fixed_id = uuid.UUID("aaaabbbb-cccc-dddd-eeee-ffffffffffff")
        fb = _make_feedback(feedback_id=str(fixed_id))
        feedback_svc = _make_feedback_service(get_user_feedbacks_result=[fb])
        event = make_group_message_event(text="/我的反馈")
        from src.services.feedback import FeedbackService

        ctx = make_context(event, services={FeedbackService: feedback_svc})

        await handler.my_feedbacks(ctx)

        reply_text: str = ctx.reply.call_args.args[0]
        assert "aaaabbbb" in reply_text

    async def test_feedbacks_list_contains_admin_reply(self, handler: FeedbackHandler) -> None:
        """有管理员回复的反馈应在列表中展示回复内容。"""
        fb = _make_feedback(
            status=FeedbackStatus.done,
            admin_reply="已修复，感谢反馈",
        )
        feedback_svc = _make_feedback_service(get_user_feedbacks_result=[fb])
        event = make_group_message_event(text="/我的反馈")
        from src.services.feedback import FeedbackService

        ctx = make_context(event, services={FeedbackService: feedback_svc})

        await handler.my_feedbacks(ctx)

        reply_text: str = ctx.reply.call_args.args[0]
        assert "已修复，感谢反馈" in reply_text

    async def test_get_user_feedbacks_exception_replies_error(
        self, handler: FeedbackHandler
    ) -> None:
        """get_user_feedbacks 抛出异常时应回复错误提示，仍返回 True。"""
        feedback_svc = _make_feedback_service()
        feedback_svc.get_user_feedbacks = AsyncMock(side_effect=RuntimeError("DB timeout"))
        event = make_group_message_event(text="/我的反馈")
        from src.services.feedback import FeedbackService

        ctx = make_context(event, services={FeedbackService: feedback_svc})

        result = await handler.my_feedbacks(ctx)

        assert result is True
        ctx.reply.assert_awaited_once()
        reply_text: str = ctx.reply.call_args.args[0]
        assert "失败" in reply_text


# ── FeedbackHandler._parse_quick_feedback 测试 ───────────────────────────────


class TestParseQuickFeedback:
    """_parse_quick_feedback 静态方法测试组。"""

    def test_bug_prefix_returns_bug_type(self) -> None:
        """'bug ...' 应返回 (FeedbackType.bug, 内容)。"""
        ftype, content = FeedbackHandler._parse_quick_feedback("bug 登录崩溃")
        assert ftype == FeedbackType.bug
        assert content == "登录崩溃"

    def test_bug_prefix_uppercase(self) -> None:
        """'Bug ...' (大写) 也应匹配 bug 类型（不区分大小写）。"""
        ftype, content = FeedbackHandler._parse_quick_feedback("Bug 内存泄漏")
        assert ftype == FeedbackType.bug
        assert content == "内存泄漏"

    def test_suggestion_prefix(self) -> None:
        """'建议 ...' 应返回 (FeedbackType.suggestion, 内容)。"""
        ftype, content = FeedbackHandler._parse_quick_feedback("建议 增加黑暗模式")
        assert ftype == FeedbackType.suggestion
        assert content == "增加黑暗模式"

    def test_complaint_prefix(self) -> None:
        """'投诉 ...' 应返回 (FeedbackType.complaint, 内容)。"""
        ftype, content = FeedbackHandler._parse_quick_feedback("投诉 管理员乱用权力")
        assert ftype == FeedbackType.complaint
        assert content == "管理员乱用权力"

    def test_suggestion_english_prefix(self) -> None:
        """'suggestion ...' 应返回 (FeedbackType.suggestion, 内容)。"""
        ftype, content = FeedbackHandler._parse_quick_feedback("suggestion add dark mode")
        assert ftype == FeedbackType.suggestion
        assert content == "add dark mode"

    def test_complaint_english_prefix(self) -> None:
        """'complaint ...' 应返回 (FeedbackType.complaint, 内容)。"""
        ftype, content = FeedbackHandler._parse_quick_feedback("complaint abusive admin")
        assert ftype == FeedbackType.complaint
        assert content == "abusive admin"

    def test_no_keyword_returns_none_type(self) -> None:
        """无关键词时应返回 (None, 原始内容)。"""
        ftype, content = FeedbackHandler._parse_quick_feedback("系统有点慢")
        assert ftype is None
        assert content == "系统有点慢"

    def test_keyword_only_no_content_returns_keyword_as_content(self) -> None:
        """仅有关键词无内容时，content 应为原始参数（关键词本身）。"""
        ftype, content = FeedbackHandler._parse_quick_feedback("bug")
        assert ftype == FeedbackType.bug
        # 剩余内容为空，回退到原始参数 "bug"
        assert content == "bug"

    def test_suggestion_keyword_only(self) -> None:
        """'建议' 仅关键词时应回退到原始参数。"""
        ftype, content = FeedbackHandler._parse_quick_feedback("建议")
        assert ftype == FeedbackType.suggestion
        assert content == "建议"

    def test_complaint_keyword_only(self) -> None:
        """'投诉' 仅关键词时应回退到原始参数。"""
        ftype, content = FeedbackHandler._parse_quick_feedback("投诉")
        assert ftype == FeedbackType.complaint
        assert content == "投诉"

    def test_problem_keyword_maps_to_bug(self) -> None:
        """'问题 ...' 应返回 (FeedbackType.bug, 内容)。"""
        ftype, content = FeedbackHandler._parse_quick_feedback("问题 无法登录")
        assert ftype == FeedbackType.bug
        assert content == "无法登录"
