"""知识库表"""

from datetime import datetime
from sqlalchemy import BigInteger, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._types import UTCDateTime


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="idx_user_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(
        String(36), nullable=False, unique=True,
        server_default=text("(UUID())"),
        comment="外部暴露标识符（UUID），API/URL 使用"
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    visibility: Mapped[str] = mapped_column(
        Enum("private", "public", name="kb_visibility"),
        default="private",
        server_default=text("'private'"),
        comment="private（仅owner可见）/ public（所有用户可检索）"
    )
    status: Mapped[str] = mapped_column(
        Enum("active", "deleting", name="kb_status"),
        default="active",
        server_default=text("'active'"),
        comment="active（正常）/ deleting（异步清理中，随后物理删除行）"
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    doc_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    owner = relationship("User", back_populates="knowledge_bases")
    documents = relationship("Document", back_populates="knowledge_base", passive_deletes=True)
    chunks = relationship("Chunk", back_populates="knowledge_base", passive_deletes=True)
    conversations = relationship("Conversation", back_populates="knowledge_base")
