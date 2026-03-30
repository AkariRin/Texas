"""SessionManager —— 全局会话管理器。

负责会话生命周期管理、消息路由、互斥检查和超时管理。
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any

import structlog

from src.core.cache import keys as cache_keys
from src.core.framework.session.base import InteractiveSession  # noqa: TC001
from src.core.framework.session.context import SessionContext  # noqa: TC001
from src.core.framework.session.decorators import SESSION_META
from src.core.framework.session.enums import SessionScope, TimeoutMode
from src.core.framework.session.state_machine import StateMachine  # noqa: TC001
from src.core.framework.session.timeout import TimeoutConfig

if TYPE_CHECKING:
    from src.core.cache.client import CacheClient
    from src.core.framework.context import Context

logger = structlog.get_logger()


class SessionManager:
    """全局会话管理器 —— 管理所有交互式会话的生命周期。"""

    def __init__(self, cache: CacheClient) -> None:
        self._cache = cache
        self._session_classes: dict[str, type[InteractiveSession[Any]]] = {}
        self._active_sessions: dict[str, InteractiveSession[Any]] = {}  # session_key → 实例
        self._timeout_tasks: dict[str, asyncio.Task[None]] = {}  # session_key → 超时任务
        self._warning_tasks: dict[str, asyncio.Task[None]] = {}  # session_key → 提醒任务

    # ── 会话类注册 ──

    def register_session_class(self, name: str, session_cls: type[InteractiveSession[Any]]) -> None:
        """注册会话类到管理器。"""
        self._session_classes[name] = session_cls
        logger.debug(
            "会话类已注册",
            session_type=name,
            event_type="session.class_registered",
        )

    # ── 会话生命周期 ──

    async def start_session(
        self,
        session_cls: type[InteractiveSession[Any]],
        ctx: Context,
        initial_data: dict[str, Any] | None = None,
    ) -> bool:
        """启动交互式会话。

        Args:
            session_cls: 会话类。
            ctx: 触发会话的事件上下文。
            initial_data: 初始化数据（传递给 Pydantic 模型构造函数）。

        Returns:
            是否成功启动。
        """
        session_meta: dict[str, Any] = getattr(session_cls, SESSION_META, {})
        scope = session_meta.get("scope", SessionScope.USER)
        session_key = self._build_session_key(ctx.user_id, ctx.group_id, scope)

        # 互斥：内存检查
        existing = self._active_sessions.get(session_key)
        if existing is not None:
            await ctx.reply("您有一个进行中的操作，请先完成或发送 /取消")
            return False

        # 互斥：Redis 残留清理（防止进程重启后内存丢失但 Redis 中仍有记录）
        if await self._cache.exists(cache_keys.session_key(session_key)):
            await asyncio.gather(
                self._cache.delete(cache_keys.session_key(session_key)),
                self._cache.delete(cache_keys.session_data_key(session_key)),
                self._cache.delete(cache_keys.session_fsm_key(session_key)),
            )

        session = session_cls()
        session.manager = self
        session._session_key = session_key

        data_cls = session_cls._resolve_data_cls()
        session.data = data_cls(**(initial_data or {}))

        states = await session.build_states()
        if states is not None:
            initial_state = states[0].name if states else None
            session.state_machine = StateMachine(states, initial_state=initial_state)
        else:
            state_list, initial_state = session_cls._build_states_from_decorators()
            session.state_machine = StateMachine(state_list, initial_state=initial_state)

        # 装饰器收集的是未绑定函数，需要绑定到 session 实例
        self._bind_state_handlers(session)

        self._active_sessions[session_key] = session
        await self._persist_session(session_key, session, session_meta)

        timeout_config = _resolve_timeout(session_meta.get("timeout", TimeoutConfig()))
        self._setup_timeout(session_key, session, timeout_config, ctx)

        initial_state_name = session.state_machine.initial_state or ""
        session_ctx = SessionContext(ctx, session, initial_state_name, None)

        try:
            await session.on_start(session_ctx)
            await session.state_machine.start(session_ctx)
        except Exception as exc:
            logger.error(
                "会话启动失败",
                session_key=session_key,
                error=str(exc),
                event_type="session.start_error",
                exc_info=True,
            )
            await self._cleanup_session(session_key)
            await session.on_error(session_ctx, exc)
            return False

        logger.info(
            "会话已启动",
            session_key=session_key,
            session_type=session_cls.__name__,
            initial_state=initial_state_name,
            event_type="session.started",
        )
        return True

    async def dispatch_input(
        self,
        session_key: str,
        ctx: Context,
    ) -> bool:
        """将用户消息路由到活跃会话。

        Args:
            session_key: 会话键。
            ctx: 事件上下文。

        Returns:
            是否成功处理。
        """
        session = self._active_sessions.get(session_key)
        if session is None:
            return False

        user_input = ctx.get_plaintext().strip()
        current_state = session.state_machine.current_state or ""
        session_ctx = SessionContext(ctx, session, current_state, user_input)

        try:
            new_state = await session.state_machine.process_input(session_ctx)

            # 刷新超时
            session_meta = getattr(type(session), SESSION_META, {})
            timeout_config = _resolve_timeout(session_meta.get("timeout", TimeoutConfig()))
            if timeout_config.mode != TimeoutMode.NEVER:
                self._refresh_timeout(session_key, session, timeout_config, ctx)

            # 持久化更新后的状态
            await self._persist_session(session_key, session, session_meta)

            # 检查是否到达终止状态
            if session.state_machine.is_finished:
                await session.on_finish(session_ctx)
                await self._cleanup_session(session_key)
                logger.info(
                    "会话已完成",
                    session_key=session_key,
                    final_state=new_state,
                    event_type="session.finished",
                )

        except Exception as exc:
            logger.error(
                "会话处理异常",
                session_key=session_key,
                state=current_state,
                error=str(exc),
                event_type="session.dispatch_error",
                exc_info=True,
            )
            await session.on_error(session_ctx, exc)
            await self._cleanup_session(session_key)
            await ctx.reply("操作过程中发生错误，会话已结束。")

        return True

    async def cancel_session(
        self,
        session_key: str,
        ctx: Context | None = None,
    ) -> bool:
        """取消指定会话。

        Args:
            session_key: 会话键。
            ctx: 可选的事件上下文。

        Returns:
            是否成功取消。
        """
        session = self._active_sessions.get(session_key)
        if session is None:
            return False

        if ctx is not None:
            current_state = session.state_machine.current_state or ""
            session_ctx = SessionContext(ctx, session, current_state, None)
            try:
                await session.on_cancel(session_ctx)
            except Exception as exc:
                logger.warning(
                    "会话取消钩子执行失败",
                    session_key=session_key,
                    error=str(exc),
                    event_type="session.cancel_hook_error",
                )

        await self._cleanup_session(session_key)
        logger.info(
            "会话已取消",
            session_key=session_key,
            event_type="session.cancelled",
        )
        return True

    # ── 查询方法 ──

    def get_active_session_key(self, user_id: int, group_id: int | None = None) -> str | None:
        """查询用户是否有活跃的会话。

        先检查用户级会话，再检查群级会话。

        Returns:
            活跃会话的 key，无则返回 None。
        """
        # 用户级会话
        user_key = self._build_session_key(user_id, None, SessionScope.USER)
        if user_key in self._active_sessions:
            return user_key

        # 群级会话
        if group_id is not None:
            group_key = self._build_session_key(user_id, group_id, SessionScope.GROUP)
            if group_key in self._active_sessions:
                return group_key

        return None

    def is_cancel_command(self, text: str, session_key: str) -> bool:
        """检查文本是否为取消命令。"""
        session = self._active_sessions.get(session_key)
        if session is None:
            return False

        session_meta = getattr(type(session), SESSION_META, {})
        cancel_commands = session_meta.get("cancel_commands", ("/取消", "/cancel"))
        return text.strip() in cancel_commands

    # ── 内部方法 ──

    @staticmethod
    def _build_session_key(user_id: int, group_id: int | None, scope: SessionScope) -> str:
        """构建会话键。"""
        if scope == SessionScope.GROUP and group_id is not None:
            return f"group:{group_id}"
        return f"user:{user_id}"

    def _bind_state_handlers(self, session: InteractiveSession[Any]) -> None:
        """将状态机中的未绑定函数绑定到会话实例。"""
        for s in session.state_machine.iter_states():
            if s.on_enter is not None:
                s.on_enter = _bind_method(s.on_enter, session)
            if s.on_exit is not None:
                s.on_exit = _bind_method(s.on_exit, session)
            if s.on_input is not None:
                s.on_input = _bind_method(s.on_input, session)

    async def _persist_session(
        self,
        session_key: str,
        session: InteractiveSession[Any],
        session_meta: dict[str, Any],
    ) -> None:
        """持久化会话状态到 Redis。"""
        timeout_config = _resolve_timeout(session_meta.get("timeout", TimeoutConfig()))
        ttl = None if timeout_config.mode == TimeoutMode.NEVER else timeout_config.duration + 60

        meta_data = {
            "session_type": type(session).__name__,
            "scope": session_meta.get("scope", SessionScope.USER),
            "current_state": session.state_machine.current_state,
        }
        data_json = session.data.model_dump(mode="json")
        fsm_data = session.state_machine.serialize()

        await asyncio.gather(
            self._cache.set(cache_keys.session_key(session_key), meta_data, ttl=ttl or 0),
            self._cache.set(cache_keys.session_data_key(session_key), data_json, ttl=ttl or 0),
            self._cache.set(cache_keys.session_fsm_key(session_key), fsm_data, ttl=ttl or 0),
        )

    async def _cleanup_session(self, session_key: str) -> None:
        """清理会话（内存 + Redis + 定时任务）。"""
        self._active_sessions.pop(session_key, None)

        timeout_task = self._timeout_tasks.pop(session_key, None)
        if timeout_task is not None and not timeout_task.done():
            timeout_task.cancel()

        warning_task = self._warning_tasks.pop(session_key, None)
        if warning_task is not None and not warning_task.done():
            warning_task.cancel()

        await asyncio.gather(
            self._cache.delete(cache_keys.session_key(session_key)),
            self._cache.delete(cache_keys.session_data_key(session_key)),
            self._cache.delete(cache_keys.session_fsm_key(session_key)),
        )

    def _setup_timeout(
        self,
        session_key: str,
        session: InteractiveSession[Any],
        config: TimeoutConfig,
        ctx: Context,
    ) -> None:
        """设置超时定时器。"""
        if config.mode == TimeoutMode.NEVER:
            return

        async def _timeout_callback() -> None:
            try:
                await asyncio.sleep(config.duration)
                # 会话仍在活跃
                if session_key in self._active_sessions:
                    active_session = self._active_sessions[session_key]
                    if config.mode == TimeoutMode.NOTIFY:
                        with contextlib.suppress(Exception):
                            await ctx.reply(config.timeout_message)
                    with contextlib.suppress(Exception):
                        await active_session.on_timeout(None)
                    await self._cleanup_session(session_key)
                    logger.info(
                        "会话已超时",
                        session_key=session_key,
                        event_type="session.timeout",
                    )
            except asyncio.CancelledError:
                pass

        async def _warning_callback() -> None:
            try:
                warning_time = config.duration - config.warning_before
                if warning_time > 0:
                    await asyncio.sleep(warning_time)
                    if session_key in self._active_sessions:
                        msg = config.warning_message.format(remaining=config.warning_before)
                        with contextlib.suppress(Exception):
                            await ctx.reply(msg)
            except asyncio.CancelledError:
                pass
            finally:
                self._warning_tasks.pop(session_key, None)

        self._timeout_tasks[session_key] = asyncio.create_task(_timeout_callback())
        if config.mode == TimeoutMode.NOTIFY and config.warning_before > 0:
            self._warning_tasks[session_key] = asyncio.create_task(_warning_callback())

    def _refresh_timeout(
        self,
        session_key: str,
        session: InteractiveSession[Any],
        config: TimeoutConfig,
        ctx: Context,
    ) -> None:
        """刷新超时（用户交互后重置倒计时）。"""
        old_timeout = self._timeout_tasks.pop(session_key, None)
        if old_timeout is not None and not old_timeout.done():
            old_timeout.cancel()

        old_warning = self._warning_tasks.pop(session_key, None)
        if old_warning is not None and not old_warning.done():
            old_warning.cancel()

        self._setup_timeout(session_key, session, config, ctx)

    async def close(self) -> None:
        """关闭管理器，清理所有活跃会话。"""
        for session_key in list(self._active_sessions):
            await self._cleanup_session(session_key)
        logger.info("SessionManager 已关闭", event_type="session.manager_closed")


def _bind_method(func: Any, instance: Any) -> Any:
    """将未绑定函数绑定到实例。

    如果 func 已经是绑定方法则直接返回。
    """
    if hasattr(func, "__self__"):
        return func
    return func.__get__(instance, type(instance))


def _resolve_timeout(raw: TimeoutConfig | int) -> TimeoutConfig:
    """将 int 或 TimeoutConfig 统一为 TimeoutConfig。"""
    if isinstance(raw, int):
        return TimeoutConfig(duration=raw)
    return raw
