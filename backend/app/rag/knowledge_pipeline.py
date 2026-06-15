"""知识管线 — 查询重写 → 双路检索 → RRF 融合 → Rerank → 句子匹配 → Prompt 构建

从 chat_service.py 解耦提取，专注检索+上下文构建管线。
对齐 ARCHITECTURE.md §5.1 / ROADMAP.md §6.1。

命名理由：该管线不是单纯的 Retrieval，而是 Retrieval + Context Construction。
未来可扩展 query transform / citation enrich / guardrail / context compression，
"KnowledgePipeline" 比 "RetrievalOrchestrator" 更准确。
"""

import logging
import time
from collections.abc import Callable, Awaitable
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.rag.bm25 import BM25Retriever
from app.rag.fusion import rrf_fusion
from app.rag.prompt_builder import PromptBuildResult, build_prompt
from app.rag.query_rewriter import _needs_rewrite, rewrite_query
from app.rag.reranker import NoopReranker
from app.rag.retriever import RetrievalOutput, VectorRetriever
from app.rag.sentence_matcher import match_sentences
from app.rag.trace_recorder import TraceRecorder

logger = logging.getLogger(__name__)

# 可检索文档状态：文档已入库、分块已写入向量存储、可用于检索
RETRIEVABLE_STATUSES = ["completed", "success_with_warnings", "partial_failed"]

# 闲谈模式 System Prompt（不注入文档上下文）
CASUAL_SYSTEM_PROMPT = "你是 DocMind，一个企业知识库助手。请友好、简洁地回答用户的问题。"


@dataclass
class KnowledgePipelineResult:
    """知识管线完整产出"""
    reranked_output: RetrievalOutput
    prompt_result: PromptBuildResult
    doc_map: dict[int, str]  # doc_id -> filename


