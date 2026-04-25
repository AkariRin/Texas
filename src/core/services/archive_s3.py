"""S3 上传服务 —— 封装 Parquet 文件和 manifest 的 S3 上传操作。"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Self

import structlog
from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.utils import SHANGHAI_TZ

logger = structlog.get_logger()


class S3Settings(BaseSettings):
    """S3 归档配置（就近定义，env 变量名与全局 Settings 保持一致）。"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True
    )

    S3_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: SecretStr = SecretStr("")
    S3_REGION: str = "us-east-1"
    S3_ARCHIVE_BUCKET: str = "texas-chat-archive"
    S3_ARCHIVE_PREFIX: str = "v1"

    @model_validator(mode="after")
    def _require_secret_when_key_id_set(self) -> Self:
        if self.S3_ACCESS_KEY_ID and not self.S3_SECRET_ACCESS_KEY.get_secret_value():
            raise ValueError("S3_ACCESS_KEY_ID 已设置，但 S3_SECRET_ACCESS_KEY 为空")
        return self


class S3Uploader:
    """负责 S3 文件上传操作，与归档编排逻辑解耦。"""

    def __init__(self, settings: S3Settings) -> None:
        self._settings = settings

    def _get_client(self) -> Any:  # boto3 无官方类型存根，返回 Any 为已知限制
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
