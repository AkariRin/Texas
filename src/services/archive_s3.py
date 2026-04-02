"""S3 上传服务 —— 封装 Parquet 文件和 manifest 的 S3 上传操作。"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

import structlog

from src.core.utils import SHANGHAI_TZ

if TYPE_CHECKING:
    from src.core.config import Settings

logger = structlog.get_logger()


class S3Uploader:
    """负责 S3 文件上传操作，与归档编排逻辑解耦。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _get_client(self) -> Any:
        """创建 S3 客户端。"""
        import boto3

        kwargs: dict[str, Any] = {
            "region_name": self._settings.S3_REGION,
        }
        if self._settings.S3_ACCESS_KEY_ID:
            kwargs["aws_access_key_id"] = self._settings.S3_ACCESS_KEY_ID
            kwargs["aws_secret_access_key"] = self._settings.S3_SECRET_ACCESS_KEY.get_secret_value()
        if self._settings.S3_ENDPOINT_URL:
            kwargs["endpoint_url"] = self._settings.S3_ENDPOINT_URL

        return boto3.client("s3", **kwargs)

    async def upload_file(self, file_path: str, s3_key: str, metadata: dict[str, str]) -> None:
        """上传文件到 S3。"""
        s3 = self._get_client()
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

    async def upload_manifest(self, manifest: dict[str, Any], s3_key: str) -> None:
        """上传 manifest.json 到 S3。"""
        s3 = self._get_client()
        s3.put_object(
            Bucket=self._settings.S3_ARCHIVE_BUCKET,
            Key=s3_key,
            Body=json.dumps(manifest, indent=2, default=str, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
        )

    @staticmethod
    def build_manifest(
        partition_name: str,
        period_start: date,
        period_end: date,
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
            "archived_at": datetime.now(SHANGHAI_TZ).isoformat(),
            "archived_by": "texas-celery-worker",
        }
