"""管理后台业务逻辑 — 统计/知识库列表/文档列表/用户管理

对齐 API.md §7：所有接口要求 admin 角色，跨用户管理视图。
"""

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import AdminSelfModifyException, PasswordSameAsCurrentException, UserNotFoundException
from app.core.security import hash_password, verify_password
from app.core.utils import escape_like
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.message import Message
from app.models.trace import Trace
from app.models.user import User
from app.schemas.admin import (
    AdminDocItem,
    AdminDocListResponse,
    AdminKBItem,
    AdminKBListResponse,
    AdminStatsResponse,
    AdminUserDetailResponse,
    AdminUserItem,
    AdminUserListResponse,
    AdminUserResetPasswordResponse,
    AdminUserStatusResponse,
    StatsChartsData,
)

logger = logging.getLogger(__name__)


# ==================== 用户统计聚合辅助函数 ====================
# 消除 list_users() 与 get_user_detail() 间的重复聚合查询


async def _get_user_kb_count(db: AsyncSession, user_id: int) -> int:
    """获取用户拥有的知识库数量"""
    result = await db.execute(
        select(func.count()).select_from(
            select(KnowledgeBase).where(KnowledgeBase.user_id == user_id).subquery()
        )
    )
    return result.scalar() or 0


async def _get_user_doc_count(db: AsyncSession, user_id: int) -> int:
    """获取用户拥有的文档数量（通过 KB 关联）"""
    result = await db.execute(
        select(func.count()).select_from(
            select(Document)
            .join(KnowledgeBase, Document.kb_id == KnowledgeBase.id)
            .where(KnowledgeBase.user_id == user_id)
            .subquery()
        )
    )
    return result.scalar() or 0


async def _get_user_conversation_count(db: AsyncSession, user_id: int) -> int:
    """获取用户的会话数量"""
    result = await db.execute(
        select(func.count()).select_from(
            select(Conversation).where(Conversation.user_id == user_id).subquery()
        )
    )
    return result.scalar() or 0


