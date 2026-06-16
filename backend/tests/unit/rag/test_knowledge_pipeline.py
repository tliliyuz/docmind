"""KnowledgePipeline 单元测试 — 知识管线（检索+上下文构建）"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import KnowledgeBaseEmptyException, RetrievalServiceException
from app.rag.knowledge_pipeline import (
    KnowledgePipeline,
    KnowledgePipelineResult,
    RETRIEVABLE_STATUSES,
    CASUAL_SYSTEM_PROMPT,
)
from app.rag.retriever import RetrievalOutput, RetrievalResult


# ==================== 辅助函数 ====================


def _make_retrieval_output():
    """构造标准检索结果"""
    return RetrievalOutput(
        results=[
            RetrievalResult(
                doc_id=1, chunk_index=0,
                content="检索到的相关内容",
                score=0.95, page=1,
            ),
        ],
        total=1,
    )


def _make_pipeline(retrieval_output=None):
    """构造 KnowledgePipeline，注入 mock 依赖"""
    if retrieval_output is None:
        retrieval_output = _make_retrieval_output()

    mock_vector = MagicMock()
    mock_vector.search = AsyncMock(return_value=retrieval_output)

    mock_bm25 = MagicMock()
    mock_bm25.search = AsyncMock(return_value=retrieval_output)

    mock_reranker = MagicMock()
    mock_reranker.rerank = AsyncMock(return_value=retrieval_output)

    pipeline = KnowledgePipeline(
        vector_retriever=mock_vector,
        reranker=mock_reranker,
    )
    # 注入预构建的 BM25 retriever，绕过懒加载
    pipeline._bm25_retriever = mock_bm25

    return pipeline, mock_vector, mock_bm25, mock_reranker, retrieval_output


# ==================== CASUAL 路径 ====================


class TestExecuteCasual:
    """execute_casual — 闲谈路径"""

    @pytest.mark.asyncio
    async def test_返回简单Prompt跳过检索(self):
        """CASUAL 路径返回无检索上下文的简单 Prompt"""
        pipeline, _, _, _, _ = _make_pipeline()

        result = await pipeline.execute_casual(
            question="你好",
            history_messages=[],
            recorder=None,
        )

        assert isinstance(result, KnowledgePipelineResult)
        assert result.prompt_result.system_prompt == CASUAL_SYSTEM_PROMPT
        assert result.prompt_result.user_prompt == "你好"
        assert result.prompt_result.used_chunks == []
        assert result.prompt_result.total_context_tokens == 0
        assert result.reranked_output.total == 0
        assert result.doc_map == {}

    @pytest.mark.asyncio
    async def test_注入历史消息(self):
        """CASUAL 路径仍注入历史消息"""
        pipeline, _, _, _, _ = _make_pipeline()

        history = [{"role": "user", "content": "之前的问题"}]
        result = await pipeline.execute_casual(
            question="继续",
            history_messages=history,
            recorder=None,
        )

        assert result.prompt_result.history_messages == history

    @pytest.mark.asyncio
    async def test_设置CASUAL响应模式(self):
        """CASUAL 路径在 recorder 上设置响应模式"""
        pipeline, _, _, _, _ = _make_pipeline()

        mock_recorder = MagicMock()
        result = await pipeline.execute_casual(
            question="你好",
            history_messages=[],
            recorder=mock_recorder,
        )

        mock_recorder.set_response_mode.assert_called_once_with("CASUAL")


# ==================== KNOWLEDGE 路径 ====================


class TestExecuteKnowledge:
    """execute_knowledge — 完整检索+上下文构建管线"""

    @pytest.mark.asyncio
    async def test_正常检索流程(self):
        """完整的 KNOWLEDGE 路径：检索 → RRF → Rerank → Prompt"""
        pipeline, mock_vector, mock_bm25, mock_reranker, retrieval_output = _make_pipeline()

        db = AsyncMock()
        # mock doc_count query
        count_result = MagicMock()
        count_result.scalar.return_value = 5  # 有 5 篇可检索文档
        # mock doc_names query
        row = MagicMock()
        row.id = 1
        row.filename = "测试文档.pdf"
        names_result = MagicMock()
        names_result.all.return_value = [row]
        db.execute = AsyncMock(side_effect=[count_result, names_result])

        with patch("app.rag.knowledge_pipeline.needs_rewrite", return_value=False), \
             patch("app.rag.knowledge_pipeline.rrf_fusion", return_value=retrieval_output), \
             patch("app.rag.knowledge_pipeline.match_sentences", return_value=retrieval_output), \
             patch("app.rag.knowledge_pipeline.build_prompt") as mock_build:
            mock_build.return_value = MagicMock(
                system_prompt="系统提示",
                user_prompt="用户提示",
                used_chunks=retrieval_output.results,
                total_context_tokens=500,
                chunks_count=1,
                history_messages=[],
            )

            result = await pipeline.execute_knowledge(
                db=db,
                question="测试问题",
                kb_id=1,
                history_messages=[],
                recorder=None,
            )

        assert isinstance(result, KnowledgePipelineResult)
        assert result.reranked_output.total == 1
        assert result.prompt_result.chunks_count == 1
        assert result.doc_map == {1: "测试文档.pdf"}
        mock_vector.search.assert_called_once()
        mock_bm25.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_空KB抛异常(self):
        """KB 下无可检索文档时抛 KnowledgeBaseEmptyException"""
        pipeline, _, _, _, _ = _make_pipeline()

        db = AsyncMock()
        count_result = MagicMock()
        count_result.scalar.return_value = 0  # 0 篇可检索文档
        db.execute = AsyncMock(return_value=count_result)

        with pytest.raises(KnowledgeBaseEmptyException):
            await pipeline.execute_knowledge(
                db=db,
                question="测试问题",
                kb_id=1,
                history_messages=[],
                recorder=None,
            )

    @pytest.mark.asyncio
    async def test_检索失败抛RetrievalServiceException(self):
        """检索链路异常时抛 E4003"""
        pipeline, mock_vector, _, _, _ = _make_pipeline()
        mock_vector.search = AsyncMock(
            side_effect=Exception("向量存储连接失败")
        )

        db = AsyncMock()
        count_result = MagicMock()
        count_result.scalar.return_value = 5
        db.execute = AsyncMock(return_value=count_result)

        with pytest.raises(RetrievalServiceException):
            await pipeline.execute_knowledge(
                db=db,
                question="测试问题",
                kb_id=1,
                history_messages=[],
                recorder=None,
            )

    @pytest.mark.asyncio
    async def test_触发查询重写(self):
        """多轮对话上下文时触发查询重写"""
        pipeline, _, _, _, retrieval_output = _make_pipeline()

        db = AsyncMock()
        count_result = MagicMock()
        count_result.scalar.return_value = 5
        names_result = MagicMock()
        names_result.all.return_value = []
        db.execute = AsyncMock(side_effect=[count_result, names_result])

        mock_rewrite = MagicMock()
        mock_rewrite.rewritten = "改写后的问题"
        mock_rewrite.metadata = {"model": "test-model", "input_tokens": 10, "output_tokens": 5}

        with patch("app.rag.knowledge_pipeline.needs_rewrite", return_value=True), \
             patch("app.rag.knowledge_pipeline.rewrite_query", new_callable=AsyncMock,
                   return_value=mock_rewrite), \
             patch("app.rag.knowledge_pipeline.rrf_fusion", return_value=retrieval_output), \
             patch("app.rag.knowledge_pipeline.match_sentences", return_value=retrieval_output), \
             patch("app.rag.knowledge_pipeline.build_prompt") as mock_build:
            mock_build.return_value = MagicMock(
                system_prompt="系统提示", user_prompt="用户提示",
                used_chunks=[], total_context_tokens=0, chunks_count=0,
                history_messages=[],
            )

            result = await pipeline.execute_knowledge(
                db=db,
                question="原始问题",
                kb_id=1,
                history_messages=[{"role": "user", "content": "之前的问题"}],
                recorder=None,
            )

        assert isinstance(result, KnowledgePipelineResult)
