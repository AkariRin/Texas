"""项目版本管理模块。"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _metadata_version


def get_version() -> str:
    """从包元数据获取项目版本，回退解析 pyproject.toml。

    优先使用 importlib.metadata（已通过 uv/pip 安装时生效）；
    未安装时（如直接 python -m 运行）则解析仓库根目录的 pyproject.toml。
    """
    try:
        return _metadata_version("Texas")
    except PackageNotFoundError:
        pass

    import re
    from pathlib import Path

    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    if pyproject.exists():
        m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(), re.MULTILINE)
        if m:
            return m.group(1)

    return "0.0.0-unknown"


def get_description() -> str:
    """从包元数据获取项目描述，回退解析 pyproject.toml。"""
    try:
        from importlib.metadata import metadata

        meta = metadata("Texas")
        desc = meta.get("Summary")
        if desc:
            return desc
    except PackageNotFoundError:
        pass

    import re
    from pathlib import Path

    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    if pyproject.exists():
        m = re.search(r'^description\s*=\s*"([^"]+)"', pyproject.read_text(), re.MULTILINE)
        if m:
            return m.group(1)

    return ""
