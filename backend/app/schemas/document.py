"""文档请求/响应模型"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import DocumentStatus


class DocumentResponse(BaseModel):
    """文档响应（列表 & 详情共用）"""
    uuid: str
    kb_uuid: str
    filename: str
    file_type: str
    file_size: int | None = None
    status: DocumentStatus
    chunk_count: int = 0
    error_msg: str | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    """文档列表分页数据"""
    total: int
    page: int
    page_size: int
    items: list[DocumentResponse]


class DocumentUploadResponse(BaseModel):
    """文档上传响应数据"""
    uuid: str
    kb_uuid: str
    filename: str
    file_type: str
    file_size: int | None = None
    status: DocumentStatus

    model_config = {"from_attributes": True}


class DocumentDeleteResponse(BaseModel):
    """文档删除响应数据"""
    doc_uuid: str
    status: DocumentStatus


class DocumentReprocessResponse(BaseModel):
    """文档重新处理响应数据"""
    doc_uuid: str
    status: DocumentStatus


class DocumentBatchUploadItem(BaseModel):
    """批量上传 — 单个成功项"""
    uuid: str
    filename: str
    status: DocumentStatus


class DocumentBatchUploadFailedItem(BaseModel):
    """批量上传 — 单个失败项"""
    filename: str
    reason: str


class DocumentBatchUploadResponse(BaseModel):
    """批量上传响应数据"""
    success: list[DocumentBatchUploadItem]
    failed: list[DocumentBatchUploadFailedItem]


class DocumentChunkResponse(BaseModel):
    """文档分块响应"""
    id: int
    chunk_index: int
    preview: str = Field(description="分块内容预览（默认截断至 200 字符）")
    token_count: int = 0
    metadata: dict[str, Any] | None = None

    model_config = {"from_attributes": True}


class DocumentChunkListResponse(BaseModel):
    """文档分块列表分页数据"""
    total: int
    page: int
    page_size: int
    items: list[DocumentChunkResponse]
