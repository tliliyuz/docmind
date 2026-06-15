"""文档 Service 单元测试 — Mock DB session

测试 document_service.py 核心业务逻辑。
此前仅有 API 层序列化测试（test_document_api.py），service 函数全部被 patch() mock。
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, ANY, patch

import pytest
from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DocumentNameExistsException,
    DocumentNotFoundException,
    DocumentProcessingError,
    PermissionDeniedException,
    ReprocessFailedException,
    UnsupportedFileFormatException,
    FileSizeExceededException,
)
from app.config import settings
from app.models.document import Document
from app.models.chunk import Chunk
from app.models.enums import DocumentStatus
from app.models.knowledge_base import KnowledgeBase
from app.services.document_service import (
    ALLOWED_EXTENSIONS,
    _build_document_response,
    _check_kb_ownership,
    _validate_file,
    delete_document,
    get_document,
    get_document_chunks,
    list_documents,
    reprocess_document,
    upload_document,
)


# ============================================================
# Mock 工具
# ============================================================


def _make_scalar_result(value):
    result = MagicMock()
    result.scalar = MagicMock(return_value=value)
    return result


def _make_scalar_one_or_none_result(value):
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=value)
    return result


def _make_scalars_all_result(rows):
    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=list(rows))
    result = MagicMock()
    result.scalars = MagicMock(return_value=scalars_mock)
    return result


def _make_kb(kb_id=1, user_id=1, status="active",
             kb_uuid="kb-uuid-0001"):
    kb = KnowledgeBase(
        id=kb_id, name="测试KB", user_id=user_id, status=status,
        visibility="private", chunk_count=0, doc_count=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    # 手动设置 uuid（ORM 实例构造时不会自动生成 server_default）
    kb.uuid = kb_uuid
    return kb


def _make_doc(doc_id=1, kb_id=1, filename="test.pdf", status="completed",
              file_type="pdf", chunk_count=10, file_size=1000,
              doc_uuid="doc-uuid-0001", kb_uuid="kb-uuid-0001"):
    doc = Document(
        id=doc_id, kb_id=kb_id, filename=filename, file_type=file_type,
        status=status, chunk_count=chunk_count, file_size=file_size,
        file_path=f"uploads/{kb_id}/{doc_id}/test.pdf",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    # 手动设置 uuid（ORM 实例构造时不会自动生成 server_default）
    doc.uuid = doc_uuid
    # 关联 KB 对象以支持 doc.kb_uuid property
    kb = _make_kb(kb_id=kb_id, kb_uuid=kb_uuid)
    doc.knowledge_base = kb
    return doc


def _make_upload_file(filename="test.pdf", size=1000):
    """构造 mock UploadFile"""
    f = MagicMock(spec=UploadFile)
    f.filename = filename
    f.size = size
    f.read = AsyncMock(return_value=b"fake file content")
    return f


@pytest.fixture
def mock_db():
    session = AsyncMock(spec=AsyncSession)
    return session


# ============================================================
# _validate_file
# 技术债务：直接测试私有函数 _validate_file()，违反 CLAUDE.md「禁止直接测试
# `_` 前缀的私有方法」规范。保留现有测试（纯校验逻辑有工程价值），
# 后续应通过 upload_document() 公共 API 间接覆盖文件校验逻辑。
# ============================================================


class TestValidateFile:
    def test_允许的扩展名不抛异常(self):
        for ext in ["pdf", "docx", "md", "txt"]:
            f = _make_upload_file(f"doc.{ext}")
            _validate_file(f)  # 不抛异常

    def test_大写扩展名也接受(self):
        f = _make_upload_file("DOC.PDF")
        _validate_file(f)  # 不抛异常

    def test_不支持格式抛异常(self):
        f = _make_upload_file("virus.exe")
        with pytest.raises(UnsupportedFileFormatException) as exc:
            _validate_file(f)
        assert exc.value.error_code == "E2002"

    def test_无扩展名抛异常(self):
        f = _make_upload_file("noextension")
        with pytest.raises(UnsupportedFileFormatException):
            _validate_file(f)

    def test_文件名为None抛异常(self):
        f = _make_upload_file(None)
        with pytest.raises(UnsupportedFileFormatException):
            _validate_file(f)

    def test_超大文件抛异常(self):
        f = _make_upload_file("big.pdf", size=settings.UPLOAD_MAX_SIZE + 1)
        with pytest.raises(FileSizeExceededException) as exc:
            _validate_file(f)
        assert exc.value.error_code == "E2003"

    def test_文件size为None不检查大小(self):
        f = _make_upload_file("doc.pdf", size=None)
        _validate_file(f)  # 不抛异常


# ============================================================
# _build_document_response
# 技术债务：直接测试私有函数 _build_document_response()，违反 CLAUDE.md
# 「禁止直接测试 `_` 前缀的私有方法」规范。保留现有测试（转换逻辑有工程价值），
# 后续应通过 list_documents() / get_document() 公共 API 间接覆盖。
# ============================================================


class TestBuildDocumentResponse:
    def test_正常转换(self):
        doc = _make_doc(doc_id=5, filename="入职指南.pdf")
        resp = _build_document_response(doc)
        assert resp.uuid == "doc-uuid-0001"
        assert resp.filename == "入职指南.pdf"
        assert resp.file_type == "pdf"
        assert resp.status == "completed"


# ============================================================
# _check_kb_ownership
# 技术债务：直接测试私有函数 _check_kb_ownership()，违反 CLAUDE.md
# 「禁止直接测试 `_` 前缀的私有方法」规范。保留现有测试（权限校验边界
# 用例有工程价值），后续应通过 upload_document() / list_documents() 等公共 API
# 间接覆盖各权限分支（owner/non-owner/admin/owner_only）。
# ============================================================


class TestCheckKBOwnership:
    @pytest.mark.asyncio
    async def test_owner可操作(self, mock_db):
        kb = _make_kb(kb_id=1, user_id=1)
        mock_db.execute.return_value = _make_scalar_one_or_none_result(kb)

        await _check_kb_ownership(mock_db, 1, 1, "user")
        # 不抛异常即通过

    @pytest.mark.asyncio
    async def test_非owner被拒绝(self, mock_db):
        kb = _make_kb(kb_id=1, user_id=1)
        mock_db.execute.return_value = _make_scalar_one_or_none_result(kb)

        with pytest.raises(PermissionDeniedException):
            await _check_kb_ownership(mock_db, 1, 2, "user")

    @pytest.mark.asyncio
    async def test_admin可操作非owner的KB(self, mock_db):
        kb = _make_kb(kb_id=1, user_id=1)
        mock_db.execute.return_value = _make_scalar_one_or_none_result(kb)

        await _check_kb_ownership(mock_db, 1, 2, "admin")
        # 不抛异常

    @pytest.mark.asyncio
    async def test_owner_only模式admin也被拒绝(self, mock_db):
        """owner_only=True 时（上传/reprocess），admin 也不允许"""
        kb = _make_kb(kb_id=1, user_id=1)
        mock_db.execute.return_value = _make_scalar_one_or_none_result(kb)

        with pytest.raises(PermissionDeniedException):
            await _check_kb_ownership(mock_db, 1, 2, "admin", owner_only=True)

    @pytest.mark.asyncio
    async def test_owner_only模式owner可通过(self, mock_db):
        kb = _make_kb(kb_id=1, user_id=1)
        mock_db.execute.return_value = _make_scalar_one_or_none_result(kb)

        await _check_kb_ownership(mock_db, 1, 1, "user", owner_only=True)
        # 不抛异常


# ============================================================
# list_documents
# ============================================================


class TestListDocuments:
    @pytest.mark.asyncio
    async def test_正常列表(self, mock_db):
        """list_documents 返回分页文档列表"""
        kb = _make_kb()
        doc = _make_doc()
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            _make_scalar_one_or_none_result(kb),  # check_kb_active → get_kb: 查 KB
            _make_scalar_result(5),                # get_kb: _get_real_chunk_counts
            _make_scalar_result(1),                # COUNT total
            _make_scalars_all_result([doc]),       # data rows
        ]

        result = await list_documents(mock_db, kb_id=1, user_id=1, role="user")

        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].filename == "test.pdf"

    @pytest.mark.asyncio
    async def test_空列表(self, mock_db):
        kb = _make_kb()
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            _make_scalar_one_or_none_result(kb),
            _make_scalar_result(0),
            _make_scalar_result(0),
            _make_scalars_all_result([]),
        ]

        result = await list_documents(mock_db, kb_id=1, user_id=1, role="user")
        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_状态筛选(self, mock_db):
        """传入 status 参数筛选文档"""
        kb = _make_kb()
        doc = _make_doc(status="completed")
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            _make_scalar_one_or_none_result(kb),
            _make_scalar_result(0),
            _make_scalar_result(1),
            _make_scalars_all_result([doc]),
        ]

        result = await list_documents(
            mock_db, kb_id=1, user_id=1, role="user",
            status="completed",
        )
        assert result.total == 1

    @pytest.mark.asyncio
    async def test_文件名筛选(self, mock_db):
        """传入 filename 参数模糊搜索"""
        kb = _make_kb()
        doc = _make_doc(filename="入职指南.pdf")
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            _make_scalar_one_or_none_result(kb),
            _make_scalar_result(0),
            _make_scalar_result(1),
            _make_scalars_all_result([doc]),
        ]

        result = await list_documents(
            mock_db, kb_id=1, user_id=1, role="user",
            filename="入职",
        )
        assert result.total == 1


# ============================================================
# get_document
# ============================================================


class TestGetDocument:
    @pytest.mark.asyncio
    async def test_正常获取(self, mock_db):
        kb = _make_kb()
        doc = _make_doc(doc_id=5)
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            _make_scalar_one_or_none_result(kb),  # check_kb_active → get_kb: 查 KB
            _make_scalar_result(0),                # get_kb: _get_real_chunk_counts
            _make_scalar_one_or_none_result(doc),  # query doc
        ]

        result = await get_document(mock_db, doc_id=5, kb_id=1, user_id=1, role="user")
        assert result.uuid == "doc-uuid-0001"
        assert result.filename == "test.pdf"

    @pytest.mark.asyncio
    async def test_文档不存在(self, mock_db):
        kb = _make_kb()
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            _make_scalar_one_or_none_result(kb),
            _make_scalar_result(0),
            _make_scalar_one_or_none_result(None),
        ]

        with pytest.raises(DocumentNotFoundException) as exc:
            await get_document(mock_db, doc_id=999, kb_id=1, user_id=1, role="user")
        assert exc.value.error_code == "E2001"


# ============================================================
# get_document_chunks
# ============================================================


class TestGetDocumentChunks:
    @pytest.mark.asyncio
    async def test_正常获取分块(self, mock_db):
        kb = _make_kb()
        doc = _make_doc(doc_id=5)
        chunk = Chunk(id=1, doc_id=5, kb_id=1, chroma_id="c1",
                      content="测试分块内容", chunk_index=0, token_count=50)
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            _make_scalar_one_or_none_result(kb),   # check_kb_active → get_kb: 查 KB
            _make_scalar_result(0),                 # get_kb: _get_real_chunk_counts
            _make_scalar_one_or_none_result(doc),   # get_document
            _make_scalar_result(1),                  # COUNT chunks
            _make_scalars_all_result([chunk]),       # chunk rows
        ]

        result = await get_document_chunks(mock_db, doc_id=5, kb_id=1, user_id=1, role="user")
        assert result.total == 1
        assert len(result.items) == 1

    @pytest.mark.asyncio
    async def test_空分块列表(self, mock_db):
        kb = _make_kb()
        doc = _make_doc(doc_id=5, chunk_count=0)
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            _make_scalar_one_or_none_result(kb),
            _make_scalar_result(0),
            _make_scalar_one_or_none_result(doc),
            _make_scalar_result(0),
            _make_scalars_all_result([]),
        ]

        result = await get_document_chunks(mock_db, doc_id=5, kb_id=1, user_id=1, role="user")
        assert result.total == 0
        assert result.items == []


# ============================================================
# delete_document
# ============================================================


class TestDeleteDocument:
    @pytest.mark.asyncio
    async def test_删除成功(self, mock_db):
        """标记 status=deleting，commit 后分发 Celery 任务"""
        kb = _make_kb()
        doc = _make_doc(doc_id=5, status="completed")
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            _make_scalar_one_or_none_result(kb),   # check_kb_active → get_kb: 查 KB
            _make_scalar_result(0),                 # get_kb: _get_real_chunk_counts
            _make_scalar_one_or_none_result(doc),   # query doc
        ]
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        with patch("app.services.document_service._delete_doc_task") as mock_task:
            with patch("app.services.document_service.invalidate_bm25_cache_async", new_callable=AsyncMock):
                result = await delete_document(mock_db, doc_id=5, kb_id=1, user_id=1, role="user")

        assert result.doc_uuid == "doc-uuid-0001"
        assert doc.status == DocumentStatus.DELETING
        mock_db.commit.assert_called_once()
        mock_task.delay.assert_called_once_with(5)

    @pytest.mark.asyncio
    async def test_文档不存在(self, mock_db):
        kb = _make_kb()
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            _make_scalar_one_or_none_result(kb),
            _make_scalar_result(0),
            _make_scalar_one_or_none_result(None),
        ]

        with pytest.raises(DocumentNotFoundException):
            await delete_document(mock_db, doc_id=999, kb_id=1, user_id=1, role="user")

    @pytest.mark.asyncio
    async def test_正在删除的文档拒绝重复删除(self, mock_db):
        """status=deleting 的文档不允许重复删除"""
        kb = _make_kb()
        doc = _make_doc(doc_id=5, status="deleting")
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            _make_scalar_one_or_none_result(kb),
            _make_scalar_result(0),
            _make_scalar_one_or_none_result(doc),
        ]

        with pytest.raises(DocumentProcessingError) as exc:
            await delete_document(mock_db, doc_id=5, kb_id=1, user_id=1, role="user")
        assert exc.value.error_code == "E2011"


# ============================================================
# reprocess_document
# ============================================================


class TestReprocessDocument:
    @pytest.mark.asyncio
    async def test_重新处理失败状态文档(self, mock_db):
        """failed 状态的文档可以重新处理"""
        kb = _make_kb()
        doc = _make_doc(doc_id=5, status="failed")
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            _make_scalar_one_or_none_result(kb),   # check_kb_active → get_kb: 查 KB
            _make_scalar_result(0),                 # get_kb: _get_real_chunk_counts
            _make_scalar_one_or_none_result(doc),   # query doc
        ]
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        with patch("app.services.document_service._ingest_doc_task") as mock_task:
            with patch("app.services.document_service.invalidate_bm25_cache_async", new_callable=AsyncMock):
                result = await reprocess_document(mock_db, doc_id=5, kb_id=1, user_id=1, role="user")

        assert result.doc_uuid == "doc-uuid-0001"
        assert result.status == "uploaded"
        mock_task.delay.assert_called_once()

    @pytest.mark.asyncio
    async def test_completed状态拒绝重新处理(self, mock_db):
        """completed 状态不是允许 reprocess 的状态"""
        kb = _make_kb()
        doc = _make_doc(doc_id=5, status="completed")
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            _make_scalar_one_or_none_result(kb),
            _make_scalar_result(0),
            _make_scalar_one_or_none_result(doc),
        ]

        with pytest.raises(ReprocessFailedException) as exc:
            await reprocess_document(mock_db, doc_id=5, kb_id=1, user_id=1, role="user")
        assert exc.value.error_code == "E2010"


# ============================================================
# upload_document — 基础路径
# ============================================================


class TestUploadDocument:
    @pytest.mark.asyncio
    async def test_权限校验失败阻止上传(self, mock_db):
        """上传前先检查 KB 所有权（owner_only=True），非 owner 拒绝"""
        kb = _make_kb(kb_id=1, user_id=99)  # owner 是 99，不是当前用户
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            _make_scalar_one_or_none_result(kb),    # check_kb_active → get_kb: 查 KB
            _make_scalar_result(0),                  # get_kb: _get_real_chunk_counts
        ]

        f = _make_upload_file("doc.pdf", 1000)
        # _check_kb_ownership 抛 PermissionDeniedException（user_id=1 ≠ owner=99）
        with pytest.raises(PermissionDeniedException):
            await upload_document(mock_db, kb_id=1, user_id=1, role="user", file=f)

    @pytest.mark.asyncio
    async def test_同名终态文档不force则抛异常(self, mock_db):
        """同名 completed 文档存在，不传 force → DocumentNameExistsException"""
        kb = _make_kb(kb_id=1, user_id=1)
        existing = _make_doc(doc_id=5, filename="已存在.pdf", status="completed")
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            _make_scalar_one_or_none_result(kb),
            _make_scalar_result(0),
            _make_scalar_one_or_none_result(existing),
        ]

        f = _make_upload_file("已存在.pdf", 1000)
        with pytest.raises(DocumentNameExistsException) as exc:
            await upload_document(mock_db, kb_id=1, user_id=1, role="user", file=f, force=False)
        assert exc.value.error_code == "E2013"

    @pytest.mark.asyncio
    async def test_不支持格式拒绝(self, mock_db):
        """上传 .exe 直接拒绝，不查 DB"""
        f = _make_upload_file("virus.exe")
        with pytest.raises(UnsupportedFileFormatException):
            await upload_document(mock_db, kb_id=1, user_id=1, role="user", file=f)
        # DB 不应被访问
        mock_db.execute.assert_not_called()
