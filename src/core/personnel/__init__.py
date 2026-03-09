"""人事管理核心模块 —— 用户、群聊、成员关系的同步与管理。"""

from src.core.personnel.models import Group, GroupMembership, User

__all__ = ["Group", "GroupMembership", "User"]
