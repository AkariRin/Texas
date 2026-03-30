"""ORM 模型统一导出 —— 确保 Base.metadata / ChatBase.metadata 感知全部表定义。

  - Base      → 主库模型（Group, User, LLM 等）
  - ChatBase  → 聊天库模型（ChatMessage 等）

新增模型后在此导出即可。
"""

# ── 主库模型（Base.metadata） ──
# ── 聊天库模型（ChatBase.metadata） ──
from src.models.chat import ChatMessage
from src.models.chat_archive import ChatArchiveLog
from src.models.feedback import Feedback, FeedbackSource, FeedbackStatus, FeedbackType
from src.models.llm import LLM, LLMProvider
from src.models.permission import Feature, GroupFeaturePermission, PrivateFeaturePermission
from src.models.personnel import Group, GroupMembership, User

__all__: list[str] = [
    # 主库
    "Group",
    "GroupMembership",
    "User",
    "LLMProvider",
    "LLM",
    "ChatArchiveLog",
    "Feature",
    "GroupFeaturePermission",
    "PrivateFeaturePermission",
    "Feedback",
    "FeedbackType",
    "FeedbackStatus",
    "FeedbackSource",
    # 聊天库
    "ChatMessage",
]
