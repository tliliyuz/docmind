"""程序级证据审计 — 三层检查：引用存在性 + 来源一致性 + 句级证据回溯

对齐 ROADMAP.md §8.3：
- 不让模型证明自己没有幻觉，而让系统验证每一句结论都能回溯到可审计的证据
- 审计在 LLM 流输出完成后、sources 事件构建阶段执行
- 审计结果影响 sources 展示和置信度标注，而非拦截流式输出
"""

import logging
import re
from collections import Counter
from dataclasses import dataclass, field

import jieba

from app.rag.retriever import RetrievalResult

logger = logging.getLogger(__name__)

# 引用标注匹配（复用 chat_service._CITATION_PATTERN 同款正则）
_CITATION_PATTERN = re.compile(r'\[来源(\d+)\]')

# 答案句子分隔符
_ANSWER_SENTENCE_SEP = re.compile(r'[。！？]')


@dataclass
class EvidenceAuditResult:
    """三层证据审计综合结果"""
    # 第一层：引用存在性
    has_citation: bool = False
    cited_indices: list[int] = field(default_factory=list)

    # 第二层：来源一致性
    unique_doc_count: int = 0
    consistency_status: str = "no_citation"  # no_citation | consistent | acceptable | dispersed
    consistency_detail: str = ""

    # 第三层：句级证据回溯
    evidence_status: str = "supported"  # supported | partial | unsupported
    unsupported_sentences: list[str] = field(default_factory=list)
    total_factual_sentences: int = 0

    # 综合置信度
    confidence_level: str = "high"  # high | medium | low
    confidence_note: str = ""


def audit_evidence(
    answer: str,
    used_chunks: list[RetrievalResult],
) -> EvidenceAuditResult:
    """执行三层证据审计。

    Args:
        answer: LLM 生成的完整回答文本
        used_chunks: Prompt 中使用的检索结果列表

    Returns:
        EvidenceAuditResult: 综合审计结果
    """
    result = EvidenceAuditResult()

    # 第一层：引用存在性检查
    _check_citation_exists(answer, result)

    # 第二层：来源一致性检查
    _check_source_consistency(result, used_chunks)

    # 第三层：句级证据回溯
    _check_sentence_evidence(answer, used_chunks, result)

    # 综合置信度
    _compute_confidence(result)

    logger.info(
        "EVIDENCE_AUDIT citation=%s consistency=%s evidence=%s confidence=%s note=%s",
        result.has_citation,
        result.consistency_status,
        result.evidence_status,
        result.confidence_level,
        result.confidence_note,
    )
    return result


def _check_citation_exists(answer: str, result: EvidenceAuditResult) -> None:
    """第一层：引用存在性检查。

    检查答案是否引用了 [来源N] 标注。
    答案含实质性内容但零引用 → 大概率编造。
    """
    if not answer:
        return

    matches = _CITATION_PATTERN.findall(answer)
    if matches:
        result.has_citation = True
        result.cited_indices = [int(m) for m in matches]
    # else: has_citation 保持 False（零引用）


def _check_source_consistency(
    result: EvidenceAuditResult,
    used_chunks: list[RetrievalResult],
) -> None:
    """第二层：来源一致性检查。

    检查答案引用的来源是否集中在一致的文档上。
    - 1 个文档 → consistent
    - 2 个文档 → acceptable
    - 3+ 个文档 → dispersed（可疑，证据分散）
    """
    if not result.cited_indices or not used_chunks:
        result.consistency_status = "no_citation"
        return

    # 将 [来源N] 编号映射到实际 chunk
    cited_chunks = [
        used_chunks[i - 1]
        for i in result.cited_indices
        if 1 <= i <= len(used_chunks)
    ]

    # 按 doc_id 统计（doc_name 可能为空，用 doc_id 更可靠）
    doc_counts = Counter(c.doc_id for c in cited_chunks if c.doc_id)
    result.unique_doc_count = len(doc_counts)

    if result.unique_doc_count == 0:
        result.consistency_status = "no_citation"
    elif result.unique_doc_count == 1:
        result.consistency_status = "consistent"
    elif result.unique_doc_count <= 2:
        result.consistency_status = "acceptable"
    else:
        result.consistency_status = "dispersed"
        result.consistency_detail = (
            f"答案依赖 {result.unique_doc_count} 个不同来源"
        )


def _check_sentence_evidence(
    answer: str,
    used_chunks: list[RetrievalResult],
    result: EvidenceAuditResult,
) -> None:
    """第三层：句级证据回溯。

    逐句检查答案中的事实性断言是否能在来源 chunk 中找到原文支撑。
    核心逻辑：
    1. 对答案切句
    2. 对每个事实性句子，在所有 used_chunks 中搜索关键词匹配
    3. 如果关键句子（含数字、流程、定义的）在来源中找不到 → 标记为无证据
    4. 超过 50% 的事实性句子无来源支撑 → 标记为 unsupported
    """
    if not answer or not used_chunks:
        result.evidence_status = "supported"
        return

    sentences = _ANSWER_SENTENCE_SEP.split(answer)
    unsupported = []
    factual_count = 0

    for sent in sentences:
        sent = sent.strip()
        if len(sent) < 8:  # 跳过过短的句子（如"是的""好的"）
            continue

        # 跳过纯引用句（如"根据来源1"）和问句
        if '来源' in sent or sent.endswith('？') or sent.endswith('?'):
            continue

        factual_count += 1

        # 提取关键词（jieba 分词，去短词，取 top-3 长词）
        words = [w for w in jieba.lcut(sent) if len(w) >= 2]
        if not words:
            continue
        keywords = sorted(set(words), key=len, reverse=True)[:3]

        # 在所有来源 chunk 中搜索（至少 2/3 关键词命中即认为有证据）
        found = False
        for chunk in used_chunks:
            hits = sum(1 for kw in keywords if kw in chunk.content)
            if hits >= max(1, len(keywords) * 2 // 3):
                found = True
                break

        if not found:
            unsupported.append(sent)

    result.total_factual_sentences = factual_count
    result.unsupported_sentences = unsupported

    if factual_count == 0:
        result.evidence_status = "supported"
    elif len(unsupported) == 0:
        result.evidence_status = "supported"
    elif len(unsupported) <= factual_count * 0.5:
        result.evidence_status = "partial"
    else:
        result.evidence_status = "unsupported"


def _compute_confidence(result: EvidenceAuditResult) -> None:
    """综合三层审计结果，计算置信度级别和提示信息。"""
    issues = []

    # 第一层问题
    if not result.has_citation and result.total_factual_sentences > 2:
        issues.append("答案未引用具体来源")

    # 第二层问题
    if result.consistency_status == "dispersed":
        issues.append(result.consistency_detail)

    # 第三层问题
    if result.evidence_status == "unsupported":
        issues.append("多项断言在来源中无法验证")
    elif result.evidence_status == "partial":
        issues.append("部分断言在来源中无法验证")

    # 综合判定
    if len(issues) >= 2 or result.evidence_status == "unsupported":
        result.confidence_level = "low"
    elif len(issues) == 1:
        result.confidence_level = "medium"
    else:
        result.confidence_level = "high"

    result.confidence_note = "；".join(issues) if issues else ""
