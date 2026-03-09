"""缓存键命名规范。

所有键遵循以下格式：texas:{scope}:{identifier}
"""

from __future__ import annotations


def user_key(qq_id: int, suffix: str = "info") -> str:
    return f"texas:user:{qq_id}:{suffix}"


def group_key(group_id: int, suffix: str = "config") -> str:
    return f"texas:group:{group_id}:{suffix}"


def handler_key(handler_name: str, key: str) -> str:
    return f"texas:handler:{handler_name}:{key}"


def rate_limit_key(user_id: int, action: str) -> str:
    return f"texas:ratelimit:{user_id}:{action}"


def conversation_key(user_id: int, group_id: int | None = None) -> str:
    if group_id:
        return f"texas:conversation:{user_id}:{group_id}"
    return f"texas:conversation:{user_id}"


# ── 人事管理 (Personnel) ──


def personnel_sync_status_key() -> str:
    """最近一次同步状态。"""
    return "texas:personnel:sync_status"


def personnel_sync_lock_key() -> str:
    """同步任务分布式锁。"""
    return "texas:lock:personnel_sync"


def user_relation_key(qq: int) -> str:
    """用户关系等级缓存。"""
    return f"texas:personnel:user:{qq}:relation"


def admin_set_key() -> str:
    """管理员 QQ 号集合（Redis Set）。"""
    return "texas:personnel:admins"
