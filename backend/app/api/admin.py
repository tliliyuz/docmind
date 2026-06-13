"""管理后台 API — 统计/知识库管理/文档管理/链路追踪/用户管理

对齐 API.md §7：所有端点要求 admin 角色（require_admin 依赖注入）。
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, require_admin
from app.core.exceptions import AppException
from app.schemas.admin import (
    AdminUserResetPasswordRequest,
    AdminUserStatusRequest,
)
from app.services.admin_service import (
    change_user_status,
    get_stats,
    get_user_detail,
    list_all_documents,
    list_all_kbs,
    list_users,
    reset_user_password,
)
from app.services.trace_service import (
    get_trace_detail,
    get_trace_stats,
    list_traces,
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
    kb_id: str | None = Query(None, description="按知识库 UUID 过滤"),
    status: str | None = Query(None, description="按状态过滤"),
    filename: str | None = Query(None, description="按文件名模糊搜索"),
    sort_by: str = Query("created_at", description="排序字段"),
    order: str = Query("desc", description="asc / desc"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """获取全部文档列表（跨知识库视图）"""
    # UUID → integer ID（API 边界转换）
    from app.core.uuid_helpers import resolve_uuid_to_id
    from app.models.knowledge_base import KnowledgeBase
    resolved_kb_id = None
    if kb_id:
        resolved_kb_id = await resolve_uuid_to_id(db, KnowledgeBase, kb_id)
    data = await list_all_documents(
        db,
        page=page,
        page_size=page_size,
        kb_id=resolved_kb_id,
        status=status,
        filename=filename,
        sort_by=sort_by,
        order=order,
    )
    return {"code": "0", "message": "ok", "data": data.model_dump()}


# ==================== Trace 链路追踪接口 ====================


@router.get("/traces")
async def list_admin_traces(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    user_id: int | None = Query(None, description="按用户筛选"),
    status: str | None = Query(None, description="success / error / partial"),
    intent_type: str | None = Query(None, description="KNOWLEDGE / CASUAL / META"),
    response_mode: str | None = Query(None, description="RAG / DIRECT_LLM / META / CASUAL / FALLBACK"),
    start_date: datetime | None = Query(None, description="开始时间（ISO 8601）"),
    end_date: datetime | None = Query(None, description="结束时间（ISO 8601）"),
    search: str | None = Query(None, description="按问题模糊搜索"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """获取 Trace 列表（分页+筛选）

    对齐 API.md §7.5：所有 /api/admin/traces/* 端点要求 role=admin。
    """
    data = await list_traces(
        db,
        page=page,
        page_size=page_size,
        user_id=user_id,
        status=status,
        intent_type=intent_type,
        response_mode=response_mode,
        start_date=start_date,
        end_date=end_date,
        search=search,
    )
    return {"code": "0", "message": "ok", "data": data.model_dump()}


@router.get("/traces/{trace_id}")
async def get_admin_trace_detail(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """获取 Trace 详情（含各阶段 JSON 详情）

    对齐 API.md §7.5。
    """
    data = await get_trace_detail(db, trace_id=trace_id)
    if data is None:
        raise AppException("E7001", "Trace 不存在", 404, f"trace_id={trace_id} 不存在")
    return {"code": "0", "message": "ok", "data": data.model_dump()}


@router.get("/stats/traces")
async def get_admin_trace_stats(
    days: int = Query(7, ge=1, le=90, description="过去 N 天"),
    group_by: str = Query("day", description="day / hour"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Trace 统计数据，用于 ECharts 图表渲染

    对齐 API.md §7.6。
    """
    data = await get_trace_stats(db, days=days, group_by=group_by)
    return {"code": "0", "message": "ok", "data": data.model_dump()}


# ==================== 用户管理接口 — 对齐 API.md §7.7 ====================


@router.get("/users")
async def list_admin_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    role: str | None = Query(None, description="user / admin"),
    status: str | None = Query(None, description="active / disabled"),
    search: str | None = Query(None, description="按用户名模糊搜索"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """获取用户列表（分页+筛选）

    对齐 API.md §7.7 GET /api/admin/users。
    """
    data = await list_users(
        db,
        page=page,
        page_size=page_size,
        role=role,
        status=status,
        search=search,
    )
    return {"code": "0", "message": "ok", "data": data.model_dump()}


@router.get("/users/{user_id}")
async def get_admin_user_detail(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """获取用户详情（含统计）

    对齐 API.md §7.7 GET /api/admin/users/{user_id}。
    """
    data = await get_user_detail(db, user_id=user_id)
    return {"code": "0", "message": "ok", "data": data.model_dump()}


@router.put("/users/{user_id}/status")
async def update_admin_user_status(
    user_id: int,
    body: AdminUserStatusRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """禁用/启用用户

    对齐 API.md §7.7 PUT /api/admin/users/{user_id}/status。
    """
    data = await change_user_status(
        db,
        user_id=user_id,
        new_status=body.status,
        current_user_id=current_user.get("user_id"),
    )
    message = "用户已禁用" if body.status == "disabled" else "用户已启用"
    return {"code": "0", "message": message, "data": data}


@router.post("/users/{user_id}/reset-password")
async def reset_admin_user_password(
    user_id: int,
    body: AdminUserResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """重置用户密码

    对齐 API.md §7.7 POST /api/admin/users/{user_id}/reset-password。
    """
    data = await reset_user_password(
        db, user_id=user_id, new_password=body.new_password
    )
    return {"code": "0", "message": "密码重置成功", "data": data}
