"""Texas 的 Structlog 配置。"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

# ── 注册 TRACE 级别（数值 5，低于 DEBUG=10）──
TRACE = 5
logging.addLevelName(TRACE, "TRACE")


def _trace(self: logging.Logger, message: object, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
    if self.isEnabledFor(TRACE):
        self._log(TRACE, message, args, **kwargs)


logging.Logger.trace = _trace  # type: ignore[attr-defined]


class _ExcInfoToTrace(logging.Filter):
    """将携带异常信息的日志记录的级别标记为 TRACE。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.exc_info:
            record.levelname = "TRACE"
            record.levelno = TRACE
        return True


def _add_uvicorn_to_structlog() -> None:
    """将 uvicorn 的所有 logger 接管到 structlog 管道，并清除其默认 Handler。"""
    uvicorn_loggers = [
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "uvicorn.asgi",
        "uvicorn.lifespan",
    ]
    for name in uvicorn_loggers:
        uv_logger = logging.getLogger(name)
        uv_logger.handlers = []      # 移除 uvicorn 自带的 Handler
        uv_logger.propagate = True   # 交由根 logger 传递到 structlog


def _bootstrap_root_logging(numeric_level: int = logging.DEBUG) -> None:
    """最早期的根 logging 初始化：安装唯一的 StreamHandler 并接管 uvicorn。

    此函数可在模块导入阶段调用，确保 uvicorn 启动时的首条日志也经过 structlog。
    """
    root_handler = logging.StreamHandler(sys.stdout)
    root_handler.setFormatter(logging.Formatter("%(message)s"))
    root_handler.addFilter(_ExcInfoToTrace())

    root_logger = logging.getLogger()
    root_logger.handlers = [root_handler]
    root_logger.setLevel(numeric_level)

    _add_uvicorn_to_structlog()


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """配置 structlog，输出 JSON（生产环境）或控制台（开发环境）格式。

    - 最高日志等级固定为 DEBUG（若传入等级比 DEBUG 更详细则以传入为准）。
    - 携带 exc_info 的日志记录会被标记为 TRACE 级别。
    - uvicorn 的日志统一接入 structlog 管道。
    """
    # 保证至少输出到 DEBUG；若传入比 DEBUG 更详细（如 TRACE=5）则以传入为准
    raw_level = getattr(logging, log_level.upper(), None) or TRACE
    numeric_level = min(raw_level, logging.DEBUG)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.ExtraAdder(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if log_format == "console":
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # 重新应用根 handler（此时级别已确定）并再次接管 uvicorn（热重载场景下可能重置）
    _bootstrap_root_logging(numeric_level)
