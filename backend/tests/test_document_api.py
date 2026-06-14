"""文档 API 接口测试 — 覆盖上传/批量上传/列表/详情/分块/删除/重新处理 + 错误码"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import (
    DocumentNameExistsException,
    DocumentNotFoundException,
    DocumentProcessingError,
    FileSizeExceededException,
    ForceOverrideConflictException,
    PermissionDeniedException,
    ReprocessFailedException,
    StorageErrorException,
    UnsupportedFileFormatException,
    KnowledgeBaseNotFoundException,
)
from app.models.enums import DocumentStatus
from app.schemas.document import (
    DocumentBatchUploadFailedItem,
    DocumentBatchUploadItem,
    DocumentBatchUploadResponse,
    DocumentChunkListResponse,
    DocumentChunkResponse,
    DocumentDeleteResponse,
    DocumentListResponse,
    DocumentReprocessResponse,
    DocumentResponse,
    DocumentUploadResponse,
)


# 测试用 UUID 常量
KB_UUID = "11111111-1111-4111-8111-111111111111"
KB_UUID_999 = "99999999-9999-4999-8999-999999999999"
DOC_UUID = "22222222-2222-4222-8222-222222222222"
DOC_UUID_2 = "33333333-3333-4333-8333-333333333333"
DOC_UUID_999 = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def _uuid_to_id_side_effect(db, model_class, uuid_str):
    """模拟 resolve_uuid_to_id：UUID 字符串 → integer ID"""
    from app.core.uuid_helpers import _get_not_found_exception
    _map = {
        KB_UUID: 1,
        KB_UUID_999: 999,
        DOC_UUID: 5,
        DOC_UUID_2: 2,
        DOC_UUID_999: 999,
    }
    if uuid_str not in _map:
        raise _get_not_found_exception(model_class)(uuid_str)
    return _map[uuid_str]


def _make_upload_response(doc_uuid=DOC_UUID, kb_uuid=KB_UUID, filename="test.pdf",
                           file_type="pdf", file_size=1024, status=DocumentStatus.UPLOADED):
    return DocumentUploadResponse(
        uuid=doc_uuid, kb_uuid=kb_uuid, filename=filename,
        file_type=file_type, file_size=file_size, status=status,
    )


def _make_doc_response(doc_uuid=DOC_UUID, kb_uuid=KB_UUID, filename="test.pdf", file_type="pdf",
                        file_size=1024, status=DocumentStatus.COMPLETED,
                        chunk_count=10, error_msg=None):
    return DocumentResponse(
        uuid=doc_uuid, kb_uuid=kb_uuid, filename=filename, file_type=file_type,
        file_size=file_size, status=status, chunk_count=chunk_count,
        error_msg=error_msg,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )


def _make_list_data(total=1, page=1, page_size=20, items=None):
    if items is None:
        items = [_make_doc_response()]
    return DocumentListResponse(total=total, page=page, page_size=page_size, items=items)


def _make_delete_data(doc_uuid=DOC_UUID, status=DocumentStatus.DELETING):
    return DocumentDeleteResponse(doc_uuid=doc_uuid, status=status)


def _make_reprocess_data(doc_uuid=DOC_UUID, status=DocumentStatus.UPLOADED):
    return DocumentReprocessResponse(doc_uuid=doc_uuid, status=status)


def _make_chunk_response(chunk_id=1, chunk_index=0, preview="测试内容",
                          token_count=50, metadata=None):
    return DocumentChunkResponse(
        id=chunk_id, chunk_index=chunk_index, preview=preview,
        token_count=token_count, metadata=metadata,
    )


def _make_chunk_list_data(total=1, page=1, page_size=20, items=None):
    if items is None:
        items = [_make_chunk_response()]
    return DocumentChunkListResponse(total=total, page=page, page_size=page_size, items=items)


# ==================== POST /{kb_id}/documents — 文档上传 ====================

class TestUploadDocument:
    """POST /api/knowledge-bases/{kb_id}/documents — 文档上传（multipart）"""

    @pytest.mark.asyncio
    async def test_upload_success(self, async_client, auth_headers):
        """A3.1: 正常上传 PDF"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.upload_document", new_callable=AsyncMock) as mock:
                mock.return_value = _make_upload_response(filename="入职指南.pdf")

                response = await async_client.post(
                    f"/api/knowledge-bases/{KB_UUID}/documents",
                    files={"file": ("入职指南.pdf", b"fake pdf content", "application/pdf")},
                    data={"force": "false"},
                    headers=auth_headers,
                )

        assert response.status_code == 201
        body = response.json()
        assert body["code"] == "0"
        assert body["message"] == "文档上传成功，已加入处理队列"
        assert body["data"]["uuid"] == DOC_UUID
        assert body["data"]["kb_uuid"] == KB_UUID
        assert body["data"]["filename"] == "入职指南.pdf"
        assert body["data"]["file_type"] == "pdf"
        assert body["data"]["status"] == "uploaded"

    @pytest.mark.asyncio
    async def test_upload_duplicate_filename(self, async_client, auth_headers):
        """A3.2: 同名文件上传 → 409 E2013"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.upload_document", new_callable=AsyncMock) as mock:
                mock.side_effect = DocumentNameExistsException(
                    "文档 '入职指南.pdf' 已存在（kb_id=1），使用 force=true 可覆盖"
                )

                response = await async_client.post(
                    f"/api/knowledge-bases/{KB_UUID}/documents",
                    files={"file": ("入职指南.pdf", b"fake content", "application/pdf")},
                    headers=auth_headers,
                )

        assert response.status_code == 409
        body = response.json()
        assert body["code"] == "E2013"
        assert body["message"] == "文档名称已存在"

    @pytest.mark.asyncio
    async def test_upload_force_override(self, async_client, auth_headers):
        """A3.3: force=true 覆盖终态文档 → 201"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.upload_document", new_callable=AsyncMock) as mock:
                mock.return_value = _make_upload_response(
                    doc_uuid=DOC_UUID_2, filename="入职指南.pdf", status=DocumentStatus.UPLOADED
                )

                response = await async_client.post(
                    f"/api/knowledge-bases/{KB_UUID}/documents",
                    files={"file": ("入职指南.pdf", b"new content", "application/pdf")},
                    data={"force": "true"},
                    headers=auth_headers,
                )

        assert response.status_code == 201
        body = response.json()
        assert body["code"] == "0"
        assert body["data"]["status"] == "uploaded"

    @pytest.mark.asyncio
    async def test_upload_force_override_conflict(self, async_client, auth_headers):
        """force=true 但旧文档仍在处理中 → 409 E2012"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.upload_document", new_callable=AsyncMock) as mock:
                mock.side_effect = ForceOverrideConflictException(
                    "文档 '入职指南.pdf' 正在处理中（状态：parsing），无法覆盖"
                )

                response = await async_client.post(
                    f"/api/knowledge-bases/{KB_UUID}/documents",
                    files={"file": ("入职指南.pdf", b"new content", "application/pdf")},
                    data={"force": "true"},
                    headers=auth_headers,
                )

        assert response.status_code == 409
        body = response.json()
        assert body["code"] == "E2012"
        assert body["message"] == "旧文档仍在处理中，无法覆盖"

    @pytest.mark.asyncio
    async def test_upload_document_processing(self, async_client, auth_headers):
        """文档处理中时上传同名文件（非 force）→ 409 E2011"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.upload_document", new_callable=AsyncMock) as mock:
                mock.side_effect = DocumentProcessingError(
                    "文档 '入职指南.pdf' 正在处理中（状态：parsing），请等待处理完成"
                )

                response = await async_client.post(
                    f"/api/knowledge-bases/{KB_UUID}/documents",
                    files={"file": ("入职指南.pdf", b"content", "application/pdf")},
                    headers=auth_headers,
                )

        assert response.status_code == 409
        body = response.json()
        assert body["code"] == "E2011"
        assert body["message"] == "文档正在处理中"

    @pytest.mark.asyncio
    async def test_upload_unsupported_format(self, async_client, auth_headers):
        """A3.4: 不支持的文件格式 → 415 E2002"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.upload_document", new_callable=AsyncMock) as mock:
                mock.side_effect = UnsupportedFileFormatException("exe")

                response = await async_client.post(
                    f"/api/knowledge-bases/{KB_UUID}/documents",
                    files={"file": ("virus.exe", b"malware", "application/x-msdownload")},
                    headers=auth_headers,
                )

        assert response.status_code == 415
        body = response.json()
        assert body["code"] == "E2002"
        assert body["message"] == "文件格式不支持"

    @pytest.mark.asyncio
    async def test_upload_file_too_large(self, async_client, auth_headers):
        """A3.5: 文件大小超限 → 400 E2003"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.upload_document", new_callable=AsyncMock) as mock:
                mock.side_effect = FileSizeExceededException()

                response = await async_client.post(
                    f"/api/knowledge-bases/{KB_UUID}/documents",
                    files={"file": ("large.pdf", b"x" * 100, "application/pdf")},
                    headers=auth_headers,
                )

        assert response.status_code == 400
        body = response.json()
        assert body["code"] == "E2003"
        assert body["message"] == "文件大小超限"

    @pytest.mark.asyncio
    async def test_upload_kb_not_found(self, async_client, auth_headers):
        """知识库不存在 → 404 E1001"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.upload_document", new_callable=AsyncMock) as mock:
                mock.side_effect = KnowledgeBaseNotFoundException(999)

                response = await async_client.post(
                    f"/api/knowledge-bases/{KB_UUID_999}/documents",
                    files={"file": ("test.pdf", b"content", "application/pdf")},
                    headers=auth_headers,
                )

        assert response.status_code == 404
        body = response.json()
        assert body["code"] == "E1001"
        assert body["message"] == "知识库不存在"

    @pytest.mark.asyncio
    async def test_upload_permission_denied(self, async_client, auth_headers):
        """非 owner 且非 admin 上传 → 403 E5005"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.upload_document", new_callable=AsyncMock) as mock:
                mock.side_effect = PermissionDeniedException()

                response = await async_client.post(
                    f"/api/knowledge-bases/{KB_UUID}/documents",
                    files={"file": ("test.pdf", b"content", "application/pdf")},
                    headers=auth_headers,
                )

        assert response.status_code == 403
        body = response.json()
        assert body["code"] == "E5005"
        assert body["message"] == "无权限执行此操作"

    @pytest.mark.asyncio
    async def test_upload_no_auth(self, async_client):
        """未登录上传 → 401 E5004"""
        response = await async_client.post(
            f"/api/knowledge-bases/{KB_UUID}/documents",
            files={"file": ("test.pdf", b"content", "application/pdf")},
        )

        assert response.status_code == 401
        assert response.json()["code"] == "E5004"

    @pytest.mark.asyncio
    async def test_upload_admin_denied(self, async_client, admin_auth_headers):
        """admin 不能上传到非自己创建的知识库（上传仅 owner）"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.upload_document", new_callable=AsyncMock) as mock:
                mock.side_effect = PermissionDeniedException()

                response = await async_client.post(
                    f"/api/knowledge-bases/{KB_UUID}/documents",
                    files={"file": ("admin_doc.pdf", b"content", "application/pdf")},
                    headers=admin_auth_headers,
                )

        assert response.status_code == 403
        assert response.json()["code"] == "E5005"

    @pytest.mark.asyncio
    async def test_upload_md_and_txt_accepted(self, async_client, auth_headers):
        """.md 和 .txt 格式也被接受"""
        for ext in ("md", "txt"):
            with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                       side_effect=_uuid_to_id_side_effect):
                with patch("app.api.document.upload_document", new_callable=AsyncMock) as mock:
                    mock.return_value = _make_upload_response(
                        filename=f"doc.{ext}", file_type=ext
                    )

                    response = await async_client.post(
                        f"/api/knowledge-bases/{KB_UUID}/documents",
                        files={"file": (f"doc.{ext}", b"content", "text/plain")},
                        headers=auth_headers,
                    )

            assert response.status_code == 201


# ==================== POST /{kb_id}/documents/batch-upload — 批量上传 ====================

class TestBatchUploadDocuments:
    """POST /api/knowledge-bases/{kb_id}/documents/batch-upload"""

    @pytest.mark.asyncio
    async def test_batch_upload_all_success(self, async_client, auth_headers):
        """批量上传全部成功"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.batch_upload_documents", new_callable=AsyncMock) as mock:
                mock.return_value = DocumentBatchUploadResponse(
                    success=[
                        DocumentBatchUploadItem(uuid=DOC_UUID, filename="a.pdf", status=DocumentStatus.UPLOADED),
                        DocumentBatchUploadItem(uuid=DOC_UUID_2, filename="b.md", status=DocumentStatus.UPLOADED),
                    ],
                    failed=[],
                )

                response = await async_client.post(
                    f"/api/knowledge-bases/{KB_UUID}/documents/batch-upload",
                    files=[
                        ("files", ("a.pdf", b"content1", "application/pdf")),
                        ("files", ("b.md", b"content2", "text/markdown")),
                    ],
                    headers=auth_headers,
                )

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "0"
        assert body["message"] == "批量上传完成（2 个文件，成功 2 个）"
        assert len(body["data"]["success"]) == 2
        assert len(body["data"]["failed"]) == 0
        assert body["data"]["success"][0]["filename"] == "a.pdf"

    @pytest.mark.asyncio
    async def test_batch_upload_partial_failure(self, async_client, auth_headers):
        """批量上传部分失败"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.batch_upload_documents", new_callable=AsyncMock) as mock:
                mock.return_value = DocumentBatchUploadResponse(
                    success=[
                        DocumentBatchUploadItem(uuid=DOC_UUID, filename="a.pdf", status=DocumentStatus.UPLOADED),
                    ],
                    failed=[
                        DocumentBatchUploadFailedItem(
                            filename="旧文档.doc",
                            reason="E2002: 不支持 .doc 格式，请先转换为 .docx",
                        ),
                        DocumentBatchUploadFailedItem(
                            filename="重复.pdf",
                            reason="E2013: 文档名称已存在",
                        ),
                    ],
                )

                response = await async_client.post(
                    f"/api/knowledge-bases/{KB_UUID}/documents/batch-upload",
                    files=[
                        ("files", ("a.pdf", b"content1", "application/pdf")),
                        ("files", ("旧文档.doc", b"doc content", "application/msword")),
                        ("files", ("重复.pdf", b"content2", "application/pdf")),
                    ],
                    headers=auth_headers,
                )

        assert response.status_code == 200
        body = response.json()
        assert len(body["data"]["success"]) == 1
        assert len(body["data"]["failed"]) == 2
        assert body["data"]["failed"][0]["filename"] == "旧文档.doc"

    @pytest.mark.asyncio
    async def test_batch_upload_kb_not_found(self, async_client, auth_headers):
        """知识库不存在"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.batch_upload_documents", new_callable=AsyncMock) as mock:
                mock.side_effect = KnowledgeBaseNotFoundException(999)

                response = await async_client.post(
                    f"/api/knowledge-bases/{KB_UUID_999}/documents/batch-upload",
                    files=[("files", ("a.pdf", b"content", "application/pdf"))],
                    headers=auth_headers,
                )

        assert response.status_code == 404
        assert response.json()["code"] == "E1001"

    @pytest.mark.asyncio
    async def test_batch_upload_no_auth(self, async_client):
        """未登录"""
        response = await async_client.post(
            f"/api/knowledge-bases/{KB_UUID}/documents/batch-upload",
            files=[("files", ("a.pdf", b"content", "application/pdf"))],
        )

        assert response.status_code == 401


