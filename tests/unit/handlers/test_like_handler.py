"""LikeHandler 单元测试 —— 覆盖所有子命令分支与边界情况。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from src.services.like import DEFAULT_LIKE_TIMES, LikeStatus, RegisterResult
from tests.conftest import make_context, make_group_message_event

# ── 辅助工厂 ─────────────────────────────────────────────────────────────────


def _make_like_service(
    *,
    send_like_now_return: bool = True,
    register_already_exists: bool = False,
    cancel_task_return: bool = True,
    has_task: bool = False,
    total_times: int = 0,
) -> MagicMock:
    """构造 LikeService 的 Mock，方法均为 AsyncMock。"""
    svc = MagicMock()
    svc.send_like_now = AsyncMock(return_value=send_like_now_return)
    svc.register_task = AsyncMock(
        return_value=RegisterResult(already_exists=register_already_exists)
    )
    svc.cancel_task = AsyncMock(return_value=cancel_task_return)
    svc.get_status = AsyncMock(
        return_value=LikeStatus(
            has_task=has_task,
            total_times=total_times,
            last_triggered_at=None,
        )
    )
    return svc


def _make_ctx(text: str = "", *, with_service: bool = True, **svc_kwargs: object):
    """构造包含 LikeService 的 Context。"""
    from src.services.like import LikeService

    event = make_group_message_event(user_id=10001, group_id=100, text=text)
    services = {}
    if with_service:
        svc = _make_like_service(**svc_kwargs)  # type: ignore[arg-type]
        services[LikeService] = svc
    ctx = make_context(event, services=services)
    return ctx


# ── 测试类 ────────────────────────────────────────────────────────────────────


class TestLikeHandlerSend:
    """_handle_send 路径：无参数和数字参数。"""

    async def test_no_args_calls_send_like_now_with_default_times(self) -> None:
        """/like 无参数时走 _handle_send，使用默认次数。"""
        from src.handlers.like import LikeHandler
        from src.services.like import LikeService

        ctx = _make_ctx("")
        svc: MagicMock = ctx._services[LikeService]  # type: ignore[attr-defined]

        await LikeHandler().handle(ctx)

        svc.send_like_now.assert_awaited_once()
        call_args = svc.send_like_now.call_args
        assert call_args.args[1] == DEFAULT_LIKE_TIMES

    async def test_no_args_replies_on_success(self) -> None:
        """/like 成功时回复包含次数的文字。"""
        from src.handlers.like import LikeHandler

        ctx = _make_ctx("", send_like_now_return=True)
        await LikeHandler().handle(ctx)

        ctx.reply.assert_awaited_once()
        reply_text: str = ctx.reply.call_args.args[0]
        assert str(DEFAULT_LIKE_TIMES) in reply_text

    async def test_digit_arg_calls_send_like_now_with_given_times(self) -> None:
        """/like 10 时 send_like_now 被调用，times=10。"""
        from src.handlers.like import LikeHandler
        from src.services.like import LikeService

        ctx = _make_ctx("10")
        # get_args() 依赖 raw_message 的空格拆分；此处手动 mock get_args
        ctx.get_args = MagicMock(return_value=["10"])  # type: ignore[method-assign]
        svc: MagicMock = ctx._services[LikeService]  # type: ignore[attr-defined]

        await LikeHandler().handle(ctx)

        svc.send_like_now.assert_awaited_once()
        call_args = svc.send_like_now.call_args
        assert call_args.args[1] == 10

    async def test_send_failure_replies_error_message(self) -> None:
        """/like 点赞 API 返回 False 时回复失败提示。"""
        from src.handlers.like import LikeHandler

        ctx = _make_ctx("", send_like_now_return=False)
        await LikeHandler().handle(ctx)

        ctx.reply.assert_awaited_once()
        reply_text: str = ctx.reply.call_args.args[0]
        assert "失败" in reply_text

    async def test_out_of_range_above_max_no_send(self) -> None:
        """/like 100 超出上限，提示错误，不调用 send_like_now。"""
        from src.handlers.like import LikeHandler
        from src.services.like import LikeService

        ctx = _make_ctx("100")
        ctx.get_args = MagicMock(return_value=["100"])  # type: ignore[method-assign]
        svc: MagicMock = ctx._services[LikeService]  # type: ignore[attr-defined]

        await LikeHandler().handle(ctx)

        svc.send_like_now.assert_not_awaited()
        ctx.reply.assert_awaited_once()
        reply_text: str = ctx.reply.call_args.args[0]
        assert "范围" in reply_text or "1~20" in reply_text or "1" in reply_text

    async def test_out_of_range_zero_no_send(self) -> None:
        """/like 0 超出下限，提示错误，不调用 send_like_now。"""
        from src.handlers.like import LikeHandler
        from src.services.like import LikeService

        ctx = _make_ctx("0")
        ctx.get_args = MagicMock(return_value=["0"])  # type: ignore[method-assign]
        svc: MagicMock = ctx._services[LikeService]  # type: ignore[attr-defined]

        await LikeHandler().handle(ctx)

        svc.send_like_now.assert_not_awaited()
        ctx.reply.assert_awaited_once()


class TestLikeHandlerSchedule:
    """_handle_schedule 路径：schedule / 定时 子命令。"""

    async def test_schedule_calls_register_task(self) -> None:
        """/like schedule 调用 register_task。"""
        from src.handlers.like import LikeHandler
        from src.services.like import LikeService

        ctx = _make_ctx("schedule")
        ctx.get_args = MagicMock(return_value=["schedule"])  # type: ignore[method-assign]
        svc: MagicMock = ctx._services[LikeService]  # type: ignore[attr-defined]

        await LikeHandler().handle(ctx)

        svc.register_task.assert_awaited_once()

    async def test_schedule_success_replies_registered_message(self) -> None:
        """/like schedule 首次注册时回复成功提示。"""
        from src.handlers.like import LikeHandler

        ctx = _make_ctx("schedule", register_already_exists=False)
        ctx.get_args = MagicMock(return_value=["schedule"])  # type: ignore[method-assign]

        await LikeHandler().handle(ctx)

        ctx.reply.assert_awaited_once()
        reply_text: str = ctx.reply.call_args.args[0]
        assert "已注册" in reply_text or "注册" in reply_text

    async def test_schedule_already_exists_replies_duplicate_message(self) -> None:
        """/like schedule 已存在时回复"已经"类提示，不重复注册。"""
        from src.handlers.like import LikeHandler

        ctx = _make_ctx("schedule", register_already_exists=True)
        ctx.get_args = MagicMock(return_value=["schedule"])  # type: ignore[method-assign]

        await LikeHandler().handle(ctx)

        ctx.reply.assert_awaited_once()
        reply_text: str = ctx.reply.call_args.args[0]
        assert "已经" in reply_text

    async def test_schedule_alias_chinese_works(self) -> None:
        """/like 定时 是 schedule 的别名，同样调用 register_task。"""
        from src.handlers.like import LikeHandler
        from src.services.like import LikeService

        ctx = _make_ctx("定时")
        ctx.get_args = MagicMock(return_value=["定时"])  # type: ignore[method-assign]
        svc: MagicMock = ctx._services[LikeService]  # type: ignore[attr-defined]

        await LikeHandler().handle(ctx)

        svc.register_task.assert_awaited_once()


class TestLikeHandlerCancel:
    """_handle_cancel 路径：cancel / 取消 子命令。"""

    async def test_cancel_calls_cancel_task(self) -> None:
        """/like cancel 调用 cancel_task。"""
        from src.handlers.like import LikeHandler
        from src.services.like import LikeService

        ctx = _make_ctx("cancel")
        ctx.get_args = MagicMock(return_value=["cancel"])  # type: ignore[method-assign]
        svc: MagicMock = ctx._services[LikeService]  # type: ignore[attr-defined]

        await LikeHandler().handle(ctx)

        svc.cancel_task.assert_awaited_once()

    async def test_cancel_success_replies_cancelled_message(self) -> None:
        """/like cancel 成功时回复取消确认。"""
        from src.handlers.like import LikeHandler

        ctx = _make_ctx("cancel", cancel_task_return=True)
        ctx.get_args = MagicMock(return_value=["cancel"])  # type: ignore[method-assign]

        await LikeHandler().handle(ctx)

        ctx.reply.assert_awaited_once()
        reply_text: str = ctx.reply.call_args.args[0]
        assert "取消" in reply_text

    async def test_cancel_not_found_replies_not_registered_message(self) -> None:
        """/like cancel 任务不存在时回复"没有注册"类提示。"""
        from src.handlers.like import LikeHandler

        ctx = _make_ctx("cancel", cancel_task_return=False)
        ctx.get_args = MagicMock(return_value=["cancel"])  # type: ignore[method-assign]

        await LikeHandler().handle(ctx)

        ctx.reply.assert_awaited_once()
        reply_text: str = ctx.reply.call_args.args[0]
        # 实际回复文本：「你还没有注册定时点赞哦」
        assert "没有" in reply_text or "未" in reply_text

    async def test_cancel_alias_chinese_works(self) -> None:
        """/like 取消 是 cancel 的别名。"""
        from src.handlers.like import LikeHandler
        from src.services.like import LikeService

        ctx = _make_ctx("取消")
        ctx.get_args = MagicMock(return_value=["取消"])  # type: ignore[method-assign]
        svc: MagicMock = ctx._services[LikeService]  # type: ignore[attr-defined]

        await LikeHandler().handle(ctx)

        svc.cancel_task.assert_awaited_once()


class TestLikeHandlerStatus:
    """_handle_status 路径：status / 状态 子命令。"""

    async def test_status_calls_get_status(self) -> None:
        """/like status 调用 get_status。"""
        from src.handlers.like import LikeHandler
        from src.services.like import LikeService

        ctx = _make_ctx("status")
        ctx.get_args = MagicMock(return_value=["status"])  # type: ignore[method-assign]
        svc: MagicMock = ctx._services[LikeService]  # type: ignore[attr-defined]

        await LikeHandler().handle(ctx)

        svc.get_status.assert_awaited_once()

    async def test_status_with_task_replies_enabled_info(self) -> None:
        """/like status has_task=True 时回复包含"已开启"。"""
        from src.handlers.like import LikeHandler

        ctx = _make_ctx("status", has_task=True, total_times=50)
        ctx.get_args = MagicMock(return_value=["status"])  # type: ignore[method-assign]

        await LikeHandler().handle(ctx)

        ctx.reply.assert_awaited_once()
        reply_text: str = ctx.reply.call_args.args[0]
        assert "已开启" in reply_text or "✅" in reply_text

    async def test_status_without_task_replies_disabled_info(self) -> None:
        """/like status has_task=False 时回复包含"未开启"。"""
        from src.handlers.like import LikeHandler

        ctx = _make_ctx("status", has_task=False, total_times=0)
        ctx.get_args = MagicMock(return_value=["status"])  # type: ignore[method-assign]

        await LikeHandler().handle(ctx)

        ctx.reply.assert_awaited_once()
        reply_text: str = ctx.reply.call_args.args[0]
        assert "未开启" in reply_text or "❌" in reply_text

    async def test_status_alias_chinese_works(self) -> None:
        """/like 状态 是 status 的别名。"""
        from src.handlers.like import LikeHandler
        from src.services.like import LikeService

        ctx = _make_ctx("状态")
        ctx.get_args = MagicMock(return_value=["状态"])  # type: ignore[method-assign]
        svc: MagicMock = ctx._services[LikeService]  # type: ignore[attr-defined]

        await LikeHandler().handle(ctx)

        svc.get_status.assert_awaited_once()


class TestLikeHandlerUnknown:
    """未知子命令 → 显示用法。"""

    async def test_unknown_subcommand_replies_usage(self) -> None:
        """/like foo 显示用法，不调用任何 service 方法。"""
        from src.handlers.like import LikeHandler
        from src.services.like import LikeService

        ctx = _make_ctx("foo")
        ctx.get_args = MagicMock(return_value=["foo"])  # type: ignore[method-assign]
        svc: MagicMock = ctx._services[LikeService]  # type: ignore[attr-defined]

        await LikeHandler().handle(ctx)

        svc.send_like_now.assert_not_awaited()
        svc.register_task.assert_not_awaited()
        svc.cancel_task.assert_not_awaited()
        svc.get_status.assert_not_awaited()
        ctx.reply.assert_awaited_once()

    async def test_unknown_subcommand_reply_contains_usage_info(self) -> None:
        """未知子命令回复内容包含用法示例。"""
        from src.handlers.like import LikeHandler

        ctx = _make_ctx("bar")
        ctx.get_args = MagicMock(return_value=["bar"])  # type: ignore[method-assign]

        await LikeHandler().handle(ctx)

        reply_text: str = ctx.reply.call_args.args[0]
        assert "like" in reply_text.lower() or "用法" in reply_text


class TestLikeHandlerNoService:
    """缺少 LikeService 时 handler 应静默返回，不报错。"""

    async def test_no_service_returns_silently(self) -> None:
        """未注入 LikeService 时，handler 直接 return，不抛异常，不回复。"""
        from src.handlers.like import LikeHandler

        ctx = _make_ctx(with_service=False)

        # 不应抛出任何异常
        await LikeHandler().handle(ctx)

        ctx.reply.assert_not_awaited()
