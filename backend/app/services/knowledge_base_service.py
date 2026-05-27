"""知识库业务逻辑 — 创建/查询/更新/删除"""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    KnowledgeBaseNameExistsException,
    KnowledgeBaseNotFoundException,
    PermissionDeniedException,
)
from app.ingest.tasks import delete_kb as delete_kb_task
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseDeleteResponse,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
    PublicKnowledgeBaseListResponse,
    PublicKnowledgeBaseResponse,
)


async def create_kb(
    db: AsyncSession, user_id: int, data: KnowledgeBaseCreate
) -> KnowledgeBaseResponse:
    """创建知识库，同名冲突时抛出 KnowledgeBaseNameExistsException"""
    kb = KnowledgeBase(
        user_id=user_id,
        name=data.name,
        description=data.description,
        visibility=data.visibility,
    )
    db.add(kb)
    try:
        await db.flush()
    except IntegrityError:
        raise KnowledgeBaseNameExistsException(data.name)
    await db.refresh(kb)
    return KnowledgeBaseResponse.model_validate(kb)


async def get_kb(
    db: AsyncSession, kb_id: int, user_id: int | None = None, role: str | None = None
) -> KnowledgeBase:
    """获取知识库，不存在时抛出 KnowledgeBaseNotFoundException。

    权限规则（visibility 优先于 ownership）：
    - public KB：所有登录用户可读
    - private KB：仅 owner 或 admin 可读
    """
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    kb = result.scalar_one_or_none()
    if kb is None:
        raise KnowledgeBaseNotFoundException(kb_id)
    if user_id is not None:
        if kb.visibility == "private" and kb.user_id != user_id and role != "admin":
            raise PermissionDeniedException()
    return kb


async def list_kbs(
    db: AsyncSession, user_id: int, page: int = 1, page_size: int = 20
) -> KnowledgeBaseListResponse:
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

    return KnowledgeBaseListResponse(total=total, page=page, page_size=page_size, items=items)


async def list_public_kbs(
    db: AsyncSession, page: int = 1, page_size: int = 20
) -> PublicKnowledgeBaseListResponse:
    """获取所有公开知识库列表（分页），仅返回 status=active 且 visibility=public 的 KB"""
    base_q = (
        select(KnowledgeBase, User.username)
        .join(User, KnowledgeBase.user_id == User.id)
        .where(
            KnowledgeBase.visibility == "public",
            KnowledgeBase.status == "active",
        )
    )
    # 总数
    count_q = select(func.count()).select_from(base_q.subquery())
    total = (await db.execute(count_q)).scalar()

    # 分页数据
    q = (
        base_q
        .order_by(KnowledgeBase.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(q)).all()
    items = [
        PublicKnowledgeBaseResponse(
            id=kb.id,
            name=kb.name,
            description=kb.description,
            user_id=kb.user_id,
            username=username,
            visibility=kb.visibility,
            status=kb.status,
            doc_count=kb.doc_count,
            chunk_count=kb.chunk_count,
            created_at=kb.created_at,
            updated_at=kb.updated_at,
        )
        for kb, username in rows
    ]

    return PublicKnowledgeBaseListResponse(total=total, page=page, page_size=page_size, items=items)


async def update_kb(
    db: AsyncSession, kb_id: int, user_id: int, role: str, data: KnowledgeBaseUpdate
) -> KnowledgeBaseResponse:
    """更新知识库元数据（名称/描述/可见性）。
    owner 可修改自己的 KB；admin 可修改任意 KB（含 visibility 修正）。
    """
    kb = await get_kb(db, kb_id)

    if kb.user_id != user_id and role != "admin":
        raise PermissionDeniedException()

    if data.name is not None:
        kb.name = data.name
    if data.description is not None:
        kb.description = data.description
    if data.visibility is not None:
        kb.visibility = data.visibility

    try:
        await db.flush()
    except IntegrityError:
        raise KnowledgeBaseNameExistsException(data.name)

    await db.refresh(kb)
    return KnowledgeBaseResponse.model_validate(kb)


async def delete_kb(
    db: AsyncSession, kb_id: int, user_id: int, role: str
) -> KnowledgeBaseDeleteResponse:
    """删除知识库（仅标记 status=deleting，不做物理删除）"""
    kb = await get_kb(db, kb_id)

    if kb.user_id != user_id and role != "admin":
        raise PermissionDeniedException()

    kb.status = "deleting"
    await db.flush()
    await db.refresh(kb)
    await db.commit()

    # 分发 Celery 异步删除任务（commit 后再分发，避免 Worker 在事务提交前读到旧状态）
    delete_kb_task.delay(kb.id)

    return KnowledgeBaseDeleteResponse(kb_id=kb.id, status=kb.status)


async def check_kb_active(db: AsyncSession, kb_id: int) -> KnowledgeBase:
    """检查知识库存在且 status==active，否则抛异常。
    供文档上传/检索/reprocess 等服务调用。
    """
    kb = await get_kb(db, kb_id)
    if kb.status != "active":
        raise KnowledgeBaseNotFoundException(kb_id)
    return kb
