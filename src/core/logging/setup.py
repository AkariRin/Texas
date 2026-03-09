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


def _silence_db_loggers() -> None:
    """将 SQLAlchemy / Alembic 日志降至 CRITICAL，完全抑制迁移过程中的库内部输出。

    迁移结果由 migration.py 通过 structlog 输出简洁摘要。
    """
    for name in ("sqlalchemy.engine", "sqlalchemy", "alembic"):
        db_logger = logging.getLogger(name)
        db_logger.setLevel(logging.CRITICAL)
        db_logger.handlers = []
        db_logger.propagate = False


def _bootstrap_root_logging(numeric_level: int = logging.DEBUG) -> None:
    """最早期的根 logging 初始化：安装唯一的 StreamHandler。

    此函数可在模块导入阶段调用。uvicorn 保留其自身的日志格式，不做接管。
    """
    root_handler = logging.StreamHandler(sys.stdout)
    root_handler.setFormatter(logging.Formatter("%(message)s"))
    root_handler.addFilter(_ExcInfoToTrace())

    root_logger = logging.getLogger()
    root_logger.handlers = [root_handler]
    root_logger.setLevel(numeric_level)

    _silence_db_loggers()


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """配置 structlog，输出 JSON（生产环境）或控制台（开发环境）格式。

    - 最高日志等级固定为 DEBUG（若传入等级比 DEBUG 更详细则以传入为准）。
    - 携带 exc_info 的日志记录会被标记为 TRACE 级别。
    - uvicorn 保留其自身的默认日志输出格式。
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

    # 重新应用根 handler（此时级别已确定）并静默数据库日志（热重载场景下可能重置）
    _bootstrap_root_logging(numeric_level)
