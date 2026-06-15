"""句级 Evidence 定位 + 修辞角色过滤 — 复用 BM25 在 chunk 内部定位最佳证据句

对齐 ARCHITECTURE.md §5.1.7（Evidence Highlight）+ ROADMAP.md §8.2：
- 对每个 chunk 切句 → 修辞角色过滤 → BM25Okapi → 取 argmax
- 不新增算法：复用 rank-bm25 + jieba（与 BM25Retriever 一致）
- 确定性：同一 question 永远返回同一句子
- 每个 chunk 独立构建微型 BM25 索引（3-8 句），
  IDF 天然区分「审批流程」和「经审批后」的关键词权重差异
- 句级修辞过滤：在 BM25 定位前过滤引用性句子（示例/测试/历史记录等），
  解决 Chunk 内部混合陈述句和引用句的污染问题
"""

import logging
import re

import jieba
from rank_bm25 import BM25Okapi

from app.rag.retriever import RetrievalOutput

logger = logging.getLogger(__name__)

# 中文句子分隔符
_SENTENCE_SEP = re.compile(r'[。！？!?\n]+')

# ==================== 句级修辞角色过滤（§3.3） ====================

# 引用性句子显式标记模式（高置信度，零成本）
_REFERENTIAL_PATTERNS = [
    re.compile(p) for p in [
        r'示例[：:]', r'例如[：:，,]', r'举例[：:]',
        r'测试[目场用]', r'测试数据', r'测试用例',
        r'用户提问[：:]', r'历史问答', r'系统返回[：:]',
        r'如果用户问', r'假设.*场景',
        r'TODO', r'FIXME',
        r'会议.*讨论', r'上次.*提到',
    ]
]


def detect_sentence_role(sentence: str) -> str:
    """判断单个句子的修辞角色。

    对齐 ROADMAP.md §8.2：
    - 规则层：显式标记（高置信度，零成本）
    - 结构层：JSON/代码块内容 → 大概率是示例
    - 默认为陈述（宁可放过，不可错杀）

    Args:
        sentence: 待判断的单个句子

    Returns:
        "assertive" — 陈述知识，可送入 Prompt
        "referential" — 引用知识，应过滤
    """
    s = sentence.strip()
    if not s:
        return "assertive"

    # 规则层：显式标记（高置信度，零成本）
    for pattern in _REFERENTIAL_PATTERNS:
        if pattern.search(s):
            return "referential"

    # 结构层：JSON/代码块内容 → 大概率是示例
    if s.startswith('{') or s.startswith('"') or '```' in s:
        return "referential"

    # 默认为陈述（宁可放过，不可错杀）
    return "assertive"


def filter_chunk_sentences(chunk_content: str) -> str:
    """对 chunk 内容做句级修辞过滤，返回过滤后的文本。

    对齐 ROADMAP.md §8.2：
    - 切句后逐句判断修辞角色
    - 仅保留陈述句
    - 若过滤后为空，返回原始内容（宁可放过，不可错杀）

    Args:
        chunk_content: 原始 chunk 文本

    Returns:
        过滤后的文本（仅含陈述句），若过滤后为空则返回原始内容
    """
    raw = _SENTENCE_SEP.split(chunk_content)
    sentences = [s.strip() for s in raw if s.strip()]
    if not sentences:
        return chunk_content

    filtered = []
    for s in sentences:
        role = detect_sentence_role(s)
        if role == "assertive":
            filtered.append(s)

    if not filtered:
        # 过滤后为空，返回原始内容（宁可放过，不可错杀）
        logger.debug("句级修辞过滤后为空，回退到原始内容")
        return chunk_content

    if len(filtered) < len(sentences):
        logger.debug(
            "句级修辞过滤: %d/%d 句子保留",
            len(filtered), len(sentences),
        )

    return '。'.join(filtered) + '。'


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
