"""Prompt 组装模块测试

对齐 ARCHITECTURE.md §5.1.2:
- 保持 RRF 相关性排序（相关性降序）
- 软上限相关性优先填充
- Token 预算控制
"""

import pytest
from app.rag.prompt_builder import (
    PromptBuildResult,
    build_prompt,
    _format_chunk_reference,
)
from app.rag.retriever import RetrievalOutput, RetrievalResult


@pytest.fixture
def sample_chunks():
    """示例检索结果"""
    return [
        RetrievalResult(
            doc_id=1,
            chunk_index=0,
            content="这是第一个chunk，内容较长一些，用于测试排序和截断逻辑。",
            score=0.9,
            page=1,
            doc_name="文档A.pdf",
        ),
        RetrievalResult(
            doc_id=1,
            chunk_index=1,
            content="短chunk",
            score=0.8,
            page=2,
            doc_name="文档A.pdf",
        ),
        RetrievalResult(
            doc_id=2,
            chunk_index=0,
            content="中等长度的chunk内容",
            score=0.7,
            page=1,
            doc_name="文档B.pdf",
        ),
    ]


@pytest.fixture
def retrieval_output(sample_chunks):
    """示例检索输出"""
    return RetrievalOutput(results=sample_chunks, total=len(sample_chunks))


class TestFormatChunkReference:
    """测试 chunk 格式化"""

    def test_完整信息(self):
        """有文档名和页码"""
        chunk = RetrievalResult(
            doc_id=1,
            chunk_index=0,
            content="测试内容",
            score=0.9,
            page=3,
            doc_name="测试文档.pdf",
        )
        result = _format_chunk_reference(chunk, 1)
        assert "[来源1]" in result
        assert "（文档: 测试文档.pdf）" in result
        assert "（页码: 3）" in result
        assert "测试内容" in result

    def test_无文档名(self):
        """无文档名"""
        chunk = RetrievalResult(
            doc_id=1,
            chunk_index=0,
            content="测试内容",
            score=0.9,
            page=1,
            doc_name="",
        )
        result = _format_chunk_reference(chunk, 2)
        assert "[来源2]" in result
        assert "（文档:" not in result
        assert "测试内容" in result

    def test_无页码(self):
        """无页码"""
        chunk = RetrievalResult(
            doc_id=1,
            chunk_index=0,
            content="测试内容",
            score=0.9,
            page=None,
            doc_name="测试.pdf",
        )
        result = _format_chunk_reference(chunk, 3)
        assert "[来源3]" in result
        assert "（页码:" not in result
        assert "测试内容" in result

    def test_最小信息(self):
        """无文档名无页码"""
        chunk = RetrievalResult(
            doc_id=1,
            chunk_index=0,
            content="测试内容",
            score=0.9,
        )
        result = _format_chunk_reference(chunk, 1)
        assert "[来源1]" in result
        assert "测试内容" in result
        assert "（文档:" not in result
        assert "（页码:" not in result


