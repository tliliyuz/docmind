"""问答请求/响应模型 — 对齐 API.md §6"""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """POST /api/chat 请求体

    对齐 API.md §6：
    - conversation_id: null 时自动创建会话
    - kb_id: 目标知识库 ID
    - question: 用户问题（≤2000 字符）
    - deep_thinking: 是否启用深度思考模式
    """
    conversation_id: int | None = Field(None, description="会话 ID，新对话传 null")
    kb_id: int = Field(..., description="目标知识库 ID")
    question: str = Field(
        ..., min_length=1, max_length=2000, description="用户问题"
    )
    deep_thinking: bool = Field(False, description="是否启用深度思考模式")


class ChatSourceChunk(BaseModel):
    """SSE sources 事件中的单条引用来源

    对齐 API.md §6.1 event: sources
    """
    chunk_index: int = Field(description="来源编号，与 LLM 回答中的 [来源N] 一一对应")
    doc_id: int
    doc_name: str
    content: str = Field(description="分块文本（截断至 200 字符）")
    score: float
    page: int | None = None


class TokenUsage(BaseModel):
    """Token 消耗统计

    对齐 API.md §6.1 event: finish
    """
    prompt: int = Field(0, description="Prompt 消耗 Token 数")
    completion: int = Field(0, description="生成内容消耗 Token 数")
    total: int = Field(0, description="总 Token 消耗")


class ChatFinishData(BaseModel):
    """SSE finish 事件数据

    对齐 API.md §6.1 event: finish
    """
    message_id: int
    title: str | None = Field(None, description="自动生成的对话标题（仅首轮返回）")
    token_usage: TokenUsage = Field(default_factory=TokenUsage, description="Token 消耗统计")


class SelectableKBItem(BaseModel):
    """KB 选择器中的单个知识库项"""
    id: int
    name: str
    visibility: str = "private"
    doc_count: int = 0
    username: str | None = Field(None, description="仅 public 分组有此字段")


class SelectableKBResponse(BaseModel):
    """GET /api/knowledge-bases/selectable 响应

    对齐 API.md §3：返回 {mine, public} 分组
    """
    mine: list[SelectableKBItem] = Field(default_factory=list)
    public: list[SelectableKBItem] = Field(default_factory=list)
