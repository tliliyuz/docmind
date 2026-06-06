"""RRF 多路融合排序 — Reciprocal Rank Fusion

对齐 ARCHITECTURE.md §6.3 / ROADMAP.md Decision #17：
- score(d) = Σ 1 / (k + rank_i(d))，k=60
- 单路为空时仅返回另一路结果
- 支持多路检索结果融合
"""

import logging
from collections import defaultdict

from app.rag.retriever import RetrievalOutput, RetrievalResult

from app.config import settings

logger = logging.getLogger(__name__)


def rrf_fusion(
    *retrieval_outputs: RetrievalOutput,
    k: int = settings.RRF_K,
) -> RetrievalOutput:
    """多路检索结果的 RRF 融合排序。

    对齐 ARCHITECTURE.md §6.3：
    - score(d) = Σ 1 / (k + rank_i(d))
    - 单路为空时仅返回另一路结果
    - 两路均空时返回空结果

    Args:
        *retrieval_outputs: 多路检索结果（可变参数）
        k: RRF 平滑常数，默认 60

    Returns:
        RetrievalOutput: 融合后的结果，按 RRF 分数降序排列
    """
    if not retrieval_outputs:
        logger.warning("未提供任何检索结果")
        return RetrievalOutput()

    # 过滤空结果
    non_empty_outputs = [output for output in retrieval_outputs if output.results]

    # 所有路均为空
    if not non_empty_outputs:
        logger.info("所有检索路均为空结果")
        return RetrievalOutput()

    # 单路非空：直接返回该路结果
    if len(non_empty_outputs) == 1:
        logger.info("仅单路有结果，直接返回")
        return non_empty_outputs[0]

    # 多路非空：执行 RRF 融合
    return _do_rrf_fusion(non_empty_outputs, k)


def _do_rrf_fusion(
    outputs: list[RetrievalOutput],
    k: int,
) -> RetrievalOutput:
    """执行 RRF 融合算法。

    Args:
        outputs: 非空的检索结果列表
        k: RRF 平滑常数

    Returns:
        RetrievalOutput: 融合后的结果
    """
    # 用于聚合每个 chunk 的 RRF 分数和最佳结果
    # key: (doc_id, chunk_index) → {"score": float, "result": RetrievalResult}
    chunk_scores: dict[tuple[int, int], dict] = defaultdict(lambda: {"score": 0.0, "result": None})

    for output in outputs:
        for rank, result in enumerate(output.results, start=1):
            chunk_key = (result.doc_id, result.chunk_index)

            # RRF 分数累加：1 / (k + rank)
            rrf_contribution = 1.0 / (k + rank)
            chunk_scores[chunk_key]["score"] += rrf_contribution

            # 保留最佳结果（优先保留有内容的）
            if chunk_scores[chunk_key]["result"] is None:
                chunk_scores[chunk_key]["result"] = result

    # 按 RRF 分数降序排列
    sorted_chunks = sorted(
        chunk_scores.items(),
        key=lambda item: item[1]["score"],
        reverse=True,
    )

    # 构建融合结果
    results: list[RetrievalResult] = []
    for chunk_key, data in sorted_chunks:
        result = data["result"]
        # 创建新的 RetrievalResult，使用 RRF 分数
        fused_result = RetrievalResult(
            doc_id=result.doc_id,
            chunk_index=result.chunk_index,
            content=result.content,
            score=data["score"],
            page=result.page,
            doc_name=result.doc_name,
        )
        results.append(fused_result)

    logger.info(
        "RRF 融合完成: %d 路输入, %d 条融合结果 (k=%d)",
        len(outputs), len(results), k,
    )

    return RetrievalOutput(results=results, total=len(results))
