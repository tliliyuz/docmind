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

from celery import Task
from sqlalchemy import select

from app.core.database import async_session
from app.ingest.celery_app import celery_app
from app.ingest.lock import acquire_idempotency_lock, release_idempotency_lock
from app.models.document import Document
from app.models.enums import DocumentStatus, is_terminal
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
    return asyncio.run(_ingest_document_async(doc_id))


async def _ingest_document_async(doc_id: int) -> dict:
    """入库流水线异步实现：幂等锁 → 解析 → 分块(待实现) → Embedding(待实现) → 向量存储(待实现)"""

    # 1. 获取幂等锁
    if not acquire_idempotency_lock(doc_id, "ingest"):
        logger.warning(f"文档 {doc_id} 幂等锁已被占用，拒绝重复入队")
        return {"status": "locked", "doc_id": doc_id}

    try:
        # 2. 加载文档记录
        async with async_session() as db:
            result = await db.execute(select(Document).where(Document.id == doc_id))
            doc = result.scalar_one_or_none()

            if doc is None:
                logger.error(f"文档 {doc_id} 不存在，跳过入库")
                return {"status": "not_found", "doc_id": doc_id}

            if doc.status == DocumentStatus.DELETING:
                logger.info(f"文档 {doc_id} 正在删除中，跳过入库")
                return {"status": "deleting", "doc_id": doc_id}

            file_path = doc.file_path
            file_type = doc.file_type

            if not file_path:
                doc.status = DocumentStatus.FAILED
                doc.error_msg = "文件路径为空，无法解析"
                await db.commit()
                return {"status": "failed", "doc_id": doc_id}

            # 3. 阶段 1: 文档解析
            doc.status = DocumentStatus.PARSING
            doc.current_stage = "parsing"
            await db.commit()

        # 解析文档（同步 IO 操作，在 DB session 外执行）
        parse_result = parse_document(file_path, file_type)
        logger.info(
            f"文档 {doc_id} 解析完成: total={parse_result.total_pages}, "
            f"failed={parse_result.failed_pages}, rate={parse_result.failure_rate:.2%}"
        )

        # 4. 容错判定
        async with async_session() as db:
            result = await db.execute(select(Document).where(Document.id == doc_id))
            doc = result.scalar_one_or_none()
            if doc is None:
                return {"status": "not_found", "doc_id": doc_id}

            if parse_result.failure_rate > FAILURE_THRESHOLD_FAILED:
                # > 50% 失败 → 终态 failed
                doc.status = DocumentStatus.FAILED
                doc.error_msg = _build_error_msg(parse_result, FAILURE_THRESHOLD_FAILED)
                doc.current_stage = None
                await db.commit()
                logger.warning(f"文档 {doc_id} 解析失败率 >50%，标记为 failed")
                return {"status": "failed", "doc_id": doc_id}

            elif parse_result.failure_rate >= FAILURE_THRESHOLD_PARTIAL:
                # 20%~50% 失败 → 终态 partial_failed
                doc.status = DocumentStatus.PARTIAL_FAILED
                doc.error_msg = _build_error_msg(parse_result, FAILURE_THRESHOLD_PARTIAL)
                doc.current_stage = None
                await db.commit()
                logger.warning(f"文档 {doc_id} 解析失败率 20%-50%，标记为 partial_failed")
                return {"status": "partial_failed", "doc_id": doc_id}

            elif parse_result.failed_pages > 0:
                # < 20% 失败 → 记录 warning，继续后续阶段
                warnings_text = "; ".join(parse_result.warnings)
                doc.error_msg = warnings_text
                doc.current_stage = "parsing_done"
                await db.commit()
                logger.info(f"文档 {doc_id} 解析有 {parse_result.failed_pages} 页警告，继续流水线")
            else:
                # 全部成功 → 继续后续阶段
                doc.current_stage = "parsing_done"
                await db.commit()
                logger.info(f"文档 {doc_id} 解析全部成功，进入下一阶段")

        # 5. 阶段 2: 智能分块（Phase 2 3.2 后续任务实现）
        # TODO: 调用 chunker.chunk_document(parse_result.full_text)

        # 6. 阶段 3: Embedding 向量化（Phase 2 3.2 后续任务实现）
        # TODO: 调用 embedder.embed_chunks(chunks)

        # 7. 阶段 4: ChromaDB 批量写入（Phase 2 3.2 后续任务实现）
        # TODO: 调用 vector_store.batch_write(chunks_with_embeddings)

        # 8. 终态判定 + chunk_count 事务更新（Phase 2 3.2 后续任务实现）
        # TODO: 全部 stage 完成后写入 completed 终态

        return {"status": "parsing_done", "doc_id": doc_id}

    except Exception as e:
        logger.exception(f"文档 {doc_id} 入库流水线异常: {e}")
        # 尝试更新文档状态为 failed
        try:
            async with async_session() as db:
                result = await db.execute(select(Document).where(Document.id == doc_id))
                doc = result.scalar_one_or_none()
                if doc is not None:
                    doc.status = DocumentStatus.FAILED
                    doc.error_msg = f"入库流水线异常: {e}"
                    doc.current_stage = None
                    await db.commit()
        except Exception:
            logger.exception(f"文档 {doc_id} 异常状态更新也失败了")
        return {"status": "error", "doc_id": doc_id, "error": str(e)}

    finally:
        # 释放幂等锁
        release_idempotency_lock(doc_id, "ingest")


def _build_error_msg(parse_result, threshold: float) -> str:
    """构建容错错误信息"""
    base = (
        f"解析失败率 {parse_result.failure_rate:.0%}，"
        f"超过 {threshold:.0%} 阈值。"
        f"（{parse_result.failed_pages}/{parse_result.total_pages} 页失败）"
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
