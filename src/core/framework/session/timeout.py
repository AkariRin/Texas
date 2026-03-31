"""会话超时配置。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from src.core.framework.session.enums import TimeoutMode


class TimeoutConfig(BaseModel):
    """会话超时配置。

    Attributes:
        duration: 超时秒数，NEVER 模式下忽略。
        mode: 超时策略。
        warning_before: NOTIFY 模式下提前多少秒提醒。
        timeout_message: 超时时发送的消息。
        warning_message: 超时前提醒消息，支持 {remaining} 占位符。
    """

    model_config = ConfigDict(frozen=True)

    duration: int = 300
    mode: TimeoutMode = TimeoutMode.silent
    warning_before: int = 30
    timeout_message: str = "操作已超时，会话已结束。"
    warning_message: str = "操作即将超时，请在 {remaining} 秒内继续。"
