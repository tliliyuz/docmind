"""文档表"""

from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import DocumentStatus


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("idx_kb_filename", "kb_id", "filename"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kb_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="所属知识库"
    )
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    file_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="pdf/docx/md/txt"
    )
    file_path: Mapped[str | None] = mapped_column(
        String(512), comment="文件存储路径：uploads/{kb_id}/{doc_id}/{uuid}_{sanitized_filename}"
    )
    file_size: Mapped[int | None] = mapped_column(BigInteger, comment="bytes")
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status"),
        default=DocumentStatus.UPLOADED,
        server_default=text("'uploaded'"),
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    error_msg: Mapped[str | None] = mapped_column(Text)
    current_stage: Mapped[str | None] = mapped_column(
        String(32), comment="当前处理阶段，用于断点恢复"
    )
    last_success_batch: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), comment="最后成功的批次号，用于批次级 checkpoint"
    )
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
