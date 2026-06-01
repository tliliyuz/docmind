"""Rerank 重排序模块 — 检索结果精排

对齐 ARCHITECTURE.md §7.3 / ROADMAP.md Decision #18：
- Phase 3: NoopReranker 占位实现，按 chunk 长度升序排列后截取 top_k=5
- Phase 3+: DashScope Rerank API 精排

设计要点：
- 短 chunk 优先：相同 token 预算下覆盖更多独立文档
- 输入不足 top_k 时返回全部
- 不改变 chunk 内容，仅调整顺序
"""

import logging
from abc import ABC, abstractmethod

from app.rag.retriever import RetrievalOutput, RetrievalResult

logger = logging.getLogger(__name__)

# 默认 top_k 值，对齐 ARCHITECTURE.md §7.3
DEFAULT_RERANK_TOP_K = 5


class BaseReranker(ABC):
    """Reranker 基类，定义重排序接口"""

    @abstractmethod
    async def rerank(
        self,
        query: str,
        retrieval_output: RetrievalOutput,
        top_k: int = DEFAULT_RERANK_TOP_K,
    ) -> RetrievalOutput:
        """对检索结果进行重排序。

        Args:
            query: 用户问题（当前 NoopReranker 不使用，保留接口一致性）
            retrieval_output: 检索结果
            top_k: 返回结果数量上限

        Returns:
            RetrievalOutput: 重排序后的结果
        """
        ...


class NoopReranker(BaseReranker):
    """占位实现：按 chunk 长度升序排列后截取 top_k

    对齐 ARCHITECTURE.md §7.3：
    - 短 chunk 优先：相同 token 预算下覆盖更多独立文档
    - 输入不足 top_k 时返回全部
    - 不改变 chunk 内容，仅调整顺序
    """

    async def rerank(
        self,
        query: str,
        retrieval_output: RetrievalOutput,
        top_k: int = DEFAULT_RERANK_TOP_K,
    ) -> RetrievalOutput:
        """按 chunk 长度升序排列后截取 top_k。

        Args:
            query: 用户问题（NoopReranker 不使用）
            retrieval_output: 检索结果
            top_k: 返回结果数量上限，默认 5

        Returns:
            RetrievalOutput: 重排序后的结果
        """
        if not retrieval_output.results:
            logger.info("NoopReranker: 输入结果为空，直接返回")
            return RetrievalOutput()

        # 按 content 长度升序排列（短 chunk 优先）
        sorted_results = sorted(
            retrieval_output.results,
            key=lambda r: len(r.content),
        )

        # 截取 top_k
        truncated_results = sorted_results[:top_k]

        logger.info(
            "NoopReranker: %d 条输入 → 按长度排序 → 截取 top_%d → %d 条输出",
            len(retrieval_output.results),
            top_k,
            len(truncated_results),
        )

        return RetrievalOutput(
            results=truncated_results,
            total=len(truncated_results),
        )
