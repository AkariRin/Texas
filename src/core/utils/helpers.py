"""通用辅助工具函数。"""

from __future__ import annotations


def ceil_div(total: int, page_size: int) -> int:
    """计算分页总页数（向上取整除法）。"""
    return (total + page_size - 1) // page_size
