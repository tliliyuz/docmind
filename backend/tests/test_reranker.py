"""Rerank 重排序模块单元测试 — 覆盖 NoopReranker 核心逻辑

对齐 ROADMAP.md §5.5 Phase 3 测试：
- 按长度排序
- 截取 top_k
- 输入不足 top_k
- 空输入
- 不改变 chunk 内容
"""

import pytest

from app.rag.reranker import BaseReranker, NoopReranker
from app.rag.retriever import RetrievalOutput, RetrievalResult


def _make_result(
    doc_id: int,
    chunk_index: int,
    content: str,
    score: float = 0.0,
    page: int | None = None,
    doc_name: str = "",
) -> RetrievalResult:
    """构造 RetrievalResult 测试数据"""
    return RetrievalResult(
        doc_id=doc_id,
        chunk_index=chunk_index,
        content=content,
        score=score,
        page=page,
        doc_name=doc_name,
    )


def _make_output(results: list[RetrievalResult]) -> RetrievalOutput:
    """构造 RetrievalOutput 测试数据"""
    return RetrievalOutput(results=results, total=len(results))


# ==================== NoopReranker 核心逻辑测试 ====================


class TestNoopReranker:
    """NoopReranker 核心逻辑测试"""

    @pytest.fixture
    def reranker(self):
        return NoopReranker()

    @pytest.mark.asyncio
    async def test_按长度排序(self, reranker: NoopReranker):
        """输入混合长度 chunks，按 content 长度升序排列（短 chunk 优先）"""
        results = _make_output([
            _make_result(1, 0, "这是最长的内容" * 10, 0.9),      # 50 字符
            _make_result(1, 1, "短", 0.8),                       # 1 字符
            _make_result(2, 0, "中等长度内容", 0.7),              # 6 字符
        ])

        result = await reranker.rerank("测试问题", results, top_k=10)

        assert result.total == 3
        # 按长度升序：1字 → 6字 → 50字
        assert result.results[0].content == "短"
        assert result.results[1].content == "中等长度内容"
        assert result.results[2].content == "这是最长的内容" * 10

    @pytest.mark.asyncio
    async def test_截取top_k(self, reranker: NoopReranker):
        """输入 10 chunks, top_k=5，排序后返回前 5 个"""
        results = _make_output([
            _make_result(i, 0, "内容" * (10 - i), 0.9 - i * 0.01)
            for i in range(10)
        ])

        result = await reranker.rerank("测试问题", results, top_k=5)

        assert result.total == 5
        assert len(result.results) == 5
        # 验证是按长度升序排列的前 5 个
        for i in range(len(result.results) - 1):
            assert len(result.results[i].content) <= len(result.results[i + 1].content)

    @pytest.mark.asyncio
    async def test_输入不足top_k(self, reranker: NoopReranker):
        """输入 3 chunks, top_k=5，返回全部 3 个"""
        results = _make_output([
            _make_result(1, 0, "短", 0.9),
            _make_result(1, 1, "中等长度", 0.8),
            _make_result(2, 0, "较长的内容", 0.7),
        ])

        result = await reranker.rerank("测试问题", results, top_k=5)

        assert result.total == 3
        assert len(result.results) == 3

    @pytest.mark.asyncio
    async def test_空输入(self, reranker: NoopReranker):
        """输入 []，返回 []"""
        empty_output = _make_output([])

        result = await reranker.rerank("测试问题", empty_output, top_k=5)

        assert result.total == 0
        assert result.results == []

    @pytest.mark.asyncio
    async def test_不改变chunk内容(self, reranker: NoopReranker):
        """仅改变顺序，chunk 的 content/metadata 不变"""
        original_results = _make_output([
            _make_result(1, 0, "内容A", 0.9, page=5, doc_name="文档1.pdf"),
            _make_result(1, 1, "较短", 0.8, page=3, doc_name="文档2.pdf"),
            _make_result(2, 0, "中等内容", 0.7, page=1, doc_name="文档3.pdf"),
        ])

        result = await reranker.rerank("测试问题", original_results, top_k=10)

        # 验证内容和 metadata 保持不变
        for r in result.results:
            if r.content == "较短":
                assert r.doc_id == 1
                assert r.chunk_index == 1
                assert r.page == 3
                assert r.doc_name == "文档2.pdf"
            elif r.content == "中等内容":
                assert r.doc_id == 2
                assert r.chunk_index == 0
                assert r.page == 1
                assert r.doc_name == "文档3.pdf"
            elif r.content == "内容A":
                assert r.doc_id == 1
                assert r.chunk_index == 0
                assert r.page == 5
                assert r.doc_name == "文档1.pdf"

    @pytest.mark.asyncio
    async def test_默认top_k为5(self, reranker: NoopReranker):
        """不传 top_k 时默认使用 5"""
        results = _make_output([
            _make_result(i, 0, "内容" * (10 - i), 0.9 - i * 0.01)
            for i in range(10)
        ])

        result = await reranker.rerank("测试问题", results)

        assert result.total == 5
        assert len(result.results) == 5

    @pytest.mark.asyncio
    async def test_单chunk输入(self, reranker: NoopReranker):
        """单 chunk 输入，返回该 chunk"""
        results = _make_output([
            _make_result(1, 0, "唯一内容", 0.9),
        ])

        result = await reranker.rerank("测试问题", results, top_k=5)

        assert result.total == 1
        assert result.results[0].content == "唯一内容"

    @pytest.mark.asyncio
    async def test_top_k为1(self, reranker: NoopReranker):
        """top_k=1 时仅返回最短的 chunk"""
        results = _make_output([
            _make_result(1, 0, "最长的内容" * 5, 0.9),
            _make_result(1, 1, "短", 0.8),
            _make_result(2, 0, "中等", 0.7),
        ])

        result = await reranker.rerank("测试问题", results, top_k=1)

        assert result.total == 1
        assert result.results[0].content == "短"

    @pytest.mark.asyncio
    async def test_相同长度chunk的稳定性(self, reranker: NoopReranker):
        """相同长度的 chunk，排序应保持稳定（不改变原有顺序）"""
        results = _make_output([
            _make_result(1, 0, "AAA", 0.9),  # 3 字符
            _make_result(2, 0, "BBB", 0.8),  # 3 字符
            _make_result(3, 0, "CCC", 0.7),  # 3 字符
        ])

        result = await reranker.rerank("测试问题", results, top_k=10)

        assert result.total == 3
        # Python 的 sorted 是稳定的，相同 key 保持原有顺序
        assert result.results[0].doc_id == 1
        assert result.results[1].doc_id == 2
        assert result.results[2].doc_id == 3


# ==================== 接口一致性测试 ====================


class TestRerankerInterface:
    """Reranker 接口一致性测试"""

    def test_noopreranker_是_base_reranker_子类(self):
        """NoopReranker 应继承 BaseReranker"""
        assert issubclass(NoopReranker, BaseReranker)

    def test_base_reranker_是抽象类(self):
        """BaseReranker 不能直接实例化"""
        with pytest.raises(TypeError):
            BaseReranker()
