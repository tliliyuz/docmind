"""管理后台 API — 统计/知识库管理/文档管理

对齐 API.md §7：所有端点要求 admin 角色（require_admin 依赖注入）。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, require_admin
from app.services.admin_service import (
    get_stats,
    list_all_documents,
    list_all_kbs,
)

router = APIRouter(prefix="/api/admin", tags=["管理后台"])


@router.get("/stats")
async def get_admin_stats(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """获取系统全局统计概览"""
    data = await get_stats(db)
    return {"code": "0", "message": "ok", "data": data.model_dump()}


@router.get("/knowledge-bases")
async def list_admin_knowledge_bases(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    user_id: int | None = Query(None, description="按 owner 过滤"),
    status: str | None = Query(None, description="按状态过滤（active / deleting）"),
    visibility: str | None = Query(None, description="按可见性过滤（private / public）"),
    search: str | None = Query(None, description="按名称模糊搜索"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """获取全部知识库列表（跨用户管理视图）"""
    data = await list_all_kbs(
        db,
        page=page,
        page_size=page_size,
        user_id=user_id,
        status=status,
        visibility=visibility,
        search=search,
    )
    return {"code": "0", "message": "ok", "data": data.model_dump()}


@router.get("/documents")
async def list_admin_documents(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    kb_id: int | None = Query(None, description="按知识库过滤"),
    status: str | None = Query(None, description="按状态过滤"),
    filename: str | None = Query(None, description="按文件名模糊搜索"),
    sort_by: str = Query("created_at", description="排序字段"),
    order: str = Query("desc", description="asc / desc"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """获取全部文档列表（跨知识库视图）"""
    data = await list_all_documents(
        db,
        page=page,
        page_size=page_size,
        kb_id=kb_id,
        status=status,
        filename=filename,
        sort_by=sort_by,
        order=order,
    )
    return {"code": "0", "message": "ok", "data": data.model_dump()}
