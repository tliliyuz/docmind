"""文件存储服务单元测试 — 覆盖文件名安全处理、存储/读取/删除、空目录清理

对齐 DATABASE.md / ARCHITECTURE.md §7.5:
- 目录结构: uploads/{kb_id}/{doc_id}/{uuid}_{sanitized_filename}
- 文件名安全: sanitize_filename 移除路径分隔符/空字节/控制字符，保留中文
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.storage import (
    LocalStorage,
    generate_stored_filename,
    sanitize_filename,
)


# ==================== sanitize_filename ====================


class TestSanitizeFilename:
    """文件名安全处理测试"""

    def test_普通文件名不变(self):
        assert sanitize_filename("入职指南.pdf") == "入职指南.pdf"

    def test_英文字母数字文件名不变(self):
        assert sanitize_filename("report_2024_v2.txt") == "report_2024_v2.txt"

    def test_路径分隔符替换为下划线_斜杠(self):
        """basename 先剥离目录部分，余下文件名中的 / 替换为 _"""
        result = sanitize_filename("a/b.pdf")
        assert "/" not in result

    def test_路径分隔符替换为下划线_反斜杠(self):
        """basename 先剥离目录部分，余下文件名中的 \\ 替换为 _"""
        result = sanitize_filename("a\\b.pdf")
        assert "\\" not in result

    def test_文件名内斜杠被替换为下划线(self):
        """basename 处理后在文件名内部的 / 应被替换"""
        # 构造一个 basename 不剥离但文件名内含 / 的场景
        # 实际上 Unix 文件名不能含 /，这里仅验证 sanitize 的安全网作用
        result = sanitize_filename("file/name.txt")
        assert "/" not in result

    def test_空字节移除(self):
        result = sanitize_filename("test\x00file.txt")
        assert "\x00" not in result
        assert "test" in result

    def test_控制字符移除(self):
        """ASCII 0x00-0x1f 的控制字符被移除"""
        result = sanitize_filename("file\x01\x02.txt")
        assert "\x01" not in result
        assert "\x02" not in result
        # 控制字符移除后 .txt 保留
        assert result.endswith(".txt")

    def test_保留中文字符(self):
        result = sanitize_filename("中文文件名测试.md")
        assert "中文文件名测试" in result

    def test_仅传递文件名不含路径(self):
        """os.path.basename 保证只取文件名部分"""
        result = sanitize_filename("/etc/passwd")
        assert result == "passwd"

    def test_去除首尾空白和点号(self):
        result = sanitize_filename("  file.txt  ")
        assert result == "file.txt"

    def test_去除首尾点号(self):
        result = sanitize_filename("...file.txt...")
        assert result == "file.txt"

    def test_空文件名返回unnamed(self):
        result = sanitize_filename("")
        assert result == "unnamed"

    def test_全空白文件名返回unnamed(self):
        result = sanitize_filename("   ")
        assert result == "unnamed"

    def test_全点号文件名返回unnamed(self):
        result = sanitize_filename("....")
        assert result == "unnamed"

    def test_含空格的合法文件名不变(self):
        result = sanitize_filename("入职 指南 v2.pdf")
        assert result == "入职 指南 v2.pdf"

    def test_含中文标点的文件名保留(self):
        result = sanitize_filename("（入职指南）第1版.pdf")
        assert result == "（入职指南）第1版.pdf"


# ==================== generate_stored_filename ====================


class TestGenerateStoredFilename:
    """存储文件名生成测试"""

    def test_格式为8位uuid_下划线_安全文件名(self):
        result = generate_stored_filename("入职指南.pdf")
        # {8位uuid}_{文件名}
        assert "_" in result
        parts = result.split("_", 1)
        assert len(parts) == 2
        assert len(parts[0]) == 8  # 8 位 uuid 前缀
        assert parts[1] == "入职指南.pdf"

    def test_危险字符被安全化后再拼接(self):
        result = generate_stored_filename("a/b.pdf")
        assert "/" not in result
        # basename 剥离 "a/" 后生成 "{uuid}_b.pdf"
        assert "_" in result
        assert result.endswith("b.pdf")

    def test_两次调用生成不同uuid前缀(self):
        r1 = generate_stored_filename("test.pdf")
        r2 = generate_stored_filename("test.pdf")
        # 极低概率相同（不同 uuid4 hex）
        assert r1.split("_")[0] != r2.split("_")[0]

    def test_uuid部分为16进制字符串(self):
        result = generate_stored_filename("doc.txt")
        uuid_part = result.split("_")[0]
        # 全 16 进制字符
        assert all(c in "0123456789abcdef" for c in uuid_part)


# ==================== LocalStorage ====================


class TestLocalStorage:
    """本地存储实现测试 — 使用 tempfile 临时目录"""

    @pytest.fixture
    def tmp_storage(self):
        """返回基于临时目录的 LocalStorage 实例"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalStorage(base_dir=tmpdir)
            yield storage

    @pytest.fixture
    def mock_upload_file(self):
        """创建 mock UploadFile"""
        file = MagicMock()
        file.filename = "测试文档.pdf"
        file.read = AsyncMock(return_value=b"hello docmind test content")
        file.seek = AsyncMock()
        return file

    # --- _get_dir ---

    def test_get_dir_返回正确路径(self, tmp_storage):
        d = tmp_storage._get_dir(kb_id=1, doc_id=5)
        assert d.parts[-2:] == ("1", "5")
        # 跨平台路径比较：使用 resolve 归一化
        assert str(d.resolve()).startswith(str(tmp_storage.base.resolve()))

    # --- save ---

    @pytest.mark.asyncio
    async def test_save_文件写入磁盘_内容正确(self, tmp_storage, mock_upload_file):
        path = await tmp_storage.save(mock_upload_file, kb_id=1, doc_id=5)

        assert os.path.exists(path)
        content = Path(path).read_bytes()
        assert content == b"hello docmind test content"

    @pytest.mark.asyncio
    async def test_save_返回路径符合目录结构(self, tmp_storage, mock_upload_file):
        path = await tmp_storage.save(mock_upload_file, kb_id=1, doc_id=5)

        # uploads/1/5/{uuid}_{sanitized_filename}
        assert "/1/5/" in path.replace("\\", "/")
        assert path.endswith("测试文档.pdf") or "测试文档" in path

    @pytest.mark.asyncio
    async def test_save_自动创建目录(self, tmp_storage, mock_upload_file):
        path = await tmp_storage.save(mock_upload_file, kb_id=2, doc_id=10)

        assert os.path.isdir(os.path.dirname(path))

    @pytest.mark.asyncio
    async def test_save_seek_reset_after_read(self, tmp_storage, mock_upload_file):
        await tmp_storage.save(mock_upload_file, kb_id=1, doc_id=1)
        mock_upload_file.seek.assert_called_once_with(0)

    @pytest.mark.asyncio
    async def test_save_两次同目录保存不冲突(self, tmp_storage):
        file1 = MagicMock()
        file1.filename = "a.pdf"
        file1.read = AsyncMock(return_value=b"aaa")
        file1.seek = AsyncMock()

        file2 = MagicMock()
        file2.filename = "b.pdf"
        file2.read = AsyncMock(return_value=b"bbb")
        file2.seek = AsyncMock()

        p1 = await tmp_storage.save(file1, kb_id=1, doc_id=1)
        p2 = await tmp_storage.save(file2, kb_id=1, doc_id=1)

        # 同一目录下两个文件，路径不同
        assert p1 != p2
        assert Path(p1).parent == Path(p2).parent
        assert Path(p1).read_bytes() == b"aaa"
        assert Path(p2).read_bytes() == b"bbb"

    @pytest.mark.asyncio
    async def test_save_无文件名时使用unnamed(self, tmp_storage):
        file = MagicMock()
        file.filename = ""
        file.read = AsyncMock(return_value=b"content")
        file.seek = AsyncMock()

        path = await tmp_storage.save(file, kb_id=1, doc_id=1)
        assert "unnamed" in os.path.basename(path)

    # --- read ---

    @pytest.mark.asyncio
    async def test_read_返回文件bytes(self, tmp_storage, mock_upload_file):
        path = await tmp_storage.save(mock_upload_file, kb_id=1, doc_id=1)

        content = await tmp_storage.read(path)
        assert content == b"hello docmind test content"
        assert isinstance(content, bytes)

    @pytest.mark.asyncio
    async def test_read_空文件(self, tmp_storage):
        # 手动创建空文件
        d = tmp_storage._get_dir(kb_id=1, doc_id=1)
        d.mkdir(parents=True, exist_ok=True)
        empty_path = d / "test_empty.txt"
        empty_path.write_bytes(b"")

        content = await tmp_storage.read(str(empty_path))
        assert content == b""

    @pytest.mark.asyncio
    async def test_read_不存在的文件抛出异常(self, tmp_storage):
        with pytest.raises(FileNotFoundError):
            await tmp_storage.read("/nonexistent/path/file.pdf")

    # --- delete ---

    @pytest.mark.asyncio
    async def test_delete_删除文件_文件不存在(self, tmp_storage, mock_upload_file):
        path = await tmp_storage.save(mock_upload_file, kb_id=1, doc_id=1)
        assert os.path.exists(path)

        await tmp_storage.delete(path)
        assert not os.path.exists(path)

    @pytest.mark.asyncio
    async def test_delete_不存在的路径不抛异常(self, tmp_storage):
        # 幂等操作，不抛异常
        await tmp_storage.delete("/nonexistent/path/file.pdf")

    @pytest.mark.asyncio
    async def test_delete_文件所在目录自动清理(self, tmp_storage, mock_upload_file):
        path = await tmp_storage.save(mock_upload_file, kb_id=1, doc_id=5)
        file_dir = os.path.dirname(path)
        assert os.path.isdir(file_dir)

        await tmp_storage.delete(path)

        # 目录为空应被清理
        assert not os.path.isdir(file_dir)

    @pytest.mark.asyncio
    async def test_delete_父目录为空也自动清理(self, tmp_storage, mock_upload_file):
        path = await tmp_storage.save(mock_upload_file, kb_id=3, doc_id=7)
        kb_dir = os.path.dirname(os.path.dirname(path))  # kb_id=3 的目录

        await tmp_storage.delete(path)

        # kb/3/7/ 和 kb/3/ 都被清理
        assert not os.path.isdir(kb_dir)

    @pytest.mark.asyncio
    async def test_delete_同目录有其他文件时保留目录(self, tmp_storage):
        # 保存两个文件到同一目录
        file1 = MagicMock()
        file1.filename = "a.pdf"
        file1.read = AsyncMock(return_value=b"aaa")
        file1.seek = AsyncMock()

        file2 = MagicMock()
        file2.filename = "b.pdf"
        file2.read = AsyncMock(return_value=b"bbb")
        file2.seek = AsyncMock()

        p1 = await tmp_storage.save(file1, kb_id=1, doc_id=1)
        p2 = await tmp_storage.save(file2, kb_id=1, doc_id=1)

        doc_dir = os.path.dirname(p1)

        # 删除一个文件
        await tmp_storage.delete(p1)
        assert not os.path.exists(p1)
        assert os.path.exists(p2)  # 另一个还在
        assert os.path.isdir(doc_dir)  # 目录还有文件，不清理

    # --- 边界情况 ---

    @pytest.mark.asyncio
    async def test_save_中文路径可正常读写(self, tmp_storage):
        file = MagicMock()
        file.filename = "入职指南（2024版）.pdf"
        file.read = AsyncMock(return_value="中文内容测试".encode("utf-8"))
        file.seek = AsyncMock()

        path = await tmp_storage.save(file, kb_id=1, doc_id=1)
        assert os.path.exists(path)

        content = await tmp_storage.read(path)
        assert "中文".encode("utf-8") in content

    @pytest.mark.asyncio
    async def test_save_不同kb_id隔离目录(self, tmp_storage):
        file1 = MagicMock()
        file1.filename = "test.pdf"
        file1.read = AsyncMock(return_value=b"kb1")
        file1.seek = AsyncMock()

        file2 = MagicMock()
        file2.filename = "test.pdf"
        file2.read = AsyncMock(return_value=b"kb2")
        file2.seek = AsyncMock()

        p1 = await tmp_storage.save(file1, kb_id=1, doc_id=1)
        p2 = await tmp_storage.save(file2, kb_id=2, doc_id=1)

        # 不同 kb_id = 不同目录
        assert Path(p1).parent != Path(p2).parent
