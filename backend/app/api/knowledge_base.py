"""知识库 API — 创建/列表/详情/更新/删除"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseResponse, KnowledgeBaseUpdate
from app.services.chat_service import get_selectable_kbs
from app.services.knowledge_base_service import (
    create_kb,
    delete_kb,
    list_kbs,
    list_public_kbs,
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


@router.get("/public")
async def list_public_knowledge_bases(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """获取所有公开知识库列表（分页），跨用户"""
    data = await list_public_kbs(db, page, page_size)
    return {"code": "0", "message": "ok", "data": data.model_dump()}


@router.get("/selectable")
async def list_selectable_knowledge_bases(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """获取当前用户可用于问答的知识库列表，按所有权分组。

    对齐 API.md §3 GET /api/knowledge-bases/selectable：
    - mine: 当前用户的所有 active KB
    - public: 其他用户的 public + active KB
    """
    data = await get_selectable_kbs(db, current_user["user_id"])
    return {"code": "0", "message": "ok", "data": data}


@router.get("/{kb_id}")
async def get_knowledge_base(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """获取知识库详情。public KB 所有登录用户可查看，private KB 仅 owner 或 admin 可查看。"""
    kb = await get_kb(db, kb_id, current_user["user_id"], current_user["role"])
    return {"code": "0", "message": "ok", "data": KnowledgeBaseResponse.model_validate(kb).model_dump()}


@router.put("/{kb_id}")
async def update_knowledge_base(
    kb_id: int,
    req: KnowledgeBaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """更新知识库元数据（名称/描述/可见性）。owner 可修改自己的 KB，admin 可修正任意 KB。"""
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
