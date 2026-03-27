"""数据库层公共工具函数。"""

from __future__ import annotations


def escape_like(value: str) -> str:
    """转义 LIKE 模式中的通配符 ``%``、``_`` 和 ``\\``，防止意外的模糊匹配。

    配合 SQLAlchemy 的 ``ilike(..., escape="\\\\")`` 使用::

        stmt.where(Column.ilike(f"%{escape_like(value)}%", escape="\\\\"))
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
