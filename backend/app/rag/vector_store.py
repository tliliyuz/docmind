"""向量存储抽象层 — BaseVectorStore ABC + ChromaVectorStore 实现

对齐 ADR-018：
- 定义 search/add/delete 三个核心操作
- 不暴露 count()：空库判断走 Document 表 COUNT，不同向量库 count 语义差异大
- ChromaVectorStore 通过 asyncio.to_thread() 将同步 ChromaDB 调用卸载到线程池

Per-KB Collection 策略（Decision #29）：
- 每个知识库独立 ChromaDB collection（`kb_{kb_id}`）
- 查询时无需 where 过滤，直接命中目标 collection，消除 metadata filter 性能瓶颈
"""

import asyncio
import logging
from abc import ABC, abstractmethod

from chromadb.api import ClientAPI, Collection

logger = logging.getLogger(__name__)


class BaseVectorStore(ABC):
    """向量存储抽象基类

    仅定义向量存储最核心的三个操作：检索、写入、删除。
    不定义 count()：不同向量库 count 语义不同（Qdrant client.count()、
    ES _index.stats()、Milvus query aggregate），强行塞入 ABC 会为了满足接口而削足适履。
    """

    @abstractmethod
    async def search(
        self,
        query_embeddings: list[list[float]],
        n_results: int,
        kb_id: int,
        include: list[str],
        where: dict | None = None,
    ) -> dict:
        """向量相似度检索

        Args:
            query_embeddings: 查询向量列表
            n_results: 返回结果数
            kb_id: 目标知识库 ID（必填，检索限定在该 KB 的 collection 内）
            include: 返回字段列表（如 ["documents", "distances", "metadatas"]）
            where: 可选的附加 metadata 过滤条件（如 {"doc_id": 42}），KB 级隔离由 kb_id 保证

        Returns:
            ChromaDB 格式的原始结果 dict：
            {"ids": [[...]], "documents": [[...]], "distances": [[...]], "metadatas": [[...]]}
        """
        ...

    @abstractmethod
    async def add(
        self,
        ids: list[str],
        kb_id: int,
        embeddings: list[list[float]] | None = None,
        documents: list[str] | None = None,
        metadatas: list[dict] | None = None,
    ) -> None:
        """批量写入向量及元数据到指定 KB 的 collection"""
        ...

    @abstractmethod
    async def delete(self, kb_id: int, where: dict | None = None) -> None:
        """按条件删除向量

        Args:
            kb_id: 目标知识库 ID
            where: 删除条件；为 None 时删除整个 KB collection
        """
        ...


class ChromaVectorStore(BaseVectorStore):
    """ChromaDB 向量存储实现（Per-KB Collection 策略）

    管理多个 KB collection（`kb_{kb_id}`），懒加载创建。
    所有同步操作通过 asyncio.to_thread() 卸载，避免阻塞事件循环。
    """

    def __init__(self, client: ClientAPI):
        self._client = client
        self._collections: dict[int, Collection] = {}

    def _get_kb_collection(self, kb_id: int) -> Collection:
        """获取或懒加载创建 KB 专属 collection"""
        if kb_id not in self._collections:
            self._collections[kb_id] = self._client.get_or_create_collection(
                name=f"kb_{kb_id}",
                metadata={"hnsw:space": "cosine"},
            )
        return self._collections[kb_id]

    async def search(
        self,
        query_embeddings: list[list[float]],
        n_results: int,
        kb_id: int,
        include: list[str],
        where: dict | None = None,
    ) -> dict:
        try:
            import threading as _threading
            import time as _time

            _inner_elapsed = 0.0
            _collection = self._get_kb_collection(kb_id)

            def _query_in_thread():
                nonlocal _inner_elapsed
                _t_inner = _time.perf_counter()
                # Per-KB collection：不再需要 where={"kb_id": kb_id}，metadata filter 仅用于 doc 级过滤
                r = _collection.query(
                    query_embeddings=query_embeddings,
                    n_results=n_results,
                    where=where,
                    include=include,
                )
                _inner_elapsed = _time.perf_counter() - _t_inner
                return r

            _t0 = _time.perf_counter()
            _threads_before = _threading.active_count()
            result = await asyncio.to_thread(_query_in_thread)
            _elapsed = _time.perf_counter() - _t0
            _threads_after = _threading.active_count()

            _queue_time = _elapsed - _inner_elapsed
            logger.info(
                "CHROMA_QUERY total=%.3fs queue=%.3fs exec=%.3fs threads_before=%d threads_after=%d n_results=%d kb_id=%d where=%s",
                _elapsed, _queue_time, _inner_elapsed, _threads_before, _threads_after, n_results, kb_id, where,
            )
            return result
        except Exception:
            logger.exception("ChromaDB search 失败: kb_id=%d", kb_id)
            raise

    async def add(
        self,
        ids: list[str],
        kb_id: int,
        embeddings: list[list[float]] | None = None,
        documents: list[str] | None = None,
        metadatas: list[dict] | None = None,
    ) -> None:
        try:
            _collection = self._get_kb_collection(kb_id)
            await asyncio.to_thread(
                _collection.add,
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )
        except Exception:
            logger.exception("ChromaDB add 失败: kb_id=%d", kb_id)
            raise

    async def delete(self, kb_id: int, where: dict | None = None) -> None:
        """删除向量。

        where=None 时直接删除整个 KB collection（O(1) 操作），
        用于知识库删除场景，比逐条 delete 快得多。
        """
        try:
            if where is None:
                # 删除整个 KB collection
                try:
                    await asyncio.to_thread(
                        self._client.delete_collection,
                        name=f"kb_{kb_id}",
                    )
                except Exception:
                    # collection 不存在时忽略
                    logger.debug("ChromaDB collection kb_%d 不存在或已删除", kb_id)
                self._collections.pop(kb_id, None)
                logger.info("ChromaDB KB %d collection 已删除", kb_id)
            else:
                _collection = self._get_kb_collection(kb_id)
                await asyncio.to_thread(
                    _collection.delete,
                    where=where,
                )
        except Exception:
            logger.exception("ChromaDB delete 失败: kb_id=%d where=%s", kb_id, where)
            raise
