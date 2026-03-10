"""ORM 模型统一导出 —— 确保 Base.metadata / ChatBase.metadata 感知全部表定义。

  - Base      → 主库模型（Group, User, LLM 等）
  - ChatBase  → 聊天库模型（ChatMessage 等）

新增模型后在此导出即可。
"""

# ── 主库模型（Base.metadata） ──
from src.core.chat.archive_models import ChatArchiveLog
from src.core.llm.models import LLM, LLMProvider
from src.core.personnel.models import Group, GroupMembership, User

# ── 聊天库模型（ChatBase.metadata） ──
from src.core.chat.models import ChatMessage

__all__: list[str] = [
    # 主库
    "Group",
    "GroupMembership",
    "User",
    "LLMProvider",
    "LLM",
    "ChatArchiveLog",
    # 聊天库
    "ChatMessage",
]
