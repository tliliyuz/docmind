"""用户表"""

from datetime import datetime
from sqlalchemy import BigInteger, Enum, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._types import UTCDateTime


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(
        Enum("user", "admin", name="user_role"),
        default="user",
        server_default=text("'user'"),
    )
    status: Mapped[str] = mapped_column(
        Enum("active", "disabled", name="user_status"),
        default="active",
        server_default=text("'active'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    knowledge_bases = relationship("KnowledgeBase", back_populates="owner")
    conversations = relationship(
        "Conversation", back_populates="user", passive_deletes=True
    )
