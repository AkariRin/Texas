"""FeedbackService 单元测试。"""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.enums import FeedbackSource, FeedbackStatus, FeedbackType
from src.services.feedback import FeedbackService
from tests.unit.services.conftest import (
    make_bot_api,
    make_execute_result,
    make_session,
    make_session_factory,
)

# ── 辅助函数 ──────────────────────────────────────────────────────────────────


def _make_feedback(
    *,
    status: FeedbackStatus = FeedbackStatus.pending,
    source: FeedbackSource = FeedbackSource.private,
    user_id: int = 10001,
    group_id: int | None = None,
    content: str = "测试反馈内容",
    admin_reply: str | None = None,
    feedback_id: str | None = None,
) -> MagicMock:
    """构造模拟 Feedback ORM 对象。"""
    fb = MagicMock()
    fb.id = uuid.UUID(feedback_id) if feedback_id else uuid.uuid4()
    fb.status = status
    fb.source = source
    fb.user_id = user_id
    fb.group_id = group_id
    fb.content = content
    fb.admin_reply = admin_reply
    fb.created_at = datetime(2024, 1, 15, 12, 0, 0)
    return fb


def _make_admin_user(qq: int = 99999) -> MagicMock:
    """构造模拟管理员 User 对象。"""
    admin = MagicMock()
    admin.qq = qq
    return admin


# ── TestCreateFeedback ────────────────────────────────────────────────────────


class TestCreateFeedback:
    """create_feedback 测试组。"""

    @pytest.fixture
    def bot_api(self) -> MagicMock:
        return make_bot_api()

    async def test_session_add_called(self, bot_api: MagicMock) -> None:
        """应调用 session.add() 插入 Feedback 对象。"""
        factory, session = make_session_factory()
        svc = FeedbackService(session_factory=factory, bot_api=bot_api)

        await svc.create_feedback(
            user_id=10001,
            content="bug report",
            source=FeedbackSource.group,
            group_id=100,
            feedback_type=FeedbackType.bug,
        )

        session.add.assert_called_once()
        session.flush.assert_awaited_once()
        session.refresh.assert_awaited_once()

    async def test_returns_feedback_object(self, bot_api: MagicMock) -> None:
        """应返回 Feedback 对象（即 session.add 收到的那个对象）。"""
        factory, session = make_session_factory()
        svc = FeedbackService(session_factory=factory, bot_api=bot_api)

        result = await svc.create_feedback(
            user_id=10001,
            content="feature request",
            source=FeedbackSource.private,
        )

        added_obj = session.add.call_args.args[0]
        assert result is added_obj

    async def test_notify_admin_exception_does_not_propagate(self, bot_api: MagicMock) -> None:
        """_notify_admins 内部异常不应向外传播。"""
        session = make_session()
        session.execute = AsyncMock(side_effect=RuntimeError("DB timeout"))
        factory, _ = make_session_factory(session)
        svc = FeedbackService(session_factory=factory, bot_api=bot_api)

        result = await svc.create_feedback(
            user_id=10001,
            content="test",
            source=FeedbackSource.group,
            group_id=100,
        )

        assert result is not None

    async def test_no_admins_skips_bot_notification(self, bot_api: MagicMock) -> None:
        """无管理员时不应调用 bot_api.send_private_msg。"""
        admin_result = make_execute_result(scalars_all=[])
        session = make_session(execute_side_effects=[admin_result])
        factory, _ = make_session_factory(session)
        svc = FeedbackService(session_factory=factory, bot_api=bot_api)

        await svc.create_feedback(
            user_id=10001,
            content="test",
            source=FeedbackSource.private,
        )

        bot_api.send_private_msg.assert_not_awaited()

    async def test_with_admins_notifies_via_bot(self, bot_api: MagicMock) -> None:
        """有管理员时应调用 bot_api.send_private_msg 通知每位管理员。"""
        admin1 = _make_admin_user(qq=111)
        admin2 = _make_admin_user(qq=222)
        admin_result = make_execute_result(scalars_all=[admin1, admin2])
        session = make_session(execute_side_effects=[admin_result])
        factory, _ = make_session_factory(session)
        svc = FeedbackService(session_factory=factory, bot_api=bot_api)

        await svc.create_feedback(
            user_id=10001,
            content="test",
            source=FeedbackSource.group,
            group_id=100,
            feedback_type=FeedbackType.bug,
        )

        assert bot_api.send_private_msg.await_count == 2


# ── TestUpdateStatus ──────────────────────────────────────────────────────────


