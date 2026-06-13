"""文档 API — 上传/批量上传/列表/详情/分块/删除/重新处理"""

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.uuid_helpers import resolve_uuid_to_id
from app.dependencies import get_current_user, get_db
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.services.document_service import (
    batch_upload_documents,
    delete_document,
    get_document,
    get_document_chunks,
    list_documents,
    reprocess_document,
    upload_document,
)

router = APIRouter(prefix="/api/knowledge-bases", tags=["文档"])

# 批量上传必须定义在 {uuid} 路由之前，避免 "batch-upload" 被解析为 doc_uuid


@router.post("/{kb_uuid}/documents/batch-upload")
async def batch_upload(
    kb_uuid: str,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """批量上传文档（多文件，部分成功返回）"""
    kb_id = await resolve_uuid_to_id(db, KnowledgeBase, kb_uuid)
    data = await batch_upload_documents(
        db, kb_id, current_user["user_id"], current_user["role"], files
    )
    total = len(data.success) + len(data.failed)
    msg = f"批量上传完成（{total} 个文件，成功 {len(data.success)} 个"
    if data.failed:
        msg += f"，失败 {len(data.failed)} 个"
    msg += "）"
    return {"code": "0", "message": msg, "data": data.model_dump()}


@router.post("/{kb_uuid}/documents", status_code=201)
async def upload(
    kb_uuid: str,
    file: UploadFile = File(...),
    force: bool = Form(False),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """上传单个文档（multipart/form-data），支持 force 覆盖"""
    kb_id = await resolve_uuid_to_id(db, KnowledgeBase, kb_uuid)
    data = await upload_document(
        db, kb_id, current_user["user_id"], current_user["role"], file, force
    )
    return {"code": "0", "message": "文档上传成功，已加入处理队列", "data": data.model_dump()}


@router.get("/{kb_uuid}/documents")
async def list_docs(
    kb_uuid: str,
    status: str | None = Query(None, description="按状态过滤"),
    filename: str | None = Query(None, description="按文件名模糊搜索"),
    sort_by: str = Query("created_at", description="排序字段"),
    order: str = Query("desc", description="排序方向 asc/desc"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """获取知识库下的文档列表（筛选 + 排序 + 分页）"""
    kb_id = await resolve_uuid_to_id(db, KnowledgeBase, kb_uuid)
    data = await list_documents(
        db,
        kb_id,
        current_user["user_id"],
        current_user["role"],
        status=status,
        filename=filename,
        sort_by=sort_by,
        order=order,
        page=page,
        page_size=page_size,
    )
    return {"code": "0", "message": "ok", "data": data.model_dump()}


@router.get("/{kb_uuid}/documents/{doc_uuid}")
async def get_doc(
    kb_uuid: str,
    doc_uuid: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """获取单个文档详情"""
    kb_id = await resolve_uuid_to_id(db, KnowledgeBase, kb_uuid)
    doc_id = await resolve_uuid_to_id(db, Document, doc_uuid)
    data = await get_document(db, kb_id, doc_id, current_user["user_id"], current_user["role"])
    return {"code": "0", "message": "ok", "data": data.model_dump()}


@router.get("/{kb_uuid}/documents/{doc_uuid}/chunks")
async def get_chunks(
    kb_uuid: str,
    doc_uuid: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """查看文档的分块列表（分页），生产环境截断 content 至预览"""
    kb_id = await resolve_uuid_to_id(db, KnowledgeBase, kb_uuid)
    doc_id = await resolve_uuid_to_id(db, Document, doc_uuid)
    data = await get_document_chunks(
        db,
        kb_id,
        doc_id,
        current_user["user_id"],
        current_user["role"],
        page=page,
        page_size=page_size,
    )
    return {"code": "0", "message": "ok", "data": data.model_dump()}


@router.post("/{kb_uuid}/documents/{doc_uuid}/reprocess")
async def reprocess(
    kb_uuid: str,
    doc_uuid: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """重新处理失败或部分失败的文档（仅 partial_failed / failed 允许）"""
    kb_id = await resolve_uuid_to_id(db, KnowledgeBase, kb_uuid)
    doc_id = await resolve_uuid_to_id(db, Document, doc_uuid)
    data = await reprocess_document(
        db, kb_id, doc_id, current_user["user_id"], current_user["role"]
    )
    return {"code": "0", "message": "重新处理任务已提交", "data": data.model_dump()}


@router.delete("/{kb_uuid}/documents/{doc_uuid}", status_code=202)
async def delete_doc(
    kb_uuid: str,
    doc_uuid: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """删除文档（标记 deleting → Celery 异步清理向量+文件+记录）"""
    kb_id = await resolve_uuid_to_id(db, KnowledgeBase, kb_uuid)
    doc_id = await resolve_uuid_to_id(db, Document, doc_uuid)
    data = await delete_document(
        db, kb_id, doc_id, current_user["user_id"], current_user["role"]
    )
    return {"code": "0", "message": "文档删除任务已提交", "data": data.model_dump()}
