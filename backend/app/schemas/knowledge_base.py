"""知识库请求/响应模型"""

from datetime import datetime

from pydantic import BaseModel, Field


class KnowledgeBaseCreate(BaseModel):
    """创建知识库请求"""
    name: str = Field(..., min_length=2, max_length=128, description="知识库名称")
    description: str | None = Field(None, max_length=2000, description="知识库描述")


class KnowledgeBaseUpdate(BaseModel):
    """更新知识库请求"""
    name: str | None = Field(None, min_length=2, max_length=128, description="知识库名称")
    description: str | None = Field(None, max_length=2000, description="知识库描述")


class KnowledgeBaseResponse(BaseModel):
    """知识库响应"""
    id: int
    name: str
    description: str | None
    user_id: int
    status: str
    doc_count: int
    chunk_count: int
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class KnowledgeBaseListData(BaseModel):
    """知识库列表分页数据"""
    total: int
    page: int
    page_size: int
    items: list[KnowledgeBaseResponse]


class KnowledgeBaseDeleteData(BaseModel):
    """知识库删除响应数据"""
    kb_id: int
    status: str
