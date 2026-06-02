"""向量检索器 — ChromaDB 向量相似度检索

对齐 ARCHITECTURE.md §5.1 / ROADMAP.md Decision #15, #21：
- 单 collection `docmind`，metadata `kb_id` 隔离
- cosine 相似度，top_k=10
- metadata 保持 native int 类型
"""

import logging
from dataclasses import dataclass, field

from chromadb.api import Collection

from app.core.chroma_client import get_collection
from app.core.exceptions import RetrievalServiceException
from app.rag.embedder import embed_chunks

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 10


@dataclass
class RetrievalResult:
    """标准化检索结果，Vector / BM25 共用，方便 RRF 融合"""
    doc_id: int
    chunk_index: int
    content: str
    score: float
    page: int | None = None
    doc_name: str = ""


@dataclass
class RetrievalOutput:
    """检索输出聚合"""
    results: list[RetrievalResult] = field(default_factory=list)
    total: int = 0


class VectorRetriever:
    """ChromaDB 向量检索器

    将用户问题向量化后，在 ChromaDB 中按 kb_id 过滤检索最相似的 chunks。
    """

    def __init__(self, collection: Collection | None = None):
        self._collection = collection or get_collection()

    async def search(
        self,
        query: str,
        kb_id: int,
        top_k: int = DEFAULT_TOP_K,
    ) -> RetrievalOutput:
        """执行向量检索。

        Args:
            query: 用户问题
            kb_id: 目标知识库 ID（int 类型，对齐 Decision #21）
            top_k: 返回结果数量上限

        Returns:
            RetrievalOutput: 包含标准化结果列表和总数

        Raises:
            RuntimeError: Embedding API 调用失败
        """
        if not query or not query.strip():
            logger.warning("查询内容为空，跳过向量检索")
            return RetrievalOutput()

        # 1. 对问题进行向量化（text_type="query"，DashScope 区分 query/document 策略）
        try:
            embed_result = await embed_chunks([query], text_type="query")
        except Exception as e:
            logger.exception("查询向量化失败: kb_id=%d", kb_id)
            raise RetrievalServiceException(f"查询向量化失败: {e}") from e

        if not embed_result.embeddings:
            logger.error("问题向量化结果为空")
            return RetrievalOutput()

        query_vector = embed_result.embeddings[0]

        # 2. ChromaDB 向量检索（where 过滤 kb_id，metadata 为 int 类型）
        try:
            chroma_results = self._collection.query(
                query_embeddings=[query_vector],
                n_results=top_k,
                where={"kb_id": kb_id},
                include=["documents", "distances", "metadatas"],
            )
        except Exception as e:
            logger.exception("ChromaDB 向量检索异常: kb_id=%d", kb_id)
            raise RetrievalServiceException(f"ChromaDB 查询失败: {e}") from e

        # 3. 解析 ChromaDB 返回结果
        return self._parse_results(chroma_results)

    def _parse_results(self, chroma_results: dict) -> RetrievalOutput:
        """将 ChromaDB 原始返回解析为标准化 RetrievalResult 列表。

        ChromaDB 返回结构（每个字段是嵌套列表，外层按 query，内层按 result）：
          ids: [[id1, id2, ...]]
          documents: [[doc1, doc2, ...]]
          distances: [[dist1, dist2, ...]]   # cosine: dist = 1 - cosine_similarity
          metadatas: [[meta1, meta2, ...]]

        空结果时 ids[0] 为空列表。
        """
        ids = chroma_results.get("ids", [[]])
        documents = chroma_results.get("documents", [[]])
        distances = chroma_results.get("distances", [[]])
        metadatas = chroma_results.get("metadatas", [[]])

        # 取第一条 query 的结果（单 query 场景）
        if not ids or not ids[0]:
            logger.info("ChromaDB 向量检索无结果")
            return RetrievalOutput()

        result_ids = ids[0]
        result_docs = documents[0] if documents and documents[0] else [None] * len(result_ids)
        result_dists = distances[0] if distances and distances[0] else [0.0] * len(result_ids)
        result_metas = metadatas[0] if metadatas and metadatas[0] else [{}] * len(result_ids)

        results: list[RetrievalResult] = []
        for i, chunk_id in enumerate(result_ids):
            meta = result_metas[i] or {}
            # cosine 空间: distance = 1 - cosine_similarity → score = 1 - distance
            distance = result_dists[i] if result_dists[i] is not None else 1.0
            score = 1.0 - distance

            # 确保 metadata 值为 int 类型（对齐 Decision #21）
            doc_id = int(meta.get("doc_id", 0))
            chunk_index = int(meta.get("chunk_index", 0))

            results.append(RetrievalResult(
                doc_id=doc_id,
                chunk_index=chunk_index,
                content=result_docs[i] or "",
                score=score,
            ))

        logger.info("向量检索完成: %d 条结果", len(results))
        return RetrievalOutput(results=results, total=len(results))
