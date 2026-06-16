"""Trace 请求/响应模型 — 对齐 API.md §7.5 / §7.6"""

from datetime import datetime

from pydantic import BaseModel, Field


class TraceListItem(BaseModel):
    """GET /api/admin/traces 响应中的单条 Trace

    对齐 API.md §7.5：列表项（不含 JSON 详情字段）
    """
    trace_id: str
    user_id: int
    username: str = Field(description="用户名")
    conversation_uuid: str | None = None
    kb_uuid: str | None = None
    kb_name: str | None = Field(None, description="知识库名称")
    question: str | None = None
    status: str = Field(description="success / error / partial")
    intent_type: str | None = None
    intent_method: str | None = None
    response_mode: str | None = None
    total_duration_ms: int | None = None
    created_at: datetime


class TraceListSummary(BaseModel):
    """Trace 列表概览统计（基于全量筛选结果，非单页）"""
    success: int = 0
    error: int = 0
    running: int = Field(0, description="partial 状态数量")
    success_rate: float = Field(0.0, description="成功率百分比")
    avg_duration_ms: float = Field(0.0, description="平均耗时（毫秒）")
    p95_duration_ms: float = Field(0.0, description="P95 耗时（毫秒）")


class TraceListResponse(BaseModel):
    """GET /api/admin/traces 响应

    对齐 API.md §7.5：分页 Trace 列表
    """
    total: int
    page: int
    page_size: int
    items: list[TraceListItem]
    summary: TraceListSummary | None = None


class TraceSpanBase(BaseModel):
    """各阶段 JSON 通用字段"""
    span_name: str
    start_time: str | None = Field(None, description="阶段开始时间（ISO 8601，由 TraceRecorder 从 perf_counter 推算）")
    duration_ms: int | None = None
    status: str = "success"


class IntentSpan(TraceSpanBase):
    """意图识别阶段详情"""
    intent_type: str | None = None
    method: str | None = None
    metadata: dict | None = None


class RewriteSpan(TraceSpanBase):
    """问题重写阶段详情"""
    original_question: str | None = None
    rewritten_question: str | None = None
    metadata: dict | None = None


class RetrieveSpan(TraceSpanBase):
    """检索阶段详情 — 细粒度拆分"""
    vector: dict | None = None
    bm25: dict | None = None
    fusion: dict | None = None
    match_sentence: dict | None = None


class RerankSpan(TraceSpanBase):
    """Rerank 阶段详情"""
    input_count: int | None = None
    output_count: int | None = None
    metadata: dict | None = None


class GenerateSpan(TraceSpanBase):
    """LLM 生成阶段详情（不存 output）"""
    model: str | None = None
    ttft_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    finish_reason: str | None = None


class EvidenceReviewSpan(TraceSpanBase):
    """证据审查阶段详情（chunk 分类 + REJECT 决策 + post-LLM 审计结果）"""
    summary: dict | None = None
    chunk_decisions: list[dict] | None = None
    sentence_review: list[dict] | None = None
    post_audit: dict | None = None


class TraceDetailResponse(BaseModel):
    """GET /api/admin/traces/{trace_id} 响应

    对齐 API.md §7.5：Trace 详情（含各阶段 JSON 详情）
    """
    trace_id: str
    user_id: int
    username: str = Field(description="用户名")
    conversation_uuid: str | None = None
    conversation_title: str | None = Field(None, description="会话标题")
    kb_uuid: str | None = None
    kb_name: str | None = Field(None, description="知识库名称")
    question: str | None = None
    status: str = Field(description="success / error / partial")
    intent_type: str | None = None
    intent_method: str | None = None
    response_mode: str | None = None
    total_duration_ms: int | None = None
    intent: IntentSpan | None = None
    rewrite: RewriteSpan | None = None
    retrieve: RetrieveSpan | None = None
    rerank: RerankSpan | None = None
    evidence_review: EvidenceReviewSpan | None = None
    generate: GenerateSpan | None = None
    error_message: str | None = None
    created_at: datetime


class TraceTrendItem(BaseModel):
    """趋势数据项"""
    date: str = Field(description="日期（YYYY-MM-DD 或 YYYY-MM-DD HH:00）")
    success: int = 0
    error: int = 0
    partial: int = 0


class TraceLatencyItem(BaseModel):
    """延迟分位数项"""
    date: str
    p50: int = Field(description="P50 延迟（毫秒）")
    p95: int = Field(description="P95 延迟（毫秒）")
    p99: int = Field(description="P99 延迟（毫秒）")


class TraceTokenItem(BaseModel):
    """Token 使用统计项"""
    date: str
    input: int = Field(description="输入 Token 总数")
    output: int = Field(description="输出 Token 总数")


class TraceIntentDistItem(BaseModel):
    """意图分布项"""
    type: str = Field(description="意图类型")
    count: int


class TraceResponseDistItem(BaseModel):
    """响应模式分布项"""
    mode: str = Field(description="响应模式")
    count: int


class TraceStatsResponse(BaseModel):
    """GET /api/admin/stats/traces 响应

    对齐 API.md §7.6：Trace 统计数据，用于 ECharts 图表渲染
    """
    trend: list[TraceTrendItem]
    latency: list[TraceLatencyItem]
    tokens: list[TraceTokenItem]
    intent_distribution: list[TraceIntentDistItem]
    response_distribution: list[TraceResponseDistItem]
