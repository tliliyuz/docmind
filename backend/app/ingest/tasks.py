"""Celery 异步入库流水线任务 — Parser → Chunker → Embedder → Vector Store

对齐 ARCHITECTURE.md §4.1 入库流程：
  上传 → 幂等锁 → 解析 → 分块 → Embedding(batch+checkpoint) → 向量存储(batch)
  每阶段更新 current_stage + last_success_batch（断点恢复）

对齐 ARCHITECTURE.md §4.7 容错判定：
  - 全部成功 → completed
  - 失败 < 20% → success_with_warnings
  - 失败 20%~50% → partial_failed
  - 失败 > 50% → failed
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, func, select, update

from app.config import settings
from app.core.redis_client import get_redis
from app.core.chroma_client import get_vector_store
from app.rag.bm25 import invalidate_bm25_cache, invalidate_bm25_cache_async
from app.core.database import async_session
from app.core.storage import local_storage
from app.ingest.celery_app import celery_app
from app.ingest.lock import (
    acquire_idempotency_lock,
    acquire_idempotency_lock_async,
    release_idempotency_lock,
    release_idempotency_lock_async,
)
from app.models.chunk import Chunk
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.enums import DocumentStatus, is_terminal
from app.models.knowledge_base import KnowledgeBase
from app.rag.chunker import chunk_document
from app.rag.embedder import embed_chunks
from app.rag.parser import parse_document

logger = logging.getLogger(__name__)

# Worker 进程持久化事件循环，避免「每任务新建 loop → 关闭」导致 SQLAlchemy 连接池
# 中的连接挂在旧 loop 上，下个任务在新 loop 中复用时触发「attached to a different loop」
_worker_loop: asyncio.AbstractEventLoop | None = None


def _get_worker_loop() -> asyncio.AbstractEventLoop:
    global _worker_loop
    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
    return _worker_loop

# 可断点恢复的阶段（chunks 已写入 MySQL，可跳过解析+分块）
RESUMABLE_STAGES: frozenset[str] = frozenset({
    "chunking_done",   # chunks 已写入，embedding 未开始
    "embedding",        # embedding 部分完成，可从 last_success_batch 续传
    "vector_storing",   # embedding 全部完成但 ChromaDB 写入中断（embeddings 内存丢失，需重做 embedding）
})


@celery_app.task(bind=True, max_retries=3, soft_time_limit=600, autoretry_for=(Exception,), retry_backoff=True)
def ingest_document(self, doc_id: int) -> dict:
    """文档入库主流水线（Celery 同步入口 → 异步执行）。

    返回格式: {"status": str, "doc_id": int}
    未捕获异常自动重试（max_retries=3），利用 current_stage/last_success_batch 断点续传。
    """
    return _get_worker_loop().run_until_complete(_ingest_document_async(doc_id))


class _LoadDocStatus:
    """_load_doc 返回状态常量"""
    OK = "ok"
    NOT_FOUND = "not_found"
    DELETING = "deleting"


@dataclass
class _LoadDocResult:
    """_load_doc 返回值：区分文档不存在、已标记删除、正常加载三种情况"""
    doc: Document | None
    status: str  # _LoadDocStatus


async def _load_doc(db, doc_id: int) -> _LoadDocResult:
    """加载文档记录并检查 DELETING 状态。

    Returns:
        _LoadDocResult: status 为 OK/NOT_FOUND/DELETING，
                        status=OK 时 doc 一定非 None，
                        status≠OK 时 doc 一定为 None。
    """
    doc = await db.get(Document, doc_id)
    if doc is None:
        return _LoadDocResult(doc=None, status=_LoadDocStatus.NOT_FOUND)
    if doc.status == DocumentStatus.DELETING:
        logger.info("文档 %d 已被标记删除，中止流水线", doc_id)
        return _LoadDocResult(doc=None, status=_LoadDocStatus.DELETING)
    return _LoadDocResult(doc=doc, status=_LoadDocStatus.OK)


async def _load_chunk_rows(db, doc_id: int) -> list[dict[str, Any]]:
    """从 MySQL 加载文档的全部 chunks（按 chunk_index 排序），返回提取后的数据列表"""
    result = await db.execute(
        select(Chunk).where(Chunk.doc_id == doc_id).order_by(Chunk.chunk_index)
    )
    chunks_db = result.scalars().all()
    return [
        {
            "id": c.id,
            "chunk_index": c.chunk_index,
            "content": c.content,
            "chroma_id": c.chroma_id,
        }
        for c in chunks_db
    ]


async def _ingest_document_async(doc_id: int) -> dict:
    """入库流水线异步实现：幂等锁 → [阶段检测] → 解析/分块(可跳过) → Embedding(可断点续传) → 向量存储 → 终态判定

    阶段检测逻辑（对齐 RESUMABLE_STAGES）：
      - 首次执行（current_stage 为空/parsing/chunking）：完整流水线
      - 断点恢复（current_stage 为 chunking_done/embedding/vector_storing）：跳过解析分块，从 Embedding 继续
      - chunk 插入前先清理旧 chunks（幂等去重），避免重试导致重复记录
    """

    # 1. 获取幂等锁（异步上下文使用异步 Redis，避免阻塞事件循环）
    if not await acquire_idempotency_lock_async(doc_id, "ingest"):
        logger.warning(f"文档 {doc_id} 幂等锁已被占用，拒绝重复入队")
        return {"status": "locked", "doc_id": doc_id}

    try:
        # 2. 加载文档 + 阶段检测
        async with async_session() as db:
            result = await _load_doc(db, doc_id)
            if result.doc is None:
                return {"status": result.status, "doc_id": doc_id}
            doc = result.doc

            file_path = doc.file_path
            file_type = doc.file_type
            kb_id = doc.kb_id
            resume_stage = doc.current_stage  # None / chunking_done / embedding / vector_storing

            if not file_path:
                doc.status = DocumentStatus.FAILED
                doc.error_msg = "文件路径为空，无法解析"
                await db.commit()
                return {"status": "failed", "doc_id": doc_id}

        # ============================
        # 3. 阶段分支：决定是否跳过解析+分块
        # ============================
        chunk_rows: list[dict[str, Any]] = []
        total_chunks = 0
        resume_batch = 0

        if resume_stage in RESUMABLE_STAGES:
            # 断点恢复路径：chunks 已在 MySQL，跳过解析+分块
            logger.info(
                "文档 %d 检测到断点 stage=%s，跳过解析分块，从 Embedding 恢复",
                doc_id, resume_stage,
            )

            async with async_session() as db:
                result = await _load_doc(db, doc_id)
                if result.doc is None:
                    return {"status": result.status, "doc_id": doc_id}
                doc = result.doc

                chunk_rows = await _load_chunk_rows(db, doc_id)
                if not chunk_rows:
                    logger.warning(
                        "文档 %d stage=%s 但无 chunks，降级为完整流水线",
                        doc_id, resume_stage,
                    )
                    resume_stage = None  # 降级
                else:
                    total_chunks = len(chunk_rows)
                    resume_batch = doc.last_success_batch or 0

                    if resume_stage == "vector_storing":
                        # 内存向量已丢失，必须重新 embedding；同时清理 ChromaDB 残留
                        resume_batch = 0
                        try:
                            store = get_vector_store()
                            await store.delete(where={"doc_id": doc_id})
                            logger.info("文档 %d 清理向量存储残留向量（vector_storing 恢复）", doc_id)
                        except Exception:
                            logger.exception("文档 %d ChromaDB 残留向量清理失败，标记 FAILED", doc_id)
                            doc.status = DocumentStatus.FAILED
                            doc.error_msg = "ChromaDB 残留向量清理失败，无法恢复入库"
                            doc.current_stage = None
                            await db.commit()
                            return {"status": "failed", "doc_id": doc_id}

        if resume_stage is None or resume_stage not in RESUMABLE_STAGES:
            # 完整流水线路径：解析 → 分块 → 写入 MySQL
            async with async_session() as db:
                result = await _load_doc(db, doc_id)
                if result.doc is None:
                    return {"status": result.status, "doc_id": doc_id}
                doc = result.doc
                doc.status = DocumentStatus.PARSING
                doc.current_stage = "parsing"
                await db.commit()

            # 3a. 文档解析（CPU 操作，DB session 外执行）
            parse_result = parse_document(file_path, file_type)
            logger.info(
                "文档 %d 解析完成: total=%d, failed=%d, rate=%.2f%%",
                doc_id, parse_result.total_pages, parse_result.failed_pages,
                parse_result.failure_rate * 100,
            )

            # 3b. 空文档检测 + 容错判定
            async with async_session() as db:
                result = await _load_doc(db, doc_id)
                if result.doc is None:
                    return {"status": result.status, "doc_id": doc_id}
                doc = result.doc

                if parse_result.total_pages == 0 or not parse_result.full_text.strip():
                    doc.status = DocumentStatus.FAILED
                    doc.error_msg = "文档无有效内容，解析后全文为空"
                    doc.current_stage = None
                    await db.commit()
                    logger.warning("文档 %d 解析后无有效内容，标记为 failed", doc_id)
                    return {"status": "failed", "doc_id": doc_id}

                if parse_result.failure_rate > settings.PARSE_FAILURE_FAILED:
                    doc.status = DocumentStatus.FAILED
                    doc.error_msg = _build_error_msg(parse_result, settings.PARSE_FAILURE_FAILED)
                    doc.current_stage = None
                    await db.commit()
                    logger.warning("文档 %d 解析失败率 >50%%，标记为 failed", doc_id)
                    return {"status": "failed", "doc_id": doc_id}

                elif parse_result.failure_rate >= settings.PARSE_FAILURE_PARTIAL:
                    doc.status = DocumentStatus.PARTIAL_FAILED
                    doc.error_msg = _build_error_msg(parse_result, settings.PARSE_FAILURE_PARTIAL)
                    doc.current_stage = None
                    await db.commit()
                    logger.warning("文档 %d 解析失败率 20%%-50%%，标记为 partial_failed", doc_id)
                    return {"status": "partial_failed", "doc_id": doc_id}

                elif parse_result.failed_pages > 0:
                    doc.error_msg = "; ".join(parse_result.warnings)
                    logger.info("文档 %d 解析有 %d 个警告，继续流水线", doc_id, parse_result.failed_pages)

                doc.status = DocumentStatus.CHUNKING
                doc.current_stage = "chunking"
                await db.commit()

            # 3c. 智能分块（CPU 操作，DB session 外执行）
            chunking_result = chunk_document(parse_result.full_text, parse_result.pages)
            logger.info("文档 %d 分块完成: %d 块", doc_id, chunking_result.total_chunks)

            # 3d. 写入 chunks（先清理旧数据，幂等去重）
            async with async_session() as db:
                result = await _load_doc(db, doc_id)
                if result.doc is None:
                    return {"status": result.status, "doc_id": doc_id}
                doc = result.doc

                if chunking_result.total_chunks == 0:
                    doc.status = DocumentStatus.FAILED
                    doc.error_msg = "文档分块结果为空，无有效文本内容"
                    doc.current_stage = None
                    await db.commit()
                    return {"status": "failed", "doc_id": doc_id}

                # 清理旧 chunks（幂等：首次无数据，重试时删除上次残留）
                await db.execute(delete(Chunk).where(Chunk.doc_id == doc_id))

                for c in chunking_result.chunks:
                    chunk = Chunk(
                        doc_id=doc_id,
                        kb_id=kb_id,
                        chroma_id=f"doc_{doc_id}_chunk_{c.chunk_index}",
                        content=c.content,
                        chunk_index=c.chunk_index,
                        token_count=c.estimated_tokens,
                        metadata_={"page": c.page_number} if c.page_number else None,
                    )
                    db.add(chunk)

                doc.current_stage = "chunking_done"
                await db.commit()

            logger.info("文档 %d 分块已写入 MySQL: %d 条", doc_id, chunking_result.total_chunks)

            total_chunks = chunking_result.total_chunks
            # chunk_rows 在步骤 4a 统一从 DB 加载（获取真实 DB id）

        # ============================
        # 4. Embedding 向量化（含断点续传）
        # ============================

        # 4a. 从 DB 重载 chunks（获取真实 DB id，用于 token 回写）、更新状态
        async with async_session() as db:
            result = await _load_doc(db, doc_id)
            if result.doc is None:
                return {"status": result.status, "doc_id": doc_id}
            doc = result.doc

            doc.status = DocumentStatus.EMBEDDING
            doc.current_stage = "embedding"
            await db.commit()

            chunk_rows = await _load_chunk_rows(db, doc_id)
            if not chunk_rows:
                doc.status = DocumentStatus.FAILED
                doc.error_msg = "分块数据丢失，无法继续 Embedding"
                doc.current_stage = None
                await db.commit()
                return {"status": "failed", "doc_id": doc_id}

            total_chunks = len(chunk_rows)

        # 4b. 分批调用 Embedding API，每批成功后写入 checkpoint（支持断点续传）
        embeddings_data: list[tuple[int, list[float], int]] = []
        token_map: dict[int, int] = {}

        try:
            batch_size = settings.EMBED_BATCH_SIZE
            total_batches = (total_chunks + batch_size - 1) // batch_size

            for batch_no in range(resume_batch, total_batches):
                batch_start = batch_no * batch_size
                batch_end = min(batch_start + batch_size, total_chunks)
                batch_texts = [
                    chunk_rows[i]["content"] for i in range(batch_start, batch_end)
                ]

                embed_result = await embed_chunks(batch_texts)

                for i in range(len(batch_texts)):
                    row_idx = batch_start + i
                    embeddings_data.append((
                        row_idx,
                        embed_result.embeddings[i],
                        embed_result.token_counts[i],
                    ))
                    token_map[chunk_rows[row_idx]["id"]] = embed_result.token_counts[i]

                # 批次级 checkpoint
                async with async_session() as db:
                    doc = await db.get(Document, doc_id)
                    if doc is not None:
                        doc.last_success_batch = batch_no + 1
                        await db.commit()

                logger.info(
                    "文档 %d Embedding 批次 %d/%d 完成",
                    doc_id, batch_no + 1, total_batches,
                )

        except Exception as e:
            logger.exception("文档 %d Embedding 向量化失败", doc_id)
            async with async_session() as db:
                doc = await db.get(Document, doc_id)
                if doc is not None:
                    doc.status = DocumentStatus.FAILED
                    doc.error_msg = f"Embedding 向量化失败: {e}"
                    doc.current_stage = None
                    await db.commit()
            return {"status": "failed", "doc_id": doc_id, "error": str(e)}

        # ============================
        # 5. ChromaDB 批量写入
        # ============================

        async with async_session() as db:
            result = await _load_doc(db, doc_id)
            if result.doc is None:
                return {"status": result.status, "doc_id": doc_id}
            doc = result.doc
            doc.status = DocumentStatus.VECTOR_STORING
            doc.current_stage = "vector_storing"
            await db.commit()

        store = get_vector_store()
        chroma_batch_size = settings.CHROMA_BATCH_SIZE

        try:
            for chroma_start in range(0, total_chunks, chroma_batch_size):
                chroma_end = min(chroma_start + chroma_batch_size, total_chunks)
                ids_batch = [
                    chunk_rows[i]["chroma_id"]
                    for i in range(chroma_start, chroma_end)
                ]
                docs_batch = [
                    chunk_rows[i]["content"]
                    for i in range(chroma_start, chroma_end)
                ]
                embs_batch = [
                    embeddings_data[i][1]
                    for i in range(chroma_start, chroma_end)
                ]
                metas_batch = [
                    {
                        "kb_id": int(kb_id),
                        "doc_id": int(doc_id),
                        "chunk_index": int(chunk_rows[i]["chunk_index"]),
                    }
                    for i in range(chroma_start, chroma_end)
                ]

                await store.add(
                    ids=ids_batch,
                    documents=docs_batch,
                    embeddings=embs_batch,
                    metadatas=metas_batch,
                )
                logger.info(
                    "文档 %d 向量存储写入批次 %d/%d: %d 条",
                    doc_id,
                    chroma_start // chroma_batch_size + 1,
                    (total_chunks + chroma_batch_size - 1) // chroma_batch_size,
                    chroma_end - chroma_start,
                )

        except Exception as e:
            logger.exception("文档 %d 向量存储批量写入失败，清理已写入向量", doc_id)
            try:
                await store.delete(where={"doc_id": doc_id})
            except Exception:
                logger.exception("文档 %d ChromaDB 清理也失败了，可能残留部分向量", doc_id)

            async with async_session() as db:
                doc = await db.get(Document, doc_id)
                if doc is not None:
                    doc.status = DocumentStatus.FAILED
                    doc.error_msg = f"ChromaDB 写入失败: {e}"
                    doc.current_stage = None
                    await db.commit()
            return {"status": "failed", "doc_id": doc_id, "error": str(e)}

        # ============================
        # 6. 终态判定 + chunk_count 事务更新
        # ============================

        async with async_session() as db:
            result = await _load_doc(db, doc_id)
            if result.doc is None:
                return {"status": result.status, "doc_id": doc_id}
            doc = result.doc

            kb = await db.get(KnowledgeBase, kb_id)
            if kb is None:
                doc.status = DocumentStatus.FAILED
                doc.error_msg = f"知识库 {kb_id} 不存在，无法更新统计"
                doc.current_stage = None
                await db.commit()
                return {"status": "failed", "doc_id": doc_id}

            # 回写 token_count（DashScope API 实际值覆盖 chunker 估算值）
            for chunk_id, actual_tokens in token_map.items():
                await db.execute(
                    update(Chunk)
                    .where(Chunk.id == chunk_id)
                    .values(token_count=actual_tokens)
                )

            # 终态判定：解析阶段有 warning 则 success_with_warnings，否则 completed
            final_status = (
                DocumentStatus.SUCCESS_WITH_WARNINGS
                if doc.error_msg
                else DocumentStatus.COMPLETED
            )
            doc.status = final_status
            doc.chunk_count = total_chunks
            doc.current_stage = None
            doc.last_success_batch = 0

            # 原子更新知识库 chunk_count
            await db.execute(
                update(KnowledgeBase)
                .where(KnowledgeBase.id == kb_id)
                .values(chunk_count=KnowledgeBase.chunk_count + total_chunks)
            )

            await db.commit()
            logger.info(
                "文档 %d 入库完成: status=%s, chunks=%d",
                doc_id, final_status.value, total_chunks,
            )

        # 清除 BM25 缓存，下次查询时懒加载重建（对齐 ARCHITECTURE.md §6.2）
        await invalidate_bm25_cache_async(kb_id)

        return {
            "status": final_status.value,
            "doc_id": doc_id,
            "chunks": total_chunks,
        }

    finally:
        await release_idempotency_lock_async(doc_id, "ingest")


def _build_error_msg(parse_result, threshold: float) -> str:
    """构建容错错误信息"""
    # docx 按段落解析用"段"，其余按页
    unit = "段" if parse_result.source_type == "docx" else "页"
    base = (
        f"解析失败率 {parse_result.failure_rate:.0%}，"
        f"超过 {threshold:.0%} 阈值。"
        f"（{parse_result.failed_pages}/{parse_result.total_pages} {unit}失败）"
    )
    if parse_result.warnings:
        base += " " + "; ".join(parse_result.warnings[:5])  # 最多记录 5 条
        if len(parse_result.warnings) > 5:
            base += f" ... 等共 {len(parse_result.warnings)} 条警告"
    return base


# ==================== 文档删除任务 ====================

async def _delete_document_async(doc_id: int) -> dict:
    """文档异步删除实现：ChromaDB 向量清理 → 磁盘文件删除 → MySQL 物理删除（FK CASCADE 清 chunks）"""

    # 1. 获取幂等锁（异步上下文使用异步 Redis，避免阻塞事件循环）
    if not await acquire_idempotency_lock_async(doc_id, "delete"):
        logger.warning("文档 %d 删除幂等锁已被占用，拒绝重复入队", doc_id)
        return {"status": "locked", "doc_id": doc_id}

    try:
        # 2. 加载文档
        async with async_session() as db:
            doc = await db.get(Document, doc_id)
            if doc is None:
                logger.warning("文档 %d 不存在，跳过删除", doc_id)
                return {"status": "not_found", "doc_id": doc_id}

            if doc.status != DocumentStatus.DELETING:
                logger.warning(
                    "文档 %d 状态为 %s（非 DELETING），跳过删除", doc_id, doc.status.value,
                )
                return {"status": "skipped", "doc_id": doc_id, "reason": f"状态为 {doc.status.value}"}

            file_path = doc.file_path
            kb_id = doc.kb_id
            deleted_chunk_count = doc.chunk_count or 0

        # 3. 清理向量存储
        try:
            store = get_vector_store()
            await store.delete(where={"doc_id": doc_id})
            logger.info("文档 %d 向量存储向量已清理", doc_id)
        except Exception as e:
            logger.exception("文档 %d 向量存储向量清理失败", doc_id)
            return {"status": "error", "doc_id": doc_id, "error": f"向量存储清理失败: {e}"}

        # 4. 清理磁盘文件
        if file_path:
            try:
                await local_storage.delete(file_path)
                logger.info("文档 %d 磁盘文件已删除: %s", doc_id, file_path)
            except Exception as e:
                logger.warning("文档 %d 磁盘文件删除失败（非致命）: %s", doc_id, e)

        # 5. 物理删除 MySQL 记录（FK CASCADE 自动清理 chunks），并递减 KB 统计计数
        async with async_session() as db:
            doc = await db.get(Document, doc_id)
            if doc is not None:
                await db.delete(doc)
                await db.execute(
                    update(KnowledgeBase)
                    .where(KnowledgeBase.id == kb_id)
                    .values(
                        doc_count=func.greatest(0, KnowledgeBase.doc_count - 1),
                        chunk_count=func.greatest(0, KnowledgeBase.chunk_count - deleted_chunk_count),
                    )
                )
                await db.commit()
                logger.info("文档 %d MySQL 记录已物理删除，KB %d 计数已更新", doc_id, kb_id)

        # 清除 BM25 缓存，下次查询时懒加载重建（对齐 ARCHITECTURE.md §6.2）
        await invalidate_bm25_cache_async(kb_id)

        return {"status": "completed", "doc_id": doc_id}

    finally:
        await release_idempotency_lock_async(doc_id, "delete")


@celery_app.task(bind=True, max_retries=3, soft_time_limit=300, autoretry_for=(Exception,), retry_backoff=True)
def delete_document(self, doc_id: int) -> dict:
    """异步删除文档：清理 ChromaDB 向量 + 磁盘文件 + MySQL 记录（FK CASCADE 清 chunks）

    返回格式: {"status": str, "doc_id": int}
    未捕获异常自动重试（max_retries=3）。
    """
    return _get_worker_loop().run_until_complete(_delete_document_async(doc_id))


# ==================== 知识库删除任务 ====================


async def _delete_kb_async(kb_id: int) -> dict:
    """知识库异步删除实现：遍历文档清理 ChromaDB + 磁盘 → 物理 DELETE KB（FK CASCADE 清文档/chunks）"""

    # 1. 获取幂等锁（异步上下文使用异步 Redis，避免阻塞事件循环）
    if not await acquire_idempotency_lock_async(kb_id, "delete_kb"):
        logger.warning("知识库 %d 删除幂等锁已被占用，拒绝重复入队", kb_id)
        return {"status": "locked", "kb_id": kb_id}

    try:
        # 2. 加载 KB 并校验状态
        async with async_session() as db:
            kb = await db.get(KnowledgeBase, kb_id)
            if kb is None:
                logger.warning("知识库 %d 不存在，跳过删除", kb_id)
                return {"status": "not_found", "kb_id": kb_id}

            if kb.status != "deleting":
                logger.warning(
                    "知识库 %d 状态为 %s（非 deleting），跳过删除", kb_id, kb.status,
                )
                return {"status": "skipped", "kb_id": kb_id, "reason": f"状态为 {kb.status}"}

            # 加载 KB 下所有文档信息
            result = await db.execute(
                select(Document).where(Document.kb_id == kb_id)
            )
            docs = result.scalars().all()
            doc_info = [(d.id, d.file_path) for d in docs]
            logger.info("知识库 %d 开始异步删除: %d 个文档", kb_id, len(doc_info))

        # 3. 逐文档清理向量存储
        store = get_vector_store()
        for doc_id, _ in doc_info:
            try:
                await store.delete(where={"doc_id": doc_id})
                logger.info("知识库 %d 文档 %d 向量存储向量已清理", kb_id, doc_id)
            except Exception as e:
                logger.exception("知识库 %d 文档 %d 向量存储向量清理失败", kb_id, doc_id)
                return {"status": "error", "kb_id": kb_id, "error": f"文档 {doc_id} 向量存储清理失败: {e}"}

        # 4. 逐文档清理磁盘文件
        for doc_id, file_path in doc_info:
            if file_path:
                try:
                    await local_storage.delete(file_path)
                    logger.info("知识库 %d 文档 %d 磁盘文件已删除", kb_id, doc_id)
                except Exception as e:
                    logger.warning("知识库 %d 文档 %d 磁盘文件删除失败（非致命）: %s", kb_id, doc_id, e)

        # 5. 批量备份孤儿会话的 kb_id / kb_name（在物理删除 KB 之前）
        async with async_session() as db:
            kb = await db.get(KnowledgeBase, kb_id)
            if kb is not None:
                await db.execute(
                    update(Conversation)
                    .where(Conversation.kb_id == kb_id)
                    .values(
                        original_kb_id=kb_id,
                        original_kb_name=kb.name,
                        original_kb_uuid=kb.uuid,
                    )
                )
                await db.commit()
                logger.info("知识库 %d 关联会话已批量备份 original_kb_id/original_kb_uuid", kb_id)

        # 6. 物理删除 KB（FK CASCADE 自动清理 documents + chunks，conversations.kb_id SET NULL）
        async with async_session() as db:
            kb = await db.get(KnowledgeBase, kb_id)
            if kb is not None:
                await db.delete(kb)
                await db.commit()
                logger.info("知识库 %d MySQL 记录已物理删除", kb_id)

        return {"status": "completed", "kb_id": kb_id, "doc_count": len(doc_info)}

    finally:
        await release_idempotency_lock_async(kb_id, "delete_kb")


@celery_app.task(bind=True, max_retries=3, soft_time_limit=600, autoretry_for=(Exception,), retry_backoff=True)
def delete_kb(self, kb_id: int) -> dict:
    """异步删除知识库：遍历文档清理 ChromaDB + 磁盘 → 物理 DELETE KB

    返回格式: {"status": str, "kb_id": int}
    未捕获异常自动重试（max_retries=3）。
    """
    return _get_worker_loop().run_until_complete(_delete_kb_async(kb_id))