# ==================== GET /{kb_id}/documents — 文档列表 ====================

class TestListDocuments:
    """GET /api/knowledge-bases/{kb_id}/documents — 文档列表"""

    @pytest.mark.asyncio
    async def test_list_success(self, async_client, auth_headers):
        """A3.6: 正常获取文档列表"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.list_documents", new_callable=AsyncMock) as mock:
                mock.return_value = _make_list_data(total=2, items=[
                    _make_doc_response(doc_uuid=DOC_UUID, filename="入职指南.pdf"),
                    _make_doc_response(doc_uuid=DOC_UUID_2, filename="报销制度.md", file_type="md"),
                ])

                response = await async_client.get(
                    f"/api/knowledge-bases/{KB_UUID}/documents",
                    headers=auth_headers,
                )

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "0"
        assert body["data"]["total"] == 2
        assert body["data"]["page"] == 1
        assert body["data"]["page_size"] == 20
        assert len(body["data"]["items"]) == 2
        assert body["data"]["items"][0]["filename"] == "入职指南.pdf"
        assert body["data"]["items"][0]["chunk_count"] == 10

    @pytest.mark.asyncio
    async def test_list_with_status_filter(self, async_client, auth_headers):
        """A3.7: 按状态筛选文档列表"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.list_documents", new_callable=AsyncMock) as mock:
                mock.return_value = _make_list_data(total=1, items=[
                    _make_doc_response(status=DocumentStatus.COMPLETED),
                ])

                response = await async_client.get(
                    f"/api/knowledge-bases/{KB_UUID}/documents?status=completed",
                    headers=auth_headers,
                )

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["items"][0]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_list_with_filename_filter(self, async_client, auth_headers):
        """按文件名模糊搜索"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.list_documents", new_callable=AsyncMock) as mock:
                mock.return_value = _make_list_data(total=1, items=[
                    _make_doc_response(filename="入职指南.pdf"),
                ])

                response = await async_client.get(
                    f"/api/knowledge-bases/{KB_UUID}/documents?filename=入职",
                    headers=auth_headers,
                )

        assert response.status_code == 200
        assert response.json()["data"]["total"] == 1

    @pytest.mark.asyncio
    async def test_list_with_sorting(self, async_client, auth_headers):
        """按指定字段排序"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.list_documents", new_callable=AsyncMock) as mock:
                mock.return_value = _make_list_data()

                response = await async_client.get(
                    f"/api/knowledge-bases/{KB_UUID}/documents?sort_by=file_size&order=asc",
                    headers=auth_headers,
                )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_with_pagination(self, async_client, auth_headers):
        """分页参数"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.list_documents", new_callable=AsyncMock) as mock:
                mock.return_value = _make_list_data(total=50, page=2, page_size=10, items=[])

                response = await async_client.get(
                    f"/api/knowledge-bases/{KB_UUID}/documents?page=2&page_size=10",
                    headers=auth_headers,
                )

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["page"] == 2
        assert body["data"]["page_size"] == 10

    @pytest.mark.asyncio
    async def test_list_empty(self, async_client, auth_headers):
        """空知识库（无文档）"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.list_documents", new_callable=AsyncMock) as mock:
                mock.return_value = _make_list_data(total=0, items=[])

                response = await async_client.get(
                    f"/api/knowledge-bases/{KB_UUID}/documents",
                    headers=auth_headers,
                )

        assert response.status_code == 200
        assert response.json()["data"]["total"] == 0
        assert response.json()["data"]["items"] == []

    @pytest.mark.asyncio
    async def test_list_kb_not_found(self, async_client, auth_headers):
        """知识库不存在"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.list_documents", new_callable=AsyncMock) as mock:
                mock.side_effect = KnowledgeBaseNotFoundException(999)

                response = await async_client.get(
                    f"/api/knowledge-bases/{KB_UUID_999}/documents",
                    headers=auth_headers,
                )

        assert response.status_code == 404
        assert response.json()["code"] == "E1001"

    @pytest.mark.asyncio
    async def test_list_permission_denied(self, async_client, auth_headers):
        """非 owner 且非 admin 查看 → 403"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.list_documents", new_callable=AsyncMock) as mock:
                mock.side_effect = PermissionDeniedException()

                response = await async_client.get(
                    f"/api/knowledge-bases/{KB_UUID}/documents",
                    headers=auth_headers,
                )

        assert response.status_code == 403
        assert response.json()["code"] == "E5005"

    @pytest.mark.asyncio
    async def test_list_no_auth(self, async_client):
        """未登录"""
        response = await async_client.get(f"/api/knowledge-bases/{KB_UUID}/documents")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_page_size_zero_rejected(self, async_client, auth_headers):
        """page_size=0 被 Query(ge=1) 拒绝"""
        response = await async_client.get(
            f"/api/knowledge-bases/{KB_UUID}/documents?page_size=0",
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_page_size_exceeds_100_rejected(self, async_client, auth_headers):
        """page_size > 100 被 Query(le=100) 拒绝"""
        response = await async_client.get(
            f"/api/knowledge-bases/{KB_UUID}/documents?page_size=101",
            headers=auth_headers,
        )

        assert response.status_code == 422


# ==================== GET /{kb_id}/documents/{doc_id} — 文档详情 ====================

class TestGetDocument:
    """GET /api/knowledge-bases/{kb_id}/documents/{doc_id} — 文档详情"""

    @pytest.mark.asyncio
    async def test_get_success(self, async_client, auth_headers):
        """A3.8: 获取文档详情，含 chunk_count"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.get_document", new_callable=AsyncMock) as mock:
                mock.return_value = _make_doc_response(
                    doc_uuid=DOC_UUID, filename="入职指南.pdf",
                    chunk_count=24, status=DocumentStatus.COMPLETED,
                )

                response = await async_client.get(
                    f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID}",
                    headers=auth_headers,
                )

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "0"
        assert body["data"]["uuid"] == DOC_UUID
        assert body["data"]["kb_uuid"] == KB_UUID
        assert body["data"]["filename"] == "入职指南.pdf"
        assert body["data"]["file_type"] == "pdf"
        assert body["data"]["chunk_count"] == 24
        assert body["data"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_get_not_found(self, async_client, auth_headers):
        """文档不存在 → 404 E2001"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.get_document", new_callable=AsyncMock) as mock:
                mock.side_effect = DocumentNotFoundException(999)

                response = await async_client.get(
                    f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID_999}",
                    headers=auth_headers,
                )

        assert response.status_code == 404
        body = response.json()
        assert body["code"] == "E2001"
        assert body["message"] == "文档不存在"

    @pytest.mark.asyncio
    async def test_get_kb_not_found(self, async_client, auth_headers):
        """知识库不存在"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.get_document", new_callable=AsyncMock) as mock:
                mock.side_effect = KnowledgeBaseNotFoundException(999)

                response = await async_client.get(
                    f"/api/knowledge-bases/{KB_UUID_999}/documents/{DOC_UUID}",
                    headers=auth_headers,
                )

        assert response.status_code == 404
        assert response.json()["code"] == "E1001"

    @pytest.mark.asyncio
    async def test_get_permission_denied(self, async_client, auth_headers):
        """非 owner 且非 admin 查看 → 403"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.get_document", new_callable=AsyncMock) as mock:
                mock.side_effect = PermissionDeniedException()

                response = await async_client.get(
                    f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID}",
                    headers=auth_headers,
                )

        assert response.status_code == 403
        assert response.json()["code"] == "E5005"

    @pytest.mark.asyncio
    async def test_get_no_auth(self, async_client):
        """未登录"""
        response = await async_client.get(f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID}")
        assert response.status_code == 401


