"""文件操作扩展 API —— 群文件/私聊文件元数据管理（不含本地流式操作）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from src.core.protocol.models.api import APIResponse


class FileAPIMixin:
    """提供群文件和私聊文件元数据操作的混入类。

    设计用于混入 BotAPI，不包含本地文件流保存接口。
    """

    _call: Callable[..., Coroutine[Any, Any, APIResponse]]

    async def delete_group_file(self, group_id: int, file_id: str, busid: int) -> APIResponse:
        """删除群文件。"""
        return await self._call(
            "delete_group_file",
            {"group_id": group_id, "file_id": file_id, "busid": busid},
        )

    async def create_group_file_folder(self, group_id: int, name: str) -> APIResponse:
        """创建群文件文件夹。"""
        return await self._call(
            "create_group_file_folder",
            {"group_id": group_id, "name": name},
        )

    async def delete_group_folder(self, group_id: int, folder_id: str) -> APIResponse:
        """删除群文件文件夹。"""
        return await self._call(
            "delete_group_folder",
            {"group_id": group_id, "folder_id": folder_id},
        )

    async def get_group_files_by_folder(self, group_id: int, folder_id: str) -> APIResponse:
        """获取指定文件夹内的群文件列表。"""
        return await self._call(
            "get_group_files_by_folder",
            {"group_id": group_id, "folder_id": folder_id},
        )

    async def move_group_file(self, group_id: int, file_id: str, target_dir: str) -> APIResponse:
        """移动群文件到指定目录。"""
        return await self._call(
            "move_group_file",
            {"group_id": group_id, "file_id": file_id, "target_dir": target_dir},
        )

    async def trans_group_file(
        self, group_id: int, file_id: str, target_group_id: int
    ) -> APIResponse:
        """将群文件转发至另一个群。"""
        return await self._call(
            "trans_group_file",
            {
                "group_id": group_id,
                "file_id": file_id,
                "target_group_id": target_group_id,
            },
        )

    async def rename_group_file(
        self,
        group_id: int,
        file_id: str,
        current_parent_directory: str,
        new_name: str,
    ) -> APIResponse:
        """重命名群文件。"""
        return await self._call(
            "rename_group_file",
            {
                "group_id": group_id,
                "file_id": file_id,
                "current_parent_directory": current_parent_directory,
                "new_name": new_name,
            },
        )

    async def get_private_file_url(self, user_id: int, file_id: str) -> APIResponse:
        """获取私聊文件下载链接。"""
        return await self._call(
            "get_private_file_url",
            {"user_id": user_id, "file_id": file_id},
        )

    async def get_file(self, file_id: str) -> APIResponse:
        """获取文件信息（通用）。"""
        return await self._call("get_file", {"file_id": file_id})
