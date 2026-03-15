"""聊天记录归档服务 —— 冷数据导出为 Parquet 并上传至 S3。"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pyarrow as pa
import pyarrow.parquet as pq
import structlog
from sqlalchemy import select, text, update

from src.core.chat.archive_models import ChatArchiveLog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from src.core.config import Settings

logger = structlog.get_logger()

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
        pa.field("created_at", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("stored_at", pa.timestamp("us", tz="UTC"), nullable=False),
    ]
)


class ArchiveService:
    """聊天记录归档服务。"""

    def __init__(
        self,
        chat_session_factory: async_sessionmaker[AsyncSession],
        main_session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._chat_sf = chat_session_factory
        self._main_sf = main_session_factory
        self._settings = settings

    # ════════════════════════════════════════════
    #  分区管理
    # ════════════════════════════════════════════

    async def ensure_partitions(self) -> dict[str, str]:
        """确保当月和下月的分区存在。"""
        async with self._chat_sf() as session:
            await session.execute(text("SELECT chat.create_monthly_partition(CURRENT_DATE)"))
            await session.execute(
                text("SELECT chat.create_monthly_partition(CURRENT_DATE + INTERVAL '1 month')")
            )
            await session.commit()
        return {"status": "ok", "message": "分区已就绪"}

    # ════════════════════════════════════════════
    #  归档主流程
    # ════════════════════════════════════════════

    async def archive(self, partition_name: str | None = None) -> dict[str, Any]:
        """执行归档流程。

        如果未指定 partition_name，则自动发现超过保留月数的分区。
        """
        if partition_name:
            partitions = [partition_name]
        else:
            partitions = await self._discover_archivable_partitions()

        if not partitions:
            return {"status": "no_partitions", "message": "没有需要归档的分区"}

        results = []
        for part_name in partitions:
            try:
                result = await self._archive_partition(part_name)
                results.append(result)
            except Exception as e:
                logger.exception(
                    "归档分区失败",
                    partition=part_name,
                    event_type="archive.partition_failed",
                )
                results.append({"partition": part_name, "status": "failed", "error": str(e)})

        return {"status": "completed", "results": results}

    async def _discover_archivable_partitions(self) -> list[str]:
        """发现可归档的分区（超过保留月数且未归档）。"""
        retention = self._settings.CHAT_ARCHIVE_RETENTION_MONTHS

        async with self._chat_sf() as chat_session:
            # 查询所有子分区
            result = await chat_session.execute(
                text("""
                    SELECT c.relname AS partition_name
                    FROM pg_inherits i
                    JOIN pg_class c ON c.oid = i.inhrelid
                    JOIN pg_class p ON p.oid = i.inhparent
                    JOIN pg_namespace n ON n.oid = p.relnamespace
                    WHERE n.nspname = 'chat' AND p.relname = 'chat_history'
                    ORDER BY c.relname
                """)
            )
            all_partitions = [row[0] for row in result.all()]

        # 过滤出超过保留期的分区
        cutoff = datetime.now(UTC) - timedelta(days=retention * 30)
        cutoff_str = cutoff.strftime("%Y_%m")

        archivable = []
        for part in all_partitions:
            # 从分区名中提取年月，如 chat_history_2024_01
            suffix = part.replace("chat_history_", "")
            if suffix < cutoff_str:
                archivable.append(part)

        # 排除已归档的分区
        if archivable:
            async with self._main_sf() as main_session:
                existing = await main_session.execute(
                    select(ChatArchiveLog.partition_name).where(
                        ChatArchiveLog.partition_name.in_(archivable),
                        ChatArchiveLog.status == "completed",
                    )
                )
                already_archived = {row[0] for row in existing.all()}
                archivable = [p for p in archivable if p not in already_archived]

        return archivable

    async def _archive_partition(self, partition_name: str) -> dict[str, Any]:
        """归档单个分区的完整流程。"""
        # 解析年月
        suffix = partition_name.replace("chat_history_", "")
        parts = suffix.split("_")
        year, month = int(parts[0]), int(parts[1])

        from datetime import date

        period_start = date(year, month, 1)
        period_end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

        # ② 创建归档记录
        archive_log = ChatArchiveLog(
            partition_name=partition_name,
            period_start=period_start,
            period_end=period_end,
            s3_bucket=self._settings.S3_ARCHIVE_BUCKET,
            s3_key="",
            s3_sha256="",
            status="pending",
        )
        async with self._main_sf() as session:
            session.add(archive_log)
            await session.commit()
            archive_id = archive_log.id

        try:
            # ③ 导出 → status = 'exporting'
            await self._update_archive_status(archive_id, "exporting")

            with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
                tmp_path = tmp.name

            try:
                (
                    total_rows,
                    original_bytes,
                    compressed_bytes,
                    sha256_hex,
                ) = await self._export_partition_to_parquet(partition_name, tmp_path)

                if total_rows == 0:
                    await self._update_archive_status(
                        archive_id, "completed", error_message="分区为空，跳过"
                    )
                    return {"partition": partition_name, "status": "empty", "rows": 0}

                # ④ 上传 S3 → status = 'uploading'
                await self._update_archive_status(archive_id, "uploading")

                s3_key = (
                    f"{self._settings.S3_ARCHIVE_PREFIX}"
                    f"/{year:04d}/{month:02d}/{partition_name}.parquet"
                )
                await self._upload_to_s3(
                    tmp_path,
                    s3_key,
                    {
                        "partition": partition_name,
                        "period_start": str(period_start),
                        "period_end": str(period_end),
                        "total_rows": str(total_rows),
                        "sha256": sha256_hex,
                    },
                )

                # 上传 manifest
                manifest = self._build_manifest(
                    partition_name,
                    period_start,
                    period_end,
                    total_rows,
                    original_bytes,
                    compressed_bytes,
                    sha256_hex,
                )
                manifest_key = s3_key.replace(".parquet", ".manifest.json")
                await self._upload_manifest(manifest, manifest_key)

            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

            # ⑤ 校验 → status = 'uploaded'
            await self._update_archive_status(archive_id, "uploaded")

            # 更新归档记录统计
            async with self._main_sf() as session:
                await session.execute(
                    update(ChatArchiveLog)
                    .where(ChatArchiveLog.id == archive_id)
                    .values(
                        total_rows=total_rows,
                        original_bytes=original_bytes,
                        compressed_bytes=compressed_bytes,
                        s3_key=s3_key,
                        s3_sha256=sha256_hex,
                    )
                )
                await session.commit()

            # ⑥ 分区清理 → status = 'partition_dropped'
            async with self._chat_sf() as session:
                await session.execute(
                    text(f"ALTER TABLE chat.chat_history DETACH PARTITION chat.{partition_name}")
                )
                await session.execute(text(f"DROP TABLE chat.{partition_name}"))
                await session.commit()

            await self._update_archive_status(archive_id, "partition_dropped")

            # ⑦ 完成
            async with self._main_sf() as session:
                await session.execute(
                    update(ChatArchiveLog)
                    .where(ChatArchiveLog.id == archive_id)
                    .values(status="completed", completed_at=datetime.now(UTC))
                )
                await session.commit()

            logger.info(
                "归档完成",
                partition=partition_name,
                rows=total_rows,
                compressed_bytes=compressed_bytes,
                event_type="archive.completed",
            )

            return {
                "partition": partition_name,
                "status": "completed",
                "rows": total_rows,
                "original_bytes": original_bytes,
                "compressed_bytes": compressed_bytes,
                "s3_key": s3_key,
            }

        except Exception as e:
            await self._update_archive_status(archive_id, "failed", error_message=str(e))
            raise

    # ════════════════════════════════════════════
    #  数据导出
    # ════════════════════════════════════════════

    async def _export_partition_to_parquet(
        self,
        partition_name: str,
        output_path: str,
    ) -> tuple[int, int, int, str]:
        """流式导出分区数据到 Parquet 文件（内置 Zstd 压缩）。

        Returns:
            (total_rows, original_bytes, compressed_bytes, sha256_hex)
        """
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
                result = await session.stream(
                    text(f"SELECT * FROM chat.{partition_name} ORDER BY created_at")
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

        # 计算压缩文件 SHA256
        compressed_bytes = os.path.getsize(output_path)
        hasher = hashlib.sha256()
        with open(output_path, "rb") as f_in:
            for chunk in iter(lambda: f_in.read(8192), b""):
                hasher.update(chunk)

        return total_rows, original_bytes, compressed_bytes, hasher.hexdigest()

    # ════════════════════════════════════════════
    #  S3 操作
    # ════════════════════════════════════════════

    def _get_s3_client(self) -> Any:
        """创建 S3 客户端。"""
        import boto3

        kwargs: dict[str, Any] = {
            "region_name": self._settings.S3_REGION,
        }
        if self._settings.S3_ACCESS_KEY_ID:
            kwargs["aws_access_key_id"] = self._settings.S3_ACCESS_KEY_ID
            kwargs["aws_secret_access_key"] = self._settings.S3_SECRET_ACCESS_KEY
        if self._settings.S3_ENDPOINT_URL:
            kwargs["endpoint_url"] = self._settings.S3_ENDPOINT_URL

        return boto3.client("s3", **kwargs)

    async def _upload_to_s3(self, file_path: str, s3_key: str, metadata: dict[str, str]) -> None:
        """上传文件到 S3。"""
        s3 = self._get_s3_client()
        s3.upload_file(
            file_path,
            self._settings.S3_ARCHIVE_BUCKET,
            s3_key,
            ExtraArgs={"Metadata": metadata},
        )
        logger.info(
            "文件已上传至 S3",
            bucket=self._settings.S3_ARCHIVE_BUCKET,
            key=s3_key,
            event_type="archive.s3_uploaded",
        )

    async def _upload_manifest(self, manifest: dict[str, Any], s3_key: str) -> None:
        """上传 manifest.json 到 S3。"""
        s3 = self._get_s3_client()
        s3.put_object(
            Bucket=self._settings.S3_ARCHIVE_BUCKET,
            Key=s3_key,
            Body=json.dumps(manifest, indent=2, default=str, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
        )

    @staticmethod
    def _build_manifest(
        partition_name: str,
        period_start: Any,
        period_end: Any,
        total_rows: int,
        original_bytes: int,
        compressed_bytes: int,
        sha256_hex: str,
    ) -> dict[str, Any]:
        """构建归档清单。"""
        ratio = round(original_bytes / compressed_bytes, 2) if compressed_bytes > 0 else 0
        return {
            "version": 1,
            "partition": partition_name,
            "period": {
                "start": str(period_start),
                "end": str(period_end),
            },
            "stats": {
                "total_rows": total_rows,
            },
            "archive": {
                "format": "parquet",
                "compression": "zstd (built-in)",
                "original_size_bytes": original_bytes,
                "compressed_size_bytes": compressed_bytes,
                "compression_ratio": ratio,
                "sha256": sha256_hex,
            },
            "archived_at": datetime.now(UTC).isoformat(),
            "archived_by": "texas-celery-worker",
        }

    # ════════════════════════════════════════════
    #  状态更新
    # ════════════════════════════════════════════

    async def _update_archive_status(
        self,
        archive_id: Any,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """更新归档记录状态。"""
        values: dict[str, Any] = {"status": status}
        if error_message:
            values["error_message"] = error_message
        if status == "completed":
            values["completed_at"] = datetime.now(UTC)

        async with self._main_sf() as session:
            await session.execute(
                update(ChatArchiveLog).where(ChatArchiveLog.id == archive_id).values(**values)
            )
            await session.commit()

    # ════════════════════════════════════════════
    #  归档数据查询
    # ════════════════════════════════════════════

    async def get_archive_logs(self, page: int = 1, page_size: int = 20) -> dict[str, Any]:
        """获取归档日志列表。"""
        async with self._main_sf() as session:
            count_stmt = select(func.count()).select_from(ChatArchiveLog)
            count_result = await session.execute(count_stmt)
            total = count_result.scalar() or 0

            stmt = (
                select(ChatArchiveLog)
                .order_by(ChatArchiveLog.period_start.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            result = await session.execute(stmt)
            items = []
            for row in result.scalars().all():
                items.append(
                    {
                        "id": str(row.id),
                        "partition_name": row.partition_name,
                        "period_start": str(row.period_start),
                        "period_end": str(row.period_end),
                        "total_rows": row.total_rows,
                        "original_bytes": row.original_bytes,
                        "compressed_bytes": row.compressed_bytes,
                        "s3_bucket": row.s3_bucket,
                        "s3_key": row.s3_key,
                        "status": row.status,
                        "error_message": row.error_message,
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                    }
                )

            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "pages": (total + page_size - 1) // page_size,
            }

    async def query_archived_messages(
        self,
        period_start: str,
        group_id: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """从 S3 归档中查询历史消息。"""
        # 查找归档记录
        from datetime import date as date_type

        import pyarrow.fs as pafs

        target_date = date_type.fromisoformat(period_start)

        async with self._main_sf() as session:
            stmt = select(ChatArchiveLog).where(
                ChatArchiveLog.period_start == target_date,
                ChatArchiveLog.status == "completed",
            )
            result = await session.execute(stmt)
            archive = result.scalars().first()

        if not archive:
            return []

        # 从 S3 读取 Parquet
        s3_kwargs: dict[str, Any] = {
            "region": self._settings.S3_REGION,
        }
        if self._settings.S3_ACCESS_KEY_ID:
            s3_kwargs["access_key"] = self._settings.S3_ACCESS_KEY_ID
            s3_kwargs["secret_key"] = self._settings.S3_SECRET_ACCESS_KEY
        if self._settings.S3_ENDPOINT_URL:
            s3_kwargs["endpoint_override"] = self._settings.S3_ENDPOINT_URL

        s3_fs = pafs.S3FileSystem(**s3_kwargs)
        s3_path = f"{archive.s3_bucket}/{archive.s3_key}"

        columns = [
            "id",
            "message_id",
            "message_type",
            "group_id",
            "user_id",
            "raw_message",
            "segments",
            "sender_nickname",
            "sender_card",
            "sender_role",
            "created_at",
        ]

        filters = None
        if group_id is not None:
            filters = [("group_id", "=", group_id)]

        try:
            table = pq.read_table(
                s3_path,
                filesystem=s3_fs,
                columns=columns,
                filters=filters,
            )
            # 取最后 limit 条
            if len(table) > limit:
                table = table.slice(len(table) - limit)

            rows: list[dict[str, Any]] = table.to_pylist()
            for row in rows:
                if isinstance(row.get("segments"), str):
                    row["segments"] = json.loads(row["segments"])
                if row.get("created_at"):
                    row["created_at"] = row["created_at"].isoformat()
            return rows
        except Exception:
            logger.exception(
                "读取归档数据失败",
                s3_path=s3_path,
                event_type="archive.query_error",
            )
            return []


# 为了 get_archive_logs 中的 func.count
from sqlalchemy import func  # noqa: E402
