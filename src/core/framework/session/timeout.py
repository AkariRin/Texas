"""会话超时配置。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator

from src.core.framework.session.enums import TimeoutMode


class TimeoutConfig(BaseModel):
    """会话超时配置。

    Attributes:
        duration: 超时秒数，NEVER 模式下忽略，必须 > 0。
        mode: 超时策略。
        warning_before: NOTIFY 模式下提前多少秒提醒，必须 < duration。
        timeout_message: 超时时发送的消息。
        warning_message: 超时前提醒消息，支持 {remaining} 占位符。
    """

    model_config = ConfigDict(frozen=True)

    duration: int = 300
    mode: TimeoutMode = TimeoutMode.silent
    warning_before: int = 30
    timeout_message: str = "操作已超时，会话已结束。"
    warning_message: str = "操作即将超时，请在 {remaining} 秒内继续。"

    @model_validator(mode="after")
    def _validate_warning_before(self) -> TimeoutConfig:
        """校验 warning_before 必须小于 duration，且 duration 必须为正数。"""
        if self.duration <= 0:
            raise ValueError(f"duration 必须 > 0，当前值: {self.duration}")
        if self.mode == TimeoutMode.notify and self.warning_before >= self.duration:
            raise ValueError(
                f"warning_before ({self.warning_before}s) 必须小于 duration ({self.duration}s)"
            )
        return self
