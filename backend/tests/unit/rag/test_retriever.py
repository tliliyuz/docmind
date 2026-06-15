"""向量检索器单元测试 — Mock ChromaDB + Embedder 覆盖核心检索逻辑"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.rag.retriever import (
    RetrievalOutput,
    RetrievalResult,
    VectorRetriever,
)
from app.core.exceptions import RetrievalServiceException
from tests.helpers import (
    MOCK_DIM,
    make_mock_chroma_results,
    make_mock_embed_result,
)


# ==================== RetrievalResult 数据类 ====================


class TestRetrievalResult:
    """RetrievalResult 数据类测试"""

    def test_正常创建(self):
        r = RetrievalResult(
            doc_id=1, chunk_index=0, content="测试内容", score=0.85,
        )
        assert r.doc_id == 1
        assert r.chunk_index == 0
        assert r.content == "测试内容"
        assert r.score == 0.85
        assert r.page is None
        assert r.doc_name == ""

    def test_带页码和文档名(self):
        r = RetrievalResult(
            doc_id=2, chunk_index=3, content="内容", score=0.7,
            page=5, doc_name="文档.pdf",
        )
        assert r.page == 5
        assert r.doc_name == "文档.pdf"


class TestRetrievalOutput:
    """RetrievalOutput 数据类测试"""

    def test_默认值(self):
        out = RetrievalOutput()
        assert out.results == []
        assert out.total == 0

    def test_包含结果(self):
        r = RetrievalResult(doc_id=1, chunk_index=0, content="c", score=0.9)
        out = RetrievalOutput(results=[r], total=1)
        assert len(out.results) == 1
        assert out.total == 1


# ==================== VectorRetriever.search ====================


class TestVectorRetrieverSearch:
    """VectorRetriever.search 端到端测试（Mock 外部依赖）"""

    @pytest.mark.asyncio
    async def test_正常检索流程(self):
        """正常检索：embed 返回向量 → ChromaDB 返回结果 → 解析输出"""
        mock_store = AsyncMock()
        mock_store.search.return_value = make_mock_chroma_results()

        retriever = VectorRetriever(vector_store=mock_store)

        with patch("app.rag.retriever.embed_chunks", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = make_mock_embed_result()
            output = await retriever.search("测试问题", kb_id=1, top_k=10)

        assert output.total == 2
        assert len(output.results) == 2

        # 验证 embed_chunks 以 text_type="query" 调用
        mock_embed.assert_called_once_with(["测试问题"], text_type="query")

        # 验证 ChromaDB query 参数
        mock_store.search.assert_called_once()
        call_kwargs = mock_store.search.call_args[1]
        assert call_kwargs["n_results"] == 10
        assert call_kwargs["where"] == {"kb_id": 1}
        assert "documents" in call_kwargs["include"]
        assert "distances" in call_kwargs["include"]

    @pytest.mark.asyncio
    async def test_空查询返回空结果(self):
        """查询内容为空时直接返回空结果，不调用 Embedding API"""
        mock_store = AsyncMock()
        retriever = VectorRetriever(vector_store=mock_store)

        with patch("app.rag.retriever.embed_chunks", new_callable=AsyncMock) as mock_embed:
            output = await retriever.search("", kb_id=1)

        assert output.total == 0
        mock_embed.assert_not_called()
        mock_store.search.assert_not_called()

    @pytest.mark.asyncio
    async def test_空白查询返回空结果(self):
        """查询内容为纯空白时返回空结果"""
        mock_store = AsyncMock()
        retriever = VectorRetriever(vector_store=mock_store)

        with patch("app.rag.retriever.embed_chunks", new_callable=AsyncMock) as mock_embed:
            output = await retriever.search("   ", kb_id=1)

        assert output.total == 0
        mock_embed.assert_not_called()

    @pytest.mark.asyncio
    async def test_embedding返回空时返回空结果(self):
        """Embedding API 返回空 embeddings 时返回空结果"""
        mock_store = AsyncMock()
        retriever = VectorRetriever(vector_store=mock_store)

        with patch("app.rag.retriever.embed_chunks", new_callable=AsyncMock) as mock_embed:
            from app.rag.embedder import EmbedResult
            mock_embed.return_value = EmbedResult()
            output = await retriever.search("问题", kb_id=1)

        assert output.total == 0
        mock_store.search.assert_not_called()

    @pytest.mark.asyncio
    async def test_chroma查询异常时抛出RetrievalServiceException(self):
        """ChromaDB 查询异常时抛出 E4003 检索服务异常"""
        mock_store = AsyncMock()
        mock_store.search.side_effect = Exception("ChromaDB 连接失败")
        retriever = VectorRetriever(vector_store=mock_store)

        with patch("app.rag.retriever.embed_chunks", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = make_mock_embed_result()
            with pytest.raises(RetrievalServiceException):
                await retriever.search("问题", kb_id=1)

    @pytest.mark.asyncio
    async def test_embedding异常时抛出RetrievalServiceException(self):
        """查询向量化失败时抛出 E4003 检索服务异常"""
        mock_store = AsyncMock()
        retriever = VectorRetriever(vector_store=mock_store)

        with patch("app.rag.retriever.embed_chunks", new_callable=AsyncMock) as mock_embed:
            mock_embed.side_effect = RuntimeError("Embedding API 调用失败")
            with pytest.raises(RetrievalServiceException):
                await retriever.search("问题", kb_id=1)

    @pytest.mark.asyncio
    async def test_top_k参数传递(self):
        """验证 top_k 参数正确传递给 ChromaDB"""
        mock_store = AsyncMock()
        mock_store.search.return_value = make_mock_chroma_results(ids=[[]], documents=[[]], distances=[[]], metadatas=[[]])
        retriever = VectorRetriever(vector_store=mock_store)

        with patch("app.rag.retriever.embed_chunks", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = make_mock_embed_result()
            await retriever.search("问题", kb_id=42, top_k=5)

        call_kwargs = mock_store.search.call_args[1]
        assert call_kwargs["n_results"] == 5
        assert call_kwargs["where"] == {"kb_id": 42}

    @pytest.mark.asyncio
    async def test_kb_id为int类型(self):
        """验证 kb_id 以 int 类型传入 ChromaDB where（Decision #21）"""
        mock_store = AsyncMock()
        mock_store.search.return_value = make_mock_chroma_results(ids=[[]], documents=[[]], distances=[[]], metadatas=[[]])
        retriever = VectorRetriever(vector_store=mock_store)

        with patch("app.rag.retriever.embed_chunks", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = make_mock_embed_result()
            await retriever.search("问题", kb_id=99)

        call_kwargs = mock_store.search.call_args[1]
        kb_id_value = call_kwargs["where"]["kb_id"]
        assert isinstance(kb_id_value, int)
        assert kb_id_value == 99

    @pytest.mark.asyncio
    async def test_metadata字段为int类型(self):
        """验证从 ChromaDB 读取的 metadata 字段都转换为 int 类型（Decision #21）"""
        mock_store = AsyncMock()
        # 模拟 ChromaDB 返回的 metadata（可能包含字符串类型）
        mock_store.search.return_value = make_mock_chroma_results(
            ids=[["doc_1_chunk_0"]],
            documents=[["测试内容"]],
            distances=[[0.3]],
            metadatas=[[{"kb_id": 1, "doc_id": 1, "chunk_index": 0}]]
        )
        retriever = VectorRetriever(vector_store=mock_store)

        with patch("app.rag.retriever.embed_chunks", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = make_mock_embed_result()
            output = await retriever.search("问题", kb_id=1)

        # 验证返回的 RetrievalResult 中的字段都是 int 类型
        assert len(output.results) == 1
        result = output.results[0]
        assert isinstance(result.doc_id, int)
        assert isinstance(result.chunk_index, int)
        assert result.doc_id == 1
        assert result.chunk_index == 0
