"""Trace 数据收集器 — 轻量级，各阶段收集数据，finish() 一次性写入 DB

对齐 ARCHITECTURE.md §5.1.8：
- 各 record_* 方法仅收集数据到内部 dict，不涉及 IO
- finish(db) 一次性写入，调用 trace_service.record_trace()
- Trace 写入失败仅 log.warning，不阻塞主流程
- 使用独立 db session，不复用请求 session
"""

import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.trace_service import record_trace

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    """返回当前 UTC 时间的 ISO 8601 字符串（用于 start_time）"""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class TraceRecorder:
    """Trace 数据收集器。

    在 chat() 流程开始时创建，各阶段调用 record_* 方法收集数据，
    流程结束时调用 finish(db) 写入 traces 表。

    使用方式：
        recorder = TraceRecorder(trace_id, user_id, conv_id, kb_id, question)
        # ... 各阶段埋点 ...
        recorder.record_intent(...)
        recorder.record_retrieve(...)
        # ... 流程结束 ...
        await recorder.finish(db)
    """

    def __init__(
        self,
        trace_id: str,
        user_id: int,
        conversation_id: int | None,
        kb_id: int | None,
        question: str,
    ):
        self.trace_id = trace_id
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.kb_id = kb_id
        self.question = question

        self._t_start = time.perf_counter()
        self._created_at = _utc_now_iso()
        self._status = "success"
        self._error_message: str | None = None

        # 顶层字段（用于筛选统计）
        self._intent_type: str | None = None
        self._intent_method: str | None = None
        self._response_mode: str | None = None

        # 各阶段 JSON 数据
        self._intent_data: dict | None = None
        self._rewrite_data: dict | None = None
        self._retrieve_data: dict | None = None
        self._rerank_data: dict | None = None
        self._generate_data: dict | None = None

    def record_intent(
        self,
        intent_type: str,
        method: str,
        duration_ms: float,
        metadata: dict | None = None,
    ) -> None:
        """记录意图识别阶段。"""
        self._intent_type = intent_type
        self._intent_method = method
        self._intent_data = {
            "span_name": "intent",
            "start_time": self._created_at,
            "duration_ms": int(duration_ms),
            "status": "success",
            "intent_type": intent_type,
            "method": method,
            "metadata": metadata or {},
        }

    def _span_start_iso(self, t_span_start: float) -> str:
        """将 perf_counter 时间戳转换为 ISO 8601 字符串。

        Args:
            t_span_start: time.perf_counter() 记录的阶段开始时间
        """
        offset_ms = (t_span_start - self._t_start) * 1000
        dt = datetime.fromisoformat(self._created_at) + timedelta(milliseconds=offset_ms)
        return dt.isoformat(timespec="milliseconds")

    def record_rewrite(
        self,
        original_question: str,
        rewritten_question: str | None,
        duration_ms: float,
        t_span_start: float | None = None,
        metadata: dict | None = None,
    ) -> None:
        """记录问题重写阶段。"""
        self._rewrite_data = {
            "span_name": "rewrite",
            "start_time": self._span_start_iso(t_span_start) if t_span_start else None,
            "duration_ms": int(duration_ms),
            "status": "success",
            "original_question": original_question,
            "rewritten_question": rewritten_question,
            "metadata": metadata or {},
        }

    def record_retrieve(
        self,
        vector_ms: float | None = None,
        vector_count: int = 0,
        bm25_ms: float | None = None,
        bm25_stats: dict | None = None,
        fusion_ms: float | None = None,
        fusion_count: int = 0,
        fusion_method: str | None = None,
        match_sentence_ms: float | None = None,
        total_ms: float | None = None,
        t_span_start: float | None = None,
    ) -> None:
        """记录检索阶段 — 细粒度拆分。

        对齐 ARCHITECTURE.md §5.1.8：
        - vector: duration_ms, result_count
        - bm25: duration_ms, redis_cache, tokenize_ms, score_ms, candidate_count, result_count
        - fusion: duration_ms, method, result_count
        - match_sentence: duration_ms
        """
        retrieve_total = total_ms or (
            (vector_ms or 0) + (bm25_ms or 0) + (fusion_ms or 0) + (match_sentence_ms or 0)
        )
        self._retrieve_data = {
            "span_name": "retrieve",
            "start_time": self._span_start_iso(t_span_start) if t_span_start else None,
            "duration_ms": int(retrieve_total),
            "status": "success",
            "vector": {
                "duration_ms": int(vector_ms) if vector_ms is not None else 0,
                "result_count": vector_count,
            },
            "bm25": {
                "duration_ms": int(bm25_ms) if bm25_ms is not None else 0,
                **(bm25_stats or {}),
            },
            "fusion": {
                "duration_ms": int(fusion_ms) if fusion_ms is not None else 0,
                "method": fusion_method,
                "result_count": fusion_count,
            },
            "match_sentence": {
                "duration_ms": int(match_sentence_ms) if match_sentence_ms is not None else 0,
            },
        }

    def record_rerank(
        self,
        input_count: int,
        output_count: int,
        duration_ms: float | None = None,
        reranker: str = "noop",
        t_span_start: float | None = None,
    ) -> None:
        """记录 Rerank 阶段。"""
        self._rerank_data = {
            "span_name": "rerank",
            "start_time": self._span_start_iso(t_span_start) if t_span_start else None,
            "duration_ms": int(duration_ms) if duration_ms is not None else 0,
            "status": "success",
            "input_count": input_count,
            "output_count": output_count,
            "metadata": {"reranker": reranker},
        }

    def record_generate(
        self,
        model: str,
        ttft_ms: float,
        total_ms: float,
        input_tokens: int,
        output_tokens: int,
        finish_reason: str | None = None,
        t_span_start: float | None = None,
    ) -> None:
        """记录 LLM 生成阶段（不存 output）。"""
        self._generate_data = {
            "span_name": "generate",
            "start_time": self._span_start_iso(t_span_start) if t_span_start else None,
            "duration_ms": int(total_ms),
            "status": "success",
            "model": model,
            "ttft_ms": int(ttft_ms),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "finish_reason": finish_reason or "stop",
        }

    def set_response_mode(self, mode: str) -> None:
        """设置响应模式（顶层字段）。"""
        self._response_mode = mode

    def record_error(self, error_message: str) -> None:
        """记录错误。"""
        self._status = "error"
        self._error_message = error_message

    async def finish(self, db: AsyncSession) -> None:
        """计算总耗时并写入 traces 表。

        使用传入的 db session 写入。写入失败仅 log.warning，不阻塞主流程。
        """
        total_duration_ms = int((time.perf_counter() - self._t_start) * 1000)

        # 根据 intent_type 推导 response_mode（如果未显式设置）
        if self._response_mode is None:
            if self._intent_type == "META":
                self._response_mode = "META"
            elif self._intent_type == "CASUAL":
                self._response_mode = "CASUAL"
            elif self._generate_data is not None:
                self._response_mode = "RAG"
            else:
                self._response_mode = "FALLBACK"

        try:
            await record_trace(
                db,
                trace_id=self.trace_id,
                user_id=self.user_id,
                conversation_id=self.conversation_id,
                kb_id=self.kb_id,
                question=self.question,
                status=self._status,
                intent_type=self._intent_type,
                intent_method=self._intent_method,
                response_mode=self._response_mode,
                total_duration_ms=total_duration_ms,
                intent=self._intent_data,
                rewrite=self._rewrite_data,
                retrieve=self._retrieve_data,
                rerank=self._rerank_data,
                generate=self._generate_data,
                error_message=self._error_message,
            )
            logger.info(
                "Trace 已记录: trace_id=%s status=%s total_ms=%d",
                self.trace_id, self._status, total_duration_ms,
            )
        except Exception:
            logger.warning("Trace 写入失败（不影响主流程）", exc_info=True)
