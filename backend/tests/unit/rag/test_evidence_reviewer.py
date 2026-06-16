"""证据审查单元测试 — review_evidence() chunk 分类 + 门控决策

对齐 ADR-021：
- 基于 filter_chunk_sentences() 返回的 FilterStats 做审查
- 异常时降级为 ALLOW
- include_sentence_detail 控制逐句详情输出
"""

import pytest

from app.rag.evidence_reviewer import (
    ChunkRoleDecision,
    EvidenceReviewResult,
    SentenceReviewItem,
    review_evidence,
)
from app.rag.retriever import RetrievalOutput, RetrievalResult
from app.rag.sentence_matcher import FilterStats


def _make_chunk(chunk_index: int, doc_id: int, content: str = "测试内容。") -> RetrievalResult:
    """构造测试用 RetrievalResult"""
    return RetrievalResult(
        chunk_index=chunk_index,
        doc_id=doc_id,
        content=content,
        score=0.9,
    )


def _make_output(chunks: list[RetrievalResult]) -> RetrievalOutput:
    """构造测试用 RetrievalOutput"""
    output = RetrievalOutput()
    output.results = chunks
    return output


class TestEvidenceReviewerDecision:
    """门控决策测试"""

    def test_全部assertive_chunk_allow(self):
        """所有 chunk 均有断言性句子 → ALLOW"""
        chunks = [_make_chunk(1, 42), _make_chunk(2, 42)]
        output = _make_output(chunks)
        stats_map = {
            1: FilterStats(total_sentences=3, assertive_count=2, referential_count=1),
            2: FilterStats(total_sentences=2, assertive_count=2, referential_count=0),
        }
        result = review_evidence(output, stats_map)
        assert result.decision == "ALLOW"
        assert result.assertive_count == 2
        assert result.rejected_count == 0
        assert result.reason is None

    def test_全部rejected_chunk_reject(self):
        """所有 chunk 在过滤后均无陈述句 → REJECT"""
        chunks = [_make_chunk(1, 42), _make_chunk(2, 42)]
        output = _make_output(chunks)
        stats_map = {
            1: FilterStats(total_sentences=3, assertive_count=0, referential_count=3),
            2: FilterStats(total_sentences=2, assertive_count=0, referential_count=2),
        }
        result = review_evidence(output, stats_map)
        assert result.decision == "REJECT"
        assert result.reason == "NO_ASSERTIVE_EVIDENCE"
        assert result.assertive_count == 0
        assert result.rejected_count == 2

    def test_混合chunk_allow(self):
        """混合 ASSERTIVE 和 REJECTED chunk → ALLOW"""
        chunks = [_make_chunk(1, 42), _make_chunk(2, 43), _make_chunk(3, 42)]
        output = _make_output(chunks)
        stats_map = {
            1: FilterStats(total_sentences=2, assertive_count=2, referential_count=0),
            2: FilterStats(total_sentences=3, assertive_count=0, referential_count=3),  # rejected
            3: FilterStats(total_sentences=1, assertive_count=0, referential_count=1),   # rejected
        }
        result = review_evidence(output, stats_map)
        assert result.decision == "ALLOW"
        assert result.assertive_count == 1
        assert result.rejected_count == 2

    def test_单chunk_assertive_allow(self):
        """单个 chunk 有断言性句子 → ALLOW"""
        chunks = [_make_chunk(1, 42)]
        output = _make_output(chunks)
        stats_map = {1: FilterStats(total_sentences=1, assertive_count=1, referential_count=0)}
        result = review_evidence(output, stats_map)
        assert result.decision == "ALLOW"
        assert result.assertive_count == 1

    def test_单chunk_rejected_reject(self):
        """单个 chunk 过滤后无陈述句 → REJECT"""
        chunks = [_make_chunk(1, 42)]
        output = _make_output(chunks)
        stats_map = {1: FilterStats(total_sentences=1, assertive_count=0, referential_count=1)}
        result = review_evidence(output, stats_map)
        assert result.decision == "REJECT"
        assert result.reason == "NO_ASSERTIVE_EVIDENCE"

    def test_空结果_reject(self):
        """空检索结果 → REJECT"""
        output = _make_output([])
        result = review_evidence(output, {})
        assert result.decision == "REJECT"
        assert result.total_chunks == 0

    def test_缺失stats的chunk视为rejected(self):
        """filter_stats_map 中缺失的 chunk → REJECTED"""
        chunks = [_make_chunk(1, 42), _make_chunk(2, 42)]
        output = _make_output(chunks)
        stats_map = {1: FilterStats(total_sentences=1, assertive_count=1, referential_count=0)}
        # chunk 2 缺失 stats
        result = review_evidence(output, stats_map)
        assert result.decision == "ALLOW"  # chunk 1 是 ASSERTIVE
        assert result.assertive_count == 1
        assert result.rejected_count == 1


