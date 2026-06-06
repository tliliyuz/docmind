"""会话 API — CRUD，对齐 API.md §5"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.schemas.conversation import ConversationCreate, ConversationUpdate
from app.services.conversation_service import (
    create_conversation,
    delete_conversation,
    get_conversation_detail,
    list_conversations,
    rename_conversation,
)

router = APIRouter(prefix="/api/conversations", tags=["会话"])


@router.post("", status_code=201)
async def create_conv(
    req: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """创建会话"""
    data = await create_conversation(db, current_user["user_id"], req)
    return {"code": "0", "message": "会话创建成功", "data": data.model_dump()}


@router.get("")
async def list_conv(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """获取当前用户会话列表（按更新时间倒序，分页）"""
    data = await list_conversations(db, current_user["user_id"], page, page_size)
    return {"code": "0", "message": "ok", "data": data.model_dump()}


@router.get("/{conv_id}")
async def get_conv(
    conv_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """获取会话详情（含消息历史）"""
    data = await get_conversation_detail(db, conv_id, current_user["user_id"])
    return {"code": "0", "message": "ok", "data": data.model_dump()}


@router.put("/{conv_id}")
async def rename_conv(
    conv_id: int,
    req: ConversationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """重命名会话"""
    data = await rename_conversation(db, conv_id, current_user["user_id"], req)
    return {"code": "0", "message": "ok", "data": data.model_dump()}


@router.delete("/{conv_id}")
async def delete_conv(
    conv_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """删除会话及其全部消息"""
    await delete_conversation(db, conv_id, current_user["user_id"])
    return {"code": "0", "message": "会话已删除", "data": None}