class TestBuildPrompt:
    """测试 Prompt 组装"""

    def test_空检索结果(self, retrieval_output):
        """空检索结果应返回空上下文"""
        empty_output = RetrievalOutput()
        result = build_prompt("测试问题", empty_output)

        assert isinstance(result, PromptBuildResult)
        assert "（无相关文档）" in result.system_prompt
        assert result.user_prompt == "测试问题"
        assert result.used_chunks == []
        assert result.chunks_count == 0

    def test_保持输入排序_不按长度重排(self):
        """chunks 应保持输入顺序（相关性降序），不按长度重排"""
        # 输入顺序：score 降序（0.9→0.8→0.7），长度非升序（长→短→中）
        # 验证不按长度重排（旧逻辑会变成：短→中→长）
        chunks = [
            RetrievalResult(doc_id=1, chunk_index=0, content="长内容" * 10, score=0.9),
            RetrievalResult(doc_id=1, chunk_index=1, content="短", score=0.8),
            RetrievalResult(doc_id=1, chunk_index=2, content="中等内容", score=0.7),
        ]
        output = RetrievalOutput(results=chunks)
        result = build_prompt("测试问题", output)

        # 验证保持 RRF 相关性排序（score 降序），而非按长度升序
        used_scores = [r.score for r in result.used_chunks]
        assert used_scores == [0.9, 0.8, 0.7]

    def test_软上限控制_预算不足时跳过后续chunk(self):
        """超预算时跳过后续 chunk，首个 chunk 即使超预算也加入"""
        # 输入按相关性降序：score 0.9→0.8→0.7，长度 200→50→100
        # 旧逻辑按长度排(50→100→200)会选 score 0.8+0.7，新逻辑应优先选 score 0.9
        chunks = [
            RetrievalResult(doc_id=1, chunk_index=0, content="A" * 200, score=0.9),
            RetrievalResult(doc_id=1, chunk_index=1, content="B" * 50, score=0.8),
            RetrievalResult(doc_id=1, chunk_index=2, content="C" * 100, score=0.7),
        ]
        output = RetrievalOutput(results=chunks)

        # 设置预算=20 tokens：首个 chunk(0.9, ~50 tokens) 超预算但仍加入
        # 后续 chunk 因预算不足被跳过
        result = build_prompt("测试问题", output, max_context_tokens=20)

        # 首个 chunk 即使超预算也加入，验证选中的是最相关的 chunk
        assert result.chunks_count == 1
        assert result.used_chunks[0].score == 0.9

    def test_最大chunk数限制(self, sample_chunks):
        """不超过最大 chunk 数"""
        output = RetrievalOutput(results=sample_chunks)
        result = build_prompt("测试问题", output, max_chunks=2)

        assert result.chunks_count <= 2

    def test_用户问题保留(self, retrieval_output):
        """用户问题应原样保留"""
        question = "这是用户的问题？"
        result = build_prompt(question, retrieval_output)
        assert result.user_prompt == question

    def test_system_prompt格式(self, retrieval_output):
        """system prompt 应包含参考文档"""
        result = build_prompt("测试问题", retrieval_output)

        assert "企业知识库助手" in result.system_prompt
        assert "参考文档" in result.system_prompt
        assert "来源" in result.system_prompt

    def test_单chunk(self):
        """单个 chunk 应正常工作"""
        chunk = RetrievalResult(
            doc_id=1,
            chunk_index=0,
            content="唯一的内容",
            score=0.9,
            page=1,
            doc_name="测试.pdf",
        )
        output = RetrievalOutput(results=[chunk])
        result = build_prompt("问题", output)

        assert result.chunks_count == 1
        assert "唯一的内容" in result.system_prompt

    def test_第一个chunk超预算仍加入(self):
        """第一个 chunk 即使超预算也应加入"""
        chunk = RetrievalResult(
            doc_id=1,
            chunk_index=0,
            content="A" * 500,  # 较长内容
            score=0.9,
        )
        output = RetrievalOutput(results=[chunk])
        result = build_prompt("问题", output, max_context_tokens=10)

        # 第一个 chunk 应该被加入
        assert result.chunks_count == 1

    def test_返回类型(self, retrieval_output):
        """返回类型应为 PromptBuildResult"""
        result = build_prompt("测试问题", retrieval_output)
        assert isinstance(result, PromptBuildResult)


class TestHistoryMessages:
    """U7.54 — Prompt 组装 history_messages 参数透传"""

    def test_history_messages透传(self, retrieval_output):
        """传入 history_messages 应正确透传到结果中"""
        history = [
            {"role": "user", "content": "上一轮问题"},
            {"role": "assistant", "content": "上一轮回答"},
        ]
        result = build_prompt("当前问题", retrieval_output, history_messages=history)

        assert result.history_messages == history
        assert len(result.history_messages) == 2
        assert result.history_messages[0]["role"] == "user"

    def test_history_messages默认空列表(self, retrieval_output):
        """不传 history_messages 时结果中应为空列表"""
        result = build_prompt("测试问题", retrieval_output)

        assert result.history_messages == []
        assert isinstance(result.history_messages, list)

    def test_history_messages传入None(self, retrieval_output):
        """传入 None 时结果中应为空列表"""
        result = build_prompt("测试问题", retrieval_output, history_messages=None)

        assert result.history_messages == []

    def test_history_messages为空不影响chunk组装(self, retrieval_output):
        """空历史不影响 chunk 组装的正常逻辑"""
        result_without = build_prompt("测试问题", retrieval_output)
        result_with = build_prompt("测试问题", retrieval_output, history_messages=[])

        # chunk 数量和内容应一致
        assert result_without.chunks_count == result_with.chunks_count
        assert result_without.used_chunks == result_with.used_chunks
        assert result_without.system_prompt == result_with.system_prompt
