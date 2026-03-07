"""NapCat 多媒体消息的资源 URL 处理工具。"""

from __future__ import annotations

import base64
import re


def is_base64_url(url: str) -> bool:
    return url.startswith("base64://")


def is_http_url(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")


def is_file_url(url: str) -> bool:
    return url.startswith("file://")


def is_data_url(url: str) -> bool:
    return url.startswith("data:")


def detect_url_type(url: str) -> str:
    """检测资源 URL 的类型。

    返回以下之一：'base64'、'http'、'file'、'data'、'local'、'unknown'。
    """
    if is_base64_url(url):
        return "base64"
    if is_http_url(url):
        return "http"
    if is_file_url(url):
        return "file"
    if is_data_url(url):
        return "data"
    # 可能是本地路径
    if re.match(r"^[A-Za-z]:", url) or url.startswith("/"):
        return "local"
    return "unknown"


def base64_encode(data: bytes) -> str:
    """将字节编码为 base64:// URL 格式。"""
    return "base64://" + base64.b64encode(data).decode()


def base64_decode(url: str) -> bytes:
    """将 base64:// URL 解码为字节。"""
    if url.startswith("base64://"):
        url = url[9:]
    return base64.b64decode(url)


def data_url_decode(url: str) -> tuple[str, bytes]:
    """解码 data URL（data:mime;base64,...）。

    返回 (mime_type, bytes)。
    """
    match = re.match(r"^data:([^;]+);base64,(.+)$", url)
    if not match:
        raise ValueError(f"Invalid data URL: {url[:50]}...")
    mime_type = match.group(1)
    data = base64.b64decode(match.group(2))
    return mime_type, data
