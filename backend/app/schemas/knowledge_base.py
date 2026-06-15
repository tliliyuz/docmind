"""知识库请求/响应模型"""

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class KnowledgeBaseCreate(BaseModel):
    """创建知识库请求"""
    name: str = Field(..., min_length=2, max_length=128, description="知识库名称")
    description: str | None = Field(None, max_length=2000, description="知识库描述")
    visibility: str = Field("private", pattern="^(private|public)$", description="可见性：private / public")

    @field_validator("name")
    @classmethod
    def validate_name_not_numeric(cls, v: str) -> str:
        """拒绝纯数字/纯空格名称（后端兜底校验，前端同步校验）"""
        stripped = v.strip()
        if not stripped:
            raise ValueError("知识库名称不能为空")
        if re.match(r"^\d+$", stripped):
            raise ValueError("知识库名称不能为纯数字，请包含文字或字母")
        return v


class KnowledgeBaseUpdate(BaseModel):
    """更新知识库请求"""
    name: str | None = Field(None, min_length=2, max_length=128, description="知识库名称")
    description: str | None = Field(None, max_length=2000, description="知识库描述")
    visibility: str | None = Field(None, pattern="^(private|public)$", description="可见性：private / public")

    @field_validator("name")
    @classmethod
    def validate_name_not_numeric(cls, v: str | None) -> str | None:
        """拒绝纯数字/纯空格名称（可选字段，None 时跳过）"""
        if v is None:
            return v
        stripped = v.strip()
        if not stripped:
            raise ValueError("知识库名称不能为空")
        if re.match(r"^\d+$", stripped):
            raise ValueError("知识库名称不能为纯数字，请包含文字或字母")
        return v


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
