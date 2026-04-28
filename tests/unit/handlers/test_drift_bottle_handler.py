"""DriftBottleHandler 单元测试 —— 覆盖扔/捞漂流瓶的主要路径。"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from tests.conftest import make_context, make_group_message_event, make_private_message_event

# ── 辅助工厂 ─────────────────────────────────────────────────────────────────


def _make_bottle_item(*, content: list[dict[str, Any]] | None = None) -> MagicMock:
    """构造 BottleItem Mock。"""
    bottle = MagicMock()
    bottle.content = content or [{"type": "text", "data": {"text": "测试内容"}}]
    return bottle


def _make_drift_svc(*, pool_id: int = 1, bottle=None) -> MagicMock:
    """构造 DriftBottleService Mock。"""
    svc = MagicMock()
    svc.get_pool_id = AsyncMock(return_value=pool_id)
    svc.throw_bottle = AsyncMock(return_value=None)
    svc.pick_bottle = AsyncMock(return_value=bottle)
    return svc


def _make_group_ctx(
    *,
    text: str = "扔漂流瓶测试内容",
    with_svc: bool = True,
    bottle=None,
    pool_id: int = 1,
):
    """构造群聊 Context，可选是否注入 DriftBottleService。"""
    from src.services.drift_bottle import DriftBottleService

    event = make_group_message_event(user_id=10001, group_id=100, text=text)
    services = {}
    if with_svc:
        services[DriftBottleService] = _make_drift_svc(pool_id=pool_id, bottle=bottle)
    return make_context(event, services)


def _make_private_ctx(*, text: str = "扔漂流瓶测试内容", with_svc: bool = True):
    """构造私聊 Context。"""
    from src.services.drift_bottle import DriftBottleService

    event = make_private_message_event(user_id=10001, text=text)
    services = {}
    if with_svc:
        services[DriftBottleService] = _make_drift_svc()
    return make_context(event, services)


# ── 扔漂流瓶测试 ──────────────────────────────────────────────────────────────


class TestHandleThrow:
    """扔漂流瓶路径测试。"""

    async def test_throw_with_content_calls_throw_bottle(self) -> None:
        """有内容时 throw_bottle 被调用，ctx.reply 被调用。"""
        from src.handlers.drift_bottle import DriftBottleHandler
        from src.services.drift_bottle import DriftBottleService

        ctx = _make_group_ctx(text="扔漂流瓶这是测试内容")
        handler = DriftBottleHandler()

        result = await handler.handle_throw(ctx)

        assert result is True
        svc: MagicMock = ctx.get_service(DriftBottleService)
        svc.throw_bottle.assert_awaited_once()
        ctx.reply.assert_awaited_once()

    async def test_throw_with_content_calls_get_pool_id(self) -> None:
        """扔瓶子时先调用 get_pool_id 获取当前群的 pool_id。"""
        from src.handlers.drift_bottle import DriftBottleHandler
        from src.services.drift_bottle import DriftBottleService

        ctx = _make_group_ctx(text="扔漂流瓶hello", pool_id=42)
        handler = DriftBottleHandler()

        await handler.handle_throw(ctx)

        svc: MagicMock = ctx.get_service(DriftBottleService)
        svc.get_pool_id.assert_awaited_once_with(100)

    async def test_throw_private_chat_returns_false(self) -> None:
        """私聊扔瓶子时返回 False，throw_bottle 不被调用。"""
        from src.handlers.drift_bottle import DriftBottleHandler
        from src.services.drift_bottle import DriftBottleService

        ctx = _make_private_ctx(text="扔漂流瓶测试")
        handler = DriftBottleHandler()

        result = await handler.handle_throw(ctx)

        assert result is False
        svc: MagicMock = ctx.get_service(DriftBottleService)
        svc.throw_bottle.assert_not_awaited()

    async def test_throw_empty_content_no_throw_bottle(self) -> None:
        """消息仅有触发词无内容时，throw_bottle 不被调用，ctx.reply 回复提示。"""
        from src.handlers.drift_bottle import DriftBottleHandler
        from src.services.drift_bottle import DriftBottleService

        # 仅有触发词"扔漂流瓶"，无实际内容
        ctx = _make_group_ctx(text="扔漂流瓶")
        handler = DriftBottleHandler()

        result = await handler.handle_throw(ctx)

        assert result is True
        svc: MagicMock = ctx.get_service(DriftBottleService)
        svc.throw_bottle.assert_not_awaited()
        ctx.reply.assert_awaited_once()
        # 回复提示内容应说明瓶中无内容
        call_text = str(ctx.reply.call_args[0][0])
        assert "没有" in call_text or "什么都" in call_text

    async def test_throw_missing_service_returns_false(self) -> None:
        """缺少 DriftBottleService 时返回 False，不调用 reply。"""
        from src.handlers.drift_bottle import DriftBottleHandler

        ctx = _make_group_ctx(with_svc=False)
        handler = DriftBottleHandler()

        result = await handler.handle_throw(ctx)

        assert result is False
        ctx.reply.assert_not_awaited()


# ── 捞漂流瓶测试 ──────────────────────────────────────────────────────────────


class TestHandlePick:
    """捞漂流瓶路径测试。"""

    async def test_pick_no_bottle_replies_empty_hint(self) -> None:
        """池中无瓶时 ctx.reply 回复提示且返回 True。"""
        from src.handlers.drift_bottle import DriftBottleHandler

        # bottle=None 表示池中无瓶
        ctx = _make_group_ctx(text="捞漂流瓶", bottle=None)
        handler = DriftBottleHandler()

        result = await handler.handle_pick(ctx)

        assert result is True
        ctx.reply.assert_awaited_once()
        call_text = str(ctx.reply.call_args[0][0])
        assert "没有" in call_text or "暂时" in call_text

    async def test_pick_with_bottle_replies(self) -> None:
        """捞到瓶子时 ctx.reply 被调用且返回 True。"""
        from src.handlers.drift_bottle import DriftBottleHandler

        bottle = _make_bottle_item()
        ctx = _make_group_ctx(text="捞漂流瓶", bottle=bottle)
        handler = DriftBottleHandler()

        result = await handler.handle_pick(ctx)

        assert result is True
        ctx.reply.assert_awaited_once()

    async def test_pick_calls_pick_bottle_with_pool_id(self) -> None:
        """捞瓶子时传入正确的 pool_id 和 user_id。"""
        from src.handlers.drift_bottle import DriftBottleHandler
        from src.services.drift_bottle import DriftBottleService

        bottle = _make_bottle_item()
        ctx = _make_group_ctx(text="捞漂流瓶", bottle=bottle, pool_id=7)
        handler = DriftBottleHandler()

        await handler.handle_pick(ctx)

        svc: MagicMock = ctx.get_service(DriftBottleService)
        svc.pick_bottle.assert_awaited_once_with(pool_id=7, user_id=10001)

    async def test_pick_private_chat_returns_false(self) -> None:
        """私聊捞瓶子时返回 False，pick_bottle 不被调用。"""
        from src.handlers.drift_bottle import DriftBottleHandler
        from src.services.drift_bottle import DriftBottleService

        ctx = _make_private_ctx(text="捞漂流瓶")
        handler = DriftBottleHandler()

        result = await handler.handle_pick(ctx)

        assert result is False
        svc: MagicMock = ctx.get_service(DriftBottleService)
        svc.pick_bottle.assert_not_awaited()

    async def test_pick_missing_service_returns_false(self) -> None:
        """缺少 DriftBottleService 时返回 False。"""
        from src.handlers.drift_bottle import DriftBottleHandler

        ctx = _make_group_ctx(text="捞漂流瓶", with_svc=False)
        handler = DriftBottleHandler()

        result = await handler.handle_pick(ctx)

        assert result is False
        ctx.reply.assert_not_awaited()
