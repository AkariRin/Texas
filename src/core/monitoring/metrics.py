"""Texas 的 Prometheus 指标定义。"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ── WebSocket 指标 ──
ws_connected = Gauge("texas_ws_connected", "Number of active NapCat WS connections")
ws_messages_received = Counter(
    "texas_ws_messages_received_total",
    "WS messages received from NapCat",
    ["post_type"],
)
ws_messages_sent = Counter("texas_ws_messages_sent_total", "WS messages sent to NapCat")

# ── 事件处理指标 ──
event_processed = Counter(
    "texas_event_processed_total",
    "Events processed",
    ["event_type", "handler"],
)
event_processing_seconds = Histogram(
    "texas_event_processing_seconds",
    "Event processing duration in seconds",
)
event_errors = Counter("texas_event_errors_total", "Event processing errors")

# ── API 调用指标 ──
api_calls = Counter("texas_api_calls_total", "OneBot API calls", ["action"])
api_call_duration = Histogram(
    "texas_api_call_duration_seconds", "OneBot API call duration"
)
api_call_errors = Counter("texas_api_call_errors_total", "OneBot API call failures")

# ── 处理器指标 ──
handlers_registered = Gauge("texas_handlers_registered", "Number of registered handler methods")

# ── 系统指标 ──
uptime_seconds = Gauge("texas_uptime_seconds", "Process uptime in seconds")

