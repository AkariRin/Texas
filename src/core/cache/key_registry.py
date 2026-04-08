"""Redis 缓存键注册表 —— cache_key() 工厂函数与全局注册表。

业务模块在本地通过 cache_key() 定义键，import 时自动注册到此注册表，
无需手动在中心文件维护键列表。

设计参考：src/core/lifecycle/registry.py
"""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

# 匹配模板中的 {param} 占位符
_PLACEHOLDER_RE: re.Pattern[str] = re.compile(r"\{(\w+)\}")


@dataclass(frozen=True)
class CacheKeyEntry:
    """描述一个已注册的 Redis 缓存键定义。

    Attributes:
        name: 唯一标识，如 "personnel.user_relation"。
        prefix: 键模板，如 "texas:personnel:user:{qq}:relation"。
        params: 从模板解析的有序参数名元组，如 ("qq",)。
        ttl_hint: 建议 TTL（秒），仅文档/工具用途，None 表示无建议。
        description: 中文描述。
        module: 定义所在模块路径，如 "src.services.personnel"。
        glob_pattern: 自动生成的 Redis glob 模式（{param} → *）。
    """

    name: str
    prefix: str
    params: tuple[str, ...]
    ttl_hint: int | None
    description: str
    module: str
    glob_pattern: str = field(default="")

    def __post_init__(self) -> None:
        # glob_pattern 默认由 prefix 推导
        if not self.glob_pattern:
            object.__setattr__(self, "glob_pattern", _derive_glob(self.prefix))


# ── 全局注册表 ──

_registry: list[CacheKeyEntry] = []


def get_all_cache_keys() -> tuple[CacheKeyEntry, ...]:
    """返回所有已注册缓存键定义（不可变快照）。"""
    return tuple(_registry)


def get_cache_key(name: str) -> CacheKeyEntry | None:
    """按名称查找缓存键定义，不存在则返回 None。"""
    for entry in _registry:
        if entry.name == name:
            return entry
    return None


def get_cache_keys_by_module(module: str) -> tuple[CacheKeyEntry, ...]:
    """返回指定模块定义的所有缓存键。"""
    return tuple(e for e in _registry if e.module == module)


def glob_for(key_func: Callable[..., str]) -> str:
    """返回缓存键函数对应的 Redis glob 模式。

    Args:
        key_func: 由 cache_key() 创建的键构建函数。

    Raises:
        TypeError: 若 key_func 不是通过 cache_key() 注册的函数。
    """
    entry: CacheKeyEntry | None = getattr(key_func, "__cache_key_entry__", None)
    if entry is None:
        msg = f"{key_func!r} 不是通过 cache_key() 注册的缓存键函数"
        raise TypeError(msg)
    return entry.glob_pattern


# ── 工厂函数 ──


def cache_key(
    name: str,
    prefix: str,
    *,
    ttl_hint: int | None = None,
    description: str = "",
    module: str = "",
) -> Any:
    """注册并返回一个 Redis 缓存键构建函数。

    在模块级别调用，import 时自动注册到全局注册表。

    Args:
        name: 全局唯一标识，建议用点号分隔，如 "personnel.user_relation"。
        prefix: 键模板字符串，支持 {param} 占位符，如 "texas:user:{qq}:info"。
        ttl_hint: 建议 TTL（秒），仅文档用途，不影响运行时行为。
        description: 中文描述。
        module: 显式指定定义模块路径（留空则自动从调用栈推导）。

    Returns:
        键构建函数，签名与 prefix 中的占位符对应，支持位置参数和关键字参数。

    Raises:
        ValueError: 若 name 已被注册（重复注册保护）。

    Example::

        checkin_key = cache_key(
            "checkin.daily",
            "texas:checkin:{group_id}:{date_str}",
            ttl_hint=90000,
            description="某群某日的打卡状态。",
        )
        checkin_key(123, "2026-04-07")    # → "texas:checkin:123:2026-04-07"
        checkin_key(group_id=123, date_str="2026-04-07")  # 同上
    """
    # 检查名称唯一性
    if any(e.name == name for e in _registry):
        msg = f"缓存键 '{name}' 已注册，请检查是否存在重复定义"
        raise ValueError(msg)

    # 解析模板中的参数列表（保持顺序）
    params: tuple[str, ...] = tuple(dict.fromkeys(_PLACEHOLDER_RE.findall(prefix)))
    glob_pattern = _derive_glob(prefix)

    # 自动推导定义模块
    if not module:
        caller = inspect.currentframe()
        caller = caller.f_back if caller else None
        module = caller.f_globals.get("__name__", "") if caller else ""

    entry = CacheKeyEntry(
        name=name,
        prefix=prefix,
        params=params,
        ttl_hint=ttl_hint,
        description=description,
        module=module,
        glob_pattern=glob_pattern,
    )
    _registry.append(entry)

    # 构建键函数
    key_func = _make_key_func(prefix, params)
    key_func.__cache_key_entry__ = entry
    key_func.__doc__ = description or f"Redis 缓存键：{prefix}"
    key_func.__name__ = name.replace(".", "_")
    return key_func


def _make_key_func(prefix: str, params: tuple[str, ...]) -> Any:
    """生成一个接受位置参数或关键字参数、返回格式化键字符串的函数。"""

    def key_func(*args: Any, **kwargs: Any) -> str:
        # 将位置参数映射为关键字参数
        if len(args) > len(params):
            msg = f"期望最多 {len(params)} 个参数，实际传入 {len(args)} 个"
            raise TypeError(msg)
        merged = dict(zip(params, args, strict=False))
        merged.update(kwargs)
        return prefix.format(**merged)

    return key_func


def _derive_glob(prefix: str) -> str:
    """将模板 {param} 替换为 * 生成 glob 模式。"""
    return _PLACEHOLDER_RE.sub("*", prefix)


# ── 兼容层辅助（供 keys.py 使用） ──


def _register_existing(
    func: Any,
    name: str,
    prefix: str,
    *,
    ttl_hint: int | None = None,
    description: str = "",
    module: str = "src.core.cache.keys",
) -> None:
    """将现有手写键函数注册到全局注册表，并挂载 __cache_key_entry__ 属性。

    仅供 keys.py 内部使用，用于向后兼容过渡期。
    """
    if any(e.name == name for e in _registry):
        return  # 幂等：已注册则跳过

    params: tuple[str, ...] = tuple(dict.fromkeys(_PLACEHOLDER_RE.findall(prefix)))
    entry = CacheKeyEntry(
        name=name,
        prefix=prefix,
        params=params,
        ttl_hint=ttl_hint,
        description=description,
        module=module,
        glob_pattern=_derive_glob(prefix),
    )
    _registry.append(entry)
    func.__cache_key_entry__ = entry
