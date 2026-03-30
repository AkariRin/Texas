"""ComponentScanner —— 发现 @controller 类并注册处理器方法。"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import TYPE_CHECKING, Any

import structlog

from src.core.framework.decorators import CONTROLLER_META, FEATURE_META, HANDLER_META
from src.core.framework.mapping import CompositeHandlerMapping, HandlerMethod
from src.core.framework.session.decorators import SESSION_META

if TYPE_CHECKING:
    from src.core.framework.session.manager import SessionManager

logger = structlog.get_logger()


class ComponentScanner:
    """扫描包中的 @controller 装饰类并注册处理器。"""

    def __init__(self, mapping: CompositeHandlerMapping) -> None:
        self._mapping = mapping
        self._controllers: list[dict[str, Any]] = []
        self._standalone_features: list[dict[str, Any]] = []
        self._feature_metadata: dict[str, dict[str, Any]] = {}
        self._session_classes: list[tuple[str, type]] = []  # (controller_name, session_cls)

    @property
    def controllers(self) -> list[dict[str, Any]]:
        """返回所有已发现控制器的元数据。"""
        return list(self._controllers)

    @property
    def standalone_features(self) -> list[dict[str, Any]]:
        """返回所有 @feature 装饰的独立功能列表（非 handler）。"""
        return list(self._standalone_features)

    @property
    def feature_metadata(self) -> dict[str, dict[str, Any]]:
        """返回所有功能的内存元数据字典 {feature_name: metadata}。

        scan() 完成后可用，包含 display_name、description、admin、
        message_scope、mapping_type、tags、children（仅 controller 级）。
        """
        return self._feature_metadata

    @property
    def session_classes(self) -> list[tuple[str, type]]:
        """返回所有已发现的交互式会话类。"""
        return list(self._session_classes)

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
        """扫描给定的包路径以查找控制器，完成后构建内存元数据注册表。"""
        for package_name in packages:
            self._scan_package(package_name)
        self._build_feature_metadata()

    def _build_feature_metadata(self) -> None:
        """从 controllers 列表构建扁平化内存元数据 map，scan() 后调用。"""
        metadata: dict[str, dict[str, Any]] = {}
        for ctrl in self._controllers:
            ctrl_name: str = ctrl["name"]
            ctrl_admin: bool = ctrl.get("admin", False)
            children: list[dict[str, Any]] = []

            for method in ctrl.get("methods", []):
                method_name = f"{ctrl_name}.{method['method']}"
                # method 级 admin：None 表示跟随 controller
                method_admin_raw = method.get("admin")
                method_admin = ctrl_admin if method_admin_raw is None else method_admin_raw

                child_meta = {
                    "name": method_name,
                    "display_name": method.get("display_name") or method["method"],
                    "description": method.get("description", ""),
                    "admin": method_admin,
                    "message_scope": method.get("message_scope", "all"),
                    "mapping_type": method.get("mapping_type", ""),
                    "tags": [],
                    "system": ctrl.get("system", False),
                }
                metadata[method_name] = child_meta
                children.append(child_meta)

            ctrl_meta = {
                "name": ctrl_name,
                "display_name": ctrl.get("display_name", ctrl_name),
                "description": ctrl.get("description", ""),
                "admin": ctrl_admin,
                "message_scope": "all",
                "mapping_type": "",
                "tags": ctrl.get("tags", []),
                "children": children,
                "system": ctrl.get("system", False),
            }
            metadata[ctrl_name] = ctrl_meta

        # 处理独立 @feature 功能
        for feat in self._standalone_features:
            feat_name: str = feat["name"]
            metadata[feat_name] = {
                "name": feat_name,
                "display_name": feat.get("display_name", feat_name),
                "description": feat.get("description", ""),
                "admin": False,
                "message_scope": "all",
                "mapping_type": "",
                "tags": feat.get("tags", []),
                "children": [],
                "system": feat.get("system", False),
            }

        self._feature_metadata = metadata

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
                    self._discover_in_module(mod)
                except Exception:
                    pass

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
