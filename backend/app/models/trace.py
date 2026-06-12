"""链路追踪表 — 对齐 DATABASE.md §2.8 / ARCHITECTURE.md §5.1.8

设计原则：Trace 不承担审计职责，仅承担性能观测。
完整对话内容通过 conversation_id JOIN 查询获取，避免重复存储。
"""

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._types import UTCDateTime


class Trace(Base):
    __tablename__ = "traces"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True,
        comment="UUID 追踪 ID",
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        comment="用户 ID",
    )
    conversation_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True,
        comment="会话 ID（可为空）",
    )
    kb_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True,
        comment="知识库 ID",
    )
    question: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="用户问题",
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False,
        comment="状态：success / error / partial",
    )
    intent_type: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment="顶层字段：KNOWLEDGE / CASUAL / META",
    )
    intent_method: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment="顶层字段：regex / llm_flash / llm_pro",
    )
    response_mode: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment="顶层字段：RAG / DIRECT_LLM / META / CASUAL / FALLBACK",
    )
    total_duration_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="总耗时（毫秒）",
    )
    intent: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="意图识别阶段详情",
    )
    rewrite: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="问题重写阶段详情",
    )
    retrieve: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="检索阶段详情（细粒度拆分：vector/bm25/fusion/match_sentence）",
    )
    rerank: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="Rerank 阶段详情",
    )
    generate: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="LLM 生成阶段详情（不存 output）",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="错误信息（status=error 时）",
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.current_timestamp(),
        comment="创建时间（UTC）",
    )

    __table_args__ = (
        Index("idx_created_at", "created_at"),
        Index("idx_created_status", "created_at", "status"),
        Index("idx_created_intent", "created_at", "intent_type"),
        Index("idx_created_response", "created_at", "response_mode"),
        Index("idx_user_created", "user_id", "created_at"),
    )
