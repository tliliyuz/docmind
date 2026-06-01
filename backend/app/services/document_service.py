"""文档业务逻辑 — 上传/批量上传/列表/详情/分块/删除/重新处理"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
from typing import Any

from fastapi import UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.chroma_client import get_collection
from app.core.exceptions import (
    DocumentNameExistsException,
    DocumentNotFoundException,
    DocumentProcessingError,
    ForceOverrideConflictException,
    PermissionDeniedException,
    ReprocessFailedException,
    StorageErrorException,
    UnsupportedFileFormatException,
    FileSizeExceededException,
)
from app.core.storage import local_storage
from app.models.document import Document
from app.models.chunk import Chunk
from app.models.enums import DocumentStatus, is_terminal
from app.models.knowledge_base import KnowledgeBase
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
from app.ingest.tasks import delete_document as _delete_doc_task
from app.ingest.tasks import ingest_document as _ingest_doc_task
from app.services.knowledge_base_service import check_kb_active

# 允许的文件类型
ALLOWED_EXTENSIONS = {"pdf", "docx", "md", "txt"}
# 最大文件大小 50MB
MAX_FILE_SIZE = 50 * 1024 * 1024
# 允许的排序字段
SORT_ALLOWED_FIELDS = {"created_at", "updated_at", "filename", "file_size", "status"}
# 分块预览截断长度
CHUNK_PREVIEW_LENGTH = 200


def _validate_file(file: UploadFile) -> None:
    """校验文件类型和大小，不通过时抛对应异常"""
    if file.filename is None:
        raise UnsupportedFileFormatException("unknown")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileFormatException(ext)

    # 读取内容并校验大小（UploadFile.size 可能为 None）
    if file.size is not None and file.size > MAX_FILE_SIZE:
        raise FileSizeExceededException()


async def _check_kb_ownership(
    db: AsyncSession, kb_id: int, user_id: int, role: str,
    *,
    owner_only: bool = False,
) -> None:
    """校验知识库存在且 active，且当前用户有操作权限

    owner_only=True 时仅 owner 可操作（admin 也不允许），用于上传/reprocess 等写操作
    """
    kb = await check_kb_active(db, kb_id)
    if owner_only:
        if kb.user_id != user_id:
            raise PermissionDeniedException()
    else:
        if kb.user_id != user_id and role != "admin":
            raise PermissionDeniedException()


def _build_document_response(doc: Document) -> DocumentResponse:
    return DocumentResponse.model_validate(doc)


async def upload_document(
    db: AsyncSession,
    kb_id: int,
    user_id: int,
    role: str,
    file: UploadFile,
    force: bool = False,
) -> DocumentUploadResponse:
    """上传单个文档，支持 force 覆盖模式"""
    _validate_file(file)
    await _check_kb_ownership(db, kb_id, user_id, role, owner_only=True)

    filename = file.filename
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    # 检查同名文档
    existing = (
        await db.execute(
            select(Document).where(
                Document.kb_id == kb_id,
                Document.filename == filename,
            )
        )
    ).scalar_one_or_none()

    doc = None  # None=新建文档；复用 deleting 记录时赋值为旧记录

    if existing is not None:
        if existing.status == DocumentStatus.DELETING:
            # 复用旧记录：清残留 → 重置状态 → 重新进入处理流程
            doc = existing

            # 清理旧 Chunk 记录并同步递减 kb.chunk_count
            chunk_result = await db.execute(
                select(func.count()).select_from(Chunk).where(Chunk.doc_id == doc.id)
            )
            old_chunk_count = chunk_result.scalar() or 0
            if old_chunk_count > 0:
                await db.execute(delete(Chunk).where(Chunk.doc_id == doc.id))
                kb = await db.get(KnowledgeBase, kb_id)
                if kb is not None:
                    kb.chunk_count = max(0, kb.chunk_count - old_chunk_count)

            # 清理旧向量（ChromaDB）
            try:
                collection = get_collection()
                collection.delete(where={"doc_id": doc.id})
            except Exception:
                logger.warning("ChromaDB 清理 doc=%d 向量失败，跳过", doc.id)

            # 重置文档状态
            doc.status = DocumentStatus.UPLOADED
            doc.error_msg = None
            doc.chunk_count = 0
            doc.current_stage = None
            doc.last_success_batch = 0
            await db.flush()
            # doc_count 不递增（复用旧记录，PRD §5.4 约束）

        elif not is_terminal(existing.status):
            # 处理中（uploaded/parsing/chunking/embedding/vector_storing）
            if force:
                raise ForceOverrideConflictException(
                    f"文档 '{filename}' 正在处理中（状态：{existing.status}），无法覆盖"
                )
            raise DocumentProcessingError(
                f"文档 '{filename}' 正在处理中（状态：{existing.status}），请等待处理完成"
            )
        else:
            # 终态文档
            if not force:
                raise DocumentNameExistsException(
                    f"文档 '{filename}' 已存在（kb_id={kb_id}），使用 force=true 可覆盖"
                )
            # force 覆盖：标记旧文档 deleting → 触发 Celery 异步清理
            existing.status = DocumentStatus.DELETING
            await db.flush()
            await db.commit()  # 必须在 delay 前提交，否则 Worker 看不到 DELETING 状态
            _delete_doc_task.delay(existing.id)

    # 非复用场景：创建新文档记录
    if doc is None:
        doc = Document(
            kb_id=kb_id,
            filename=filename,
            file_type=ext,
        )
        db.add(doc)
        await db.flush()

        # 递增 KB 文档计数
        kb = await db.get(KnowledgeBase, kb_id)
        if kb is not None:
            kb.doc_count = KnowledgeBase.doc_count + 1

    await db.refresh(doc)

    # 保存文件
    try:
        file_path = await local_storage.save(file, kb_id, doc.id)
        doc.file_path = file_path
        doc.file_size = Path(file_path).stat().st_size
        await db.flush()
        await db.commit()  # 必须在 delay 前提交，否则 Worker 看不到新记录
        await db.refresh(doc)
    except Exception:
        raise StorageErrorException(f"文件保存失败：{filename}")

    # 分发 Celery 入库任务
    _ingest_doc_task.delay(doc.id)

    return DocumentUploadResponse.model_validate(doc)



async def batch_upload_documents(
    db: AsyncSession,
    kb_id: int,
    user_id: int,
    role: str,
    files: list[UploadFile],
) -> DocumentBatchUploadResponse:
    """批量上传文档，部分成功返回"""
    await _check_kb_ownership(db, kb_id, user_id, role, owner_only=True)

    success: list[DocumentBatchUploadItem] = []
    failed: list[DocumentBatchUploadFailedItem] = []

    for file in files:
        try:
            result = await upload_document(db, kb_id, user_id, role, file, force=False)
            success.append(
                DocumentBatchUploadItem(
                    id=result.id,
                    filename=result.filename,
                    status=result.status,
                )
            )
        except Exception as e:
            filename = file.filename or "unknown"
            if hasattr(e, "error_code"):
                detail = getattr(e, "error_detail", "")
                reason = f"{e.error_code}: {e.error_message}"
                if detail:
                    reason += f"（{detail}）"
            else:
                reason = str(e)
            failed.append(
                DocumentBatchUploadFailedItem(filename=filename, reason=reason)
            )

    return DocumentBatchUploadResponse(success=success, failed=failed)


async def list_documents(
    db: AsyncSession,
    kb_id: int,
    user_id: int,
    role: str,
    *,
    status: str | None = None,
    filename: str | None = None,
    sort_by: str = "created_at",
    order: str = "desc",
    page: int = 1,
    page_size: int = 20,
) -> DocumentListResponse:
    """获取知识库下的文档列表（筛选 + 排序 + 分页）"""
    await _check_kb_ownership(db, kb_id, user_id, role)

    # 排序字段白名单校验
    if sort_by not in SORT_ALLOWED_FIELDS:
        sort_by = "created_at"

    sort_col = getattr(Document, sort_by)
    if order == "asc":
        sort_expr = sort_col.asc()
    else:
        sort_expr = sort_col.desc()

    # 构建过滤条件
    conditions = [Document.kb_id == kb_id]
    # 排除已标记 deleting 的文档（数据仍存在但不在列表展示）
    conditions.append(Document.status != DocumentStatus.DELETING)

    if status:
        conditions.append(Document.status == status)
    if filename:
        conditions.append(Document.filename.like(f"%{filename}%"))

    # 总数
    count_q = (
        select(func.count())
        .select_from(Document)
        .where(*conditions)
    )
    total = (await db.execute(count_q)).scalar() or 0

    # 分页
    q = (
        select(Document)
        .where(*conditions)
        .order_by(sort_expr)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(q)).scalars().all()
    items = [_build_document_response(r) for r in rows]

    return DocumentListResponse(total=total, page=page, page_size=page_size, items=items)


async def get_document(
    db: AsyncSession,
    kb_id: int,
    doc_id: int,
    user_id: int,
    role: str,
) -> DocumentResponse:
    """获取单个文档详情"""
    await _check_kb_ownership(db, kb_id, user_id, role)

    doc = await _get_doc_in_kb(db, kb_id, doc_id)
    return _build_document_response(doc)


async def _get_doc_in_kb(
    db: AsyncSession, kb_id: int, doc_id: int
) -> Document:
    """按 kb_id + doc_id 查文档，不存在抛 DocumentNotFoundException"""
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.kb_id == kb_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise DocumentNotFoundException(doc_id)
    return doc


async def get_document_chunks(
    db: AsyncSession,
    kb_id: int,
    doc_id: int,
    user_id: int,
    role: str,
    *,
    page: int = 1,
    page_size: int = 20,
) -> DocumentChunkListResponse:
    """查看文档的分块列表（分页），生产环境默认截断 content 至 200 字符"""
    await _check_kb_ownership(db, kb_id, user_id, role)
    doc = await _get_doc_in_kb(db, kb_id, doc_id)

    # 总数
    count_q = select(func.count()).select_from(Chunk).where(Chunk.doc_id == doc_id)
    total = (await db.execute(count_q)).scalar() or 0

    # 分页
    q = (
        select(Chunk)
        .where(Chunk.doc_id == doc_id)
        .order_by(Chunk.chunk_index)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(q)).scalars().all()

    items = []
    for r in rows:
        full_content = r.content or ""
        if settings.DEBUG_CHUNK_FULL:
            preview = full_content
        else:
            preview = full_content[:CHUNK_PREVIEW_LENGTH]
        items.append(
            DocumentChunkResponse(
                id=r.id,
                chunk_index=r.chunk_index,
                preview=preview,
                token_count=r.token_count or 0,
                metadata=r.metadata_,
            )
        )

    return DocumentChunkListResponse(
        total=total, page=page, page_size=page_size, items=items
    )


async def delete_document(
    db: AsyncSession,
    kb_id: int,
    doc_id: int,
    user_id: int,
    role: str,
) -> DocumentDeleteResponse:
    """删除文档（标记 deleting → 异步清理），返回 202 语义"""
    await _check_kb_ownership(db, kb_id, user_id, role)
    doc = await _get_doc_in_kb(db, kb_id, doc_id)

    if doc.status == DocumentStatus.DELETING:
        raise DocumentProcessingError(f"文档 {doc_id} 正在删除中")

    doc.status = DocumentStatus.DELETING
    await db.flush()
    await db.commit()  # 必须在 delay 前提交，否则 Worker 看不到 DELETING 状态
    await db.refresh(doc)

    # 分发 Celery 异步删除任务
    _delete_doc_task.delay(doc.id)

    return DocumentDeleteResponse(doc_id=doc.id, status=doc.status)


async def reprocess_document(
    db: AsyncSession,
    kb_id: int,
    doc_id: int,
    user_id: int,
    role: str,
) -> DocumentReprocessResponse:
    """重新处理失败或部分失败的文档（仅 partial_failed / failed 允许）"""
    await _check_kb_ownership(db, kb_id, user_id, role, owner_only=True)
    doc = await _get_doc_in_kb(db, kb_id, doc_id)

    if doc.status not in (DocumentStatus.PARTIAL_FAILED, DocumentStatus.FAILED):
        raise ReprocessFailedException(
            f"文档 {doc_id} 当前状态为 {doc.status}，仅 partial_failed/failed 状态允许重新处理"
        )

    # 清理 ChromaDB 旧向量（新文档分块数可能少于旧文档，残留向量需清除）
    try:
        collection = get_collection()
        collection.delete(where={"doc_id": doc_id})
        logger.info("文档 %d reprocess 前 ChromaDB 旧向量已清理", doc_id)
    except Exception:
        logger.exception("文档 %d reprocess 前 ChromaDB 旧向量清理失败", doc_id)

    # 清除 BM25 缓存（对齐 ARCHITECTURE.md §6.2）
    from app.core.redis_client import get_redis
    from app.rag.bm25 import invalidate_bm25_cache
    invalidate_bm25_cache(get_redis(), kb_id)

    # 清理旧 chunk 记录（MySQL FK CASCADE 自动删除）并重置状态
    doc.status = DocumentStatus.UPLOADED
    doc.error_msg = None
    doc.current_stage = None
    doc.last_success_batch = 0
    await db.flush()
    await db.commit()  # 必须在 delay 前提交，否则 Worker 看不到状态变更
    await db.refresh(doc)

    # 分发 Celery 入库任务（重新处理）
    _ingest_doc_task.delay(doc.id)

    return DocumentReprocessResponse(doc_id=doc.id, status=doc.status)