# ==================== GET /{kb_id}/documents/{doc_id}/chunks — 分块列表 ====================

class TestGetDocumentChunks:
    """GET /api/knowledge-bases/{kb_id}/documents/{doc_id}/chunks — 分块列表"""

    @pytest.mark.asyncio
    async def test_chunks_success(self, async_client, auth_headers):
        """正常获取分块列表"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.get_document_chunks", new_callable=AsyncMock) as mock:
                mock.return_value = _make_chunk_list_data(total=3, items=[
                    _make_chunk_response(chunk_id=1, chunk_index=0, preview="第一段内容..."),
                    _make_chunk_response(chunk_id=2, chunk_index=1, preview="第二段内容..."),
                    _make_chunk_response(chunk_id=3, chunk_index=2, preview="第三段内容..."),
                ])

                response = await async_client.get(
                    f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID}/chunks",
                    headers=auth_headers,
                )

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "0"
        assert body["data"]["total"] == 3
        assert len(body["data"]["items"]) == 3
        assert body["data"]["items"][0]["chunk_index"] == 0
        assert body["data"]["items"][0]["preview"] == "第一段内容..."
        assert body["data"]["items"][0]["token_count"] == 50

    @pytest.mark.asyncio
    async def test_chunks_empty(self, async_client, auth_headers):
        """文档无分块"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.get_document_chunks", new_callable=AsyncMock) as mock:
                mock.return_value = _make_chunk_list_data(total=0, items=[])

                response = await async_client.get(
                    f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID}/chunks",
                    headers=auth_headers,
                )

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["total"] == 0
        assert body["data"]["items"] == []

    @pytest.mark.asyncio
    async def test_chunks_with_pagination(self, async_client, auth_headers):
        """分块分页"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.get_document_chunks", new_callable=AsyncMock) as mock:
                mock.return_value = _make_chunk_list_data(
                    total=150, page=2, page_size=20, items=[_make_chunk_response()]
                )

                response = await async_client.get(
                    f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID}/chunks?page=2&page_size=20",
                    headers=auth_headers,
                )

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["page"] == 2
        assert body["data"]["page_size"] == 20

    @pytest.mark.asyncio
    async def test_chunks_doc_not_found(self, async_client, auth_headers):
        """文档不存在"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.get_document_chunks", new_callable=AsyncMock) as mock:
                mock.side_effect = DocumentNotFoundException(999)

                response = await async_client.get(
                    f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID_999}/chunks",
                    headers=auth_headers,
                )

        assert response.status_code == 404
        assert response.json()["code"] == "E2001"

    @pytest.mark.asyncio
    async def test_chunks_no_auth(self, async_client):
        """未登录"""
        response = await async_client.get(f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID}/chunks")
        assert response.status_code == 401


