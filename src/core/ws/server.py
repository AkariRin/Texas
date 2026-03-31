"""NapCat 反向 WebSocket 连接的 WebSocket 服务端端点（一对一架构）。"""

from __future__ import annotations

import asyncio
import json

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from src.core.dependencies import WsDeps
from src.core.protocol.event import parse_event
from src.core.protocol.models.events import HeartbeatEvent

logger = structlog.get_logger()

ws_router = APIRouter()


def _check_token(token_param: str | None, headers: dict[str, str], access_token: str) -> bool:
    """从 URL 参数或 Authorization 请求头中验证访问令牌。"""
    if token_param and token_param == access_token:
        return True
    auth = headers.get("authorization", "")
    return bool(auth.startswith("Bearer ") and auth[7:] == access_token)


@ws_router.websocket("")
async def onebot_ws_endpoint(
    ws: WebSocket,
    access_token: str | None = Query(default=None),
) -> None:
    """NapCat 反向 WebSocket 端点。NapCat 以客户端身份连接至此（仅允许单连接）。"""
    deps = WsDeps(ws)
    conn_mgr = deps.conn_mgr
    bot_api = deps.bot_api
    heartbeat = deps.heartbeat

    # 令牌鉴权
    headers = {k.decode(): v.decode() for k, v in ws.scope.get("headers", [])}
    if not _check_token(access_token, headers, deps.access_token):
        logger.critical(
            "WebSocket 连接已拒绝：访问令牌无效",
            event_type="ws.auth_failed",
        )
        await ws.close(code=4001, reason="Unauthorized")
        return

    # 一对一架构：拒绝重复连接
    if conn_mgr.connected:
        logger.warning(
            "WebSocket 连接已拒绝：已有活跃连接",
            event_type="ws.duplicate_rejected",
        )
        await ws.close(code=4002, reason="Already connected")
        return

    await conn_mgr.accept(ws)
    heartbeat.start()

    # 追踪后台事件处理任务，以便在断连时做清理
    background_tasks: set[asyncio.Task[None]] = set()

    def _on_task_done(task: asyncio.Task[None]) -> None:
        background_tasks.discard(task)
        if not task.cancelled() and task.exception():
            logger.error(
                "后台事件处理器发生错误",
                error=str(task.exception()),
                event_type="ws.handler_error",
            )

    # ── 触发首次用户数据同步（由协调器管理去重） ──
    _sync_task = deps.sync_coordinator.request_sync(source="ws_connect")
    if _sync_task is not None:
        background_tasks.add(_sync_task)
        _sync_task.add_done_callback(_on_task_done)

    # ── 触发每日打卡（由服务内部去重，今日已打卡则跳过） ──
    _checkin_task = deps.checkin_service.request_checkin(source="ws_connect")
    if _checkin_task is not None:
        background_tasks.add(_checkin_task)
        _checkin_task.add_done_callback(_on_task_done)

    # 获取事件分发回调
    event_dispatch_callback = deps.event_dispatch_callback

    async def _dispatch_event(event: object) -> None:
        if event_dispatch_callback is not None:
            await event_dispatch_callback(event)
        else:
            logger.debug("未设置事件分发器，已忽略事件", event_type="ws.no_dispatcher")

    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning(
                    "收到来自 NapCat 的无效 JSON", raw=raw[:200], event_type="ws.bad_json"
                )
                continue

            # 检查是否为 API 响应（含有 echo 字段且与挂起的调用匹配）
            if bot_api.handle_response(data):
                continue

            # 跳过迟到的 API 响应（超时后才到达的响应，不在 _pending 中但仍属于 API 响应）
            if "echo" in data and "post_type" not in data:
                logger.debug(
                    "忽略已过期的 API 响应",
                    echo=data.get("echo"),
                    status=data.get("status"),
                    event_type="ws.stale_response",
                )
                continue

            try:
                # 解析为事件
                event = parse_event(data)
            except Exception as exc:
                logger.warning(
                    "事件解析失败，已跳过",
                    error=str(exc),
                    data_keys=list(data.keys()),
                    event_type="ws.parse_error",
                )
                continue

            # 处理心跳事件
            if isinstance(event, HeartbeatEvent):
                status = event.status.model_dump() if event.status else None
                heartbeat.record_heartbeat(status)
                continue

            # 分发至框架（作为后台任务，避免阻塞接收循环导致 API 响应无法被处理）
            task = asyncio.create_task(_dispatch_event(event))
            background_tasks.add(task)
            task.add_done_callback(_on_task_done)

    except WebSocketDisconnect:
        logger.info("NapCat 已断开连接", event_type="ws.disconnected")
    except Exception as exc:
        logger.error("WebSocket 发生错误", error=str(exc), event_type="ws.error")
    finally:
        # 取消尚未完成的后台任务
        for task in background_tasks:
            task.cancel()
        if background_tasks:
            await asyncio.gather(*background_tasks, return_exceptions=True)
        conn_mgr.disconnect()
        heartbeat.stop()
