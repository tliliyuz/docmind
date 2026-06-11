"""句级 Evidence 定位 — 复用 BM25 在 chunk 内部定位最佳证据句

对齐 ARCHITECTURE.md §5.1.7（Evidence Highlight）：
- 对每个 chunk 切句 → BM25Okapi → 取 argmax
- 不新增算法：复用 rank-bm25 + jieba（与 BM25Retriever 一致）
- 确定性：同一 question 永远返回同一句子
- 每个 chunk 独立构建微型 BM25 索引（3-8 句），
  IDF 天然区分「审批流程」和「经审批后」的关键词权重差异
"""

import logging
import re

import jieba
from rank_bm25 import BM25Okapi

from app.rag.retriever import RetrievalOutput

logger = logging.getLogger(__name__)

# 中文句子分隔符
_SENTENCE_SEP = re.compile(r'[。！？!?\n]+')


def match_sentences(output: RetrievalOutput, question: str) -> RetrievalOutput:
    """对每个 chunk 内部做句级 BM25 定位，记录最佳证据句。

    每个 chunk 独立构建微型 BM25 索引（3-8 句），
    IDF 天然区分「审批流程」和「经审批后」的关键词权重差异。

    Args:
        output: 检索结果（已 RRF 融合 + Rerank）
        question: 用户问题

    Returns:
        同一 RetrievalOutput，每个 result 的 matched_sentence 已填充
    """
    if not output.results:
        return output

    question_tokens = jieba.lcut(question)

    for result in output.results:
        if not result.content or not result.content.strip():
            continue

        # 切句
        raw = _SENTENCE_SEP.split(result.content)
        sentences = [s.strip() for s in raw if s.strip()]
        if not sentences:
            continue

        # 句级 BM25（每 chunk 独立索引，~1ms）
        tokenized = [jieba.lcut(s) for s in sentences]
        bm25 = BM25Okapi(tokenized)
        scores = bm25.get_scores(question_tokens)

        best_idx = max(range(len(scores)), key=lambda i: scores[i])
        result.matched_sentence = sentences[best_idx]
        result.matched_sentence_score = float(scores[best_idx])

    return output
