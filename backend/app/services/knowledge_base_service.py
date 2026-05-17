"""知识库业务逻辑 — 创建/查询/更新/删除"""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    KnowledgeBaseNameExistsException,
    KnowledgeBaseNotFoundException,
    PermissionDeniedException,
)
from app.models.knowledge_base import KnowledgeBase
from app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseDeleteData,
    KnowledgeBaseListData,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
)


async def create_kb(
    db: AsyncSession, user_id: int, data: KnowledgeBaseCreate
) -> KnowledgeBaseResponse:
    """创建知识库，同名冲突时抛出 KnowledgeBaseNameExistsException"""
    kb = KnowledgeBase(
        user_id=user_id,
        name=data.name,
        description=data.description,
    )
    db.add(kb)
    try:
        await db.flush()
    except IntegrityError:
        raise KnowledgeBaseNameExistsException(data.name)
    await db.refresh(kb)
    return KnowledgeBaseResponse.model_validate(kb)


async def get_kb(db: AsyncSession, kb_id: int) -> KnowledgeBase:
    """获取知识库，不存在时抛出 KnowledgeBaseNotFoundException"""
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    kb = result.scalar_one_or_none()
    if kb is None:
        raise KnowledgeBaseNotFoundException(kb_id)
    return kb


async def list_kbs(
    db: AsyncSession, user_id: int, page: int = 1, page_size: int = 20
) -> KnowledgeBaseListData:
    """获取用户的知识库列表（分页）"""
    # 总数
    count_q = select(func.count()).select_from(KnowledgeBase).where(KnowledgeBase.user_id == user_id)
    total = (await db.execute(count_q)).scalar()

    # 分页数据
    q = (
        select(KnowledgeBase)
        .where(KnowledgeBase.user_id == user_id)
        .order_by(KnowledgeBase.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(q)).scalars().all()
    items = [KnowledgeBaseResponse.model_validate(r) for r in rows]

    return KnowledgeBaseListData(total=total, page=page, page_size=page_size, items=items)


async def update_kb(
    db: AsyncSession, kb_id: int, user_id: int, role: str, data: KnowledgeBaseUpdate
) -> KnowledgeBaseResponse:
    """更新知识库名称或描述"""
    kb = await get_kb(db, kb_id)

    if kb.user_id != user_id and role != "admin":
        raise PermissionDeniedException()

    if data.name is not None:
        kb.name = data.name
    if data.description is not None:
        kb.description = data.description

    try:
        await db.flush()
    except IntegrityError:
        raise KnowledgeBaseNameExistsException(data.name)

    await db.refresh(kb)
    return KnowledgeBaseResponse.model_validate(kb)


async def delete_kb(
    db: AsyncSession, kb_id: int, user_id: int, role: str
) -> KnowledgeBaseDeleteData:
    """删除知识库（仅标记 status=deleting，不做物理删除）"""
    kb = await get_kb(db, kb_id)

    if kb.user_id != user_id and role != "admin":
        raise PermissionDeniedException()

    kb.status = "deleting"
    await db.flush()
    await db.refresh(kb)
    return KnowledgeBaseDeleteData(kb_id=kb.id, status=kb.status)


async def check_kb_active(db: AsyncSession, kb_id: int) -> KnowledgeBase:
    """检查知识库存在且 status==active，否则抛异常。
    供文档上传/检索/reprocess 等服务调用。
    """
    kb = await get_kb(db, kb_id)
    if kb.status != "active":
        raise KnowledgeBaseNotFoundException(kb_id)
    return kb
