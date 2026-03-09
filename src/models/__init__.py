"""ORM 模型统一导出 —— 确保 Base.metadata 感知全部表定义。

新增模型后在此导出即可。
"""

from src.core.personnel.models import Group, GroupMembership, User

__all__: list[str] = ["Group", "GroupMembership", "User"]
