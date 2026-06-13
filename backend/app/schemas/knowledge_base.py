"""知识库请求/响应模型"""

from datetime import datetime

from pydantic import BaseModel, Field


class KnowledgeBaseCreate(BaseModel):
    """创建知识库请求"""
    name: str = Field(..., min_length=2, max_length=128, description="知识库名称")
    description: str | None = Field(None, max_length=2000, description="知识库描述")
    visibility: str = Field("private", pattern="^(private|public)$", description="可见性：private / public")


class KnowledgeBaseUpdate(BaseModel):
    """更新知识库请求"""
    name: str | None = Field(None, min_length=2, max_length=128, description="知识库名称")
    description: str | None = Field(None, max_length=2000, description="知识库描述")
    visibility: str | None = Field(None, pattern="^(private|public)$", description="可见性：private / public")


class KnowledgeBaseResponse(BaseModel):
    """知识库响应"""
    uuid: str
    name: str
    description: str | None
    user_id: int
    visibility: str
    status: str
    doc_count: int
    chunk_count: int
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class KnowledgeBaseListResponse(BaseModel):
    """知识库列表分页数据"""
    total: int
    page: int
    page_size: int
    items: list[KnowledgeBaseResponse]


class KnowledgeBaseDeleteResponse(BaseModel):
    """知识库删除响应数据"""
    kb_uuid: str
    status: str


class PublicKnowledgeBaseResponse(BaseModel):
    """公共知识库响应（含 owner 用户名）"""
    uuid: str
    name: str
    description: str | None
    user_id: int
    username: str
    visibility: str
    status: str
    doc_count: int
    chunk_count: int
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PublicKnowledgeBaseListResponse(BaseModel):
    """公共知识库列表分页数据"""
    total: int
    page: int
    page_size: int
    items: list[PublicKnowledgeBaseResponse]
