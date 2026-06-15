"""程序级证据审计单元测试 — audit_evidence()

对齐 ROADMAP.md §8.3 + TEST_CASES.md：
- 三层审计各自独立验证
- 综合置信度计算
- 边界：空答案、空 chunks、零引用、全引用
"""

import pytest

from app.rag.evidence_auditor import (
    EvidenceAuditResult,
    _check_citation_exists,
    _check_source_consistency,
    _check_sentence_evidence,
    _compute_confidence,
    audit_evidence,
)
from app.rag.retriever import RetrievalResult


def _make_chunks(*contents_and_docs: tuple[str, int]) -> list[RetrievalResult]:
    """快捷构造 RetrievalResult 列表"""
    results = []
    for i, (content, doc_id) in enumerate(contents_and_docs):
        results.append(RetrievalResult(
            doc_id=doc_id,
            chunk_index=i,
            content=content,
            score=0.9 - i * 0.1,
        ))
    return results


# ==================== 第一层：引用存在性检查 ====================


class TestCitationExists:
    """引用存在性检查"""

    def test_有引用_检测到来源编号(self):
        """答案含 [来源1] 时应检测到引用"""
        result = EvidenceAuditResult()
        _check_citation_exists("根据公司规定[来源1]，报销需提交申请单。", result)
        assert result.has_citation is True
        assert result.cited_indices == [1]

    def test_多引用_检测到全部编号(self):
        """答案含多个 [来源N] 时应检测到全部"""
        result = EvidenceAuditResult()
        _check_citation_exists("参见[来源1]和[来源3]的规定。", result)
        assert result.has_citation is True
        assert result.cited_indices == [1, 3]

    def test_零引用_has_citation为False(self):
        """答案无 [来源N] 时 has_citation 为 False"""
        result = EvidenceAuditResult()
        _check_citation_exists("报销需提交申请单和发票。", result)
        assert result.has_citation is False
        assert result.cited_indices == []

    def test_空答案_无引用(self):
        """空答案无引用"""
        result = EvidenceAuditResult()
        _check_citation_exists("", result)
        assert result.has_citation is False

    def test_假来源标记_不匹配(self):
        """类似 [来源N] 但非标准格式的不匹配"""
        result = EvidenceAuditResult()
        _check_citation_exists("请参考来源1和来源2。", result)
        assert result.has_citation is False


# ==================== 第二层：来源一致性检查 ====================


class TestSourceConsistency:
    """来源一致性检查"""

    def test_单文档来源_consistent(self):
        """所有引用来自同一文档 → consistent"""
        chunks = _make_chunks(
            ("内容A", 1), ("内容B", 1), ("内容C", 1),
        )
        result = EvidenceAuditResult()
        result.has_citation = True
        result.cited_indices = [1, 2]
        _check_source_consistency(result, chunks)
        assert result.consistency_status == "consistent"
        assert result.unique_doc_count == 1

    def test_两文档来源_acceptable(self):
        """引用来自 2 个文档 → acceptable"""
        chunks = _make_chunks(
            ("内容A", 1), ("内容B", 2),
        )
        result = EvidenceAuditResult()
        result.has_citation = True
        result.cited_indices = [1, 2]
        _check_source_consistency(result, chunks)
        assert result.consistency_status == "acceptable"
        assert result.unique_doc_count == 2

    def test_三文档以上_dispersed(self):
        """引用来自 3+ 个文档 → dispersed"""
        chunks = _make_chunks(
            ("内容A", 1), ("内容B", 2), ("内容C", 3),
        )
        result = EvidenceAuditResult()
        result.has_citation = True
        result.cited_indices = [1, 2, 3]
        _check_source_consistency(result, chunks)
        assert result.consistency_status == "dispersed"
        assert result.unique_doc_count == 3

    def test_无引用_no_citation(self):
        """无引用时 consistency_status 为 no_citation"""
        result = EvidenceAuditResult()
        _check_source_consistency(result, [])
        assert result.consistency_status == "no_citation"

    def test_引用索引越界_忽略越界引用(self):
        """[来源N] 编号超出 used_chunks 范围时安全忽略"""
        chunks = _make_chunks(("内容A", 1),)
        result = EvidenceAuditResult()
        result.has_citation = True
        result.cited_indices = [1, 5, 99]  # 5 和 99 越界
        _check_source_consistency(result, chunks)
        # 仅有效索引 1 被计数
        assert result.unique_doc_count == 1
        assert result.consistency_status == "consistent"


# ==================== 第三层：句级证据回溯 ====================


