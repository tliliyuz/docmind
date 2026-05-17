"""知识库 API — 创建/列表/详情/更新/删除"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseUpdate
from app.services.knowledge_base_service import (
    create_kb,
    delete_kb,
    list_kbs,
    get_kb,
    update_kb,
)

router = APIRouter(prefix="/api/knowledge-bases", tags=["知识库"])


@router.post("", status_code=201)
async def create_knowledge_base(
    req: KnowledgeBaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """创建知识库"""
    kb = await create_kb(db, current_user["user_id"], req)
    return {"code": "0", "message": "知识库创建成功", "data": kb.model_dump()}


@router.get("")
async def list_knowledge_bases(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """获取当前用户的知识库列表（分页）"""
    data = await list_kbs(db, current_user["user_id"], page, page_size)
    return {"code": "0", "message": "ok", "data": data.model_dump()}


@router.get("/{kb_id}")
async def get_knowledge_base(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """获取知识库详情"""
    kb = await get_kb(db, kb_id)
    from app.schemas.knowledge_base import KnowledgeBaseResponse
    return {"code": "0", "message": "ok", "data": KnowledgeBaseResponse.model_validate(kb).model_dump()}


@router.put("/{kb_id}")
async def update_knowledge_base(
    kb_id: int,
    req: KnowledgeBaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """更新知识库名称或描述"""
    kb = await update_kb(db, kb_id, current_user["user_id"], current_user["role"], req)
    return {"code": "0", "message": "知识库更新成功", "data": kb.model_dump()}


@router.delete("/{kb_id}", status_code=202)
async def delete_knowledge_base(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """删除知识库（标记 status=deleting，异步清理由 Celery 处理）"""
    data = await delete_kb(db, kb_id, current_user["user_id"], current_user["role"])
    return {"code": "0", "message": "知识库删除任务已提交", "data": data.model_dump()}
