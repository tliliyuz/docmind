"""Sources Evidence 预览单元测试

对齐 TEST_CASES.md §6.11：
- U11.1 Evidence定位-精确匹配：match_sentences 定位最佳句，_build_sources 生成 preview
- U11.2 Evidence定位-无匹配降级：无 matched_sentence 时 preview 为 None
- U11.3 Evidence定位-短 chunk（<200字符）：窗口覆盖全 chunk
- U11.4 SSE-sources 含 preview_text/preview_range：_build_sources 格式校验
- U11.5 SSE-sources 向前兼容：content 字段保留完整内容

覆盖 app/rag/sentence_matcher.py match_sentences + app/services/chat_service.py _build_sources
"""

import pytest

from app.rag.retriever import RetrievalOutput, RetrievalResult
from app.rag.sentence_matcher import match_sentences
from app.schemas.chat import ChatSourceChunk, PreviewRange


# ==================== 辅助函数 ====================


def _make_chunk_content() -> str:
    """构造测试用 chunk 内容（>200 字符，含多句可定位）"""
    return (
        "新员工入职流程包括以下步骤："
        "第一步，提交入职申请表和个人身份证明文件。"
        "第二步，人力资源部门审核资料并发放工牌。"
        "第三步，IT 部门开通工作账号和VPN权限。"
        "第四步，参加新员工入职培训，了解公司规章制度。"
        "整个流程从入职当天开始，预计需要3个工作日完成。"
    )


def _make_result(content: str, doc_id: int = 1, score: float = 0.9) -> RetrievalResult:
    """快捷构造单个 RetrievalResult"""
    return RetrievalResult(
        doc_id=doc_id,
        chunk_index=0,
        content=content,
        score=score,
    )


# ==================== Evidence 定位：match_sentences + _build_sources 集成 ====================


