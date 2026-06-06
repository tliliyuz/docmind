"""会话业务逻辑 — CRUD + 权限校验，对齐 API.md §5"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConversationAccessDeniedException,
    ConversationNotFoundException,
)
from app.models.conversation import Conversation
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


async def create_conversation(
    db: AsyncSession, user_id: int, data: ConversationCreate
) -> ConversationResponse:
    """创建会话"""
    conv = Conversation(
        user_id=user_id,
        kb_id=data.kb_id,
        title=data.title or "新对话",
    )
    db.add(conv)
    await db.flush()
    await db.refresh(conv)
    return ConversationResponse.model_validate(conv)


async def list_conversations(
    db: AsyncSession, user_id: int, page: int = 1, page_size: int = 20
) -> ConversationListResponse:
    """获取当前用户会话列表，按 updated_at DESC 分页"""
    # 总数
    count_q = (
        select(func.count())
        .select_from(Conversation)
        .where(Conversation.user_id == user_id)
    )
    total = (await db.execute(count_q)).scalar() or 0

    # 分页查询
    offset = (page - 1) * page_size
    list_q = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = (await db.execute(list_q)).scalars().all()

    return ConversationListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[ConversationResponse.model_validate(c) for c in rows],
    )


async def get_conversation_detail(
    db: AsyncSession, conv_id: int, user_id: int
) -> ConversationDetailResponse:
    """获取会话详情（含消息列表）"""
    conv = await _get_owned_conversation(db, conv_id, user_id)

    # 查询消息（按创建时间正序）
    msg_q = (
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at.asc())
    )
    messages = (await db.execute(msg_q)).scalars().all()

    base = ConversationResponse.model_validate(conv)
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
    return ConversationResponse.model_validate(conv)


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
