"""分块表 — 存储分块文本和 ChromaDB 引用"""

from datetime import datetime
from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._types import UTCDateTime


class Chunk(Base):
    __tablename__ = "chunks"
    # 复合索引：BM25 评分后按 (doc_id, chunk_index) 批量取 chunk 原文（tuple_.in_()），
    # 单列 idx_doc_id 在该查询下退化为按 doc_id 过滤 + chunk_index 回表，复合索引可走覆盖定位
    __table_args__ = (
        Index("idx_chunks_doc_id_chunk_index", "doc_id", "chunk_index"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    doc_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    kb_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    chroma_id: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="ChromaDB 中的 chunk id"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="在原文档中的顺序"
    )
    token_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSON, comment="页码、段落标题等"
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.current_timestamp()
    )

    document = relationship("Document", back_populates="chunks")
    knowledge_base = relationship("KnowledgeBase", back_populates="chunks")
