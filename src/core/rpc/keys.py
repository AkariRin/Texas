"""RPC 模块的 Redis 缓存键定义。"""

from __future__ import annotations

from src.core.cache.key_registry import cache_key

rpc_request_queue = cache_key(
    "rpc.request_queue",
    "texas:rpc:requests",
    description="RPC 请求队列（Redis List），Worker → 主进程。",
)

rpc_response_channel = cache_key(
    "rpc.response_channel",
    "texas:rpc:resp:{request_id}",
    description="RPC 响应通道（Redis Pub/Sub），主进程 → Worker。",
)