async def _get_user_message_count(db: AsyncSession, user_id: int) -> int:
    """获取用户的消息数量（通过 Conversation 关联）"""
    result = await db.execute(
        select(func.count()).select_from(
            select(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(Conversation.user_id == user_id)
            .subquery()
        )
    )
    return result.scalar() or 0


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
        conditions.append(KnowledgeBase.name.like(f"%{escape_like(search)}%", escape="\\"))

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
            uuid=kb.uuid,
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
            KnowledgeBase.uuid.label("kb_uuid"),
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
        conditions.append(Document.filename.like(f"%{escape_like(filename)}%", escape="\\"))

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
    for doc, kb_name, kb_uuid_val, kb_visibility, owner_id, owner_username in rows:
        items.append(AdminDocItem(
            uuid=doc.uuid,
            kb_uuid=kb_uuid_val,
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


# ==================== 用户管理 — 对齐 API.md §7.7 ====================


async def list_users(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    role: str | None = None,
    status: str | None = None,
    search: str | None = None,
) -> AdminUserListResponse:
    """获取用户列表（分页+筛选）。

    对齐 API.md §7.7 GET /api/admin/users：
    - 支持 role/status/search 筛选
    - 聚合 kb_count/doc_count/conversation_count
    - 从 traces 表获取 last_active_at
    """
    # 基础查询
    base_q = select(User)

    # 筛选条件
    conditions = []
    if role is not None:
        conditions.append(User.role == role)
    if status is not None:
        conditions.append(User.status == status)
    if search:
        conditions.append(User.username.like(f"%{escape_like(search)}%", escape="\\"))

    if conditions:
        base_q = base_q.where(*conditions)

    # 总数
    count_q = select(func.count()).select_from(base_q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # 分页数据
    q = (
        base_q
        .order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    users = (await db.execute(q)).scalars().all()

    items = []
    for user in users:
        # 聚合统计（委托辅助函数，消除与 get_user_detail 的重复）
        kb_count = await _get_user_kb_count(db, user.id)
        doc_count = await _get_user_doc_count(db, user.id)
        conversation_count = await _get_user_conversation_count(db, user.id)

        # 最后活跃时间（从 traces 表聚合）
        last_active_at = (await db.execute(
            select(func.max(Trace.created_at)).where(Trace.user_id == user.id)
        )).scalar()

        items.append(AdminUserItem(
            id=user.id,
            username=user.username,
            role=user.role,
            status=user.status,
            kb_count=kb_count,
            doc_count=doc_count,
            conversation_count=conversation_count,
            last_active_at=last_active_at,
            created_at=user.created_at,
        ))

    return AdminUserListResponse(
        total=total, page=page, page_size=page_size, items=items
    )


async def get_user_detail(
    db: AsyncSession,
    user_id: int,
) -> AdminUserDetailResponse:
    """获取用户详情（含统计 + Token 聚合）。

    对齐 API.md §7.7 GET /api/admin/users/{user_id}：
    - 基础统计 + message_count
    - 从 traces 表聚合 total_input_tokens / total_output_tokens / last_active_at
    """
    user = await db.get(User, user_id)
    if user is None:
        raise UserNotFoundException(user_id)

    # 聚合统计（委托辅助函数，消除与 list_users 的重复）
    kb_count = await _get_user_kb_count(db, user_id)
    doc_count = await _get_user_doc_count(db, user_id)
    conversation_count = await _get_user_conversation_count(db, user_id)
    message_count = await _get_user_message_count(db, user_id)

    # Token 聚合（从 traces 表 JSON_EXTRACT）
    token_stats = (await db.execute(
        select(
            func.coalesce(func.sum(func.JSON_EXTRACT(Trace.generate, "$.input_tokens")), 0),
            func.coalesce(func.sum(func.JSON_EXTRACT(Trace.generate, "$.output_tokens")), 0),
            func.max(Trace.created_at),
        ).where(Trace.user_id == user_id)
    )).one()
    total_input_tokens = int(token_stats[0] or 0)
    total_output_tokens = int(token_stats[1] or 0)
    last_active_at = token_stats[2]

    return AdminUserDetailResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        status=user.status,
        kb_count=kb_count,
        doc_count=doc_count,
        conversation_count=conversation_count,
        message_count=message_count,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        last_active_at=last_active_at,
        created_at=user.created_at,
    )


async def change_user_status(
    db: AsyncSession,
    user_id: int,
    new_status: str,
    current_user_id: int,
) -> AdminUserStatusResponse:
    """禁用/启用用户。

    对齐 API.md §7.7 PUT /api/admin/users/{user_id}/status：
    - 禁用时吊销全部 refresh_token
    - 不能操作自己
    """
    if user_id == current_user_id:
        raise AdminSelfModifyException()

    user = await db.get(User, user_id)
    if user is None:
        raise UserNotFoundException(user_id)
    if user.status == new_status:
        return AdminUserStatusResponse(id=user.id, username=user.username, status=user.status)

    user.status = new_status
    await db.flush()

    # 禁用时吊销全部 refresh_token
    if new_status == "disabled":
        from app.services.auth_service import revoke_all_user_tokens
        await revoke_all_user_tokens(db, user_id)

    logger.info("用户状态变更: user_id=%d, new_status=%s", user_id, new_status)
    return AdminUserStatusResponse(id=user.id, username=user.username, status=user.status)


async def reset_user_password(
    db: AsyncSession,
    user_id: int,
    new_password: str,
) -> AdminUserResetPasswordResponse:
    """重置用户密码 + 吊销全部 refresh_token。

    对齐 API.md §7.7 POST /api/admin/users/{user_id}/reset-password。
    新密码不能与当前密码相同。
    """
    user = await db.get(User, user_id)
    if user is None:
        raise UserNotFoundException(user_id)

    if verify_password(new_password, user.password_hash):
        raise PasswordSameAsCurrentException()

    user.password_hash = hash_password(new_password)
    await db.flush()

    # 吊销全部 refresh_token（密码已变更，强制重新登录）
    from app.services.auth_service import revoke_all_user_tokens
    await revoke_all_user_tokens(db, user_id)

    logger.info("管理员重置用户密码: user_id=%d", user_id)
    return AdminUserResetPasswordResponse(id=user.id, username=user.username)
