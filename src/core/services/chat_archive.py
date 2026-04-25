"""聊天记录归档服务 —— 编排冷数据归档流程（发现分区 → 导出 → 上传 S3 → 清理）。"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import func, select, text, update
from sqlalchemy.sql import quoted_name

from src.core.services.archive_exporter import (
    _PARTITION_NAME_RE,
    ChatArchiveSettings,
    ParquetExporter,
)
from src.core.services.archive_s3 import S3Settings, S3Uploader
from src.core.utils import SHANGHAI_TZ
from src.core.utils.helpers import ceil_div
from src.models.chat_archive import ChatArchiveLog
from src.models.enums import ArchiveStatus

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = structlog.get_logger()


class ArchiveService:
    """聊天记录归档编排服务 —— 协调分区发现、导出、上传和状态更新。"""

    def __init__(
        self,
        chat_session_factory: async_sessionmaker[AsyncSession],
        main_session_factory: async_sessionmaker[AsyncSession],
        archive_settings: ChatArchiveSettings,
        s3_settings: S3Settings,
    ) -> None:
        self._chat_sf = chat_session_factory
        self._main_sf = main_session_factory
        self._archive_settings = archive_settings
        self._s3_settings = s3_settings
        self._exporter = ParquetExporter(chat_session_factory, archive_settings)
        self._uploader = S3Uploader(s3_settings)

    # ════════════════════════════════════════════
    #  分区管理
    # ════════════════════════════════════════════

    async def ensure_partitions(self) -> dict[str, str]:
        """确保当月和下月的分区存在。"""
        async with self._chat_sf() as session:
            await session.execute(text("SELECT chat.create_monthly_partition(CURRENT_DATE)"))
            next_month_sql = (
                "SELECT chat.create_monthly_partition((CURRENT_DATE + INTERVAL '1 month')::DATE)"
            )
            await session.execute(text(next_month_sql))
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
            if not _PARTITION_NAME_RE.match(partition_name):
                raise ValueError(f"非法分区名: {partition_name!r}，格式须为 chat_history_YYYY_MM")
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
        retention = self._archive_settings.CHAT_ARCHIVE_RETENTION_MONTHS

        # 计算截止年月字符串，格式与分区名后缀一致（如 2024_01）
        cutoff = datetime.now(SHANGHAI_TZ) - timedelta(days=retention * 30)
        cutoff_suffix = cutoff.strftime("%Y_%m")

        async with self._chat_sf() as chat_session:
            # 直接在 SQL 中过滤超过保留期的分区，避免全量加载到内存
            result = await chat_session.execute(
                text("""
                    SELECT c.relname AS partition_name
                    FROM pg_inherits i
                    JOIN pg_class c ON c.oid = i.inhrelid
                    JOIN pg_class p ON p.oid = i.inhparent
                    JOIN pg_namespace n ON n.oid = p.relnamespace
                    WHERE n.nspname = 'chat'
                      AND p.relname = 'chat_history'
                      AND replace(c.relname, 'chat_history_', '') < :cutoff_suffix
                    ORDER BY c.relname
                """),
                {"cutoff_suffix": cutoff_suffix},
            )
            archivable = [row[0] for row in result.all()]

        # 排除已归档的分区
        if archivable:
            async with self._main_sf() as main_session:
                existing = await main_session.execute(
                    select(ChatArchiveLog.partition_name).where(
                        ChatArchiveLog.partition_name.in_(archivable),
                        ChatArchiveLog.status == ArchiveStatus.completed,
                    )
                )
                already_archived = {row[0] for row in existing.all()}
                archivable = [p for p in archivable if p not in already_archived]

        return archivable

    async def _archive_partition(self, partition_name: str) -> dict[str, Any]:
        """归档单个分区的完整流程。"""
        # 纵深防御：无论来源均强制校验分区名格式
        if not _PARTITION_NAME_RE.match(partition_name):
            raise ValueError(f"非法分区名: {partition_name!r}，格式须为 chat_history_YYYY_MM")
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
            s3_bucket=self._s3_settings.S3_ARCHIVE_BUCKET,
            s3_key="",
            s3_sha256="",
            status=ArchiveStatus.pending,
        )
        async with self._main_sf() as session:
            session.add(archive_log)
            await session.commit()
            archive_id = archive_log.id

        try:
            # ③ 导出 → status = 'exporting'
            await self._update_archive_status(archive_id, ArchiveStatus.exporting)

            with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
                tmp_path = tmp.name

            try:
                (
                    total_rows,
                    original_bytes,
                    compressed_bytes,
                    sha256_hex,
                ) = await self._exporter.export_partition(partition_name, tmp_path)

                if total_rows == 0:
                    await self._update_archive_status(
                        archive_id, ArchiveStatus.completed, error_message="分区为空，跳过"
                    )
                    return {"partition": partition_name, "status": "empty", "rows": 0}

                # ④ 上传 S3 → status = 'uploading'
                await self._update_archive_status(archive_id, ArchiveStatus.uploading)

                s3_key = (
                    f"{self._s3_settings.S3_ARCHIVE_PREFIX}"
                    f"/{year:04d}/{month:02d}/{partition_name}.parquet"
                )
                await self._uploader.upload_file(
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
                manifest = S3Uploader.build_manifest(
                    partition_name,
                    period_start,
                    period_end,
                    total_rows,
                    original_bytes,
                    compressed_bytes,
                    sha256_hex,
                )
                manifest_key = s3_key.replace(".parquet", ".manifest.json")
                await self._uploader.upload_manifest(manifest, manifest_key)

            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

            # ⑤ 校验 → status = 'uploaded'
            await self._update_archive_status(archive_id, ArchiveStatus.uploaded)

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
            # 使用 quoted_name 对标识符进行引号转义，防止 SQL 注入（纵深防御）
            safe_name = str(quoted_name(partition_name, quote=True))
            async with self._chat_sf() as session:
                await session.execute(
                    text(f"ALTER TABLE chat.chat_history DETACH PARTITION chat.{safe_name}")
                )
                await session.execute(text(f"DROP TABLE chat.{safe_name}"))
                await session.commit()

            await self._update_archive_status(archive_id, ArchiveStatus.partition_dropped)

            # ⑦ 完成
            async with self._main_sf() as session:
                await session.execute(
                    update(ChatArchiveLog)
                    .where(ChatArchiveLog.id == archive_id)
                    .values(status=ArchiveStatus.completed, completed_at=datetime.now(SHANGHAI_TZ))
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
            await self._update_archive_status(
                archive_id, ArchiveStatus.failed, error_message=str(e)
            )
            raise

    # ════════════════════════════════════════════
    #  状态更新
    # ════════════════════════════════════════════

    async def _update_archive_status(
        self,
        archive_id: uuid.UUID,
        status: ArchiveStatus,
        error_message: str | None = None,
    ) -> None:
        """更新归档记录状态。"""
        values: dict[str, Any] = {"status": status}
        if error_message:
            values["error_message"] = error_message
        if status == ArchiveStatus.completed:
            values["completed_at"] = datetime.now(SHANGHAI_TZ)

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
                "pages": ceil_div(total, page_size),
            }

    async def query_archived_messages(
        self,
        period_start: str,
        group_id: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """从 S3 归档中查询历史消息。"""
        import json
        from datetime import date as date_type

        import pyarrow.fs as pafs
        import pyarrow.parquet as pq

        target_date = date_type.fromisoformat(period_start)

        async with self._main_sf() as session:
            stmt = select(ChatArchiveLog).where(
                ChatArchiveLog.period_start == target_date,
                ChatArchiveLog.status == ArchiveStatus.completed,
            )
            result = await session.execute(stmt)
            archive = result.scalars().first()

        if not archive:
            return []

        # 从 S3 读取 Parquet
        s3_kwargs: dict[str, Any] = {
            "region": self._s3_settings.S3_REGION,
        }
        if self._s3_settings.S3_ACCESS_KEY_ID:
            s3_kwargs["access_key"] = self._s3_settings.S3_ACCESS_KEY_ID
            s3_kwargs["secret_key"] = self._s3_settings.S3_SECRET_ACCESS_KEY.get_secret_value()
        if self._s3_settings.S3_ENDPOINT_URL:
            s3_kwargs["endpoint_override"] = self._s3_settings.S3_ENDPOINT_URL

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
