"""生命周期编排器 —— 拓扑排序 + 按序启动/关闭业务模块。

与 ComponentScanner 配合：scanner.scan(["src.services", ...]) 会 import 所有 service 模块，
import 时 @startup / @shutdown 装饰器自动注册到注册表，随后由 LifecycleOrchestrator 统一执行。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from src.core.lifecycle.registry import ShutdownEntry, StartupEntry

logger = structlog.get_logger()


def _topo_sort(entries: list[StartupEntry], available: set[str]) -> list[StartupEntry]:
    """Kahn 算法拓扑排序。

    Args:
        entries: 待排序的启动入口列表。
        available: 初始已有的 key 集合（基础设施 provides）。

    Returns:
        按依赖顺序排列的入口列表。

    Raises:
        ValueError: 存在无法满足的依赖（循环依赖或缺失的 requires）。
    """
    remaining = list(entries)
    ordered: list[StartupEntry] = []
    resolved = set(available)

    while remaining:
        ready = [e for e in remaining if all(r in resolved for r in e.requires)]
        if not ready:
            unresolved = {e.name: [r for r in e.requires if r not in resolved] for e in remaining}
            raise ValueError(f"无法解析模块依赖，未满足的 requires: {unresolved}")
        for entry in ready:
            ordered.append(entry)
            resolved.update(entry.provides)
            remaining.remove(entry)

    return ordered


class LifecycleOrchestrator:
    """管理业务模块的启动与关闭。

    典型用法（在 lifespan() 中）::

        orchestrator = LifecycleOrchestrator()
        # scanner.scan(["src.services", ...]) 已触发 @startup 注册
        await orchestrator.startup(infra_services)
        orchestrator.populate_app_state(app.state)
        orchestrator.populate_dispatcher(dispatcher)
        # ...
        await orchestrator.shutdown()
    """

    def __init__(self) -> None:
        self._services: dict[str, Any] = {}
        self._startup_order: list[StartupEntry] = []

    @property
    def services(self) -> dict[str, Any]:
        """已启动的所有服务（含基础设施）。"""
        return self._services

    async def startup(
        self,
        infra_services: dict[str, Any],
        startup_entries: tuple[StartupEntry, ...],
    ) -> None:
        """按拓扑顺序启动所有已注册业务模块。

        Args:
            infra_services: 基础设施提供的初始服务 dict（由 lifespan 传入）。
            startup_entries: 由 ComponentScanner 快照的 @startup 入口元组。
        """
        self._services.update(infra_services)
        entries = list(startup_entries)

        if not entries:
            logger.debug("无业务模块注册，跳过生命周期启动", event_type="lifecycle.empty")
            return

        self._startup_order = _topo_sort(entries, set(infra_services.keys()))

        for entry in self._startup_order:
            deps = {k: self._services[k] for k in entry.requires}
            provided = await entry.factory(deps)
            self._services.update(provided)
            logger.info(
                "业务模块已启动",
                module=entry.name,
                provides=list(entry.provides),
                event_type="lifecycle.module_started",
            )

    async def shutdown(self, shutdown_entries: tuple[ShutdownEntry, ...]) -> None:
        """按启动逆序关闭所有模块（仅执行声明了 @shutdown 的模块）。

        Args:
            shutdown_entries: 由 ComponentScanner 快照的 @shutdown 入口元组。
        """
        shutdowns = {e.name: e for e in shutdown_entries}
        for entry in reversed(self._startup_order):
            hook_entry = shutdowns.get(entry.name)
            if hook_entry is None:
                continue
            try:
                svc_dict = {k: self._services[k] for k in entry.provides if k in self._services}
                await hook_entry.hook(svc_dict)
                logger.info(
                    "业务模块已关闭",
                    module=entry.name,
                    event_type="lifecycle.module_stopped",
                )
            except Exception:
                logger.exception(
                    "业务模块关闭失败",
                    module=entry.name,
                    event_type="lifecycle.stop_error",
                )

    def populate_app_state(self, app_state: Any, *, exclude: frozenset[str] = frozenset()) -> None:
        """将业务服务 setattr 到 app.state。

        Args:
            app_state: FastAPI app.state 对象。
            exclude: 跳过的 key 集合（通常为基础设施 key，已由 lifespan 单独赋值）。
        """
        for key, value in self._services.items():
            if key not in exclude:
                setattr(app_state, key, value)

    def populate_dispatcher(self, dispatcher: Any) -> None:
        """根据各模块 dispatcher_services 声明，注册服务到 EventDispatcher.services。

        使用 type(svc) 作为 key，与 ctx.get_service(SomeServiceClass) 消费端一致。
        """
        for entry in self._startup_order:
            for provides_key in entry.dispatcher_services:
                if provides_key in self._services:
                    svc = self._services[provides_key]
                    dispatcher.services[type(svc)] = svc
