"""管理后台业务逻辑 — 统计/知识库列表/文档列表

对齐 API.md §7：所有接口要求 admin 角色，跨用户管理视图。
"""

import logging
import os
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.message import Message
from app.models.user import User
from app.schemas.admin import (
    AdminDocItem,
    AdminDocListResponse,
    AdminKBItem,
    AdminKBListResponse,
    AdminStatsResponse,
    StatsChartsData,
)

logger = logging.getLogger(__name__)


async def get_stats(db: AsyncSession) -> AdminStatsResponse:
    """获取系统全局统计概览 + ECharts 图表数据。

    对齐 API.md §7.1 / §7.6：
    - 基础统计：单次聚合查询，当前规模（<100K 行）直接 SQL
    - charts：从 traces 表聚合 trend/latency/tokens，复用 get_trace_stats()
    - storage_bytes 使用 SUM(documents.file_size) 而非扫描磁盘目录
    """
    from app.services.trace_service import get_trace_stats

    user_count = (await db.execute(
        select(func.count()).select_from(User)
    )).scalar() or 0

    kb_count = (await db.execute(
        select(func.count()).select_from(KnowledgeBase)
    )).scalar() or 0

    doc_count = (await db.execute(
        select(func.count()).select_from(Document)
    )).scalar() or 0

    chunk_count_result = (await db.execute(
        select(func.coalesce(func.sum(Document.chunk_count), 0))
    )).scalar()

    conversation_count = (await db.execute(
        select(func.count()).select_from(Conversation)
    )).scalar() or 0

    message_count = (await db.execute(
        select(func.count()).select_from(Message)
    )).scalar() or 0

    storage_bytes = (await db.execute(
        select(func.coalesce(func.sum(Document.file_size), 0))
    )).scalar()

    # ECharts 图表数据：默认取最近 7 天，按天聚合
    trace_stats = await get_trace_stats(db, days=7, group_by="day")
    charts = StatsChartsData(
        trend=trace_stats.trend,
        latency=trace_stats.latency,
        tokens=trace_stats.tokens,
    )

    return AdminStatsResponse(
        user_count=user_count,
        kb_count=kb_count,
        doc_count=doc_count,
        chunk_count=chunk_count_result or 0,
        conversation_count=conversation_count,
        message_count=message_count,
        storage_bytes=storage_bytes or 0,
        charts=charts,
    )


async def list_all_kbs(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    user_id: int | None = None,
    status: str | None = None,
    visibility: str | None = None,
    search: str | None = None,
) -> AdminKBListResponse:
    """获取全部知识库列表（跨用户管理视图）。

    对齐 API.md §7.2：含 owner 信息和统计，支持筛选。
    """
    # 构建基础查询：JOIN users 获取 username
    base_q = select(KnowledgeBase, User.username).join(
        User, KnowledgeBase.user_id == User.id
    )

    # 筛选条件
    conditions = []
    if user_id is not None:
        conditions.append(KnowledgeBase.user_id == user_id)
    if status is not None:
        conditions.append(KnowledgeBase.status == status)
    if visibility is not None:
        conditions.append(KnowledgeBase.visibility == visibility)
    if search:
        conditions.append(KnowledgeBase.name.like(f"%{search}%"))

    if conditions:
        base_q = base_q.where(*conditions)

    # 总数
    count_q = select(func.count()).select_from(base_q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # 分页数据
    q = (
        base_q
        .order_by(KnowledgeBase.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(q)).all()

    items = []
    for kb, username in rows:
        items.append(AdminKBItem(
            id=kb.id,
            name=kb.name,
            description=kb.description,
            visibility=kb.visibility,
            user_id=kb.user_id,
            username=username,
            status=kb.status,
            doc_count=kb.doc_count,
            chunk_count=kb.chunk_count,
            created_at=kb.created_at,
            updated_at=kb.updated_at,
        ))

    return AdminKBListResponse(
        total=total, page=page, page_size=page_size, items=items
    )


async def list_all_documents(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    kb_id: int | None = None,
    status: str | None = None,
    filename: str | None = None,
    sort_by: str = "created_at",
    order: str = "desc",
) -> AdminDocListResponse:
    """获取全部文档列表（跨知识库视图）。

    对齐 API.md §7.3：含 KB 名称和 owner 信息，支持筛选和排序。
    """
    # 构建基础查询：JOIN knowledge_bases + users
    base_q = (
        select(
            Document,
            KnowledgeBase.name.label("kb_name"),
            KnowledgeBase.visibility.label("kb_visibility"),
            KnowledgeBase.user_id.label("owner_id"),
            User.username.label("owner_username"),
        )
        .join(KnowledgeBase, Document.kb_id == KnowledgeBase.id)
        .join(User, KnowledgeBase.user_id == User.id)
    )

    # 筛选条件
    conditions = []
    if kb_id is not None:
        conditions.append(Document.kb_id == kb_id)
    if status is not None:
        conditions.append(Document.status == status)
    if filename:
        conditions.append(Document.filename.like(f"%{filename}%"))

    if conditions:
        base_q = base_q.where(*conditions)

    # 总数
    count_q = select(func.count()).select_from(base_q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # 排序字段映射（防止 SQL 注入）
    sort_column_map = {
        "created_at": Document.created_at,
        "updated_at": Document.updated_at,
        "filename": Document.filename,
        "file_size": Document.file_size,
        "status": Document.status,
    }
    sort_col = sort_column_map.get(sort_by, Document.created_at)
    order_clause = sort_col.desc() if order == "desc" else sort_col.asc()

    # 分页数据
    q = (
        base_q
        .order_by(order_clause)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(q)).all()

    items = []
    for doc, kb_name, kb_visibility, owner_id, owner_username in rows:
        items.append(AdminDocItem(
            id=doc.id,
            kb_id=doc.kb_id,
            kb_name=kb_name,
            kb_visibility=kb_visibility,
            owner_id=owner_id,
            owner_username=owner_username,
            filename=doc.filename,
            file_type=doc.file_type,
            file_size=doc.file_size,
            status=doc.status.value if hasattr(doc.status, 'value') else doc.status,
            current_stage=doc.current_stage,
            chunk_count=doc.chunk_count,
            error_message=doc.error_msg,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        ))

    return AdminDocListResponse(
        total=total, page=page, page_size=page_size, items=items
    )
