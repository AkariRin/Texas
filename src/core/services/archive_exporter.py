"""Parquet 导出服务 —— 将分区数据流式导出为 Parquet 文件。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
from typing import TYPE_CHECKING, Any, Literal

import pyarrow as pa
import pyarrow.parquet as pq
import structlog
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import text
from sqlalchemy.sql.elements import quoted_name

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class ChatArchiveSettings(BaseSettings):
    """聊天归档策略配置。

    注意：定义在此处（而非 chat_archive.py）以避免循环导入——
    chat_archive.py 已导入本模块的 ParquetExporter。
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True
    )

    CHAT_ARCHIVE_RETENTION_MONTHS: int = Field(default=12, ge=1)
    CHAT_ARCHIVE_BATCH_SIZE: int = Field(default=5000, ge=100)
    CHAT_ARCHIVE_COMPRESSION: Literal["zstd", "gzip", "none"] = "zstd"


logger = structlog.get_logger()

# 分区名白名单：只允许 chat_history_YYYY_MM 格式
_PARTITION_NAME_RE = re.compile(r"^chat_history_\d{4}_\d{2}$")

# ── Parquet Schema 定义 ──

CHAT_HISTORY_SCHEMA = pa.schema(
    [
        pa.field("id", pa.int64(), nullable=False),
        pa.field("message_id", pa.int64(), nullable=False),
        pa.field("message_type", pa.int16(), nullable=False),
        pa.field("group_id", pa.int64(), nullable=True),
        pa.field("user_id", pa.int64(), nullable=False),
        pa.field("self_id", pa.int64(), nullable=False),
        pa.field("raw_message", pa.utf8(), nullable=False),
        pa.field("segments", pa.utf8(), nullable=False),  # JSON string
        pa.field("sender_nickname", pa.utf8(), nullable=False),
        pa.field("sender_card", pa.utf8(), nullable=True),
        pa.field("sender_role", pa.utf8(), nullable=True),
        pa.field("created_at", pa.timestamp("us", tz="Asia/Shanghai"), nullable=False),
        pa.field("stored_at", pa.timestamp("us", tz="Asia/Shanghai"), nullable=False),
    ]
)


class ParquetExporter:
    """负责将聊天记录分区流式导出为 Parquet 文件。"""

    def __init__(
        self,
        chat_session_factory: async_sessionmaker[AsyncSession],
        settings: ChatArchiveSettings,
    ) -> None:
        self._chat_sf = chat_session_factory
        self._settings = settings

    async def export_partition(
        self,
        partition_name: str,
        output_path: str,
    ) -> tuple[int, int, int, str]:
        """流式导出分区数据到 Parquet 文件（内置 Zstd 压缩）。

        Returns:
            (total_rows, original_bytes, compressed_bytes, sha256_hex)
        """
        # 防御性校验：分区名必须符合白名单格式，防止 SQL 注入
        if not _PARTITION_NAME_RE.match(partition_name):
            raise ValueError(f"非法的分区名: {partition_name!r}")

        batch_size = self._settings.CHAT_ARCHIVE_BATCH_SIZE
        compression = self._settings.CHAT_ARCHIVE_COMPRESSION

        total_rows = 0
        original_bytes = 0
        batch_rows: list[dict[str, Any]] = []

        writer = pq.ParquetWriter(
            output_path,
            schema=CHAT_HISTORY_SCHEMA,
            compression=compression,
        )

        try:
            async with self._chat_sf() as session:
                # partition_name 已通过 _PARTITION_NAME_RE 白名单验证；
                # 额外使用 quoted_name 对标识符进行双引号转义，彻底消除 SQL 注入路径
                safe_name = quoted_name(partition_name, quote=True)
                result = await session.stream(
                    text(f"SELECT * FROM chat.{safe_name} ORDER BY created_at")  # noqa: S608
                )
                async for row in result:
                    row_dict = dict(row._mapping)
                    # segments (JSONB) → JSON string for Parquet storage
                    row_dict["segments"] = json.dumps(
                        row_dict["segments"], default=str, ensure_ascii=False
                    )
                    original_bytes += len(json.dumps(row_dict, default=str).encode("utf-8"))
                    batch_rows.append(row_dict)
                    total_rows += 1

                    if len(batch_rows) >= batch_size:
                        table = pa.Table.from_pylist(batch_rows, schema=CHAT_HISTORY_SCHEMA)
                        writer.write_table(table)
                        batch_rows.clear()

                # 写入剩余数据
                if batch_rows:
                    table = pa.Table.from_pylist(batch_rows, schema=CHAT_HISTORY_SCHEMA)
                    writer.write_table(table)
        finally:
            writer.close()

        # 计算压缩文件 SHA256（同步 IO 卸载到线程池，不阻塞 EventLoop）
        compressed_bytes = os.path.getsize(output_path)

        def _compute_sha256(path: str) -> str:
            hasher = hashlib.sha256()
            with open(path, "rb") as f_in:
                for chunk in iter(lambda: f_in.read(8192), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()

        sha256_hex = await asyncio.to_thread(_compute_sha256, output_path)
        return total_rows, original_bytes, compressed_bytes, sha256_hex
