"""Sources Evidence 预览单元测试

对齐 TEST_CASES.md §6.11：
- U11.1 Evidence定位-精确匹配：match_sentences 定位最佳句，build_sources 生成 preview + highlight
- U11.2 Evidence定位-无匹配降级：无 matched_sentence 时 preview/highlight 为 None
- U11.3 Evidence定位-短 chunk（<200字符）：窗口覆盖全 chunk
- U11.4 SSE-sources 含 preview_text/highlight_start/highlight_end：build_sources 格式校验
- U11.5 SSE-sources 向前兼容：content 字段保留完整内容

覆盖 app/rag/sentence_matcher.py match_sentences + app/services/chat_service.py build_sources
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


# ==================== Evidence 定位：match_sentences + build_sources 集成 ====================


class TestEvidencePreviewIntegration:
    """match_sentences → build_sources 完整链路测试"""

    def test_evidence定位_精确匹配_highlight区间正确(self):
        """U11.1：match_sentences 定位最佳句 → build_sources 计算 highlight_start/end"""
        from app.services.chat_service import build_sources

        chunk_content = _make_chunk_content()
        output = RetrievalOutput(results=[_make_result(chunk_content)])

        # Step 1: 句级 Evidence 定位
        matched = match_sentences(output, "入职申请表提交")
        best_sentence = matched.results[0].matched_sentence
        assert best_sentence is not None
        assert "入职申请表" in best_sentence

        # Step 2: build_sources 基于 matched_sentence 生成 preview + highlight
        sources = build_sources(matched.results, {1: "入职流程.pdf"})

        assert len(sources) == 1
        src = sources[0]
        assert src.preview_text is not None
        assert src.preview_text in chunk_content
        assert len(src.preview_text) <= 200

        # highlight 区间在 preview_text 内，且覆盖证据句
        assert src.highlight_start is not None
        assert src.highlight_end is not None
        assert 0 <= src.highlight_start < src.highlight_end <= len(src.preview_text)
        highlighted = src.preview_text[src.highlight_start:src.highlight_end]
        assert highlighted == best_sentence

    def test_evidence定位_不同question命中不同句子(self):
        """不同 question 对同一 chunk 应命中不同证据句（matched_sentence 不同）"""
        from app.services.chat_service import build_sources

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

        # 验证 highlight 区间各自正确
        sources1 = build_sources(matched1.results, {1: "报销制度.md"})
        sources2 = build_sources(matched2.results, {1: "报销制度.md"})
        h1 = sources1[0].preview_text[sources1[0].highlight_start:sources1[0].highlight_end]
        h2 = sources2[0].preview_text[sources2[0].highlight_start:sources2[0].highlight_end]
        assert "差旅费" in h1
        assert "办公用品" in h2

    def test_evidence定位_多chunk各自独立(self):
        """多条 chunk 时每条独立执行句级定位，chunk_index 从 1 递增"""
        from app.services.chat_service import build_sources

        chunk1 = "员工入职需要提交身份证复印件和学历证明。人力资源部审核通过后办理入职手续。"
        chunk2 = "VPN 配置步骤：打开系统设置，选择网络和Internet，点击VPN添加连接。"

        output = RetrievalOutput(results=[
            _make_result(chunk1, doc_id=1),
            _make_result(chunk2, doc_id=2),
        ])

        matched = match_sentences(output, "入职需要什么材料 VPN配置")
        sources = build_sources(matched.results, {1: "入职.pdf", 2: "IT手册.pdf"})

        assert len(sources) == 2
        assert sources[0].chunk_index == 1
        assert sources[1].chunk_index == 2
        # 各自有 preview + highlight
        for src in sources:
            assert src.preview_text is not None
            assert src.highlight_start is not None
            assert src.highlight_end is not None
        # chunk1 的 preview 在 chunk1 中
        assert sources[0].preview_text in chunk1
        # chunk2 的 preview 在 chunk2 中
        assert sources[1].preview_text in chunk2


# ==================== 降级：无 matched_sentence 时 preview 为 None ====================


class TestEvidencePreviewFallback:
    """无 matched_sentence → build_sources 降级测试"""

    def test_无matched_sentence时preview和highlight均为None(self):
        """U11.2：chunk 无 matched_sentence 时 preview_text / highlight 为 None"""
        from app.services.chat_service import build_sources

        result = RetrievalResult(
            doc_id=1, chunk_index=0,
            content="测试内容" * 50,
            score=0.9,
            # matched_sentence 默认为 None
        )

        sources = build_sources([result], {1: "test.txt"})

        assert sources[0].preview_text is None
        assert sources[0].preview_range is None
        assert sources[0].highlight_start is None
        assert sources[0].highlight_end is None
        # content 仍在
        assert sources[0].content == "测试内容" * 50

    def test_空content时preview为None(self):
        """chunk.content 为空时不执行 Evidence 定位"""
        from app.services.chat_service import build_sources

        result = RetrievalResult(
            doc_id=1, chunk_index=0,
            content="",
            score=0.5,
            matched_sentence="某句",
        )

        sources = build_sources([result], {1: "test.txt"})

        assert len(sources) == 1
        assert sources[0].content == ""
        assert sources[0].preview_text is None
        assert sources[0].highlight_start is None
        assert sources[0].highlight_end is None

    def test_matched_sentence为None_空字符串content(self):
        """空 content 且无 matched_sentence → 安全返回 None"""
        from app.services.chat_service import build_sources

        result = RetrievalResult(
            doc_id=1, chunk_index=0,
            content="",
            score=0.5,
        )

        sources = build_sources([result], {1: "test.txt"})
        assert sources[0].preview_text is None
        assert sources[0].highlight_start is None


# ==================== 短 chunk 边界 ====================


class TestEvidencePreviewShortChunk:
    """短 chunk（<200 字符）Evidence 定位测试"""

    def test_短chunk_evidence定位后窗口覆盖全内容(self):
        """U11.3：chunk < 200 字符时 Evidence 窗口可能覆盖全 chunk"""
        from app.services.chat_service import build_sources

        chunk_content = "新员工入职需要提交身份证复印件。"
        output = RetrievalOutput(results=[_make_result(chunk_content)])

        matched = match_sentences(output, "入职需要提交什么")
        sources = build_sources(matched.results, {1: "入职.txt"})

        assert sources[0].preview_text is not None
        assert sources[0].preview_text in chunk_content
        assert 0 <= sources[0].preview_range.start < sources[0].preview_range.end <= len(chunk_content)
        # highlight 区间有效
        assert sources[0].highlight_start is not None
        assert sources[0].highlight_end is not None
        assert sources[0].highlight_start < sources[0].highlight_end

    def test_恰好200字符chunk(self):
        """chunk 恰好 200 字符，Evidence 定位正常"""
        from app.services.chat_service import build_sources

        chunk_content = "A" * 200
        # 加标点使其可切句
        chunk_with_periods = "AAAA。BBBB。CCCC。" + "X" * 182

        output = RetrievalOutput(results=[_make_result(chunk_with_periods)])
        matched = match_sentences(output, "AAAA BBBB")

        # 有 matched_sentence 则应有 preview + highlight
        # "AAAA。BBBB。CCCC。" + "X" * 182 中 "AAAA" 和 "BBBB" 应被匹配到
        matched_sentence = matched.results[0].matched_sentence
        assert matched_sentence is not None, "AAAA BBBB 应能匹配到含 AAAA 和 BBBB 的句子"
        sources = build_sources(matched.results, {1: "test.txt"})
        assert sources[0].preview_text is not None
        assert len(sources[0].preview_text) <= len(chunk_with_periods)
        assert sources[0].highlight_start is not None
        assert sources[0].highlight_end is not None


# ==================== highlight_start/end 精确校验 ====================


class TestHighlightRange:
    """highlight_start / highlight_end 精确校验"""

    def test_highlight区间精确覆盖matched_sentence(self):
        """highlight 切片 == matched_sentence（确定性）"""
        from app.services.chat_service import build_sources

        content = "第一条：适用范围。第二条：年假申请流程需提前3天提交。第三条：审批权限分级。"
        output = RetrievalOutput(results=[_make_result(content)])
        matched = match_sentences(output, "年假申请流程提前几天")
        best_sentence = matched.results[0].matched_sentence
        assert "年假" in best_sentence

        sources = build_sources(matched.results, {1: "test.md"})
        src = sources[0]

        highlighted = src.preview_text[src.highlight_start:src.highlight_end]
        assert highlighted == best_sentence

    def test_highlight在preview_text边界内(self):
        """highlight_start/end 始终在 [0, len(preview_text)] 范围内"""
        from app.services.chat_service import build_sources

        # 构造长 chunk，使窗口裁剪发生
        content = "A" * 50 + "目标句子在这里。" + "B" * 200
        output = RetrievalOutput(results=[_make_result(content)])
        matched = match_sentences(output, "目标句子")
        sources = build_sources(matched.results, {1: "test.md"})
        src = sources[0]

        # "目标句子在这里。" 应被匹配到，highlight 必须存在
        assert src.highlight_start is not None, "目标句子应被定位到，highlight_start 不应为 None"
        assert 0 <= src.highlight_start <= len(src.preview_text)
        assert 0 <= src.highlight_end <= len(src.preview_text)
        assert src.highlight_start < src.highlight_end

    def test_无matched_sentence时highlight为None(self):
        """直接构造无 matched_sentence 的 result → highlight 为 None"""
        from app.services.chat_service import build_sources

        result = RetrievalResult(doc_id=1, chunk_index=0, content="内容。", score=0.9)
        sources = build_sources([result], {1: "x.txt"})
        assert sources[0].highlight_start is None
        assert sources[0].highlight_end is None


# ==================== build_sources 格式校验 ====================


class TestBuildSourcesFormat:
    """build_sources() 输出格式校验"""

    def test_highlight字段类型正确(self):
        """U11.4：sources 每项 highlight_start / highlight_end 字段类型正确"""
        from app.services.chat_service import build_sources

        content = "公司报销制度规定：差旅报销需提交差旅申请单和交通票据。报销金额上限为每次5000元。"
        output = RetrievalOutput(results=[_make_result(content)])
        matched = match_sentences(output, "差旅报销需提交什么")

        sources = build_sources(matched.results, {1: "报销制度.md"})

        assert len(sources) == 1
        assert isinstance(sources[0].highlight_start, int)
        assert isinstance(sources[0].highlight_end, int)
        assert sources[0].highlight_start < sources[0].highlight_end

    def test_content字段保留完整内容_向前兼容(self):
        """U11.5：content 字段保留完整 chunk 内容"""
        from app.services.chat_service import build_sources

        content = "X" * 500
        output = RetrievalOutput(results=[_make_result(content)])
        matched = match_sentences(output, "X" * 30)

        sources = build_sources(matched.results, {1: "test.txt"})

        assert sources[0].content == content
        assert len(sources[0].content) == 500
        assert sources[0].preview_text is not None
        assert len(sources[0].preview_text) <= 200
        assert sources[0].preview_text in content

    def test_score保留4位小数(self):
        """score 保留 4 位小数精度"""
        from app.services.chat_service import build_sources

        result = RetrievalResult(
            doc_id=1, chunk_index=0,
            content="测试内容。",
            score=0.123456,
        )

        sources = build_sources([result], {1: "test.txt"})
        assert sources[0].score == 0.1235  # round(0.123456, 4)


class TestBuildSourcesEdgeCases:
    """build_sources() 边界条件测试"""

    def test_空chunks列表(self):
        """空检索结果不抛异常"""
        from app.services.chat_service import build_sources

        sources = build_sources([], {})
        assert sources == []

    def test_chunk_index从1开始递增(self):
        """chunk_index 从 1 开始，与 LLM Prompt 中 [来源N] 编号一致"""
        from app.services.chat_service import build_sources

        results = [
            RetrievalResult(doc_id=1, chunk_index=0, content="A。", score=0.9),
            RetrievalResult(doc_id=2, chunk_index=1, content="B。", score=0.8),
            RetrievalResult(doc_id=3, chunk_index=2, content="C。", score=0.7),
        ]

        sources = build_sources(results, {1: "A", 2: "B", 3: "C"})

        assert sources[0].chunk_index == 1
        assert sources[1].chunk_index == 2
        assert sources[2].chunk_index == 3

    def test_doc_name从doc_map查询(self):
        """doc_name 正确从 doc_map 映射"""
        from app.services.chat_service import build_sources

        results = [
            RetrievalResult(doc_id=10, chunk_index=0, content="内容。", score=0.9),
            RetrievalResult(doc_id=20, chunk_index=0, content="内容。", score=0.8),
        ]

        sources = build_sources(results, {10: "文档A.pdf", 20: "文档B.pdf"})

        assert sources[0].doc_name == "文档A.pdf"
        assert sources[1].doc_name == "文档B.pdf"

    def test_doc_id不在doc_map中返回空字符串(self):
        """doc_id 不在 doc_map 中时 doc_name 为空字符串"""
        from app.services.chat_service import build_sources

        results = [RetrievalResult(doc_id=99, chunk_index=0, content="内容。", score=0.9)]
        sources = build_sources(results, {})

        assert sources[0].doc_name == ""

    def test_page字段透传(self):
        """page 字段正确透传到 ChatSourceChunk"""
        from app.services.chat_service import build_sources

        results = [
            RetrievalResult(doc_id=1, chunk_index=0, content="内容。", score=0.9, page=5),
            RetrievalResult(doc_id=2, chunk_index=0, content="内容。", score=0.8, page=None),
        ]

        sources = build_sources(results, {1: "a.pdf", 2: "b.pdf"})

        assert sources[0].page == 5
        assert sources[1].page is None

    def test_章节字段透传(self):
        """section_title / section_path 字段正确透传到 ChatSourceChunk"""
        from app.services.chat_service import build_sources

        results = [
            RetrievalResult(
                doc_id=1, chunk_index=0, content="内容。", score=0.9,
                section_title="§6.1 SSE 事件完整格式",
                section_path="RAG Pipeline > §6 SSE 事件流",
            ),
            RetrievalResult(
                doc_id=2, chunk_index=0, content="内容。", score=0.8,
                section_title=None, section_path=None,
            ),
        ]

        sources = build_sources(results, {1: "API.md", 2: "文档B.md"})

        assert sources[0].section_title == "§6.1 SSE 事件完整格式"
        assert sources[0].section_path == "RAG Pipeline > §6 SSE 事件流"
        assert sources[1].section_title is None
        assert sources[1].section_path is None


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

    def test_ChatSourceChunk含highlight字段序列化(self):
        """ChatSourceChunk 含 highlight_start + highlight_end 时正确序列化"""
        chunk = ChatSourceChunk(
            chunk_index=1,
            doc_id=10,
            doc_name="测试.pdf",
            content="完整的 chunk 内容" * 20,
            score=0.95,
            page=3,
            preview_text="预览文本",
            highlight_start=2,
            highlight_end=6,
        )

        d = chunk.model_dump()
        assert d["chunk_index"] == 1
        assert d["doc_id"] == 10
        assert d["preview_text"] == "预览文本"
        assert d["highlight_start"] == 2
        assert d["highlight_end"] == 6
        assert d["content"] == "完整的 chunk 内容" * 20

    def test_ChatSourceChunk含章节字段序列化(self):
        """ChatSourceChunk 含 section_title + section_path 时正确序列化"""
        chunk = ChatSourceChunk(
            chunk_index=1,
            doc_id=10,
            doc_name="API.md",
            content="SSE 事件格式详解",
            score=0.95,
            page=3,
            section_title="§6.1 SSE 事件完整格式",
            section_path="RAG Pipeline > §6 SSE 事件流",
        )

        d = chunk.model_dump()
        assert d["section_title"] == "§6.1 SSE 事件完整格式"
        assert d["section_path"] == "RAG Pipeline > §6 SSE 事件流"
        assert d["page"] == 3
        assert d["doc_name"] == "API.md"

    def test_ChatSourceChunk章节字段默认None(self):
        """不传 section_title/section_path 时默认为 None（向前兼容）"""
        chunk = ChatSourceChunk(
            chunk_index=1,
            doc_id=10,
            doc_name="旧文档.pdf",
            content="旧内容",
            score=0.5,
        )

        d = chunk.model_dump()
        assert d["section_title"] is None
        assert d["section_path"] is None

    def test_ChatSourceChunk无highlight字段序列化(self):
        """无 highlight 字段时序列化为 null（向前兼容）"""
        chunk = ChatSourceChunk(
            chunk_index=1,
            doc_id=10,
            doc_name="测试.pdf",
            content="内容",
            score=0.5,
        )

        d = chunk.model_dump()
        assert d["preview_text"] is None
        assert d["highlight_start"] is None
        assert d["highlight_end"] is None

    def test_PreviewRange边界值_零窗口(self):
        """PreviewRange(0, 0) 表示空窗口"""
        pr = PreviewRange(start=0, end=0)
        assert pr.start == 0
        assert pr.end == 0

    def test_PreviewRange边界值_非负start(self):
        """start 应为非负，由 build_sources 中 max(0, ...) 保证"""
        pr = PreviewRange(start=0, end=100)
        assert pr.start >= 0
