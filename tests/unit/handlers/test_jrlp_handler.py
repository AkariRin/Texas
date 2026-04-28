"""JrlpHandler 单元测试 —— 覆盖今日老婆抽取的主要路径。"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from tests.conftest import make_context, make_group_message_event, make_private_message_event

# ── 辅助工厂 ─────────────────────────────────────────────────────────────────


def _make_jrlp_record(*, wife_qq: int = 20002) -> MagicMock:
    """构造 JrlpRecord Mock。"""
    record = MagicMock()
    record.wife_qq = wife_qq
    return record


def _make_jrlp_svc(
    *,
    is_new: bool = True,
    wife_display_name: str = "测试老婆",
    wife_qq: int = 20002,
    raise_value_error: bool = False,
    raise_exception: bool = False,
) -> MagicMock:
    """构造 JrlpService Mock。"""
    svc = MagicMock()
    if raise_value_error:
        svc.get_or_draw = AsyncMock(side_effect=ValueError("无可用成员"))
    elif raise_exception:
        svc.get_or_draw = AsyncMock(side_effect=RuntimeError("未知错误"))
    else:
        record = _make_jrlp_record(wife_qq=wife_qq)
        svc.get_or_draw = AsyncMock(return_value=(record, is_new, wife_display_name))
    return svc


def _make_group_ctx(
    *,
    text: str = "jrlp",
    with_svc: bool = True,
    is_new: bool = True,
    wife_display_name: str = "测试老婆",
    wife_qq: int = 20002,
    raise_value_error: bool = False,
    raise_exception: bool = False,
):
    """构造群聊 Context，可选是否注入 JrlpService。"""
    from src.services.jrlp import JrlpService

    event = make_group_message_event(user_id=10001, group_id=100, text=text)
    services = {}
    if with_svc:
        services[JrlpService] = _make_jrlp_svc(
            is_new=is_new,
            wife_display_name=wife_display_name,
            wife_qq=wife_qq,
            raise_value_error=raise_value_error,
            raise_exception=raise_exception,
        )
    return make_context(event, services)


def _make_private_ctx(*, text: str = "jrlp", with_svc: bool = True):
    """构造私聊 Context，可选是否注入 JrlpService。"""
    from src.services.jrlp import JrlpService

    event = make_private_message_event(user_id=10001, text=text)
    services = {}
    if with_svc:
        services[JrlpService] = _make_jrlp_svc()
    return make_context(event, services)


# ── 测试类 ────────────────────────────────────────────────────────────────────


class TestJrlpHandlerNewDraw:
    """首次抽取（is_new=True）路径测试。"""

    async def test_new_draw_calls_get_or_draw(self) -> None:
        """首次抽取时 get_or_draw 被调用，参数包含 group_id、user_id、today。"""
        from src.handlers.jrlp import JrlpHandler
        from src.services.jrlp import JrlpService

        ctx = _make_group_ctx(is_new=True)
        handler = JrlpHandler()

        with patch("src.handlers.jrlp.datetime") as mock_dt:
            fixed_date = date(2024, 1, 1)
            mock_dt.now.return_value.date.return_value = fixed_date
            await handler.draw_wife(ctx)

        svc: MagicMock = ctx.get_service(JrlpService)
        svc.get_or_draw.assert_awaited_once_with(
            group_id=100,
            user_id=10001,
            today=fixed_date,
        )

    async def test_new_draw_calls_reply(self) -> None:
        """首次抽取时 ctx.reply 被调用一次并返回 True。"""
        from src.handlers.jrlp import JrlpHandler

        ctx = _make_group_ctx(is_new=True)
        handler = JrlpHandler()

        with patch("src.handlers.jrlp.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2024, 1, 1)
            result = await handler.draw_wife(ctx)

        assert result is True
        ctx.reply.assert_awaited_once()

    async def test_new_draw_reply_contains_wife_name(self) -> None:
        """首次抽取时回复内容包含老婆名字。"""
        from src.handlers.jrlp import JrlpHandler

        ctx = _make_group_ctx(is_new=True, wife_display_name="小花", wife_qq=99999)
        handler = JrlpHandler()

        with patch("src.handlers.jrlp.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2024, 1, 1)
            await handler.draw_wife(ctx)

        ctx.reply.assert_awaited_once()
        call_text = str(ctx.reply.call_args[0][0])
        assert "小花" in call_text


class TestJrlpHandlerRepeatDraw:
    """重复抽取（is_new=False）路径测试。"""

    async def test_repeat_draw_calls_reply(self) -> None:
        """重复抽取时 ctx.reply 仍被调用一次且返回 True。"""
        from src.handlers.jrlp import JrlpHandler

        ctx = _make_group_ctx(is_new=False)
        handler = JrlpHandler()

        with patch("src.handlers.jrlp.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2024, 1, 1)
            result = await handler.draw_wife(ctx)

        assert result is True
        ctx.reply.assert_awaited_once()

    async def test_repeat_draw_reply_differs_from_new(self) -> None:
        """重复抽取的回复文本与首次抽取不同（包含"已经"等字样）。"""
        from src.handlers.jrlp import JrlpHandler

        ctx = _make_group_ctx(is_new=False, wife_display_name="测试老婆", wife_qq=20002)
        handler = JrlpHandler()

        with patch("src.handlers.jrlp.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2024, 1, 1)
            await handler.draw_wife(ctx)

        ctx.reply.assert_awaited_once()
        call_text = str(ctx.reply.call_args[0][0])
        # 重复抽取时应包含"已经"字样
        assert "已经" in call_text


class TestJrlpHandlerPreconditions:
    """前置条件失败路径测试。"""

    async def test_private_chat_returns_false(self) -> None:
        """私聊时直接返回 False，get_or_draw 不被调用。"""
        from src.handlers.jrlp import JrlpHandler
        from src.services.jrlp import JrlpService

        ctx = _make_private_ctx()
        handler = JrlpHandler()

        result = await handler.draw_wife(ctx)

        assert result is False
        svc: MagicMock = ctx.get_service(JrlpService)
        svc.get_or_draw.assert_not_awaited()
        ctx.reply.assert_not_awaited()

    async def test_missing_service_returns_false(self) -> None:
        """缺少 JrlpService 时直接返回 False，不调用 reply。"""
        from src.handlers.jrlp import JrlpHandler

        ctx = _make_group_ctx(with_svc=False)
        handler = JrlpHandler()

        result = await handler.draw_wife(ctx)

        assert result is False
        ctx.reply.assert_not_awaited()

    async def test_private_missing_service_returns_false(self) -> None:
        """私聊且缺少服务时同样返回 False。"""
        from src.handlers.jrlp import JrlpHandler

        ctx = _make_private_ctx(with_svc=False)
        handler = JrlpHandler()

        result = await handler.draw_wife(ctx)

        assert result is False
        ctx.reply.assert_not_awaited()


class TestJrlpHandlerErrorHandling:
    """异常处理路径测试。"""

    async def test_value_error_replies_no_member_hint(self) -> None:
        """ValueError（无可用成员）时 ctx.reply 回复「暂无」或「同步」提示，不抛出异常。"""
        from src.handlers.jrlp import JrlpHandler

        ctx = _make_group_ctx(raise_value_error=True)
        handler = JrlpHandler()

        with patch("src.handlers.jrlp.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2024, 1, 1)
            # 不应抛出 ValueError
            result = await handler.draw_wife(ctx)

        assert result is True
        ctx.reply.assert_awaited_once()
        call_text = str(ctx.reply.call_args[0][0])
        assert "暂无" in call_text or "同步" in call_text

    async def test_value_error_does_not_propagate(self) -> None:
        """ValueError 不会向外层传播，handler 正常返回 True。"""
        from src.handlers.jrlp import JrlpHandler

        ctx = _make_group_ctx(raise_value_error=True)
        handler = JrlpHandler()

        with patch("src.handlers.jrlp.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2024, 1, 1)
            # 不应抛出任何异常
            result = await handler.draw_wife(ctx)

        assert result is True

    async def test_generic_exception_replies_and_returns_true(self) -> None:
        """其他未预期异常时 ctx.reply 回复错误提示，返回 True 不传播异常。"""
        from src.handlers.jrlp import JrlpHandler

        ctx = _make_group_ctx(raise_exception=True)
        handler = JrlpHandler()

        with patch("src.handlers.jrlp.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2024, 1, 1)
            result = await handler.draw_wife(ctx)

        assert result is True
        ctx.reply.assert_awaited_once()