class TestChunkDecisions:
    """chunk_decisions 结构验证"""

    def test_chunk决策结构正确(self):
        """验证 chunk_decisions 字段完整"""
        chunks = [_make_chunk(1, 42), _make_chunk(2, 43)]
        output = _make_output(chunks)
        stats_map = {
            1: FilterStats(total_sentences=3, assertive_count=2, referential_count=1),
            2: FilterStats(total_sentences=2, assertive_count=0, referential_count=2),
        }
        result = review_evidence(output, stats_map)
        assert len(result.chunk_decisions) == 2

        d1 = result.chunk_decisions[0]
        assert d1.chunk_index == 1
        assert d1.doc_id == 42
        assert d1.role == "ASSERTIVE"
        assert d1.assertive_sentence_count == 2
        assert d1.referential_sentence_count == 1
        assert d1.reason is None

        d2 = result.chunk_decisions[1]
        assert d2.chunk_index == 2
        assert d2.role == "REJECTED"
        assert d2.reason == "过滤后无陈述性句子（全部为引用性知识）"


class TestSentenceDetail:
    """include_sentence_detail 控制测试"""

    def test_无sentence_detail默认空(self):
        """include_sentence_detail=False 时 sentence_review 为空"""
        chunks = [_make_chunk(1, 42, "这是一句陈述。示例：这是一句引用。")]
        output = _make_output(chunks)
        stats_map = {1: FilterStats(total_sentences=2, assertive_count=1, referential_count=1)}
        result = review_evidence(output, stats_map, include_sentence_detail=False)
        assert result.sentence_review == []

    def test_有sentence_detail填充(self):
        """include_sentence_detail=True 时填充句子详情"""
        content = "这是一句陈述。示例：这是一句引用。"
        chunks = [_make_chunk(1, 42, content)]
        output = _make_output(chunks)
        stats_map = {1: FilterStats(total_sentences=2, assertive_count=1, referential_count=1)}
        result = review_evidence(output, stats_map, include_sentence_detail=True)
        assert len(result.sentence_review) > 0
        # 验证基本结构
        for item in result.sentence_review:
            assert isinstance(item, SentenceReviewItem)
            assert item.chunk_index in (1,)
            assert item.role in ("assertive", "referential")
            assert len(item.text) > 0


class TestDegradation:
    """异常降级测试"""

    def test_异常降级allow(self, monkeypatch):
        """review_evidence 内部抛异常时降级为 ALLOW"""
        chunks = [_make_chunk(1, 42)]
        output = _make_output(chunks)
        stats_map = {}  # 这会触发 KeyError

        # Mock _do_review 抛异常
        import app.rag.evidence_reviewer as mod

        def _raise(*args, **kwargs):
            raise RuntimeError("模拟异常")

        monkeypatch.setattr(mod, "_do_review", _raise)
        result = review_evidence(output, stats_map)
        assert result.decision == "ALLOW"
        assert result.total_chunks == 0
        assert result.chunk_decisions == []


class TestPerformance:
    """性能测试"""

    def test_5chunks耗时小于5ms(self):
        """5 个 chunk 的 Evidence Review 应在 5ms 内完成"""
        chunks = [_make_chunk(i, 42) for i in range(1, 6)]
        output = _make_output(chunks)
        stats_map = {
            i: FilterStats(total_sentences=2, assertive_count=1, referential_count=1)
            for i in range(1, 6)
        }
        result = review_evidence(output, stats_map)
        assert result.duration_ms < 5
        assert len(result.chunk_decisions) == 5


class TestTotalCounts:
    """数量统计验证"""

    def test_统计计数正确(self):
        """total_chunks / assertive_count / referential_count / rejected_count 正确"""
        chunks = [
            _make_chunk(1, 42),
            _make_chunk(2, 42),
            _make_chunk(3, 43),
            _make_chunk(4, 43),
        ]
        output = _make_output(chunks)
        stats_map = {
            1: FilterStats(total_sentences=2, assertive_count=1, referential_count=1),  # ASSERTIVE
            2: FilterStats(total_sentences=1, assertive_count=1, referential_count=0),  # ASSERTIVE
            3: FilterStats(total_sentences=3, assertive_count=0, referential_count=3),  # REJECTED
            4: FilterStats(total_sentences=1, assertive_count=0, referential_count=1),  # REJECTED
        }
        result = review_evidence(output, stats_map)
        assert result.total_chunks == 4
        assert result.assertive_count == 2
        assert result.referential_count == 0
        assert result.rejected_count == 2
        assert result.decision == "ALLOW"
