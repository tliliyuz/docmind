"""粗排层（Coarse Ranking）— ADR-024

在 RRF 融合后、DashScope Rerank 精排前插入廉价向量相似度粗排，
过滤明显不相关的 chunk，缩候选池后送精排，降低精排噪声比。

核心设计：
- 算法：query embedding 与 chunk embedding 余弦相似度（L2 归一化点积）
- 复用性：query embedding 在向量检索阶段已生成，零额外 API 调用
- 性能：≤20 次点积运算，<1ms
- 降级：任何异常 → 跳过粗排，直接传递原始结果
- 下限保护：粗排后候选不足 RERANK_TOP_K 时标记 skip_rerank
"""

import logging
import math

from app.config import settings
from app.rag.retriever import RetrievalOutput, RetrievalResult

logger = logging.getLogger(__name__)


class CoarseRanker:
    """向量相似度粗排器

    复用向量检索阶段已生成的 query embedding 与每条候选 chunk embedding
    做余弦相似度计算，过滤低于阈值的低分 chunk，按相似度降序排列后
    取 top_k 截断，缩候选池后送入精排。
    """

    def __init__(self) -> None:
        self._enabled = settings.COARSE_RANK_ENABLED
        self._threshold = settings.COARSE_RANK_THRESHOLD
        self._top_k = settings.COARSE_TOP_K

    def rank(
        self,
        query_embedding: list[float],
        retrieval_output: RetrievalOutput,
    ) -> RetrievalOutput:
        """对融合后的候选列表执行粗排。

        Args:
            query_embedding: 查询向量（来自 VectorRetriever.search() 的 query_embedding）
            retrieval_output: RRF 融合后的候选结果

        Returns:
            RetrievalOutput: 粗排后的结果（过滤+截断），保留原始 stats/fusion_method

        降级路径：
          - COARSE_RANK_ENABLED=False → 直接返回原始结果
          - 任何异常 → 返回原始结果
          - 全部低于阈值 → 返回原始结果的前 COARSE_TOP_K
          - 候选为空 → 返回空结果
        """
        if not self._enabled:
            logger.debug("CoarseRank: 已禁用，跳过粗排")
            return retrieval_output

        candidates = retrieval_output.results
        if not candidates:
            logger.debug("CoarseRank: 候选为空，跳过粗排")
            return retrieval_output

        try:
            scored = self._score_candidates(query_embedding, candidates)
            filtered = self._filter_and_truncate(scored, candidates)
            return self._build_output(filtered, retrieval_output)
        except Exception:
            logger.exception("CoarseRanker 异常，降级返回原始融合结果")
            return retrieval_output

    def _score_candidates(
        self,
        query_embedding: list[float],
        candidates: list[RetrievalResult],
    ) -> list[tuple[float, int]]:
        """计算每个候选与查询向量的余弦相似度。

        有 embedding 的候选：计算真实余弦相似度
        无 embedding 的候选（BM25-only）：分配中性分数（阈值），不过滤

        Returns:
            [(similarity, original_index), ...] 按原始顺序排列
        """
        query_norm = self._l2_normalize(query_embedding)
        scored: list[tuple[float, int]] = []

        for i, candidate in enumerate(candidates):
            if candidate.embedding is not None:
                chunk_norm = self._l2_normalize(candidate.embedding)
                sim = self._dot_product(query_norm, chunk_norm)
            else:
                # BM25-only 结果无 embedding，分配中性分数（不低于阈值，不过滤）
                sim = self._threshold
                logger.debug(
                    "CoarseRank: 候选 #%d (doc_id=%d) 无 embedding，分配中性分数 %.3f",
                    i, candidate.doc_id, sim,
                )

            scored.append((sim, i))

        return scored

    def _filter_and_truncate(
        self,
        scored: list[tuple[float, int]],
        candidates: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        """过滤低于阈值的候选 + 按相似度降序排列 + top_k 截断。

        全部低于阈值时：降级返回原始候选的前 COARSE_TOP_K（回退策略）。
        """
        # 过滤：余弦相似度 >= 阈值 才保留
        passed = [(sim, idx) for sim, idx in scored if sim >= self._threshold]

        if not passed:
            # 全部低于阈值 → 降级：返回原始结果的前 COARSE_TOP_K
            fallback_count = min(len(candidates), self._top_k)
            logger.warning(
                "CoarseRank: 全部 %d 条候选低于阈值 %.3f，降级返回原始前 %d 条",
                len(candidates), self._threshold, fallback_count,
            )
            return candidates[:fallback_count]

        # 按相似度降序排列
        passed.sort(key=lambda x: x[0], reverse=True)

        # top_k 截断
        top_indices = [idx for _, idx in passed[:self._top_k]]

        logger.info(
            "CoarseRank: %d 条输入 → %d 条通过阈值 → top_%d → %d 条输出",
            len(candidates), len(passed), self._top_k, len(top_indices),
        )

        return [candidates[idx] for idx in top_indices]

    @staticmethod
    def _build_output(
        results: list[RetrievalResult],
        original: RetrievalOutput,
    ) -> RetrievalOutput:
        """构建粗排后的 RetrievalOutput，保留原始元数据"""
        return RetrievalOutput(
            results=results,
            total=len(results),
            stats=original.stats,
            fusion_method=original.fusion_method,
            query_embedding=original.query_embedding,
        )

    @staticmethod
    def _l2_normalize(vec: list[float]) -> list[float]:
        """L2 归一化向量，用于余弦相似度计算"""
        norm = math.sqrt(sum(x * x for x in vec))
        if norm == 0:
            return vec
        return [x / norm for x in vec]

    @staticmethod
    def _dot_product(a: list[float], b: list[float]) -> float:
        """两个等长向量的点积"""
        return sum(x * y for x, y in zip(a, b))
