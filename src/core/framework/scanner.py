"""ComponentScanner —— 发现 @controller 类并注册处理器方法。"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any

import structlog

from src.core.framework.decorators import CONTROLLER_META, HANDLER_META
from src.core.framework.mapping import CompositeHandlerMapping, HandlerMethod

logger = structlog.get_logger()


class ComponentScanner:
    """扫描包中的 @controller 装饰类并注册处理器。"""

    def __init__(self, mapping: CompositeHandlerMapping) -> None:
        self._mapping = mapping
        self._controllers: list[dict[str, Any]] = []

    @property
    def controllers(self) -> list[dict[str, Any]]:
        """返回所有已发现控制器的元数据。"""
        return list(self._controllers)

    def scan(self, packages: list[str]) -> None:
        """扫描给定的包路径以查找控制器。"""
        for package_name in packages:
            self._scan_package(package_name)

    def _scan_package(self, package_name: str) -> None:
        """导入包中所有模块并发现控制器。"""
        try:
            package = importlib.import_module(package_name)
        except ModuleNotFoundError:
            logger.warning(
                "Package not found for scanning",
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
                        "Failed to import module",
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
                    self._discover_in_module(mod)
                except Exception:
                    pass

    def _discover_in_module(self, module: Any) -> None:
        """查找模块中所有被 @controller 装饰的类。"""
        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ != module.__name__:
                continue
            ctrl_meta = getattr(obj, CONTROLLER_META, None)
            if ctrl_meta is None:
                continue
            self._register_controller(obj, ctrl_meta)

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
                    metadata=meta,
                    controller_name=controller_name,
                    method_name=method_name,
                )
                self._mapping.register(hm)
                handler_count += 1
                methods_info.append({
                    "method": method_name,
                    "mapping_type": meta.get("mapping_type"),
                    "priority": priority,
                })

        ctrl_info = {
            **ctrl_meta,
            "class": cls.__name__,
            "handler_count": handler_count,
            "methods": methods_info,
        }
        self._controllers.append(ctrl_info)

        logger.info(
            "Registered controller",
            controller=controller_name,
            handler_count=handler_count,
            event_type="scanner.controller_registered",
        )

