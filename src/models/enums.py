"""业务枚举定义 —— 跨层共享，不依赖 ORM。"""

from __future__ import annotations

import enum

# ── 反馈相关 ──


class FeedbackType(enum.StrEnum):
    """反馈类型枚举。"""

    bug = "bug"
    suggestion = "suggestion"
    complaint = "complaint"
    other = "other"


class FeedbackStatus(enum.StrEnum):
    """反馈状态枚举。"""

    pending = "pending"
    done = "done"


class FeedbackSource(enum.StrEnum):
    """反馈来源枚举。"""

    group = "group"
    private = "private"


# ── 用户关系 ──


class UserRelation(enum.StrEnum):
    """用户与机器人的关系等级枚举。"""

    stranger = "stranger"
    group_member = "group_member"
    friend = "friend"
    admin = "admin"


# ── 群内角色 ──


class GroupRole(enum.StrEnum):
    """群成员角色枚举（owner/admin/member）。"""

    owner = "owner"
    admin = "admin"
    member = "member"


# ── 聊天归档状态 ──


class ArchiveStatus(enum.StrEnum):
    """聊天记录归档任务状态枚举。

    状态机：pending → exporting → uploading → uploaded → partition_dropped → completed
    任意阶段 → failed
    """

    pending = "pending"
    exporting = "exporting"
    uploading = "uploading"
    uploaded = "uploaded"
    partition_dropped = "partition_dropped"
    completed = "completed"
    failed = "failed"
