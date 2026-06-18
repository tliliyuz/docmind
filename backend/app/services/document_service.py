"""文档业务逻辑 — 上传/批量上传/列表/详情/分块/删除/重新处理"""
import logging
import time
import uuid as uuid_lib
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.chroma_client import get_vector_store
from app.core.database import engine
from app.core.exceptions import (
    AppException,
    BatchUploadCountExceededException,
    DocumentNameExistsException,
    DocumentNotFoundException,
    DocumentProcessingError,
    ForceOverrideConflictException,
    ReprocessFailedException,
    StorageErrorException,
    UnsupportedFileFormatException,
    FileSizeExceededException,
)
from app.core.permissions import require_kb_owner, require_kb_readable, require_kb_writable
from app.core.redis_client import get_redis
from app.core.storage import local_storage
from app.rag.bm25 import invalidate_bm25_cache_async
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
from app.ingest.delete_tasks import delete_document as delete_doc_task
from app.ingest.tasks import ingest_document as ingest_doc_task
from app.core.utils import escape_like
from app.services.knowledge_base_service import check_kb_active

logger = logging.getLogger(__name__)


def _pool_status() -> str:
    """获取数据库连接池状态（用于诊断连接池耗尽）"""
    try:
        pool = engine.sync_engine.pool
        return (
            f"pool[size={pool.size()}, checkedin={pool.checkedin()}, "
            f"checkedout={pool.checkedout()}, overflow={pool.overflow()}]"
        )
    except Exception:
        return "pool[unavailable]"

# 允许的排序字段
SORT_ALLOWED_FIELDS = {"created_at", "updated_at", "filename", "file_size", "status"}

# 从 settings 解析允许的文件类型（逗号分隔 → set）
ALLOWED_EXTENSIONS = set(
    ext.strip().lower()
    for ext in settings.ALLOWED_EXTENSIONS.split(",")
    if ext.strip()
)


# 文件魔数签名（magic bytes），防止扩展名伪装
MAGIC_BYTES = {
    "pdf": b"%PDF",
    "docx": b"PK\x03\x04",
    # md/txt 无魔数，纯文本不做二进制校验
}


def validate_file(file: UploadFile) -> None:
    """校验文件类型和大小，不通过时抛对应异常

    安全关键路径，包含三条独立规则：
    1. 扩展名白名单校验（ALLOWED_EXTENSIONS）
    2. 文件大小限制校验（UPLOAD_MAX_SIZE）
    3. 魔数字节校验（MAGIC_BYTES，防止扩展名伪装）
    """
    if file.filename is None:
        raise UnsupportedFileFormatException("unknown")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileFormatException(ext)

    # 读取内容并校验大小（UploadFile.size 可能为 None）
    if file.size is not None and file.size > settings.UPLOAD_MAX_SIZE:
        raise FileSizeExceededException()

    # 魔数校验：防止将 .exe 改名为 .pdf 等恶意上传
    expected_magic = MAGIC_BYTES.get(ext)
    if expected_magic is not None:
        try:
            header = file.file.read(len(expected_magic))
            file.file.seek(0)  # 回退指针，供后续保存使用
            if header != expected_magic:
                raise UnsupportedFileFormatException(ext)
        except UnsupportedFileFormatException:
            raise
        except Exception:
            # 读取失败时放行（可能为空文件或特殊流），交由后续处理阶段报错
            pass


