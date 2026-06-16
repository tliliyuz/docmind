"""证据审查 — PRE-LLM chunk 分类与门控决策

对齐 ADR-021：
- 在 filter_chunk_sentences() 之后执行，基于 LLM 实际会看到的内容判定
- 复用 sentence_matcher.FilterStats，避免重复切句+角色判定
- 异常时降级为 ALLOW（宁可多调一次 LLM，也不因审查模块 bug 拒答）
- 默认不输出逐句详情（sentence_review 仅 debug 模式）

与 evidence_auditor.py 的关系：
- evidence_reviewer: PRE-LLM — chunk 分类 + 门控决策（决定是否调 LLM）
- evidence_auditor:  POST-LLM — 答案审计 + 置信度标注（验证 LLM 输出质量）
"""

import logging
import time
from dataclasses import dataclass, field

from app.rag.retriever import RetrievalOutput
from app.rag.sentence_matcher import FilterStats, _SENTENCE_SEP, detect_sentence_role

logger = logging.getLogger(__name__)


@dataclass
class ChunkRoleDecision:
    """单 chunk 角色判定结果"""
    chunk_index: int
    doc_id: int
    role: str                    # "ASSERTIVE" — 过滤后仍有陈述句 / "REJECTED" — 过滤后为空
    filtered_sentence_count: int
    assertive_sentence_count: int
    referential_sentence_count: int
    reason: str | None = None    # REJECTED 时说明原因


@dataclass
class SentenceReviewItem:
    """逐句详情（仅 debug 模式输出）"""
    chunk_index: int
    sentence_index: int
    text: str
    role: str                    # "assertive" | "referential"
    reason: str | None = None


@dataclass
class EvidenceReviewResult:
    """综合证据审查结果"""
    decision: str                # "ALLOW" | "REJECT"
    total_chunks: int
    assertive_count: int
    referential_count: int
    rejected_count: int
    reason: str | None           # "NO_ASSERTIVE_EVIDENCE" when REJECT
    chunk_decisions: list[ChunkRoleDecision]
    sentence_review: list[SentenceReviewItem] = field(default_factory=list)
    duration_ms: float = 0.0
    status: str = "success"     # "success" | "error"（异常降级时标记 error）


def review_evidence(
    reranked_output: RetrievalOutput,
    filter_stats_map: dict[int, FilterStats],
    include_sentence_detail: bool = False,
) -> EvidenceReviewResult:
    """在过滤后内容上做证据审查，逐 chunk 判定 ASSERTIVE / REJECTED。

    判定规则（对齐 ADR-021）：
    - 过滤后 chunk 中 assertive_count == 0 → chunk 角色 REJECTED
    - 过滤后 chunk 中 assertive_count > 0  → chunk 角色 ASSERTIVE
    - 所有 chunk 均为 REJECTED → 整体 decision REJECT，reason NO_ASSERTIVE_EVIDENCE
    - 至少 1 个 ASSERTIVE chunk → 整体 decision ALLOW

    异常处理：内部异常捕获后降级为 ALLOW，避免审查模块 bug 导致用户被拒答。

    Args:
        reranked_output: 已 Rerank + 句级过滤后的检索结果
        filter_stats_map: chunk_index → FilterStats（由 filter_chunk_sentences 产生）
        include_sentence_detail: 是否输出逐句详情（debug 模式）

    Returns:
        EvidenceReviewResult 含完整分类结果和门控决策
    """
    t_start = time.perf_counter()

    try:
        result = _do_review(reranked_output, filter_stats_map, include_sentence_detail)
    except Exception:
        logger.exception("证据审查执行失败，降级为 ALLOW")
        result = EvidenceReviewResult(
            decision="ALLOW",
            total_chunks=0,
            assertive_count=0,
            referential_count=0,
            rejected_count=0,
            reason=None,
            chunk_decisions=[],
            sentence_review=[],
            duration_ms=(time.perf_counter() - t_start) * 1000,
            status="error",
        )

    result.duration_ms = (time.perf_counter() - t_start) * 1000
    logger.info(
        "EVIDENCE_REVIEW decision=%s assertive=%d referential=%d rejected=%d reason=%s duration=%.2fms",
        result.decision,
        result.assertive_count,
        result.referential_count,
        result.rejected_count,
        result.reason,
        result.duration_ms,
    )
    return result


