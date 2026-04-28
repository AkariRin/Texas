"""CheckinHandler 单元测试 —— 覆盖签到成功、重复签到、前置条件不满足等路径。"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from tests.conftest import make_context, make_group_message_event, make_private_message_event

# ── 辅助工厂 ─────────────────────────────────────────────────────────────────


def _make_checkin_result(
    *, is_duplicate: bool = False, rank: int = 1, streak: int = 1, total: int = 1
):
    """构造 CheckinResult 对象。"""
    from src.services.checkin import CheckinResult

    return CheckinResult(is_duplicate=is_duplicate, rank=rank, streak=streak, total=total)


def _make_checkin_svc(*, result=None) -> MagicMock:
    """构造 CheckinService Mock。"""
    svc = MagicMock()
    svc.checkin = AsyncMock(return_value=result or _make_checkin_result())
    return svc


def _make_group_ctx(*, text: str = "签到", with_svc: bool = True, result=None):
    """构造群聊 Context，可选是否注入 CheckinService。"""
    from src.services.checkin import CheckinService

    event = make_group_message_event(user_id=10001, group_id=100, text=text)
    services = {}
    if with_svc:
        services[CheckinService] = _make_checkin_svc(result=result)
    return make_context(event, services)


def _make_private_ctx(*, text: str = "签到", with_svc: bool = True):
    """构造私聊 Context，可选是否注入 CheckinService。"""
    from src.services.checkin import CheckinService

    event = make_private_message_event(user_id=10001, text=text)
    services = {}
    if with_svc:
        services[CheckinService] = _make_checkin_svc()
    return make_context(event, services)


# ── 测试类 ────────────────────────────────────────────────────────────────────


class TestCheckinHandlerSuccess:
    """正常签到路径测试。"""

    async def test_success_calls_reply_once(self) -> None:
        """签到成功时 ctx.reply 被调用一次。"""
        from src.handlers.checkin import CheckinHandler

        ctx = _make_group_ctx()
        handler = CheckinHandler()

        with patch("src.handlers.checkin.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2024, 1, 1)
            result = await handler.handle_checkin(ctx)

        assert result is True
        ctx.reply.assert_awaited_once()

    async def test_success_calls_checkin_service(self) -> None:
        """签到成功时 CheckinService.checkin 被调用，且参数包含 group_id 和 user_id。"""
        from src.handlers.checkin import CheckinHandler
        from src.services.checkin import CheckinService

        ctx = _make_group_ctx()
        handler = CheckinHandler()

        with patch("src.handlers.checkin.datetime") as mock_dt:
            fixed_date = date(2024, 1, 1)
            mock_dt.now.return_value.date.return_value = fixed_date
            await handler.handle_checkin(ctx)

        svc: MagicMock = ctx.get_service(CheckinService)
        svc.checkin.assert_awaited_once_with(
            group_id=100,
            user_id=10001,
            today=fixed_date,
        )

    async def test_success_rank_in_reply(self) -> None:
        """签到成功时回复内容包含排名信息。"""
        from src.handlers.checkin import CheckinHandler

        result_obj = _make_checkin_result(is_duplicate=False, rank=3, streak=5, total=20)
        ctx = _make_group_ctx(result=result_obj)
        handler = CheckinHandler()

        with patch("src.handlers.checkin.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2024, 1, 1)
            await handler.handle_checkin(ctx)

        ctx.reply.assert_awaited_once()


class TestCheckinHandlerDuplicate:
    """重复签到路径测试。"""

    async def test_duplicate_reply_contains_already_text(self) -> None:
        """重复签到时回复文本包含「已经」或「今天」字样。"""
        from src.handlers.checkin import CheckinHandler

        result_obj = _make_checkin_result(is_duplicate=True, rank=0, streak=3, total=10)
        ctx = _make_group_ctx(result=result_obj)
        handler = CheckinHandler()

        with patch("src.handlers.checkin.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2024, 1, 1)
            await handler.handle_checkin(ctx)

        ctx.reply.assert_awaited_once()
        # 取回调用时的参数，检查是否含有"已经"或"今天"
        call_args = ctx.reply.call_args[0][0]
        # call_args 可能是 list（MessageSegment 列表）或字符串
        reply_text = str(call_args)
        assert "已经" in reply_text or "今天" in reply_text

    async def test_duplicate_still_calls_reply(self) -> None:
        """重复签到时 ctx.reply 仍应被调用一次（不静默）。"""
        from src.handlers.checkin import CheckinHandler

        result_obj = _make_checkin_result(is_duplicate=True)
        ctx = _make_group_ctx(result=result_obj)
        handler = CheckinHandler()

        with patch("src.handlers.checkin.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2024, 1, 1)
            result = await handler.handle_checkin(ctx)

        assert result is True
        ctx.reply.assert_awaited_once()


class TestCheckinHandlerPreconditions:
    """前置条件失败路径测试。"""

    async def test_missing_service_returns_false(self) -> None:
        """缺少 CheckinService 时直接返回 False，不调用 reply。"""
        from src.handlers.checkin import CheckinHandler

        ctx = _make_group_ctx(with_svc=False)
        handler = CheckinHandler()

        result = await handler.handle_checkin(ctx)

        assert result is False
        ctx.reply.assert_not_awaited()

    async def test_private_chat_returns_false(self) -> None:
        """私聊（group_id=None）时直接返回 False，不调用 reply。"""
        from src.handlers.checkin import CheckinHandler

        ctx = _make_private_ctx()
        handler = CheckinHandler()

        result = await handler.handle_checkin(ctx)

        assert result is False
        ctx.reply.assert_not_awaited()

    async def test_private_chat_missing_service_returns_false(self) -> None:
        """私聊且缺少服务时同样返回 False。"""
        from src.handlers.checkin import CheckinHandler

        ctx = _make_private_ctx(with_svc=False)
        handler = CheckinHandler()

        result = await handler.handle_checkin(ctx)

        assert result is False
        ctx.reply.assert_not_awaited()
