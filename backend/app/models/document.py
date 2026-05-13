"""文档表"""

from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kb_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="所属知识库"
    )
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    file_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="pdf/docx/md/txt"
    )
    file_size: Mapped[int | None] = mapped_column(BigInteger, comment="bytes")
    status: Mapped[str] = mapped_column(
        Enum(
            "uploading",
            "parsing",
            "chunking",
            "embedding",
            "indexing",
            "completed",
            "failed",
            name="document_status",
        ),
        default="uploading",
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    error_msg: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document")
