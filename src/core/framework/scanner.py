"""ComponentScanner —— 发现 @controller 类并注册处理器方法。"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import TYPE_CHECKING, Any

import structlog

from src.core.framework.decorators import CONTROLLER_META, FEATURE_META, HANDLER_META
from src.core.framework.feature_registry import FeatureRegistry, build_registry
from src.core.framework.mapping import CompositeHandlerMapping, HandlerMethod
from src.core.framework.session.decorators import SESSION_META

if TYPE_CHECKING:
    from src.core.cache.key_registry import CacheKeyEntry
    from src.core.framework.session.manager import SessionManager
    from src.core.lifecycle.registry import ShutdownEntry, StartupEntry

logger = structlog.get_logger()


def _compute_trigger(meta: dict[str, Any]) -> str:
    """根据 handler 元数据计算用户可感知的触发方式描述。

    Args:
        meta: _handler_decorator 生成的元数据 dict。

    Returns:
        触发方式描述字符串，不适合展示时返回空字符串。
    """
    mapping_type = meta.get("mapping_type", "")

    if mapping_type == "command":
        cmd: str = meta.get("cmd") or ""
        aliases: set[str] = meta.get("aliases") or set()
        parts = [cmd, *sorted(aliases)]
        return " | ".join(p for p in parts if p)

    if mapping_type == "keyword":
        keywords: set[str] = meta.get("keywords") or set()
        return " | ".join(sorted(keywords))

    if mapping_type == "fullmatch":
        return meta.get("text") or ""

    if mapping_type == "startswith":
        prefix: str = meta.get("prefix") or ""
        return f"{prefix}..." if prefix else ""

    if mapping_type == "endswith":
        suffix: str = meta.get("suffix") or ""
        return f"...{suffix}" if suffix else ""

    # regex / event_type 等：不适合直接展示给用户，返回空字符串
    return ""


class ComponentScanner:
    """扫描包中的 @controller 装饰类并注册处理器。"""

    def __init__(self, mapping: CompositeHandlerMapping) -> None:
        self._mapping = mapping
        self._controllers: list[dict[str, Any]] = []
        self._standalone_features: list[dict[str, Any]] = []
        self._feature_registry: FeatureRegistry = FeatureRegistry({})
        self._session_classes: list[tuple[str, type]] = []  # (controller_name, session_cls)
        self._startup_entries: tuple[StartupEntry, ...] = ()
        self._shutdown_entries: tuple[ShutdownEntry, ...] = ()
        self._cache_key_entries: tuple[CacheKeyEntry, ...] = ()

    @property
    def controllers(self) -> list[dict[str, Any]]:
        """返回所有已发现控制器的元数据。"""
        return list(self._controllers)

    @property
    def standalone_features(self) -> list[dict[str, Any]]:
        """返回所有 @feature 装饰的独立功能列表（非 handler）。"""
        return list(self._standalone_features)

    @property
    def feature_registry(self) -> FeatureRegistry:
        """返回不可变功能注册表单例，scan() 完成后可用。"""
        return self._feature_registry

    @property
    def session_classes(self) -> list[tuple[str, type]]:
        """返回所有已发现的交互式会话类。"""
        return list(self._session_classes)

    @property
    def startup_entries(self) -> tuple[StartupEntry, ...]:
        """返回 scan() 完成后快照的所有 @startup 入口。"""
        return self._startup_entries

    @property
    def shutdown_entries(self) -> tuple[ShutdownEntry, ...]:
        """返回 scan() 完成后快照的所有 @shutdown 入口。"""
        return self._shutdown_entries

    @property
    def cache_key_entries(self) -> tuple[CacheKeyEntry, ...]:
        """返回 scan() 完成后快照的所有已注册缓存键定义。"""
        return self._cache_key_entries

    def register_sessions(self, session_manager: SessionManager) -> None:
        """将扫描到的会话类注册到 SessionManager。"""
        for controller_name, session_cls in self._session_classes:
            name = f"{controller_name}.{session_cls.__name__}"
            session_manager.register_session_class(name, session_cls)

        if self._session_classes:
            logger.info(
                "交互式会话注册完成",
                count=len(self._session_classes),
                event_type="scanner.sessions_registered",
            )

    def scan(self, packages: list[str]) -> None:
        """扫描给定的包路径以查找控制器，完成后构建内存元数据注册表并快照生命周期入口。"""
        from src.core.cache.key_registry import get_all_cache_keys
        from src.core.lifecycle.registry import get_all_shutdowns, get_all_startups

        for package_name in packages:
            self._scan_package(package_name)
        self._build_feature_metadata()
        # 快照生命周期入口（import 触发的 @startup/@shutdown 注册）
        self._startup_entries = tuple(get_all_startups())
        self._shutdown_entries = tuple(get_all_shutdowns())
        # 快照缓存键注册表（import 触发的 cache_key() 注册）
        self._cache_key_entries = get_all_cache_keys()

    def _build_feature_metadata(self) -> None:
        """从扫描结果构建不可变 FeatureRegistry，scan() 后调用。"""
        self._feature_registry = build_registry(self._controllers, self._standalone_features)

    def _scan_package(self, package_name: str) -> None:
        """导入包中所有模块并发现控制器。"""
        try:
            package = importlib.import_module(package_name)
        except ModuleNotFoundError:
            logger.warning(
                "扫描目标包未找到",
                package=package_name,
                event_type="scanner.package_not_found",
            )
            return

        # 如果是含有路径的正规包，则遍历子模块
        package_path = getattr(package, "__path__", None)
        if package_path:
            for _importer, module_name, _is_pkg in pkgutil.walk_packages(
                package_path, prefix=package_name + "."
            ):
                try:
                    importlib.import_module(module_name)
                except Exception as exc:
                    logger.warning(
                        "模块导入失败",
                        module=module_name,
                        error=str(exc),
                        event_type="scanner.import_error",
                    )

        # 扫描所有已导入的模块以查找控制器类
        self._discover_in_module(package)
        if package_path:
            for _importer, module_name, _is_pkg in pkgutil.walk_packages(
                package_path, prefix=package_name + "."
            ):
                try:
                    mod = importlib.import_module(module_name)
                except Exception:
                    continue  # 导入失败已在上方循环记录日志，此处跳过
                try:
                    self._discover_in_module(mod)
                except Exception as exc:
                    logger.warning(
                        "控制器发现失败",
                        module=module_name,
                        error=str(exc),
                        event_type="scanner.discover_error",
                    )

    def _discover_in_module(self, module: Any) -> None:
        """查找模块中所有被 @controller 或 @feature 装饰的类。"""
        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ != module.__name__:
                continue
            ctrl_meta = getattr(obj, CONTROLLER_META, None)
            if ctrl_meta is not None:
                self._register_controller(obj, ctrl_meta)
                continue
            feat_meta = getattr(obj, FEATURE_META, None)
            if feat_meta is not None:
                self._standalone_features.append(feat_meta)
                logger.info(
                    "独立功能注册成功",
                    feature=feat_meta["name"],
                    event_type="scanner.feature_registered",
                )

    def _register_controller(self, cls: type, ctrl_meta: dict[str, Any]) -> None:
        """实例化控制器并注册其处理器方法。"""
        instance = cls()
        controller_name = ctrl_meta.get("name", cls.__name__)
        default_priority = ctrl_meta.get("default_priority", 50)

        handler_count = 0
        methods_info: list[dict[str, Any]] = []

        for method_name in dir(instance):
            method = getattr(instance, method_name, None)
            if method is None or not callable(method):
                continue

            # 获取未绑定的函数以读取装饰器元数据
            func = getattr(cls, method_name, None)
            if func is None:
                continue

            handler_metas: list[dict[str, Any]] = getattr(func, HANDLER_META, [])
            if not handler_metas:
                continue

            for meta in handler_metas:
                priority = meta.get("priority")
                if priority is None:
                    priority = default_priority

                hm = HandlerMethod(
                    controller=instance,
                    method=method,
                    priority=priority,
                    permission=meta.get("permission", 0),
                    metadata={**meta, "system": ctrl_meta.get("system", False)},
                    controller_name=controller_name,
                    method_name=method_name,
                )
                self._mapping.register(hm)
                handler_count += 1
                methods_info.append(
                    {
                        "method": method_name,
                        "mapping_type": meta.get("mapping_type"),
                        "priority": priority,
                        # None 表示跟随 controller 的 default_enabled
                        "default_enabled": meta.get("default_enabled"),
                        # 元数据注解字段
                        "display_name": meta.get("display_name") or meta.get("cmd", method_name),
                        "description": meta.get("description", ""),
                        "admin": meta.get("admin"),
                        "message_scope": meta.get("message_scope", "all"),
                        "trigger": _compute_trigger(meta),
                    }
                )

        ctrl_info = {
            **ctrl_meta,
            "class": cls.__name__,
            "handler_count": handler_count,
            "methods": methods_info,
        }
        self._controllers.append(ctrl_info)

        # 扫描内部类中的 @interactive_session 标记
        for attr_name in dir(cls):
            inner_cls = getattr(cls, attr_name, None)
            if inner_cls is None or not inspect.isclass(inner_cls):
                continue
            session_meta = getattr(inner_cls, SESSION_META, None)
            if session_meta is not None:
                self._session_classes.append((controller_name, inner_cls))
                logger.info(
                    "交互式会话已发现",
                    controller=controller_name,
                    session=inner_cls.__name__,
                    event_type="scanner.session_discovered",
                )

        logger.info(
            "控制器注册成功",
            controller=controller_name,
            handler_count=handler_count,
            event_type="scanner.controller_registered",
        )
