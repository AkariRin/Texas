"""交互式会话模块的 Redis 缓存键。"""

from __future__ import annotations

from src.core.cache.key_registry import cache_key

session_key = cache_key(
    "session.meta",
    "texas:session:{session_key}",
    description="会话元信息。",
)

session_data_key = cache_key(
    "session.data",
    "texas:session:{session_key}:data",
    description="会话数据（Pydantic 模型序列化）。",
)