# ==================== POST /{kb_id}/documents/{doc_id}/reprocess — 重新处理 ====================

class TestReprocessDocument:
    """POST /api/knowledge-bases/{kb_id}/documents/{doc_id}/reprocess — 重新处理"""

    @pytest.mark.asyncio
    async def test_reprocess_success(self, async_client, auth_headers):
        """A3.10: 重新处理失败文档 → 200"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.reprocess_document", new_callable=AsyncMock) as mock:
                mock.return_value = _make_reprocess_data(doc_uuid=DOC_UUID, status=DocumentStatus.UPLOADED)

                response = await async_client.post(
                    f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID}/reprocess",
                    headers=auth_headers,
                )

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "0"
        assert body["message"] == "重新处理任务已提交"
        assert body["data"]["doc_uuid"] == DOC_UUID
        assert body["data"]["status"] == "uploaded"

    @pytest.mark.asyncio
    async def test_reprocess_invalid_status(self, async_client, auth_headers):
        """非 partial_failed/failed 状态不允许 reprocess → 400 E2010"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.reprocess_document", new_callable=AsyncMock) as mock:
                mock.side_effect = ReprocessFailedException(
                    "文档 5 当前状态为 completed，仅 partial_failed/failed 状态允许重新处理"
                )

                response = await async_client.post(
                    f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID}/reprocess",
                    headers=auth_headers,
                )

        assert response.status_code == 400
        body = response.json()
        assert body["code"] == "E2010"
        assert body["message"] == "重新处理失败"

    @pytest.mark.asyncio
    async def test_reprocess_doc_not_found(self, async_client, auth_headers):
        """文档不存在"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.reprocess_document", new_callable=AsyncMock) as mock:
                mock.side_effect = DocumentNotFoundException(999)

                response = await async_client.post(
                    f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID_999}/reprocess",
                    headers=auth_headers,
                )

        assert response.status_code == 404
        assert response.json()["code"] == "E2001"

    @pytest.mark.asyncio
    async def test_reprocess_permission_denied(self, async_client, auth_headers):
        """非 owner 且非 admin → 403"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.reprocess_document", new_callable=AsyncMock) as mock:
                mock.side_effect = PermissionDeniedException()

                response = await async_client.post(
                    f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID}/reprocess",
                    headers=auth_headers,
                )

        assert response.status_code == 403
        assert response.json()["code"] == "E5005"

    @pytest.mark.asyncio
    async def test_reprocess_no_auth(self, async_client):
        """未登录"""
        response = await async_client.post(
            f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID}/reprocess"
        )
        assert response.status_code == 401


