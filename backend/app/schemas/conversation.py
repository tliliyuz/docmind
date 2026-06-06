"""会话请求/响应模型 — 对齐 API.md §5"""

from datetime import datetime

from pydantic import BaseModel, Field


# ── 请求模型 ──


class ConversationCreate(BaseModel):
    """POST /api/conversations 请求体"""
    kb_id: int = Field(..., description="关联知识库 ID")
    title: str | None = Field(None, max_length=256, description="会话标题，不传则默认'新对话'")


class ConversationUpdate(BaseModel):
    """PUT /api/conversations/{id} 请求体"""
    title: str = Field(..., min_length=1, max_length=256, description="新标题")


# ── 响应模型 ──


class MessageResponse(BaseModel):
    """消息响应"""
    id: int
    role: str
    content: str
    thinking_content: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    """会话响应（列表项 + 详情共用）"""
    id: int
    user_id: int
    kb_id: int | None
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetailResponse(ConversationResponse):
    """会话详情响应（含消息列表）"""
    messages: list[MessageResponse] = Field(default_factory=list)


class ConversationListResponse(BaseModel):
    """会话列表分页响应"""
    total: int
    page: int
    page_size: int
    items: list[ConversationResponse]
