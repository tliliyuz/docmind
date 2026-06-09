"""刷新令牌表 — 对齐 DATABASE.md §2.7 / ARCHITECTURE.md §9.2"""

from datetime import datetime
from sqlalchemy import BigInteger, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._types import UTCDateTime


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(
        String(256), nullable=False,
        comment="refresh_token 的 SHA-256 哈希，不存明文",
    )
    expires_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False,
        comment="过期时间（创建后 7 天，UTC）",
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, nullable=True, server_default=text("NULL"),
        comment="吊销时间（NULL=有效，非NULL=已吊销，UTC）",
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.current_timestamp()
    )

    __table_args__ = (
        Index("idx_user_id", "user_id"),
        Index("idx_token_hash", "token_hash"),
        Index("idx_user_active", "user_id", "revoked_at", "expires_at"),
    )