class TestSentenceEvidence:
    """句级证据回溯检查"""

    def test_全部有证据_supported(self):
        """所有事实句子都能在来源中找到 → supported"""
        chunks = _make_chunks(
            ("差旅报销需提交申请单和交通票据。每月25日前提交至财务部。", 1),
        )
        result = EvidenceAuditResult()
        _check_sentence_evidence(
            "差旅报销需提交申请单和交通票据。每月25日前提交至财务部。",
            chunks,
            result,
        )
        assert result.evidence_status == "supported"
        assert len(result.unsupported_sentences) == 0

    def test_部分无证据_partial(self):
        """部分句子在来源中找不到 → partial（≤50% 无证据）"""
        chunks = _make_chunks(
            ("差旅报销需提交申请单。", 1),
        )
        result = EvidenceAuditResult()
        _check_sentence_evidence(
            "差旅报销需提交申请单。审批周期为3-5个工作日。财务部在3楼。",
            chunks,
            result,
        )
        # 仅第一句有证据，后两句无证据
        assert result.evidence_status == "partial"

    def test_大面积无证据_unsupported(self):
        """超过 50% 的句子无证据 → unsupported"""
        chunks = _make_chunks(
            ("差旅报销需提交申请单。", 1),
        )
        result = EvidenceAuditResult()
        _check_sentence_evidence(
            "差旅报销需提交申请单。审批流程通常需要三到五个工作日。"
            "需要部门经理签字确认。",
            chunks,
            result,
        )
        # 第1句有证据（差旅报销），后2句在来源中找不到 → 2/3 > 50%
        assert result.evidence_status == "unsupported"
        assert len(result.unsupported_sentences) >= 2

    def test_跳过引用句(self):
        """以「来源」开头的句子不计入事实句"""
        chunks = _make_chunks(("测试内容", 1),)
        result = EvidenceAuditResult()
        _check_sentence_evidence("根据来源1的规定。报销需提交申请单。", chunks, result)
        # "根据来源1的规定" 被跳过，仅 "报销需提交申请单" 计入
        assert result.total_factual_sentences == 1

    def test_跳过短句(self):
        """过短的句子（<8 字符）不计入事实句"""
        chunks = _make_chunks(("测试内容", 1),)
        result = EvidenceAuditResult()
        _check_sentence_evidence("好的。没问题。就这样。", chunks, result)
        assert result.total_factual_sentences == 0
        assert result.evidence_status == "supported"

    def test_空chunks_supported(self):
        """无 used_chunks 时默认 supported"""
        result = EvidenceAuditResult()
        _check_sentence_evidence("报销需提交申请单。", [], result)
        assert result.evidence_status == "supported"

    def test_空答案_supported(self):
        """空答案默认 supported"""
        chunks = _make_chunks(("内容", 1),)
        result = EvidenceAuditResult()
        _check_sentence_evidence("", chunks, result)
        assert result.evidence_status == "supported"


# ==================== 综合置信度计算 ====================


class TestComputeConfidence:
    """综合置信度计算测试"""

    def test_全部通过_high(self):
        """三层审计全部通过 → high"""
        result = EvidenceAuditResult(
            has_citation=True,
            consistency_status="consistent",
            evidence_status="supported",
        )
        _compute_confidence(result)
        assert result.confidence_level == "high"
        assert result.confidence_note == ""

    def test_单一问题_medium(self):
        """仅有一项问题 → medium"""
        result = EvidenceAuditResult(
            has_citation=False,
            consistency_status="no_citation",
            evidence_status="supported",
            total_factual_sentences=3,
        )
        _compute_confidence(result)
        assert result.confidence_level == "medium"
        assert "未引用具体来源" in result.confidence_note

    def test_dispersed_加_unsupported_low(self):
        """两项问题叠加 → low"""
        result = EvidenceAuditResult(
            has_citation=True,
            consistency_status="dispersed",
            evidence_status="unsupported",
        )
        _compute_confidence(result)
        assert result.confidence_level == "low"

    def test_unsupported单独_low(self):
        """仅 unsupported 也可触发 low"""
        result = EvidenceAuditResult(
            has_citation=True,
            consistency_status="consistent",
            evidence_status="unsupported",
        )
        _compute_confidence(result)
        assert result.confidence_level == "low"


# ==================== audit_evidence 集成测试 ====================


class TestAuditEvidenceIntegration:
    """audit_evidence() 端到端集成测试"""

    def test_正常答案_有引用_来源一致_high(self):
        """正常答案：有引用 + 来源一致 + 证据充分 → high"""
        chunks = _make_chunks(
            ("差旅报销需提交申请单和交通票据。每月25日前提交至财务部。", 1),
        )
        answer = "差旅报销需提交申请单和交通票据[来源1]。每月25日前提交至财务部。"
        result = audit_evidence(answer, chunks)
        assert result.has_citation is True
        assert result.confidence_level == "high"

    def test_零引用_中等长度答案_medium(self):
        """答案未引用任何来源且有多句事实断言 → medium"""
        chunks = _make_chunks(
            ("差旅报销需提交申请单和交通票据。", 1),
        )
        answer = (
            "差旅报销需要提交申请单和交通票据。"
            "每月25日前提交至财务部进行审核。"
            "审批完成后由出纳统一打款。"
        )
        result = audit_evidence(answer, chunks)
        # 有 >2 个事实句但零引用 → medium
        assert result.has_citation is False
        assert result.confidence_level in ("medium", "low")

    def test_空答案_空chunks(self):
        """空答案 + 空 chunks 不抛异常"""
        result = audit_evidence("", [])
        assert result.confidence_level == "high"
        assert result.has_citation is False

    def test_审计结果结构完整(self):
        """审计结果包含所有预期字段"""
        chunks = _make_chunks(("测试内容", 1),)
        result = audit_evidence("测试回答[来源1]", chunks)
        assert isinstance(result, EvidenceAuditResult)
        assert hasattr(result, "has_citation")
        assert hasattr(result, "consistency_status")
        assert hasattr(result, "evidence_status")
        assert hasattr(result, "confidence_level")
        assert hasattr(result, "confidence_note")
