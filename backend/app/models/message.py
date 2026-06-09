"""消息表"""

from datetime import datetime
from sqlalchemy import BigInteger, Enum, ForeignKey, Integer, JSON, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._types import UTCDateTime


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(
        Enum("user", "assistant", "system", name="message_role"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    thinking_content: Mapped[str | None] = mapped_column(Text, comment="深度思考内容")
    token_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    feedback: Mapped[str | None] = mapped_column(Enum("like", "dislike", name="message_feedback"))
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSON, nullable=True, server_default=text("NULL"),
        comment="扩展元数据：未来 Tool Call / Web Search / Agent 等场景的非结构化数据"
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.current_timestamp()
    )

    conversation = relationship("Conversation", back_populates="messages")
