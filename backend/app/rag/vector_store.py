"""向量存储抽象层 — BaseVectorStore ABC + ChromaVectorStore 实现

对齐 ADR-018：
- 定义 search/add/delete 三个核心操作
- 不暴露 count()：空库判断走 Document 表 COUNT，不同向量库 count 语义差异大
- ChromaVectorStore 通过 asyncio.to_thread() 将同步 ChromaDB 调用卸载到线程池
"""

import logging
from abc import ABC, abstractmethod

from chromadb.api import Collection

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
        where: dict,
        include: list[str],
    ) -> dict:
        """向量相似度检索

        Args:
            query_embeddings: 查询向量列表
            n_results: 返回结果数
            where: metadata 过滤条件（如 {"kb_id": 1}）
            include: 返回字段列表（如 ["documents", "distances", "metadatas"]）

        Returns:
            ChromaDB 格式的原始结果 dict：
            {"ids": [[...]], "documents": [[...]], "distances": [[...]], "metadatas": [[...]]}
        """
        ...

    @abstractmethod
    async def add(
        self,
        ids: list[str],
        embeddings: list[list[float]] | None = None,
        documents: list[str] | None = None,
        metadatas: list[dict] | None = None,
    ) -> None:
        """批量写入向量及元数据"""
        ...

    @abstractmethod
    async def delete(self, where: dict) -> None:
        """按条件删除向量"""
        ...


class ChromaVectorStore(BaseVectorStore):
    """ChromaDB 向量存储实现

    包装 ChromaDB Collection，所有同步操作通过 asyncio.to_thread() 卸载，
    避免阻塞事件循环（对齐 CLAUDE.md 异步 IO 约束）。
    """

    def __init__(self, collection: Collection):
        self._collection = collection

    async def search(
        self,
        query_embeddings: list[list[float]],
        n_results: int,
        where: dict,
        include: list[str],
    ) -> dict:
        import asyncio

        try:
            return await asyncio.to_thread(
                self._collection.query,
                query_embeddings=query_embeddings,
                n_results=n_results,
                where=where,
                include=include,
            )
        except Exception:
            logger.exception("ChromaDB search 失败")
            raise

    async def add(
        self,
        ids: list[str],
        embeddings: list[list[float]] | None = None,
        documents: list[str] | None = None,
        metadatas: list[dict] | None = None,
    ) -> None:
        import asyncio

        try:
            await asyncio.to_thread(
                self._collection.add,
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )
        except Exception:
            logger.exception("ChromaDB add 失败")
            raise

    async def delete(self, where: dict) -> None:
        import asyncio

        try:
            await asyncio.to_thread(
                self._collection.delete,
                where=where,
            )
        except Exception:
            logger.exception("ChromaDB delete 失败")
            raise