# ==================== DELETE /{kb_id}/documents/{doc_id} — 文档删除 ====================

class TestDeleteDocument:
    """DELETE /api/knowledge-bases/{kb_id}/documents/{doc_id} — 文档删除"""

    @pytest.mark.asyncio
    async def test_delete_success(self, async_client, auth_headers):
        """A3.9: 删除文档 → 202，异步清理"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.delete_document", new_callable=AsyncMock) as mock:
                mock.return_value = _make_delete_data(doc_uuid=DOC_UUID, status=DocumentStatus.DELETING)

                response = await async_client.delete(
                    f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID}",
                    headers=auth_headers,
                )

        assert response.status_code == 202
        body = response.json()
        assert body["code"] == "0"
        assert body["message"] == "文档删除任务已提交"
        assert body["data"]["doc_uuid"] == DOC_UUID
        assert body["data"]["status"] == "deleting"

    @pytest.mark.asyncio
    async def test_delete_already_deleting(self, async_client, auth_headers):
        """文档已在删除中 → 409 E2011"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.delete_document", new_callable=AsyncMock) as mock:
                mock.side_effect = DocumentProcessingError("文档 5 正在删除中")

                response = await async_client.delete(
                    f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID}",
                    headers=auth_headers,
                )

        assert response.status_code == 409
        body = response.json()
        assert body["code"] == "E2011"
        assert body["message"] == "文档正在处理中"

    @pytest.mark.asyncio
    async def test_delete_not_found(self, async_client, auth_headers):
        """文档不存在 → 404 E2001"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.delete_document", new_callable=AsyncMock) as mock:
                mock.side_effect = DocumentNotFoundException(999)

                response = await async_client.delete(
                    f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID_999}",
                    headers=auth_headers,
                )

        assert response.status_code == 404
        body = response.json()
        assert body["code"] == "E2001"
        assert body["message"] == "文档不存在"

    @pytest.mark.asyncio
    async def test_delete_permission_denied(self, async_client, auth_headers):
        """非 owner 且非 admin 删除 → 403"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.delete_document", new_callable=AsyncMock) as mock:
                mock.side_effect = PermissionDeniedException()

                response = await async_client.delete(
                    f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID}",
                    headers=auth_headers,
                )

        assert response.status_code == 403
        assert response.json()["code"] == "E5005"

    @pytest.mark.asyncio
    async def test_delete_no_auth(self, async_client):
        """未登录"""
        response = await async_client.delete(f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID}")
        assert response.status_code == 401


