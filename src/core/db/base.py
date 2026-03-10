"""SQLAlchemy DeclarativeBase —— ORM 模型基类。

提供两个完全独立的声明式基类：
  - Base      → 主库（默认 schema），由 alembic.ini 管理迁移
  - ChatBase  → 聊天库（chat schema），由 alembic_chat.ini 管理迁移

两者各自拥有独立的 metadata 注册表，互不干扰。
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """主库声明式基类 —— 管理默认 schema 下的所有表。

    所有主库 ORM 模型继承此类以共享同一个 metadata 注册表，
    但各模型需自行声明全部字段（包括主键）。

    注意：不要为模型默认添加 created_at / updated_at 等时间戳列，
    仅在业务逻辑明确需要时才添加。
    """


class ChatBase(DeclarativeBase):
    """聊天库声明式基类 —— 管理 chat schema 下的表。

    与 Base 拥有完全独立的 metadata，确保两个 Alembic 实例
    各自只感知属于自己的表定义，互不污染。
    """
