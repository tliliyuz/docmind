"""文档/知识库异步删除任务 — ChromaDB 向量清理 + 磁盘文件删除 + MySQL 物理删除

从 tasks.py 提取，与入库管线完全独立的删除工作流。
"""

import logging

from sqlalchemy import delete, func, select, text, update

from app.core.chroma_client import get_vector_store
from app.rag.bm25 import invalidate_bm25_cache_async
from app.core.database import async_session
from app.core.storage import local_storage
from app.ingest.celery_app import celery_app
from app.ingest.lock import (
    acquire_idempotency_lock_async,
    release_idempotency_lock_async,
)
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.models.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)


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
            await store.delete(kb_id=kb_id, where={"doc_id": doc_id})
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
    # 局部导入解决循环依赖（delete_tasks → tasks._get_worker_loop）
    from app.ingest.tasks import _get_worker_loop
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

        # 3. 按 kb_id 删除整个 KB collection（O(1) 操作，比逐条 delete 快得多）
        store = get_vector_store()
        try:
            await store.delete(kb_id=kb_id)
            logger.info("知识库 %d 向量存储 collection 已删除（%d 个文档）", kb_id, len(doc_info))
        except Exception as e:
            logger.exception("知识库 %d 向量存储批量清理失败", kb_id)
            return {"status": "error", "kb_id": kb_id, "error": f"向量存储批量清理失败: {e}"}

        # 4. 逐文档清理磁盘文件
        for doc_id, file_path in doc_info:
            if file_path:
                try:
                    await local_storage.delete(file_path)
                    logger.info("知识库 %d 文档 %d 磁盘文件已删除", kb_id, doc_id)
                except Exception as e:
                    logger.warning("知识库 %d 文档 %d 磁盘文件删除失败（非致命）: %s", kb_id, doc_id, e)

        # 5. 批量备份孤儿会话的 kb_id / kb_name / kb_uuid（在物理删除 KB 之前）
        #    使用 raw SQL 避免 SQLAlchemy ORM update() 的列映射歧义
        async with async_session() as db:
            kb = await db.get(KnowledgeBase, kb_id)
            if kb is not None:
                result = await db.execute(
                    text(
                        "UPDATE conversations "
                        "SET original_kb_id = :orig_kb_id, "
                        "    original_kb_name = :orig_kb_name, "
                        "    original_kb_uuid = :orig_kb_uuid "
                        "WHERE kb_id = :kb_id"
                    ),
                    {
                        "orig_kb_id": kb_id,
                        "orig_kb_name": kb.name,
                        "orig_kb_uuid": kb.uuid,
                        "kb_id": kb_id,
                    },
                )
                await db.commit()
                logger.info(
                    "知识库 %d（name=%s uuid=%s）关联会话已批量备份 original_kb_*，影响 %d 行",
                    kb_id, kb.name, kb.uuid, result.rowcount,
                )

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
    # 局部导入解决循环依赖（delete_tasks → tasks._get_worker_loop）
    from app.ingest.tasks import _get_worker_loop
    return _get_worker_loop().run_until_complete(_delete_kb_async(kb_id))
