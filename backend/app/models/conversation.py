"""会话表"""

from datetime import datetime
from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._types import UTCDateTime


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
    original_kb_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True,
        comment="KB 删除前的原始 kb_id，用于孤儿会话检测"
    )
    original_kb_name: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="KB 删除前的原始名称，用于孤儿会话 Banner 展示"
    )
    title: Mapped[str] = mapped_column(
        String(256), default="新对话", server_default=text("'新对话'")
    )
    message_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        comment="会话元数据更新时间（标题/归档/pin 等）",
    )
    last_message_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime,
        nullable=True,
        comment="最后一次产生消息的时间，用于列表排序。仅 send_message/assistant_reply 更新",
    )

    user = relationship("User", back_populates="conversations")
    knowledge_base = relationship("KnowledgeBase", back_populates="conversations")
    messages = relationship(
        "Message", back_populates="conversation", passive_deletes=True
    )

    __table_args__ = (
        Index("idx_conversations_user_updated", "user_id", "updated_at"),
        Index("idx_conversations_user_last_msg", "user_id", "last_message_at"),
    )