async def _check_kb_ownership(
    db: AsyncSession, kb_id: int, user_id: int, role: str,
    *,
    owner_only: bool = False,
    allow_public_read: bool = False,
) -> None:
    """校验知识库存在且 active，且当前用户有操作权限

    owner_only=True 时仅 owner 可操作（admin 也不允许），用于上传/reprocess 等写操作
    allow_public_read=True 时，public KB 允许任意登录用户读取（仅限 list/get 等只读操作）

    实际权限逻辑委托给 core/permissions.py 共享函数。
    """
    kb = await check_kb_active(db, kb_id)

    # 公开 KB 只读访问：任意登录用户可通过
    if allow_public_read and kb.visibility == "public":
        return

    if owner_only:
        require_kb_owner(kb, user_id)
    else:
        require_kb_writable(kb, user_id, role)


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
    validate_file(file)
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
    is_new_doc = False  # 标记是否为新建文档（用于文件保存成功后才递增 doc_count）

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

            # 清理旧向量（通过 VectorStore 抽象，内部已处理异步线程卸载）
            try:
                store = get_vector_store()
                await store.delete(kb_id=kb_id, where={"doc_id": doc.id})
            except Exception:
                logger.warning("向量存储清理 doc=%d 失败，跳过", doc.id)

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
            delete_doc_task.delay(existing.id)

    # 非复用场景：创建新文档记录（doc_count 延后到文件保存成功后再递增）
    if doc is None:
        doc = Document(
            uuid=str(uuid_lib.uuid4()),
            kb_id=kb_id,
            filename=filename,
            file_type=ext,
        )
        db.add(doc)
        await db.flush()
        is_new_doc = True

    await db.refresh(doc)

    # 保存文件
    kb_for_count: KnowledgeBase | None = None
    try:
        file_path = await local_storage.save(file, kb_id, doc.id)
        doc.file_path = file_path
        doc.file_size = Path(file_path).stat().st_size
        # 二次校验：UploadFile.size 可能为 None，以实际磁盘文件大小为准
        if doc.file_size > settings.UPLOAD_MAX_SIZE:
            # 删除已保存的超大文件
            try:
                Path(file_path).unlink(missing_ok=True)
            except Exception:
                pass
            raise FileSizeExceededException()

        # 文件保存成功后才递增 doc_count
        # 避免保存失败时 Identity Map 残留未提交脏值，导致批量上传后续计数错误
        if is_new_doc:
            kb_for_count = await db.get(KnowledgeBase, kb_id)
            if kb_for_count is not None:
                kb_for_count.doc_count = kb_for_count.doc_count + 1

        await db.flush()
        await db.commit()  # 必须在 delay 前提交，否则 Worker 看不到新记录
        await db.refresh(doc)

        # 提交后手动过期 KB 对象，确保批量上传场景下
        # 下一次迭代的 db.get() 读到 DB 最新值
        # （expire_on_commit=False 配置下不会自动过期）
        if kb_for_count is not None:
            db.expire(kb_for_count)
    except AppException:
        raise
    except Exception:
        raise StorageErrorException(f"文件保存失败：{filename}")

    # 分发 Celery 入库任务
    ingest_doc_task.delay(doc.id)

    # 获取 KB uuid 用于响应（关系未预加载，直接查 KB）
    kb = await db.get(KnowledgeBase, kb_id)
    kb_uuid = kb.uuid if kb else ""

    return DocumentUploadResponse(
        uuid=doc.uuid,
        kb_uuid=kb_uuid,
        filename=doc.filename,
        file_type=doc.file_type,
        file_size=doc.file_size,
        status=doc.status,
    )



