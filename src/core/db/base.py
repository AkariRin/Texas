"""SQLAlchemy DeclarativeBase —— 所有 ORM 模型的基类。"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """纯粹的声明式基类，不包含任何公共列。

    所有 ORM 模型继承此类以共享同一个 metadata 注册表，
    但各模型需自行声明全部字段（包括主键）。

    注意：不要为模型默认添加 created_at / updated_at 等时间戳列，
    仅在业务逻辑明确需要时才添加。
    """
