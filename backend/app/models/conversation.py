"""会话表"""

from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    kb_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("knowledge_bases.id", ondelete="SET NULL"),
        comment="关联的知识库"
    )
    title: Mapped[str] = mapped_column(
        String(256), default="新对话", server_default=text("'新对话'")
    )
    message_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    user = relationship("User", back_populates="conversations")
    knowledge_base = relationship("KnowledgeBase", back_populates="conversations")
    messages = relationship(
        "Message", back_populates="conversation", passive_deletes=True
    )

    __table_args__ = (
        Index("idx_conversations_user_updated", "user_id", "updated_at"),
    )
