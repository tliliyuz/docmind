"""文件存储 — 抽象 StorageBackend + 本地磁盘实现，对齐 ARCHITECTURE.md §7.5"""
import asyncio
import os
import re
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from fastapi import UploadFile

from app.config import settings


def sanitize_filename(filename: str) -> str:
    """移除路径分隔符、空字节等危险字符，保留中文/字母/数字/常用标点"""
    name = os.path.basename(filename)
    name = name.replace("\x00", "")
    # 移除路径分隔符（Windows / Unix）
    name = name.replace("/", "_").replace("\\", "_")
    # 移除其他不安全字符，保留 Unicode（含中文）
    name = re.sub(r"[\x00-\x1f]", "", name)
    # 去除首尾空白和点号
    name = name.strip(". ")
    if not name:
        name = "unnamed"
    return name


def generate_stored_filename(original_filename: str) -> str:
    """生成存储用文件名：{8位uuid}_{安全文件名}"""
    safe = sanitize_filename(original_filename)
    short_uuid = uuid.uuid4().hex[:8]
    return f"{short_uuid}_{safe}"


class StorageBackend(ABC):
    """文件存储抽象基类，支持本地 / OSS 互换"""

    @abstractmethod
    async def save(self, file: UploadFile, kb_id: int, doc_id: int) -> str:
        """保存文件，返回存储路径"""
        ...

    @abstractmethod
    async def read(self, path: str) -> bytes:
        """读取文件内容"""
        ...

    @abstractmethod
    async def delete(self, path: str) -> None:
        """删除文件"""
        ...


class LocalStorage(StorageBackend):
    """本地磁盘存储，目录结构：uploads/{kb_id}/{doc_id}/{uuid}_{sanitized_filename}"""

    def __init__(self, base_dir: str = ""):
        self.base = Path(base_dir or settings.UPLOAD_DIR)

    def _get_dir(self, kb_id: int, doc_id: int) -> Path:
        return self.base / str(kb_id) / str(doc_id)

    async def save(self, file: UploadFile, kb_id: int, doc_id: int) -> str:
        stored_name = generate_stored_filename(file.filename or "unnamed")
        target_dir = self._get_dir(kb_id, doc_id)
        await asyncio.to_thread(target_dir.mkdir, parents=True, exist_ok=True)

        file_path = target_dir / stored_name
        content = await file.read()
        await asyncio.to_thread(file_path.write_bytes, content)
        # 重置文件指针位置，供后续可能的重复读取
        await file.seek(0)

        return str(file_path)

    async def read(self, path: str) -> bytes:
        return await asyncio.to_thread(Path(path).read_bytes)

    async def delete(self, path: str) -> None:
        file_path = Path(path)
        if await asyncio.to_thread(file_path.is_file):
            await asyncio.to_thread(file_path.unlink)
        # 尝试清理空目录（最多向上清理到知识库层级）
        for parent in [file_path.parent, file_path.parent.parent]:
            try:
                if await asyncio.to_thread(parent.is_dir) and not any(
                    await asyncio.to_thread(list, parent.iterdir())
                ):
                    await asyncio.to_thread(parent.rmdir)
            except OSError:
                break


# 全局单例
local_storage = LocalStorage()
