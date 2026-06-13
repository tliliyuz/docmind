"""Trace 业务逻辑 — 记录 / 列表 / 详情 / 统计

对齐 API.md §7.5 / §7.6：
- record_trace() 由 TraceRecorder 调用，写入单条 Trace 记录
- list_traces() 分页+筛选列表，JOIN users + knowledge_bases
- get_trace_detail() 单条详情
- get_trace_stats() 聚合统计（trend/latency/tokens/distribution）
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_base import KnowledgeBase
from app.models.trace import Trace
from app.models.user import User
from app.models.conversation import Conversation
from app.schemas.trace import (
    TraceDetailResponse,
    TraceIntentDistItem,
    TraceLatencyItem,
    TraceListResponse,
    TraceListItem,
    TraceResponseDistItem,
    TraceStatsResponse,
    TraceTokenItem,
    TraceTrendItem,
)

logger = logging.getLogger(__name__)


async def record_trace(db: AsyncSession, **kwargs) -> None:
    """写入单条 Trace 记录。

    由 TraceRecorder.finish() 调用，kwargs 对应 Trace 模型字段。
    使用独立 session 时由调用方传入 db。
    """
    trace = Trace(**kwargs)
    db.add(trace)
    await db.commit()


async def list_traces(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    user_id: int | None = None,
    status: str | None = None,
    intent_type: str | None = None,
    response_mode: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    search: str | None = None,
) -> TraceListResponse:
    """获取 Trace 列表（分页+筛选）。

    对齐 API.md §7.5：JOIN users 取 username，LEFT JOIN knowledge_bases 取 kb_name。
    """
    # 构建基础查询
    base_q = (
        select(
            Trace,
            User.username,
            KnowledgeBase.name.label("kb_name"),
            KnowledgeBase.uuid.label("kb_uuid"),
            Conversation.uuid.label("conversation_uuid"),
        )
        .join(User, Trace.user_id == User.id)
        .outerjoin(KnowledgeBase, Trace.kb_id == KnowledgeBase.id)
        .outerjoin(Conversation, Trace.conversation_id == Conversation.id)
    )

    # 筛选条件
    conditions = []
    if user_id is not None:
        conditions.append(Trace.user_id == user_id)
    if status is not None:
        conditions.append(Trace.status == status)
    if intent_type is not None:
        conditions.append(Trace.intent_type == intent_type)
    if response_mode is not None:
        conditions.append(Trace.response_mode == response_mode)
    if start_date is not None:
        conditions.append(Trace.created_at >= start_date)
    if end_date is not None:
        conditions.append(Trace.created_at <= end_date)
    if search:
        conditions.append(Trace.question.like(f"%{search}%"))

    if conditions:
        base_q = base_q.where(*conditions)

    # 总数
    count_q = select(func.count()).select_from(base_q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # 分页数据
    q = (
        base_q
        .order_by(Trace.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(q)).all()

    items = []
    for trace, username, kb_name, kb_uuid_val, conv_uuid in rows:
        items.append(TraceListItem(
            trace_id=trace.trace_id,
            user_id=trace.user_id,
            username=username,
            conversation_uuid=conv_uuid,
            kb_uuid=kb_uuid_val,
            kb_name=kb_name,
            question=trace.question,
            status=trace.status,
            intent_type=trace.intent_type,
            intent_method=trace.intent_method,
            response_mode=trace.response_mode,
            total_duration_ms=trace.total_duration_ms,
            created_at=trace.created_at,
        ))

    return TraceListResponse(
        total=total, page=page, page_size=page_size, items=items,
    )


async def get_trace_detail(
    db: AsyncSession,
    trace_id: str,
) -> TraceDetailResponse | None:
    """获取 Trace 详情（含各阶段 JSON 详情）。

    对齐 API.md §7.5：返回完整 Trace 信息含 intent/rewrite/retrieve/rerank/generate JSON。
    """
    q = (
        select(
            Trace,
            User.username,
            KnowledgeBase.name.label("kb_name"),
            KnowledgeBase.uuid.label("kb_uuid"),
            Conversation.title.label("conversation_title"),
            Conversation.uuid.label("conversation_uuid"),
        )
        .join(User, Trace.user_id == User.id)
        .outerjoin(KnowledgeBase, Trace.kb_id == KnowledgeBase.id)
        .outerjoin(Conversation, Trace.conversation_id == Conversation.id)
        .where(Trace.trace_id == trace_id)
    )
    row = (await db.execute(q)).first()
    if row is None:
        return None

    trace, username, kb_name, kb_uuid_val, conversation_title, conv_uuid = row

    return TraceDetailResponse(
        trace_id=trace.trace_id,
        user_id=trace.user_id,
        username=username,
        conversation_uuid=conv_uuid,
        conversation_title=conversation_title,
        kb_uuid=kb_uuid_val,
        kb_name=kb_name,
        question=trace.question,
        status=trace.status,
        intent_type=trace.intent_type,
        intent_method=trace.intent_method,
        response_mode=trace.response_mode,
        total_duration_ms=trace.total_duration_ms,
        intent=trace.intent,
        rewrite=trace.rewrite,
        retrieve=trace.retrieve,
        rerank=trace.rerank,
        generate=trace.generate,
        error_message=trace.error_message,
        created_at=trace.created_at,
    )


def _group_date_expr(group_by: str):
    """根据 group_by 返回日期分组表达式。

    day: DATE(created_at) → 'YYYY-MM-DD'
    hour: DATE_FORMAT(created_at, '%Y-%m-%d %H:00') → 'YYYY-MM-DD HH:00'
    """
    if group_by == "hour":
        return func.date_format(Trace.created_at, "%Y-%m-%d %H:00")
    return func.date(Trace.created_at)


async def get_trace_stats(
    db: AsyncSession,
    days: int = 7,
    group_by: str = "day",
) -> TraceStatsResponse:
    """Trace 统计数据，用于 ECharts 图表渲染。

    对齐 API.md §7.6：
    - trend: 按天/小时统计 success/error/partial 数量
    - latency: p50/p95/p99 分位数（Python 排序计算）
    - tokens: input/output token 汇总
    - intent_distribution / response_mode_distribution: 分布统计
    """
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days)
    date_expr = _group_date_expr(group_by)

    # ===== 1. Trend: 按日期+状态分组（MySQL IF） =====
    trend_q = (
        select(
            date_expr.label("date"),
            func.sum(func.IF(Trace.status == "success", 1, 0)).label("success"),
            func.sum(func.IF(Trace.status == "error", 1, 0)).label("error"),
            func.sum(func.IF(Trace.status == "partial", 1, 0)).label("partial"),
        )
        .where(Trace.created_at >= start_date)
        .group_by(date_expr)
        .order_by(date_expr)
    )
    trend_rows = (await db.execute(trend_q)).all()
    trend = [
        TraceTrendItem(
            date=str(row.date),
            success=row.success or 0,
            error=row.error or 0,
            partial=row.partial or 0,
        )
        for row in trend_rows
    ]

    # ===== 2. Latency: p50/p95/p99 =====
    latency_q = (
        select(date_expr.label("date"), Trace.total_duration_ms)
        .where(Trace.created_at >= start_date, Trace.total_duration_ms.isnot(None))
        .order_by(date_expr, Trace.total_duration_ms)
    )
    latency_rows = (await db.execute(latency_q)).all()

    # 按日期分组，Python 排序计算分位数
    latency_by_date: dict[str, list[int]] = defaultdict(list)
    for row in latency_rows:
        latency_by_date[str(row.date)].append(row.total_duration_ms)

    latency = []
    for date_str in sorted(latency_by_date.keys()):
        values = latency_by_date[date_str]
        n = len(values)
        if n == 0:
            continue
        p50 = values[int(n * 0.5)] if n > 1 else values[0]
        p95 = values[int(n * 0.95)] if n > 1 else values[0]
        p99 = values[int(n * 0.99)] if n > 1 else values[0]
        latency.append(TraceLatencyItem(date=date_str, p50=p50, p95=p95, p99=p99))

    # ===== 3. Tokens: JSON_EXTRACT 汇总 =====
    tokens_q = (
        select(
            date_expr.label("date"),
            func.coalesce(
                func.sum(func.JSON_EXTRACT(Trace.generate, "$.input_tokens")), 0
            ).label("input_tokens"),
            func.coalesce(
                func.sum(func.JSON_EXTRACT(Trace.generate, "$.output_tokens")), 0
            ).label("output_tokens"),
        )
        .where(Trace.created_at >= start_date, Trace.generate.isnot(None))
        .group_by(date_expr)
        .order_by(date_expr)
    )
    tokens_rows = (await db.execute(tokens_q)).all()
    tokens = [
        TraceTokenItem(
            date=str(row.date),
            input=int(row.input_tokens or 0),
            output=int(row.output_tokens or 0),
        )
        for row in tokens_rows
    ]

    # ===== 4. Intent 分布 =====
    intent_dist_q = (
        select(Trace.intent_type.label("type"), func.count().label("count"))
        .where(Trace.created_at >= start_date, Trace.intent_type.isnot(None))
        .group_by(Trace.intent_type)
        .order_by(func.count().desc())
    )
    intent_dist_rows = (await db.execute(intent_dist_q)).all()
    intent_distribution = [
        TraceIntentDistItem(type=row.type, count=row.count)
        for row in intent_dist_rows
    ]

    # ===== 5. Response Mode 分布 =====
    response_dist_q = (
        select(Trace.response_mode.label("mode"), func.count().label("count"))
        .where(Trace.created_at >= start_date, Trace.response_mode.isnot(None))
        .group_by(Trace.response_mode)
        .order_by(func.count().desc())
    )
    response_dist_rows = (await db.execute(response_dist_q)).all()
    response_distribution = [
        TraceResponseDistItem(mode=row.mode, count=row.count)
        for row in response_dist_rows
    ]

    return TraceStatsResponse(
        trend=trend,
        latency=latency,
        tokens=tokens,
        intent_distribution=intent_distribution,
        response_distribution=response_distribution,
    )