def _do_review(
    reranked_output: RetrievalOutput,
    filter_stats_map: dict[int, FilterStats],
    include_sentence_detail: bool = False,
) -> EvidenceReviewResult:
    """实际审查逻辑（从 review_evidence 拆出以隔离异常处理）。"""
    assertive_chunks = 0
    referential_chunks = 0
    rejected_chunks = 0
    chunk_decisions: list[ChunkRoleDecision] = []
    sentence_review: list[SentenceReviewItem] = []

    for result in reranked_output.results:
        chunk_idx = result.chunk_index
        stats = filter_stats_map.get(chunk_idx)
        doc_id = result.doc_id or 0

        if stats is None or stats.total_sentences == 0:
            # 无统计信息 → 视为 REJECTED
            rejected_chunks += 1
            chunk_decisions.append(ChunkRoleDecision(
                chunk_index=chunk_idx,
                doc_id=doc_id,
                role="REJECTED",
                filtered_sentence_count=0,
                assertive_sentence_count=0,
                referential_sentence_count=0,
                reason="无法获取过滤统计信息或 chunk 无有效句子",
            ))
            continue

        if stats.assertive_count > 0:
            assertive_chunks += 1
            chunk_decisions.append(ChunkRoleDecision(
                chunk_index=chunk_idx,
                doc_id=doc_id,
                role="ASSERTIVE",
                filtered_sentence_count=stats.total_sentences,
                assertive_sentence_count=stats.assertive_count,
                referential_sentence_count=stats.referential_count,
                reason=None,
            ))
        else:
            # 过滤后为空（all sentences were filtered out, fallback returned original）
            # 但 stats 显示 assertive_count == 0，说明过滤后确实没有陈述句
            rejected_chunks += 1
            chunk_decisions.append(ChunkRoleDecision(
                chunk_index=chunk_idx,
                doc_id=doc_id,
                role="REJECTED",
                filtered_sentence_count=stats.total_sentences,
                assertive_sentence_count=0,
                referential_sentence_count=stats.referential_count,
                reason="过滤后无陈述性句子（全部为引用性知识）",
            ))

        # Debug 模式：逐句详情
        # 注意：分析的是 result.content（过滤后文本），仅包含过滤后剩余的断言性句子。
        # 被 filter_chunk_sentences() 过滤掉的引用性句子不会出现在这里。
        # 完整对比（过滤前后）可通过 filter_stats_map 中对应 chunk 的 FilterStats 获得。
        if include_sentence_detail and result.content:
            raw = _SENTENCE_SEP.split(result.content)
            sentences = [s.strip() for s in raw if s.strip()]
            for si, sent in enumerate(sentences):
                role = detect_sentence_role(sent)
                sentence_review.append(SentenceReviewItem(
                    chunk_index=chunk_idx,
                    sentence_index=si,
                    text=sent[:200],  # 截断长句
                    role=role,
                    reason=None,
                ))

    total = len(reranked_output.results)
    decision = "REJECT" if assertive_chunks == 0 else "ALLOW"
    reason = "NO_ASSERTIVE_EVIDENCE" if decision == "REJECT" else None

    return EvidenceReviewResult(
        decision=decision,
        total_chunks=total,
        assertive_count=assertive_chunks,
        referential_count=referential_chunks,
        rejected_count=rejected_chunks,
        reason=reason,
        chunk_decisions=chunk_decisions,
        sentence_review=sentence_review,
    )