class TestUpdateStatus:
    """update_status 测试组。"""

    @pytest.fixture
    def bot_api(self) -> MagicMock:
        return make_bot_api()

    async def test_not_found_returns_none(self, bot_api: MagicMock) -> None:
        """session.get 返回 None 时应返回 None，不抛异常。"""
        factory, _ = make_session_factory(make_session(get_result=None))
        svc = FeedbackService(session_factory=factory, bot_api=bot_api)

        result = await svc.update_status(uuid.uuid4(), FeedbackStatus.done)

        assert result is None

    async def test_sets_processed_at_on_first_done_transition(self, bot_api: MagicMock) -> None:
        """pending → done 首次转换应设置 processed_at 为当前时间。"""
        feedback = _make_feedback(
            status=FeedbackStatus.pending,
            source=FeedbackSource.private,
        )
        factory, _ = make_session_factory(make_session(get_result=feedback))
        svc = FeedbackService(session_factory=factory, bot_api=bot_api)

        await svc.update_status(feedback.id, FeedbackStatus.done)

        assert isinstance(feedback.processed_at, datetime)

    async def test_does_not_reset_processed_at_for_done_to_done(self, bot_api: MagicMock) -> None:
        """done → done 重复更新时，不应重设 processed_at。"""
        original_time = datetime(2024, 1, 10, 8, 0, 0)
        feedback = _make_feedback(status=FeedbackStatus.done, source=FeedbackSource.private)
        feedback.processed_at = original_time
        factory, _ = make_session_factory(make_session(get_result=feedback))
        svc = FeedbackService(session_factory=factory, bot_api=bot_api)

        await svc.update_status(feedback.id, FeedbackStatus.done)

        assert feedback.processed_at is original_time

    async def test_notifies_user_on_done_transition(self, bot_api: MagicMock) -> None:
        """pending → done 时应通知用户（私聊反馈走 send_private_msg）。"""
        feedback = _make_feedback(
            status=FeedbackStatus.pending,
            source=FeedbackSource.private,
            user_id=10001,
        )
        factory, _ = make_session_factory(make_session(get_result=feedback))
        svc = FeedbackService(session_factory=factory, bot_api=bot_api)

        await svc.update_status(feedback.id, FeedbackStatus.done)

        bot_api.send_private_msg.assert_awaited_once()
        call_user_id = bot_api.send_private_msg.call_args.args[0]
        assert call_user_id == 10001

    async def test_group_source_feedback_notified_via_group_msg(self, bot_api: MagicMock) -> None:
        """群聊反馈 done 通知走 send_group_msg，而非 send_private_msg。"""
        feedback = _make_feedback(
            status=FeedbackStatus.pending,
            source=FeedbackSource.group,
            group_id=500,
        )
        factory, _ = make_session_factory(make_session(get_result=feedback))
        svc = FeedbackService(session_factory=factory, bot_api=bot_api)

        await svc.update_status(feedback.id, FeedbackStatus.done)

        bot_api.send_group_msg.assert_awaited_once()
        call_group_id = bot_api.send_group_msg.call_args.args[0]
        assert call_group_id == 500
        bot_api.send_private_msg.assert_not_awaited()

    async def test_does_not_notify_for_non_done_status(self, bot_api: MagicMock) -> None:
        """更新为非 done 状态（保持 pending 并写入 admin_reply）时不应发送通知。

        FeedbackStatus 只有 pending / done 两个成员，
        用 pending → pending 覆盖"非 done 转换"路径。
        """
        feedback = _make_feedback(status=FeedbackStatus.pending, source=FeedbackSource.private)
        factory, _ = make_session_factory(make_session(get_result=feedback))
        svc = FeedbackService(session_factory=factory, bot_api=bot_api)

        await svc.update_status(feedback.id, FeedbackStatus.pending, admin_reply="内部备注")

        bot_api.send_private_msg.assert_not_awaited()
        bot_api.send_group_msg.assert_not_awaited()

    async def test_stores_admin_reply(self, bot_api: MagicMock) -> None:
        """admin_reply 参数应写入 feedback.admin_reply 字段。"""
        feedback = _make_feedback(status=FeedbackStatus.pending, source=FeedbackSource.private)
        factory, _ = make_session_factory(make_session(get_result=feedback))
        svc = FeedbackService(session_factory=factory, bot_api=bot_api)

        await svc.update_status(feedback.id, FeedbackStatus.done, admin_reply="问题已修复")

        assert feedback.admin_reply == "问题已修复"


# ── TestNotifyUserContentTruncation ──────────────────────────────────────────


class TestNotifyUserContentTruncation:
    """_notify_user 内容截断逻辑测试（通过 update_status 间接验证）。"""

    @pytest.fixture
    def bot_api(self) -> MagicMock:
        return make_bot_api()

    async def test_truncates_content_longer_than_50_chars(self, bot_api: MagicMock) -> None:
        """content 超过 50 字符时，通知消息中应截断为前 50 字 + '...'。"""
        long_content = "x" * 60
        feedback = _make_feedback(
            status=FeedbackStatus.pending,
            source=FeedbackSource.private,
            content=long_content,
        )
        factory, _ = make_session_factory(make_session(get_result=feedback))
        svc = FeedbackService(session_factory=factory, bot_api=bot_api)

        await svc.update_status(feedback.id, FeedbackStatus.done)

        message: str = bot_api.send_private_msg.call_args.args[1]
        assert "x" * 50 + "..." in message
        assert "x" * 60 not in message

    async def test_does_not_truncate_short_content(self, bot_api: MagicMock) -> None:
        """content 不超过 50 字符时，通知消息中应完整显示。"""
        short_content = "短内容"
        feedback = _make_feedback(
            status=FeedbackStatus.pending,
            source=FeedbackSource.private,
            content=short_content,
        )
        factory, _ = make_session_factory(make_session(get_result=feedback))
        svc = FeedbackService(session_factory=factory, bot_api=bot_api)

        await svc.update_status(feedback.id, FeedbackStatus.done)

        message: str = bot_api.send_private_msg.call_args.args[1]
        assert "短内容" in message
        assert "..." not in message
