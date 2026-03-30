"""业务枚举定义 —— 跨层共享，不依赖 ORM。"""

from __future__ import annotations

import enum

# ── 反馈相关 ──


class FeedbackType(enum.StrEnum):
    """反馈类型枚举。"""

    BUG = "bug"
    SUGGESTION = "suggestion"
    COMPLAINT = "complaint"
    OTHER = "other"


class FeedbackStatus(enum.StrEnum):
    """反馈状态枚举。"""

    PENDING = "pending"
    PROCESSED = "processed"


class FeedbackSource(enum.StrEnum):
    """反馈来源枚举。"""

    GROUP = "group"
    PRIVATE = "private"
