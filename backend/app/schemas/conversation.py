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
    kb_status: str | None = Field(
        None,
        description="关联知识库状态：active=正常 / deleted=已删除 / unavailable=不可访问。"
                    "kb_id 为 null 且 original_kb_id 非 null 时为 deleted",
    )
    kb_name: str | None = Field(
        None,
        description="关联知识库名称（含已删除/不可访问的），前端用于孤儿会话提示。"
                    "孤儿会话从 original_kb_name 读取",
    )
    original_kb_id: int | None = Field(
        None,
        description="KB 删除前的原始 ID，用于孤儿会话检测",
    )
    original_kb_name: str | None = Field(
        None,
        description="KB 删除前的原始名称，用于孤儿会话 Banner 展示",
    )
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None = Field(
        None,
        description="最后一次产生消息的时间，列表排序字段。"
                    "新创建尚无消息的会话为 null",
    )

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
