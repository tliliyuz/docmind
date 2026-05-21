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

from app.core.database import async_session
from app.ingest.celery_app import celery_app
from app.ingest.lock import acquire_idempotency_lock, release_idempotency_lock
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.enums import DocumentStatus, is_terminal
from app.rag.chunker import chunk_document
from app.rag.parser import parse_document

logger = logging.getLogger(__name__)

# 容错阈值（对齐 ARCHITECTURE.md §4.7）
FAILURE_THRESHOLD_PARTIAL = 0.2   # 20% 失败 → partial_failed
FAILURE_THRESHOLD_FAILED = 0.5    # 50% 失败 → failed


@celery_app.task(bind=True, max_retries=3, soft_time_limit=600)
def ingest_document(self, doc_id: int) -> dict:
    """文档入库主流水线（Celery 同步入口 → 异步执行）。

    返回格式: {"status": str, "doc_id": int}
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_ingest_document_async(doc_id))
    finally:
        loop.close()


async def _load_doc(db, doc_id: int) -> Document | None:
    """加载文档记录并检查 DELETING 状态。

    返回 None 表示已标记删除或不存在，调用方需区分两种情况。
    返回 Document 对象表示可继续处理。
    """
    doc = await db.get(Document, doc_id)
    if doc is None:
        return None
    if doc.status == DocumentStatus.DELETING:
        logger.info(f"文档 {doc_id} 已被标记删除，中止流水线")
        return None
    return doc


async def _ingest_document_async(doc_id: int) -> dict:
    """入库流水线异步实现：幂等锁 → 解析 → 分块 → Embedding(待实现) → 向量存储(待实现)"""

    # 1. 获取幂等锁
    if not acquire_idempotency_lock(doc_id, "ingest"):
        logger.warning(f"文档 {doc_id} 幂等锁已被占用，拒绝重复入队")
        return {"status": "locked", "doc_id": doc_id}

    try:
        # 2. 阶段 1: 加载文档 + 开始解析
        async with async_session() as db:
            doc = await _load_doc(db, doc_id)
            if doc is None:
                # _load_doc 返回 None 有两种可能：文档不存在或 DELETING
                doc_check = await db.get(Document, doc_id)
                if doc_check is None:
                    logger.error(f"文档 {doc_id} 不存在，跳过入库")
                    return {"status": "not_found", "doc_id": doc_id}
                return {"status": "deleting", "doc_id": doc_id}

            file_path = doc.file_path
            file_type = doc.file_type
            kb_id = doc.kb_id

            if not file_path:
                doc.status = DocumentStatus.FAILED
                doc.error_msg = "文件路径为空，无法解析"
                await db.commit()
                return {"status": "failed", "doc_id": doc_id}

            doc.status = DocumentStatus.PARSING
            doc.current_stage = "parsing"
            await db.commit()

        # 3. 文档解析（CPU 操作，在 DB session 外执行）
        parse_result = parse_document(file_path, file_type)
        logger.info(
            f"文档 {doc_id} 解析完成: total={parse_result.total_pages}, "
            f"failed={parse_result.failed_pages}, rate={parse_result.failure_rate:.2%}"
        )

        # 4. 空文档检测 + 容错判定 → 阶段 2 准备
        async with async_session() as db:
            doc = await db.get(Document, doc_id)
            if doc is None:
                return {"status": "not_found", "doc_id": doc_id}
            if doc.status == DocumentStatus.DELETING:
                return {"status": "deleting", "doc_id": doc_id}

            # 空文档：total_pages 为 0 或 full_text 为空
            if parse_result.total_pages == 0 or not parse_result.full_text.strip():
                doc.status = DocumentStatus.FAILED
                doc.error_msg = "文档无有效内容，解析后全文为空"
                doc.current_stage = None
                await db.commit()
                logger.warning(f"文档 {doc_id} 解析后无有效内容，标记为 failed")
                return {"status": "failed", "doc_id": doc_id}

            if parse_result.failure_rate > FAILURE_THRESHOLD_FAILED:
                doc.status = DocumentStatus.FAILED
                doc.error_msg = _build_error_msg(parse_result, FAILURE_THRESHOLD_FAILED)
                doc.current_stage = None
                await db.commit()
                logger.warning(f"文档 {doc_id} 解析失败率 >50%，标记为 failed")
                return {"status": "failed", "doc_id": doc_id}

            elif parse_result.failure_rate >= FAILURE_THRESHOLD_PARTIAL:
                doc.status = DocumentStatus.PARTIAL_FAILED
                doc.error_msg = _build_error_msg(parse_result, FAILURE_THRESHOLD_PARTIAL)
                doc.current_stage = None
                await db.commit()
                logger.warning(f"文档 {doc_id} 解析失败率 20%-50%，标记为 partial_failed")
                return {"status": "partial_failed", "doc_id": doc_id}

            elif parse_result.failed_pages > 0:
                warnings_text = "; ".join(parse_result.warnings)
                doc.error_msg = warnings_text
                logger.info(f"文档 {doc_id} 解析有 {parse_result.failed_pages} 个警告，继续流水线")

            # 阶段 2: 开始分块
            doc.status = DocumentStatus.CHUNKING
            doc.current_stage = "chunking"
            await db.commit()

        # 5. 智能分块（CPU 操作，在 DB session 外执行）
        chunking_result = chunk_document(parse_result.full_text, parse_result.pages)
        logger.info(f"文档 {doc_id} 分块完成: {chunking_result.total_chunks} 块")

        # 6. 写入 chunks + 终态判定
        async with async_session() as db:
            doc = await db.get(Document, doc_id)
            if doc is None:
                return {"status": "not_found", "doc_id": doc_id}
            if doc.status == DocumentStatus.DELETING:
                return {"status": "deleting", "doc_id": doc_id}

            if chunking_result.total_chunks == 0:
                doc.status = DocumentStatus.FAILED
                doc.error_msg = "文档分块结果为空，无有效文本内容"
                doc.current_stage = None
                await db.commit()
                return {"status": "failed", "doc_id": doc_id}

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

        logger.info(f"文档 {doc_id} 分块已写入 MySQL: {chunking_result.total_chunks} 条")

        # 7. 阶段 3: Embedding 向量化（Phase 2 3.2 后续任务实现）
        # TODO: 调用 embedder.embed_chunks(chunks)

        # 8. 阶段 4: ChromaDB 批量写入（Phase 2 3.2 后续任务实现）
        # TODO: 调用 vector_store.batch_write(chunks_with_embeddings)

        # 9. 终态判定 + chunk_count 事务更新（Phase 2 3.2 后续任务实现）
        # TODO: 全部 stage 完成后写入 completed 终态

        return {"status": "chunking_done", "doc_id": doc_id, "chunks": chunking_result.total_chunks}

    except Exception as e:
        logger.exception(f"文档 {doc_id} 入库流水线异常: {e}")
        try:
            async with async_session() as db:
                doc = await db.get(Document, doc_id)
                if doc is not None:
                    doc.status = DocumentStatus.FAILED
                    doc.error_msg = f"入库流水线异常: {e}"
                    doc.current_stage = None
                    await db.commit()
        except Exception:
            logger.exception(f"文档 {doc_id} 异常状态更新也失败了")
        return {"status": "error", "doc_id": doc_id, "error": str(e)}

    finally:
        release_idempotency_lock(doc_id, "ingest")


def _build_error_msg(parse_result, threshold: float) -> str:
    """构建容错错误信息"""
    unit = "段" if parse_result.total_pages > 0 and any(
        p.page_number > 1 for p in parse_result.pages
    ) else "页"
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


# ==================== 文档删除任务（Phase 2 后续实现） ====================

@celery_app.task(bind=True, max_retries=3, soft_time_limit=300)
def delete_document(self, doc_id: int) -> dict:
    """异步删除文档：清理 ChromaDB 向量 + 磁盘文件 + MySQL 记录"""
    # TODO: Phase 2 后续任务实现
    return {"status": "not_implemented", "doc_id": doc_id}
