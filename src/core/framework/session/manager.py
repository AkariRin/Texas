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
from src.core.framework.session.commands import CANCEL_COMMANDS
from src.core.framework.session.context import SessionContext  # noqa: TC001
from src.core.framework.session.decorators import SESSION_META
from src.core.framework.session.enums import TimeoutMode
from src.core.framework.session.state_machine import StateMachine  # noqa: TC001
from src.core.framework.session.timeout import TimeoutConfig
from src.core.protocol.segment import build_mention_message

if TYPE_CHECKING:
    from src.core.cache.client import CacheClient
    from src.core.framework.context import Context

logger = structlog.get_logger()


class SessionManager:
    """全局会话管理器 —— 管理所有交互式会话的生命周期。

    Notes:
        Redis 持久化仅用于设置 TTL 和跨实例互斥感知，**不支持进程重启后的会话恢复**。
        进程重启时内存中的活跃会话会丢失，Redis 残留记录会在下次同 key 启动时被清除。
    """

    def __init__(self, cache: CacheClient) -> None:
        self._cache = cache
        self._session_classes: dict[str, type[InteractiveSession[Any]]] = {}
        self._active_sessions: dict[str, InteractiveSession[Any]] = {}  # session_key → 实例
        self._timeout_tasks: dict[str, asyncio.Task[None]] = {}  # session_key → 超时任务
        self._warning_tasks: dict[str, asyncio.Task[None]] = {}  # session_key → 提醒任务
        # per-key 锁：防止同一用户的并发消息绕过互斥检查（同时保护 start 和 dispatch）
        self._session_locks: dict[str, asyncio.Lock] = {}

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
        session_key = self._build_session_key(ctx.user_id, ctx.group_id)

        # per-key 锁：防止同一用户的并发消息在 await 间隙绕过互斥检查
        lock = self._session_locks.setdefault(session_key, asyncio.Lock())
        async with lock:
            return await self._start_session_locked(
                session_cls, session_meta, session_key, ctx, initial_data
            )

    async def _start_session_locked(
        self,
        session_cls: type[InteractiveSession[Any]],
        session_meta: dict[str, Any],
        session_key: str,
        ctx: Context,
        initial_data: dict[str, Any] | None,
    ) -> bool:
        """在持有 per-key 锁的情况下执行会话启动逻辑。"""
        # 互斥：内存检查（此时已持有锁，检查与写入之间不会有其他协程介入）
        existing = self._active_sessions.get(session_key)
        if existing is not None:
            cancel_hint = next(iter(CANCEL_COMMANDS))
            await ctx.reply(
                build_mention_message(
                    f"您有一个进行中的操作，请先完成或发送 {cancel_hint}",
                    ctx.user_id,
                    ctx.is_group,
                )
            )
            return False

        # 互斥：Redis 残留清理（防止进程重启后内存丢失但 Redis 中仍有记录）
        if await self._cache.exists(cache_keys.session_key(session_key)):
            await asyncio.gather(
                self._cache.delete(cache_keys.session_key(session_key)),
                self._cache.delete(cache_keys.session_data_key(session_key)),
                return_exceptions=True,
            )

        session_ctx: SessionContext | None = None
        session: InteractiveSession[Any] | None = None
        try:
            session = session_cls()
            session.manager = self
            session._session_key = session_key
            session._creator_user_id = ctx.user_id

            data_cls = session_cls._resolve_data_cls()
            session.data = data_cls(**(initial_data or {}))

            states = await session.build_states()
            if states is not None:
                if not states:
                    raise ValueError(
                        f"{session_cls.__name__}.build_states() 返回了空列表，无法确定初始状态"
                    )
                session.state_machine = StateMachine(states, initial_state=states[0].name)
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
            # 清理内存、Redis 及 per-key 锁（无论会话是否已写入 _active_sessions）
            await self._cleanup_session(session_key)
            if session_ctx is not None and session is not None:
                with contextlib.suppress(Exception):
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
        # 复用 per-key 锁，防止同一用户的并发消息同时进入状态机造成状态不一致
        lock = self._session_locks.get(session_key)
        if lock is None:
            # 无锁说明该 key 从未启动过会话，直接返回
            return False

        async with lock:
            return await self._dispatch_input_locked(session_key, ctx)

    async def _dispatch_input_locked(self, session_key: str, ctx: Context) -> bool:
        """在持有 per-key 锁的情况下执行消息分发逻辑。"""
        session = self._active_sessions.get(session_key)
        if session is None:
            return False

        user_input = ctx.get_plaintext().strip()
        if session.state_machine is None:
            raise RuntimeError(
                f"会话 {session_key} 的状态机未初始化（请通过 start_session() 启动）"
            )
        current_state = session.state_machine.current_state or ""
        session_ctx = SessionContext(ctx, session, current_state, user_input)

        try:
            new_state = await session.state_machine.process_input(session_ctx)

            # 刷新超时
            session_meta = getattr(type(session), SESSION_META, {})
            timeout_config = _resolve_timeout(session_meta.get("timeout", TimeoutConfig()))
            if timeout_config.mode != TimeoutMode.never:
                self._refresh_timeout(session_key, session, timeout_config, ctx)

            # 检查是否到达终止状态：已完成的会话直接清理，无需再持久化
            if session.state_machine.is_finished:
                await session.on_finish(session_ctx)
                await self._cleanup_session(session_key)
                logger.info(
                    "会话已完成",
                    session_key=session_key,
                    final_state=new_state,
                    event_type="session.finished",
                )
            else:
                # 会话仍在进行中，持久化最新状态
                await self._persist_session(session_key, session, session_meta)

        except Exception as exc:
            logger.error(
                "会话处理异常",
                session_key=session_key,
                state=current_state,
                error=str(exc),
                event_type="session.dispatch_error",
                exc_info=True,
            )
            # 先清理会话，确保无论后续钩子是否抛出，内存和 Redis 都能被释放
            await self._cleanup_session(session_key)
            with contextlib.suppress(Exception):
                await session.on_error(session_ctx, exc)
            with contextlib.suppress(Exception):
                await ctx.reply(
                    build_mention_message(
                        "操作过程中发生错误，会话已结束。", session._creator_user_id, ctx.is_group
                    )
                )

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
            if session.state_machine is None:
                raise RuntimeError(
                    f"会话 {session_key} 的状态机未初始化（请通过 start_session() 启动）"
                )
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

    def get_active_session_count(self) -> int:
        """返回当前内存中活跃会话的数量（可用于监控和运维巡检）。"""
        return len(self._active_sessions)

    async def cancel_all_sessions(self) -> int:
        """取消所有活跃会话（维护模式 / 优雅关闭前使用）。

        Notes:
            批量取消**不会**触发各会话的 ``on_cancel`` 钩子（因为没有对应的用户上下文）。
            如需在关闭前执行清理逻辑，请在 ``on_timeout`` 或业务层自行处理。

        Returns:
            被取消的会话数量。
        """
        keys = list(self._active_sessions)
        if keys:
            await asyncio.gather(*(self.cancel_session(k) for k in keys))
            logger.info(
                "批量取消所有活跃会话",
                count=len(keys),
                event_type="session.cancel_all",
            )
        return len(keys)

    def get_active_session_key(self, user_id: int, group_id: int | None = None) -> str | None:
        """查询用户在当前来源是否有活跃会话。

        按 user+source 粒度查找：同一用户在不同群的会话互不干扰。

        Returns:
            活跃会话的 key，无则返回 None。
        """
        key = self._build_session_key(user_id, group_id)
        return key if key in self._active_sessions else None

    @staticmethod
    def is_cancel_command(text: str) -> bool:
        """检查文本是否为全局取消命令。

        Args:
            text: 用户输入文本。
        """
        return text.strip() in CANCEL_COMMANDS

    # ── 内部方法 ──

    @staticmethod
    def _build_session_key(user_id: int, group_id: int | None) -> str:
        """构建会话键。

        统一采用 user+source 粒度：同一用户在不同来源（群/私聊）的会话互不干扰，
        同一用户在同一来源下只能有一个活跃会话。

        Args:
            user_id: 会话创建者 QQ 号。
            group_id: 群号（私聊为 None）。

        Returns:
            会话键，格式为 ``user:{user_id}:source:{group_id|private}``。
        """
        source_id = str(group_id) if group_id is not None else "private"
        return f"user:{user_id}:source:{source_id}"

    def _bind_state_handlers(self, session: InteractiveSession[Any]) -> None:
        """将状态机中的未绑定函数绑定到会话实例。"""
        if session.state_machine is None:
            raise RuntimeError(
                f"会话 {session._session_key!r} 的状态机未初始化（请通过 start_session() 启动）"
            )
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
        # CacheClient.set 约定：ttl=None 时使用客户端默认 TTL；ttl=0（falsy）时不设过期。
        # TimeoutMode.never 的会话不应受客户端默认 TTL 影响，故显式传 0 表示"永不过期"。
        redis_ttl: int = (
            0  # 永不过期
            if timeout_config.mode == TimeoutMode.never
            else timeout_config.duration + 60  # 比超时时间多 60s 的安全余量
        )

        if session.state_machine is None:
            raise RuntimeError(
                f"会话 {session_key!r} 的状态机未初始化（请通过 start_session() 启动）"
            )
        meta_data = {
            "session_type": type(session).__name__,
            "current_state": session.state_machine.current_state,
        }
        data_json = session.data.model_dump(mode="json")

        results = await asyncio.gather(
            self._cache.set(cache_keys.session_key(session_key), meta_data, ttl=redis_ttl),
            self._cache.set(cache_keys.session_data_key(session_key), data_json, ttl=redis_ttl),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                logger.warning(
                    "会话持久化 Redis 写入失败",
                    session_key=session_key,
                    error=str(result),
                    event_type="session.persist_error",
                )

    async def _cleanup_session(self, session_key: str) -> None:
        """清理会话（内存 + Redis + 定时任务 + 互斥锁）。"""
        self._active_sessions.pop(session_key, None)
        self._session_locks.pop(session_key, None)

        timeout_task = self._timeout_tasks.pop(session_key, None)
        if timeout_task is not None and not timeout_task.done():
            timeout_task.cancel()

        warning_task = self._warning_tasks.pop(session_key, None)
        if warning_task is not None and not warning_task.done():
            warning_task.cancel()

        results = await asyncio.gather(
            self._cache.delete(cache_keys.session_key(session_key)),
            self._cache.delete(cache_keys.session_data_key(session_key)),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                logger.warning(
                    "会话清理 Redis 删除失败",
                    session_key=session_key,
                    error=str(result),
                    event_type="session.cleanup_error",
                )

    def _setup_timeout(
        self,
        session_key: str,
        session: InteractiveSession[Any],
        config: TimeoutConfig,
        ctx: Context,
    ) -> None:
        """设置超时定时器。"""
        if config.mode == TimeoutMode.never:
            return

        async def _timeout_callback() -> None:
            try:
                await asyncio.sleep(config.duration)
                # 会话仍在活跃
                if session_key in self._active_sessions:
                    active_session = self._active_sessions[session_key]
                    if config.mode == TimeoutMode.notify:
                        with contextlib.suppress(Exception):
                            await ctx.reply(
                                build_mention_message(
                                    config.timeout_message,
                                    active_session._creator_user_id,
                                    ctx.is_group,
                                )
                            )
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
                        active_session = self._active_sessions[session_key]
                        msg_text = config.warning_message.format(remaining=config.warning_before)
                        with contextlib.suppress(Exception):
                            await ctx.reply(
                                build_mention_message(
                                    msg_text,
                                    active_session._creator_user_id,
                                    ctx.is_group,
                                )
                            )
            except asyncio.CancelledError:
                pass
            finally:
                self._warning_tasks.pop(session_key, None)

        self._timeout_tasks[session_key] = asyncio.create_task(_timeout_callback())
        if config.mode == TimeoutMode.notify and config.warning_before > 0:
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
