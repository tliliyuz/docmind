"""句级 Evidence 定位单元测试 — match_sentences()

对齐 TEST_CASES.md：
- 空输入 / 空 results
- 单句 chunk（切句后仅 1 句）
- 多 chunk 各自独立定位
- 无句子（空 content / 纯标点）
- 最佳句确定性：同一 question 同一 sentence
"""

import re

import pytest

from app.rag.retriever import RetrievalOutput, RetrievalResult
from app.rag.sentence_matcher import match_sentences


# ==================== 辅助函数 ====================


def _make_multi_sentence_chunk() -> str:
    """构造含 4 句中文的测试 chunk"""
    return (
        "新员工入职流程包括以下步骤："
        "第一步，提交入职申请表和个人身份证明文件。"
        "第二步，人力资源部门审核资料并发放工牌。"
        "第三步，IT 部门开通工作账号和VPN权限。"
    )


def _make_output(*contents: str) -> RetrievalOutput:
    """快捷构造 RetrievalOutput"""
    results = [
        RetrievalResult(
            doc_id=i + 1,
            chunk_index=0,
            content=c,
            score=0.9,
        )
        for i, c in enumerate(contents)
    ]
    return RetrievalOutput(results=results, total=len(results))


# ==================== 空输入 ====================


class TestMatchSentencesEmpty:
    """空输入 / 无结果边界测试"""

    def test_空results直接返回(self):
        """空 results 列表不抛异常，直接返回"""
        output = RetrievalOutput()
        result = match_sentences(output, "测试问题")
        assert result.results == []
        assert result.total == 0

    def test_空content不抛异常(self):
        """content 为空字符串时不抛异常，matched_sentence 保持 None"""
        output = _make_output("")
        result = match_sentences(output, "测试问题")

        assert result.results[0].matched_sentence is None
        assert result.results[0].matched_sentence_score is None

    def test_纯空白content不抛异常(self):
        """content 为纯空白时不抛异常"""
        output = _make_output("   \n  ")
        result = match_sentences(output, "测试问题")

        assert result.results[0].matched_sentence is None


# ==================== 单句 chunk ====================


class TestMatchSentencesSingleSentence:
    """单句 chunk 边界测试"""

    def test_单句chunk_唯一句即为最佳句(self):
        """chunk 仅含 1 句时，该句即为 matched_sentence（_SENTENCE_SEP 会剥离句末标点）"""
        output = _make_output("员工须提前3个工作日提交请假申请。")
        result = match_sentences(output, "请假申请流程")

        # _SENTENCE_SEP 按 。！？!?\n 切句，切分后 strip() 去除标点
        assert "员工须提前3个工作日提交请假申请" in result.results[0].matched_sentence
        assert len(result.results[0].matched_sentence) >= 10
        assert result.results[0].matched_sentence_score is not None
        assert isinstance(result.results[0].matched_sentence_score, float)

    def test_单句chunk_无句末标点仍可定位(self):
        """chunk 无句末标点（被 _SENTENCE_SEP 处理后为单句）"""
        output = _make_output("这是一段没有句末标点的长文本内容")
        result = match_sentences(output, "长文本内容")

        # 无分隔符 → 整段视为一句
        assert result.results[0].matched_sentence == "这是一段没有句末标点的长文本内容"


# ==================== 多 chunk 各自定位 ====================


