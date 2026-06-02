"""Prompt 组装模块测试

对齐 ARCHITECTURE.md §5.1.2:
- 按 chunk 长度升序排列（短者优先）
- 软上限择优填充
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

    def test_按长度升序排列(self, sample_chunks):
        """chunks 应按长度升序排列"""
        output = RetrievalOutput(results=sample_chunks)
        result = build_prompt("测试问题", output)

        # 验证 chunks 按长度升序
        used_lengths = [len(r.content) for r in result.used_chunks]
        assert used_lengths == sorted(used_lengths)

    def test_软上限控制(self):
        """超预算时应跳过较长 chunk"""
        # 创建不同长度的 chunks
        chunks = [
            RetrievalResult(doc_id=1, chunk_index=0, content="A" * 100, score=0.9),
            RetrievalResult(doc_id=1, chunk_index=1, content="B" * 50, score=0.8),
            RetrievalResult(doc_id=1, chunk_index=2, content="C" * 200, score=0.7),
        ]
        output = RetrievalOutput(results=chunks)

        # 设置较小的 token 预算
        result = build_prompt("测试问题", output, max_context_tokens=50)

        # 应该优先选择较短的 chunks
        assert result.chunks_count <= len(chunks)
        assert result.total_context_tokens <= 50 or result.chunks_count == 1

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


