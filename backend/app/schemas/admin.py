"""管理后台请求/响应模型 — 对齐 API.md §7"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.trace import TraceLatencyItem, TraceTokenItem, TraceTrendItem


class StatsChartsData(BaseModel):
    """ECharts 图表数据 — 对齐 API.md §7.6

    嵌入 /api/admin/stats 响应的 charts 字段。
    数据来源：traces 表聚合（复用 get_trace_stats 逻辑）。
    """
    trend: list[TraceTrendItem] = Field(default_factory=list, description="问答量趋势（按天/小时）")
    latency: list[TraceLatencyItem] = Field(default_factory=list, description="响应时间分位数（P50/P95/P99）")
    tokens: list[TraceTokenItem] = Field(default_factory=list, description="Token 使用统计（Input/Output）")


class AdminStatsResponse(BaseModel):
    """GET /api/admin/stats 响应

    对齐 API.md §7.1：系统全局统计概览 + ECharts 图表数据（§7.6）
    """
    user_count: int = Field(description="注册用户总数")
    kb_count: int = Field(description="知识库总数（含 private+public，不含已删除）")
    doc_count: int = Field(description="文档总数（所有状态）")
    chunk_count: int = Field(description="分块总数（所有 KB 合计）")
    conversation_count: int = Field(description="会话总数")
    message_count: int = Field(description="消息总数")
    storage_bytes: int = Field(description="存储空间占用（字节）")
    charts: StatsChartsData = Field(default_factory=StatsChartsData, description="ECharts 图表数据")


class AdminKBItem(BaseModel):
    """GET /api/admin/knowledge-bases 响应中的单条知识库

    对齐 API.md §7.2：跨用户管理视图，含 owner 信息
    """
    id: int
    name: str
    description: str | None = None
    visibility: str = Field(description="private / public")
    user_id: int = Field(description="owner 用户 ID")
    username: str = Field(description="owner 用户名")
    status: str = Field(description="active / deleting")
    doc_count: int = 0
    chunk_count: int = 0
    created_at: datetime
    updated_at: datetime


class AdminKBListResponse(BaseModel):
    """GET /api/admin/knowledge-bases 响应

    对齐 API.md §7.2：分页知识库列表
    """
    total: int
    page: int
    page_size: int
    items: list[AdminKBItem]


class AdminDocItem(BaseModel):
    """GET /api/admin/documents 响应中的单条文档

    对齐 API.md §7.3：跨知识库视图，含 KB 名称和 owner 信息
    """
    id: int
    kb_id: int
    kb_name: str = Field(description="所属知识库名称")
    kb_visibility: str = Field(description="所属知识库可见性")
    owner_id: int = Field(description="知识库 owner 用户 ID")
    owner_username: str = Field(description="知识库 owner 用户名")
    filename: str
    file_type: str
    file_size: int | None = None
    status: str
    current_stage: str | None = None
    chunk_count: int = 0
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class AdminDocListResponse(BaseModel):
    """GET /api/admin/documents 响应

    对齐 API.md §7.3：分页文档列表
    """
    total: int
    page: int
    page_size: int
    items: list[AdminDocItem]