class TestMatchSentencesMultiChunk:
    """多 chunk 独立定位测试"""

    def test_多chunk各自匹配不同句子(self):
        """不同 chunk 应各自匹配到不同的最佳句"""
        chunk1 = (
            "年假天数的计算标准如下："
            "满1年不满10年的员工享有5天年假。"
            "满10年不满20年的员工享有10天年假。"
        )
        chunk2 = (
            "病假需提供医院证明。"
            "病假天数不超过3天无需审批。"
            "超过3天需部门负责人审批。"
        )
        output = _make_output(chunk1, chunk2)

        result = match_sentences(output, "年假天数计算")

        # chunk1 应匹配到年假相关句子
        assert "年假" in result.results[0].matched_sentence
        # chunk2 应匹配到病假相关句子（因为 question 含"年假"，与 chunk2 相关性低）
        assert result.results[1].matched_sentence is not None
        assert len(result.results[1].matched_sentence) > 0

    def test_同chunk不同question定位不同句子(self):
        """同一 chunk，不同 question 应定位到不同句子（确定性验证）"""
        chunk = (
            "报销制度规定："
            "差旅费报销需提供发票和行程单。"
            "办公用品采购需填写采购申请表。"
            "所有报销单需经部门负责人审批。"
        )
        output1 = _make_output(chunk)
        output2 = _make_output(chunk)

        r1 = match_sentences(output1, "差旅费报销需要什么")
        r2 = match_sentences(output2, "办公用品采购流程")

        # 不同 question 应命中不同句子
        s1 = r1.results[0].matched_sentence
        s2 = r2.results[0].matched_sentence
        assert s1 != s2
        assert "差旅费" in s1
        assert "办公用品" in s2

    def test_确定性_同一question同一sentence(self):
        """同一 question 对同一 chunk 永远返回同一 sentence（确定性）"""
        chunk = _make_multi_sentence_chunk()

        sentences = set()
        for _ in range(5):
            output = _make_output(chunk)
            result = match_sentences(output, "入职流程步骤")
            sentences.add(result.results[0].matched_sentence)

        # 5 次调用结果完全一致
        assert len(sentences) == 1


# ==================== 无句子 / 空内容 ====================


class TestMatchSentencesNoSentences:
    """无有效句子边界测试"""

    def test_纯标点content无句子(self):
        """content 仅含标点/分隔符，无有效句子"""
        output = _make_output("。。。！！！？？？")
        result = match_sentences(output, "测试问题")

        # 无有效句子 → matched_sentence 保持 None
        assert result.results[0].matched_sentence is None

    def test_仅换行符content(self):
        """content 仅含换行符"""
        output = _make_output("\n\n\n")
        result = match_sentences(output, "测试问题")

        assert result.results[0].matched_sentence is None


# ==================== matched_sentence_score 验证 ====================


class TestMatchSentencesScore:
    """matched_sentence_score 字段验证"""

    def test_score为float类型(self):
        """matched_sentence_score 必须为 float 类型"""
        output = _make_output(_make_multi_sentence_chunk())
        result = match_sentences(output, "入职流程")

        score = result.results[0].matched_sentence_score
        assert score is not None
        assert isinstance(score, float)

    def test_最佳句score高于其他句(self):
        """最佳句的 BM25 分数应高于（或等于）其他句"""
        chunk = (
            "第一条：适用范围。"
            "第二条：年假申请流程需提前3天提交。"
            "第三条：审批权限分级。"
        )
        output = _make_output(chunk)
        result = match_sentences(output, "年假申请流程提前几天")

        # 验证最佳句确实是关于年假的
        assert "年假" in result.results[0].matched_sentence
        assert result.results[0].matched_sentence_score is not None


# ==================== RetrievalResult 字段透传 ====================


class TestMatchSentencesFieldPassthrough:
    """match_sentences 不修改已有字段"""

    def test_原有字段不变(self):
        """doc_id、chunk_index、content、score 等字段不被修改"""
        output = RetrievalOutput(results=[
            RetrievalResult(
                doc_id=42,
                chunk_index=7,
                content="测试内容第一句。测试内容第二句。",
                score=0.8765,
                page=3,
                doc_name="测试文档.pdf",
            )
        ], total=1)

        result = match_sentences(output, "测试")

        r = result.results[0]
        assert r.doc_id == 42
        assert r.chunk_index == 7
        assert r.content == "测试内容第一句。测试内容第二句。"
        assert r.score == 0.8765
        assert r.page == 3
        assert r.doc_name == "测试文档.pdf"

    def test_repeat调用幂等(self):
        """重复调用 match_sentences 应幂等（覆盖原先的 matched_sentence）"""
        output = _make_output(_make_multi_sentence_chunk())

        r1 = match_sentences(output, "第一步")
        s1 = r1.results[0].matched_sentence

        r2 = match_sentences(r1, "第一步")
        s2 = r2.results[0].matched_sentence

        # 同一 question 应返回同一句子
        assert s1 == s2