class KnowledgePipeline:
    """知识管线：查询重写 → 双路检索 → RRF 融合 → Rerank → 句子匹配 → Prompt 构建

    不包含意图分类（调用方在 chat_service 中已处理）、权限检查、会话管理。
    """

    def __init__(
        self,
        vector_retriever: VectorRetriever | None = None,
        bm25_retriever_factory: Callable[[], Awaitable[BM25Retriever]] | None = None,
        reranker: NoopReranker | None = None,
    ):
        self._vector_retriever = vector_retriever or VectorRetriever()
        self._reranker = reranker or NoopReranker()
        self._bm25_retriever: BM25Retriever | None = None
        self._bm25_factory = bm25_retriever_factory

    async def _get_bm25(self) -> BM25Retriever:
        """懒加载 BM25 检索器（需要异步 Redis 客户端）"""
        if self._bm25_retriever is None:
            if self._bm25_factory is None:
                raise RuntimeError("BM25 retriever factory not configured")
            self._bm25_retriever = await self._bm25_factory()
        return self._bm25_retriever

    async def execute_knowledge(
        self,
        db: AsyncSession,
        question: str,
        kb_id: int,
        history_messages: list[dict[str, str]],
        recorder: TraceRecorder | None = None,
    ) -> KnowledgePipelineResult:
        """KNOWLEDGE 路径：完整检索+上下文构建管线。

        1. 查询重写（多轮对话上下文触发）
        2. 检查 KB 是否有可检索文档
        3. 向量+BM25 双路检索 → RRF 融合 → Rerank
        4. 句级 Evidence 定位 → Prompt 构建
        5. 查询涉及的文档名映射
        6. Trace 记录

        Raises:
            KnowledgeBaseEmptyException: KB 无可检索文档
            RetrievalServiceException: 检索链路异常
        """
        from app.core.exceptions import KnowledgeBaseEmptyException, RetrievalServiceException

        # 1. 查询重写（仅多轮对话上下文触发，对齐 ARCHITECTURE.md §5.1.5）
        _original_question = question
        t_rewrite_start = time.perf_counter()
        t_rewrite = t_rewrite_start

        if _needs_rewrite(question, history_messages):
            rewrite_result = await rewrite_query(question, history_messages)
            question = rewrite_result.rewritten
            t_rewrite = time.perf_counter()
            logger.info(
                "QUERY_REWRITE original=%s rewritten=%s triggered=True",
                _original_question[:100], question[:100],
            )
            if recorder:
                recorder.record_rewrite(
                    original_question=_original_question,
                    rewritten_question=question,
                    duration_ms=(t_rewrite - t_rewrite_start) * 1000,
                    t_span_start=t_rewrite_start,
                    metadata=rewrite_result.metadata,
                )
        else:
            logger.info(
                "QUERY_REWRITE original=%s rewritten=(skipped) triggered=False",
                _original_question[:100],
            )
            if recorder:
                recorder.record_rewrite(
                    original_question=_original_question,
                    rewritten_question=None,
                    duration_ms=0,
                    t_span_start=t_rewrite_start,
                    metadata={"model": None, "input_tokens": 0, "output_tokens": 0},
                )

        # 2. 检查 KB 是否有可检索文档（含 partial_failed：部分分块可用）
        doc_count_q = (
            select(func.count())
            .select_from(Document)
            .where(
                Document.kb_id == kb_id,
                Document.status.in_(RETRIEVABLE_STATUSES),
            )
        )
        doc_count = (await db.execute(doc_count_q)).scalar()
        if doc_count == 0:
            raise KnowledgeBaseEmptyException(kb_id)

        # 3. 多路检索 → RRF 融合 → Rerank → 句子匹配 → Prompt 构建
        try:
            t_retrieve_start = t_rewrite
            vector_output = await self._vector_retriever.search(question, kb_id)
            t_vector = time.perf_counter()
            bm25 = await self._get_bm25()
            bm25_output = await bm25.search(question, kb_id)
            t_bm25 = time.perf_counter()
            fused_output = rrf_fusion(vector_output, bm25_output)
            t_fusion = time.perf_counter()
            reranked_output = await self._reranker.rerank(question, fused_output)
            t_rerank = time.perf_counter()
            reranked_output = match_sentences(reranked_output, question)
            prompt_result = build_prompt(question, reranked_output, history_messages=history_messages)
            t_retrieval_done = time.perf_counter()

            if recorder:
                recorder.record_retrieve(
                    vector_ms=(t_vector - t_retrieve_start) * 1000,
                    vector_count=len(vector_output.results),
                    bm25_ms=(t_bm25 - t_vector) * 1000,
                    bm25_stats=bm25_output.stats,
                    fusion_ms=(t_fusion - t_bm25) * 1000,
                    fusion_count=len(fused_output.results),
                    fusion_method=fused_output.fusion_method,
                    match_sentence_ms=(t_retrieval_done - t_rerank) * 1000,
                    total_ms=(t_retrieval_done - t_retrieve_start) * 1000,
                    t_span_start=t_retrieve_start,
                )
                recorder.record_rerank(
                    input_count=len(fused_output.results),
                    output_count=len(reranked_output.results),
                    duration_ms=(t_rerank - t_fusion) * 1000,
                    t_span_start=t_fusion,
                )
        except Exception as e:
            logger.exception("检索链路异常")
            raise RetrievalServiceException(detail=str(e))

        # 4. 查询涉及的文档名（用于 sources 事件）
        doc_ids = list({c.doc_id for c in reranked_output.results})
        doc_map: dict[int, str] = {}
        if doc_ids:
            doc_rows = await db.execute(
                select(Document.id, Document.filename).where(Document.id.in_(doc_ids))
            )
            doc_map = {row.id: row.filename for row in doc_rows.all()}

        logger.info(
            "KNOWLEDGE_PIPELINE 重写=%.3fs 向量=%.3fs BM25=%.3fs 融合+Rerank=%.3fs 总计=%.3fs",
            t_rewrite - t_rewrite_start,
            t_vector - t_rewrite,
            t_bm25 - t_vector,
            t_retrieval_done - t_bm25,
            t_retrieval_done - t_rewrite_start,
        )

        return KnowledgePipelineResult(
            reranked_output=reranked_output,
            prompt_result=prompt_result,
            doc_map=doc_map,
        )

    async def execute_casual(
        self,
        question: str,
        history_messages: list[dict[str, str]],
        recorder: TraceRecorder | None = None,
    ) -> KnowledgePipelineResult:
        """CASUAL 路径：跳过检索，直接构建简单 Prompt。

        统一 async 接口（非 staticmethod）：未来 Casual 可能增加
        Prompt 模板 / Persona / Safety 过滤 / Memory 压缩等依赖，预留扩展空间。
        """
        logger.info("检测到闲谈意图，跳过检索: %s", question[:30])

        if recorder:
            recorder.set_response_mode("CASUAL")

        return KnowledgePipelineResult(
            reranked_output=RetrievalOutput(),
            prompt_result=PromptBuildResult(
                system_prompt=CASUAL_SYSTEM_PROMPT,
                user_prompt=question,
                used_chunks=[],
                total_context_tokens=0,
                chunks_count=0,
                history_messages=history_messages,
            ),
            doc_map={},
        )
