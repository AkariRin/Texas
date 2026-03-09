"""SQLAlchemy DeclarativeBase —— 所有 ORM 模型的基类。"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """纯粹的声明式基类，不包含任何公共列。

    所有 ORM 模型继承此类以共享同一个 metadata 注册表，
    但各模型需自行声明全部字段（包括主键和时间戳）。
    """