class TestEvidencePreviewIntegration:
    """match_sentences → _build_sources 完整链路测试"""

    def test_evidence定位_精确匹配_preview窗口中心在证据句附近(self):
        """U11.1：match_sentences 定位最佳句 → _build_sources 以该句为中心生成 ±100 窗口"""
        from app.services.chat_service import _build_sources

        chunk_content = _make_chunk_content()
        output = RetrievalOutput(results=[_make_result(chunk_content)])

        # Step 1: 句级 Evidence 定位
        matched = match_sentences(output, "入职申请表提交")
        best_sentence = matched.results[0].matched_sentence
        assert best_sentence is not None
        assert "入职申请表" in best_sentence

        # Step 2: _build_sources 基于 matched_sentence 生成 preview
        sources = _build_sources(matched.results, {1: "入职流程.pdf"})

        assert len(sources) == 1
        assert sources[0].preview_text is not None
        assert sources[0].preview_range is not None
        # preview_text 应在 chunk 中
        assert sources[0].preview_text in chunk_content
        # 窗口大小 ≤ 200
        assert len(sources[0].preview_text) <= 200
        # 窗口中心应覆盖证据句
        center_pos = sources[0].preview_range.start + len(sources[0].preview_text) // 2
        best_pos = chunk_content.find(best_sentence)
        assert abs(center_pos - (best_pos + len(best_sentence) // 2)) <= 100

    def test_evidence定位_不同question命中不同句子(self):
        """不同 question 对同一 chunk 应命中不同证据句（matched_sentence 不同）"""
        from app.services.chat_service import _build_sources

        chunk = (
            "报销制度规定：差旅费报销需提供发票和行程单。"
            "办公用品采购需填写采购申请表。"
            "所有报销单需经部门负责人审批。"
        )

        # Question 1: 差旅费
        out1 = RetrievalOutput(results=[_make_result(chunk)])
        matched1 = match_sentences(out1, "差旅费报销需要什么材料")

        # Question 2: 办公用品
        out2 = RetrievalOutput(results=[_make_result(chunk)])
        matched2 = match_sentences(out2, "办公用品怎么采购")

        # 验证 matched_sentence 定位到不同句子
        s1 = matched1.results[0].matched_sentence
        s2 = matched2.results[0].matched_sentence
        assert s1 is not None
        assert s2 is not None
        assert s1 != s2, f"不同 question 应命中不同句子，但都命中: {s1}"
        assert "差旅费" in s1
        assert "办公用品" in s2

    def test_evidence定位_多chunk各自独立(self):
        """多条 chunk 时每条独立执行句级定位，chunk_index 从 1 递增"""
        from app.services.chat_service import _build_sources

        chunk1 = "员工入职需要提交身份证复印件和学历证明。人力资源部审核通过后办理入职手续。"
        chunk2 = "VPN 配置步骤：打开系统设置，选择网络和Internet，点击VPN添加连接。"

        output = RetrievalOutput(results=[
            _make_result(chunk1, doc_id=1),
            _make_result(chunk2, doc_id=2),
        ])

        matched = match_sentences(output, "入职需要什么材料 VPN配置")
        sources = _build_sources(matched.results, {1: "入职.pdf", 2: "IT手册.pdf"})

        assert len(sources) == 2
        assert sources[0].chunk_index == 1
        assert sources[1].chunk_index == 2
        # 各自有 preview
        assert sources[0].preview_text is not None
        assert sources[1].preview_text is not None
        # chunk1 的 preview 在 chunk1 中
        assert sources[0].preview_text in chunk1
        # chunk2 的 preview 在 chunk2 中
        assert sources[1].preview_text in chunk2


# ==================== 降级：无 matched_sentence 时 preview 为 None ====================


class TestEvidencePreviewFallback:
    """无 matched_sentence → _build_sources 降级测试"""

    def test_无matched_sentence时preview为None(self):
        """U11.2：chunk 无 matched_sentence 时 preview_text / preview_range 为 None"""
        from app.services.chat_service import _build_sources

        # 不调用 match_sentences，直接构造无 matched_sentence 的 result
        result = RetrievalResult(
            doc_id=1, chunk_index=0,
            content="测试内容" * 50,
            score=0.9,
            # matched_sentence 默认为 None
        )

        sources = _build_sources([result], {1: "test.txt"})

        assert sources[0].preview_text is None
        assert sources[0].preview_range is None
        # content 仍在
        assert sources[0].content == "测试内容" * 50

    def test_空content时preview为None(self):
        """chunk.content 为空时不执行 Evidence 定位"""
        from app.services.chat_service import _build_sources

        result = RetrievalResult(
            doc_id=1, chunk_index=0,
            content="",
            score=0.5,
            matched_sentence="某句",
        )

        sources = _build_sources([result], {1: "test.txt"})

        assert len(sources) == 1
        assert sources[0].content == ""
        assert sources[0].preview_text is None
        assert sources[0].preview_range is None

    def test_matched_sentence为None_空字符串content(self):
        """空 content 且无 matched_sentence → 安全返回 None"""
        from app.services.chat_service import _build_sources

        result = RetrievalResult(
            doc_id=1, chunk_index=0,
            content="",
            score=0.5,
        )

        sources = _build_sources([result], {1: "test.txt"})
        assert sources[0].preview_text is None


# ==================== 短 chunk 边界 ====================


class TestEvidencePreviewShortChunk:
    """短 chunk（<200 字符）Evidence 定位测试"""

    def test_短chunk_evidence定位后窗口覆盖全内容(self):
        """U11.3：chunk < 200 字符时 Evidence 窗口可能覆盖全 chunk"""
        from app.services.chat_service import _build_sources

        chunk_content = "新员工入职需要提交身份证复印件。"
        output = RetrievalOutput(results=[_make_result(chunk_content)])

        matched = match_sentences(output, "入职需要提交什么")
        sources = _build_sources(matched.results, {1: "入职.txt"})

        assert sources[0].preview_text is not None
        # 窗口在 chunk 内容范围内
        assert sources[0].preview_text in chunk_content
        # 范围有效
        assert 0 <= sources[0].preview_range.start < sources[0].preview_range.end <= len(chunk_content)

    def test_恰好200字符chunk(self):
        """chunk 恰好 200 字符，Evidence 定位正常"""
        from app.services.chat_service import _build_sources

        chunk_content = "A" * 200
        # 加标点使其可切句
        chunk_with_periods = "AAAA。BBBB。CCCC。" + "X" * 182

        output = RetrievalOutput(results=[_make_result(chunk_with_periods)])
        matched = match_sentences(output, "AAAA BBBB")

        # 有 matched_sentence 则应有 preview
        if matched.results[0].matched_sentence:
            sources = _build_sources(matched.results, {1: "test.txt"})
            assert sources[0].preview_text is not None
            assert len(sources[0].preview_text) <= len(chunk_with_periods)


# ==================== _build_sources 格式校验 ====================


class TestBuildSourcesFormat:
    """_build_sources() 输出格式校验"""

    def test_preview_text和preview_range字段类型正确(self):
        """U11.4：sources 每项 preview_text / preview_range 字段类型正确"""
        from app.services.chat_service import _build_sources

        content = "公司报销制度规定：差旅报销需提交差旅申请单和交通票据。报销金额上限为每次5000元。"
        output = RetrievalOutput(results=[_make_result(content)])
        matched = match_sentences(output, "差旅报销需提交什么")

        sources = _build_sources(matched.results, {1: "报销制度.md"})

        assert len(sources) == 1
        assert isinstance(sources[0].preview_text, str)
        assert isinstance(sources[0].preview_range, PreviewRange)
        assert isinstance(sources[0].preview_range.start, int)
        assert isinstance(sources[0].preview_range.end, int)
        assert sources[0].preview_range.start < sources[0].preview_range.end

    def test_content字段保留完整内容_向前兼容(self):
        """U11.5：content 字段保留完整 chunk 内容"""
        from app.services.chat_service import _build_sources

        content = "X" * 500
        output = RetrievalOutput(results=[_make_result(content)])
        matched = match_sentences(output, "X" * 30)

        sources = _build_sources(matched.results, {1: "test.txt"})

        assert sources[0].content == content
        assert len(sources[0].content) == 500
        assert sources[0].preview_text is not None
        assert len(sources[0].preview_text) <= 200
        assert sources[0].preview_text in content

    def test_score保留4位小数(self):
        """score 保留 4 位小数精度"""
        from app.services.chat_service import _build_sources

        result = RetrievalResult(
            doc_id=1, chunk_index=0,
            content="测试内容。",
            score=0.123456,
        )

        sources = _build_sources([result], {1: "test.txt"})
        assert sources[0].score == 0.1235  # round(0.123456, 4)


class TestBuildSourcesEdgeCases:
    """_build_sources() 边界条件测试"""

    def test_空chunks列表(self):
        """空检索结果不抛异常"""
        from app.services.chat_service import _build_sources

        sources = _build_sources([], {})
        assert sources == []

    def test_chunk_index从1开始递增(self):
        """chunk_index 从 1 开始，与 LLM Prompt 中 [来源N] 编号一致"""
        from app.services.chat_service import _build_sources

        results = [
            RetrievalResult(doc_id=1, chunk_index=0, content="A。", score=0.9),
            RetrievalResult(doc_id=2, chunk_index=1, content="B。", score=0.8),
            RetrievalResult(doc_id=3, chunk_index=2, content="C。", score=0.7),
        ]

        sources = _build_sources(results, {1: "A", 2: "B", 3: "C"})

        assert sources[0].chunk_index == 1
        assert sources[1].chunk_index == 2
        assert sources[2].chunk_index == 3

    def test_doc_name从doc_map查询(self):
        """doc_name 正确从 doc_map 映射"""
        from app.services.chat_service import _build_sources

        results = [
            RetrievalResult(doc_id=10, chunk_index=0, content="内容。", score=0.9),
            RetrievalResult(doc_id=20, chunk_index=0, content="内容。", score=0.8),
        ]

        sources = _build_sources(results, {10: "文档A.pdf", 20: "文档B.pdf"})

        assert sources[0].doc_name == "文档A.pdf"
        assert sources[1].doc_name == "文档B.pdf"

    def test_doc_id不在doc_map中返回空字符串(self):
        """doc_id 不在 doc_map 中时 doc_name 为空字符串"""
        from app.services.chat_service import _build_sources

        results = [RetrievalResult(doc_id=99, chunk_index=0, content="内容。", score=0.9)]
        sources = _build_sources(results, {})

        assert sources[0].doc_name == ""

    def test_page字段透传(self):
        """page 字段正确透传到 ChatSourceChunk"""
        from app.services.chat_service import _build_sources

        results = [
            RetrievalResult(doc_id=1, chunk_index=0, content="内容。", score=0.9, page=5),
            RetrievalResult(doc_id=2, chunk_index=0, content="内容。", score=0.8, page=None),
        ]

        sources = _build_sources(results, {1: "a.pdf", 2: "b.pdf"})

        assert sources[0].page == 5
        assert sources[1].page is None


# ==================== ChatSourceChunk Schema 校验 ====================


class TestChatSourceChunkSchema:
    """ChatSourceChunk / PreviewRange Pydantic 模型校验"""

    def test_PreviewRange正常构造(self):
        """PreviewRange 应能正常构造和序列化"""
        pr = PreviewRange(start=10, end=150)
        assert pr.start == 10
        assert pr.end == 150
        d = pr.model_dump()
        assert d == {"start": 10, "end": 150}

    def test_ChatSourceChunk含preview字段序列化(self):
        """ChatSourceChunk 含 preview_text + preview_range 时正确序列化"""
        pr = PreviewRange(start=0, end=100)
        chunk = ChatSourceChunk(
            chunk_index=1,
            doc_id=10,
            doc_name="测试.pdf",
            content="完整的 chunk 内容" * 20,
            score=0.95,
            page=3,
            preview_text="预览文本",
            preview_range=pr,
        )

        d = chunk.model_dump()
        assert d["chunk_index"] == 1
        assert d["doc_id"] == 10
        assert d["preview_text"] == "预览文本"
        assert d["preview_range"] == {"start": 0, "end": 100}
        assert d["content"] == "完整的 chunk 内容" * 20

    def test_ChatSourceChunk无preview字段序列化(self):
        """无 preview 字段时序列化为 null（向前兼容）"""
        chunk = ChatSourceChunk(
            chunk_index=1,
            doc_id=10,
            doc_name="测试.pdf",
            content="内容",
            score=0.5,
        )

        d = chunk.model_dump()
        assert d["preview_text"] is None
        assert d["preview_range"] is None

    def test_PreviewRange边界值_零窗口(self):
        """PreviewRange(0, 0) 表示空窗口"""
        pr = PreviewRange(start=0, end=0)
        assert pr.start == 0
        assert pr.end == 0

    def test_PreviewRange边界值_非负start(self):
        """start 应为非负，由 _build_sources 中 max(0, ...) 保证"""
        pr = PreviewRange(start=0, end=100)
        assert pr.start >= 0