async def batch_upload_documents(
    db: AsyncSession,
    kb_id: int,
    user_id: int,
    role: str,
    files: list[UploadFile],
) -> DocumentBatchUploadResponse:
    """批量上传文档，部分成功返回"""
    await _check_kb_ownership(db, kb_id, user_id, role, owner_only=True)

    # 批量上传数量限制（防止单次请求文件数过多导致 Celery 队列阻塞 + 连接池耗尽）
    if len(files) > settings.BATCH_UPLOAD_MAX_COUNT:
        raise BatchUploadCountExceededException(
            actual=len(files), maximum=settings.BATCH_UPLOAD_MAX_COUNT
        )

    success: list[DocumentBatchUploadItem] = []
    failed: list[DocumentBatchUploadFailedItem] = []

    for file in files:
        try:
            result = await upload_document(db, kb_id, user_id, role, file, force=False)
            success.append(
                DocumentBatchUploadItem(
                    uuid=result.uuid,
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
    """获取知识库下的文档列表（筛选 + 排序 + 分页）

    public KB 允许任意登录用户查看文档列表（只读），对齐 PRD.md §5.4
    """
    t_start = time.time()

    t0 = time.time()
    await _check_kb_ownership(db, kb_id, user_id, role, allow_public_read=True)
    t_perm = time.time() - t0

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
        conditions.append(Document.filename.like(f"%{escape_like(filename)}%", escape="\\"))

    # 总数
    count_q = (
        select(func.count())
        .select_from(Document)
        .where(*conditions)
    )
    t0 = time.time()
    total = (await db.execute(count_q)).scalar() or 0
    t_count = time.time() - t0

    # 分页（selectinload KB 用于 kb_uuid 属性）
    q = (
        select(Document)
        .options(selectinload(Document.knowledge_base))
        .where(*conditions)
        .order_by(sort_expr)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    t0 = time.time()
    rows = (await db.execute(q)).scalars().all()
    t_select = time.time() - t0

    t0 = time.time()
    items = [_build_document_response(r) for r in rows]
    t_serialize = time.time() - t0

    t_total = time.time() - t_start
    logger.info(
        "list_documents kb=%d page=%d %s → PERM=%.3fs COUNT=%.3fs SELECT=%.3fs SERIALIZE=%.3fs TOTAL=%.3fs %s",
        kb_id, page, _pool_status(), t_perm, t_count, t_select, t_serialize, t_total,
        f"({total} docs, {len(items)} items)" if t_total > 0.3 else "",
    )

    return DocumentListResponse(total=total, page=page, page_size=page_size, items=items)


async def get_document(
    db: AsyncSession,
    kb_id: int,
    doc_id: int,
    user_id: int,
    role: str,
) -> DocumentResponse:
    """获取单个文档详情"""
    await _check_kb_ownership(db, kb_id, user_id, role, allow_public_read=True)

    doc = await _get_doc_in_kb(db, kb_id, doc_id)
    return _build_document_response(doc)


async def _get_doc_in_kb(
    db: AsyncSession, kb_id: int, doc_id: int
) -> Document:
    """按 kb_id + doc_id 查文档，不存在抛 DocumentNotFoundException"""
    result = await db.execute(
        select(Document)
        .options(selectinload(Document.knowledge_base))
        .where(Document.id == doc_id, Document.kb_id == kb_id)
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
    await _check_kb_ownership(db, kb_id, user_id, role, allow_public_read=True)
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
            preview = full_content[:settings.CHUNK_PREVIEW_LENGTH]
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
    delete_doc_task.delay(doc.id)

    return DocumentDeleteResponse(doc_uuid=doc.uuid, status=doc.status)


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
    # 清理旧向量（通过 VectorStore 抽象，内部已处理异步线程卸载）
    try:
        store = get_vector_store()
        await store.delete(kb_id=kb_id, where={"doc_id": doc_id})
        logger.info("文档 %d reprocess 前向量存储旧向量已清理", doc_id)
    except Exception:
        logger.exception("文档 %d reprocess 前 ChromaDB 旧向量清理失败", doc_id)

    # 清除 BM25 缓存（对齐 ARCHITECTURE.md §6.2）
    await invalidate_bm25_cache_async(kb_id)

    # 清理旧 chunk 记录（MySQL FK CASCADE 自动删除）并重置状态
    doc.status = DocumentStatus.UPLOADED
    doc.error_msg = None
    doc.current_stage = None
    doc.last_success_batch = 0
    await db.flush()
    await db.commit()  # 必须在 delay 前提交，否则 Worker 看不到状态变更
    await db.refresh(doc)

    # 分发 Celery 入库任务（重新处理）
    ingest_doc_task.delay(doc.id)

    return DocumentReprocessResponse(doc_uuid=doc.uuid, status=doc.status)
