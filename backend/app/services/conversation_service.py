"""会话业务逻辑 — CRUD + 权限校验，对齐 API.md §5"""

import uuid as uuid_lib

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    ConversationAccessDeniedException,
    ConversationNotFoundException,
)
from app.models.conversation import Conversation
from app.models.knowledge_base import KnowledgeBase
from app.models.message import Message
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationResponse,
    ConversationUpdate,
    MessageResponse,
)


async def _get_owned_conversation(
    db: AsyncSession, conv_id: int, user_id: int
) -> Conversation:
    """获取会话并校验所有权，不存在/非 owner 抛异常"""
    conv = await db.get(Conversation, conv_id)
    if conv is None:
        raise ConversationNotFoundException(conv_id)
    if conv.user_id != user_id:
        raise ConversationAccessDeniedException()
    return conv


def _enrich_kb_status(resp: ConversationResponse, conv: Conversation, user_id: int) -> None:
    """就地填充 kb_status / kb_name / kb_uuid 字段。

    规则：
    - kb_id 为 null 且 original_kb_uuid 非 null → kb_status="deleted"（孤儿会话）
    - kb_id 为 null 且 original_kb_uuid 为 null → kb_status=None（从未关联 KB）
    - KB 存在且可访问 → kb_status="active"
    - KB 存在但 visibility=private 且非 owner → kb_status="unavailable"
    """
    if conv.kb_id is None:
        if conv.original_kb_uuid is not None:
            resp.kb_status = "deleted"
            resp.kb_name = conv.original_kb_name
            resp.kb_uuid = None
        else:
            resp.kb_status = None
            resp.kb_name = None
            resp.kb_uuid = None
        return

    kb = conv.knowledge_base  # 由 selectinload 预加载
    if kb is None:
        # 不应发生（FK 约束保证 kb_id 非 null 时 KB 一定存在），但防御性处理
        resp.kb_status = "deleted"
        resp.kb_name = None
        resp.kb_uuid = None
        return

    resp.kb_uuid = kb.uuid
    resp.kb_name = kb.name
    if kb.visibility == "private" and kb.user_id != user_id:
        resp.kb_status = "unavailable"
    else:
        resp.kb_status = "active"


async def create_conversation(
    db: AsyncSession, user_id: int, data: ConversationCreate
) -> ConversationResponse:
    """创建会话"""
    from app.core.uuid_helpers import resolve_uuid_to_id

    # UUID → integer ID（API 边界转换）
    kb_id = await resolve_uuid_to_id(db, KnowledgeBase, data.kb_uuid)

    conv = Conversation(
        uuid=str(uuid_lib.uuid4()),
        user_id=user_id,
        kb_id=kb_id,
        title=data.title or "新对话",
    )
    db.add(conv)
    await db.flush()
    await db.refresh(conv)
    # 预加载 KB 关系（kb_uuid 属性需要）
    await db.refresh(conv, ["knowledge_base"])
    resp = ConversationResponse.model_validate(conv)
    _enrich_kb_status(resp, conv, user_id)
    return resp


async def list_conversations(
    db: AsyncSession, user_id: int, page: int = 1, page_size: int = 20
) -> ConversationListResponse:
    """获取当前用户会话列表，按 last_message_at DESC 分页"""
    # 总数
    count_q = (
        select(func.count())
        .select_from(Conversation)
        .where(Conversation.user_id == user_id)
    )
    total = (await db.execute(count_q)).scalar() or 0

    # 分页查询（selectinload KB 用于 kb_status 填充）
    offset = (page - 1) * page_size
    list_q = (
        select(Conversation)
        .options(selectinload(Conversation.knowledge_base))
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.last_message_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = (await db.execute(list_q)).scalars().unique().all()

    items = []
    for c in rows:
        resp = ConversationResponse.model_validate(c)
        _enrich_kb_status(resp, c, user_id)
        items.append(resp)

    return ConversationListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


async def get_conversation_detail(
    db: AsyncSession, conv_id: int, user_id: int
) -> ConversationDetailResponse:
    """获取会话详情（含消息列表）"""
    # 带 selectinload 查询，避免 async 上下文中触发 lazy load（MissingGreenlet）
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.knowledge_base))
        .where(Conversation.id == conv_id)
    )
    conv = result.scalars().unique().one_or_none()
    if conv is None:
        raise ConversationNotFoundException(conv_id)
    if conv.user_id != user_id:
        raise ConversationAccessDeniedException()

    # 查询消息（按创建时间正序）
    msg_q = (
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at.asc())
    )
    messages = (await db.execute(msg_q)).scalars().all()

    base = ConversationResponse.model_validate(conv)
    _enrich_kb_status(base, conv, user_id)
    return ConversationDetailResponse(
        **base.model_dump(),
        messages=[MessageResponse.model_validate(m) for m in messages],
    )


async def rename_conversation(
    db: AsyncSession, conv_id: int, user_id: int, data: ConversationUpdate
) -> ConversationResponse:
    """重命名会话"""
    conv = await _get_owned_conversation(db, conv_id, user_id)
    conv.title = data.title
    await db.flush()
    await db.refresh(conv)
    # 预加载 KB 关系（kb_uuid 属性需要）
    await db.refresh(conv, ["knowledge_base"])
    resp = ConversationResponse.model_validate(conv)
    _enrich_kb_status(resp, conv, user_id)
    return resp


async def delete_conversation(
    db: AsyncSession, conv_id: int, user_id: int
) -> None:
    """硬删除会话及其全部消息

    依赖 messages 表 FK ON DELETE CASCADE 自动级联删除。
    对齐 ARCHITECTURE.md §8.7：硬删除，无软删除。
    """
    conv = await _get_owned_conversation(db, conv_id, user_id)
    await db.delete(conv)
    await db.flush()