# ==================== Phase 2.5 文档接口权限矩阵 ====================


class TestDocumentPermissionMatrix:
    """文档接口权限验证（ROADMAP §4.2 最后一项）

    上传/reprocess 仅 owner（admin 不可）
    查看/分块/删除 owner + admin
    """

    # --- 上传权限 ---

    @pytest.mark.asyncio
    async def test_owner_can_upload(self, async_client, auth_headers):
        """owner 可上传文档"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.upload_document", new_callable=AsyncMock) as mock:
                mock.return_value = _make_upload_response(filename="owner_doc.pdf")

                response = await async_client.post(
                    f"/api/knowledge-bases/{KB_UUID}/documents",
                    files={"file": ("owner_doc.pdf", b"content", "application/pdf")},
                    headers=auth_headers,
                )

        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_admin_cannot_upload(self, async_client, admin_auth_headers):
        """admin 不能上传到他人知识库（上传仅 owner）"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.upload_document", new_callable=AsyncMock) as mock:
                mock.side_effect = PermissionDeniedException()

                response = await async_client.post(
                    f"/api/knowledge-bases/{KB_UUID}/documents",
                    files={"file": ("admin_doc.pdf", b"content", "application/pdf")},
                    headers=admin_auth_headers,
                )

        assert response.status_code == 403
        assert response.json()["code"] == "E5005"

    @pytest.mark.asyncio
    async def test_other_user_cannot_upload(self, async_client, other_user_auth_headers):
        """非 owner 普通用户不能上传"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.upload_document", new_callable=AsyncMock) as mock:
                mock.side_effect = PermissionDeniedException()

                response = await async_client.post(
                    f"/api/knowledge-bases/{KB_UUID}/documents",
                    files={"file": ("test.pdf", b"content", "application/pdf")},
                    headers=other_user_auth_headers,
                )

        assert response.status_code == 403

    # --- 列表权限 ---

    @pytest.mark.asyncio
    async def test_owner_can_list(self, async_client, auth_headers):
        """owner 可查看文档列表"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.list_documents", new_callable=AsyncMock) as mock:
                mock.return_value = _make_list_data()

                response = await async_client.get(
                    f"/api/knowledge-bases/{KB_UUID}/documents",
                    headers=auth_headers,
                )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_can_list(self, async_client, admin_auth_headers):
        """admin 可查看任意 KB 文档列表（private KB 审计）"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.list_documents", new_callable=AsyncMock) as mock:
                mock.return_value = _make_list_data()

                response = await async_client.get(
                    f"/api/knowledge-bases/{KB_UUID}/documents",
                    headers=admin_auth_headers,
                )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_other_user_cannot_list(self, async_client, other_user_auth_headers):
        """非 owner 普通用户不能查看他人 private KB 文档列表"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.list_documents", new_callable=AsyncMock) as mock:
                mock.side_effect = PermissionDeniedException()

                response = await async_client.get(
                    f"/api/knowledge-bases/{KB_UUID}/documents",
                    headers=other_user_auth_headers,
                )

        assert response.status_code == 403

    # --- 详情权限 ---

    @pytest.mark.asyncio
    async def test_owner_can_get(self, async_client, auth_headers):
        """owner 可查看文档详情"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.get_document", new_callable=AsyncMock) as mock:
                mock.return_value = _make_doc_response()

                response = await async_client.get(
                    f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID}",
                    headers=auth_headers,
                )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_can_get(self, async_client, admin_auth_headers):
        """admin 可查看任意 KB 文档详情（private KB 审计）"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.get_document", new_callable=AsyncMock) as mock:
                mock.return_value = _make_doc_response()

                response = await async_client.get(
                    f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID}",
                    headers=admin_auth_headers,
                )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_other_user_cannot_get(self, async_client, other_user_auth_headers):
        """非 owner 普通用户不能查看他人 private KB 文档详情"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.get_document", new_callable=AsyncMock) as mock:
                mock.side_effect = PermissionDeniedException()

                response = await async_client.get(
                    f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID}",
                    headers=other_user_auth_headers,
                )

        assert response.status_code == 403

    # --- 分块权限 ---

    @pytest.mark.asyncio
    async def test_owner_can_get_chunks(self, async_client, auth_headers):
        """owner 可查看文档分块"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.get_document_chunks", new_callable=AsyncMock) as mock:
                mock.return_value = _make_chunk_list_data()

                response = await async_client.get(
                    f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID}/chunks",
                    headers=auth_headers,
                )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_can_get_chunks(self, async_client, admin_auth_headers):
        """admin 可查看任意 KB 文档分块（private KB 审计）"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.get_document_chunks", new_callable=AsyncMock) as mock:
                mock.return_value = _make_chunk_list_data()

                response = await async_client.get(
                    f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID}/chunks",
                    headers=admin_auth_headers,
                )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_other_user_cannot_get_chunks(self, async_client, other_user_auth_headers):
        """非 owner 普通用户不能查看他人 private KB 文档分块"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.get_document_chunks", new_callable=AsyncMock) as mock:
                mock.side_effect = PermissionDeniedException()

                response = await async_client.get(
                    f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID}/chunks",
                    headers=other_user_auth_headers,
                )

        assert response.status_code == 403

    # --- 删除权限 ---

    @pytest.mark.asyncio
    async def test_owner_can_delete(self, async_client, auth_headers):
        """owner 可删除文档"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.delete_document", new_callable=AsyncMock) as mock:
                mock.return_value = _make_delete_data()

                response = await async_client.delete(
                    f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID}",
                    headers=auth_headers,
                )

        assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_admin_can_delete(self, async_client, admin_auth_headers):
        """admin 可删除任意 KB 文档（违规清理）"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.delete_document", new_callable=AsyncMock) as mock:
                mock.return_value = _make_delete_data()

                response = await async_client.delete(
                    f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID}",
                    headers=admin_auth_headers,
                )

        assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_other_user_cannot_delete(self, async_client, other_user_auth_headers):
        """非 owner 普通用户不能删除他人文档"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.delete_document", new_callable=AsyncMock) as mock:
                mock.side_effect = PermissionDeniedException()

                response = await async_client.delete(
                    f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID}",
                    headers=other_user_auth_headers,
                )

        assert response.status_code == 403

    # --- reprocess 权限 ---

    @pytest.mark.asyncio
    async def test_owner_can_reprocess(self, async_client, auth_headers):
        """owner 可重新处理文档"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.reprocess_document", new_callable=AsyncMock) as mock:
                mock.return_value = _make_reprocess_data()

                response = await async_client.post(
                    f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID}/reprocess",
                    headers=auth_headers,
                )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_cannot_reprocess(self, async_client, admin_auth_headers):
        """admin 不能重新处理他人文档（reprocess 仅 owner）"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.reprocess_document", new_callable=AsyncMock) as mock:
                mock.side_effect = PermissionDeniedException()

                response = await async_client.post(
                    f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID}/reprocess",
                    headers=admin_auth_headers,
                )

        assert response.status_code == 403
        assert response.json()["code"] == "E5005"

    @pytest.mark.asyncio
    async def test_other_user_cannot_reprocess(self, async_client, other_user_auth_headers):
        """非 owner 普通用户不能重新处理他人文档"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock,
                   side_effect=_uuid_to_id_side_effect):
            with patch("app.api.document.reprocess_document", new_callable=AsyncMock) as mock:
                mock.side_effect = PermissionDeniedException()

                response = await async_client.post(
                    f"/api/knowledge-bases/{KB_UUID}/documents/{DOC_UUID}/reprocess",
                    headers=other_user_auth_headers,
                )

        assert response.status_code == 403
