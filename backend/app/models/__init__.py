"""ORM 模型 — 导入所有模型确保 Alembic 能识别"""

from app.core.database import Base

from .enums import DocumentStatus, TERMINAL_STATUSES, is_terminal  # noqa: F401
from .user import User
from .knowledge_base import KnowledgeBase
from .document import Document
from .chunk import Chunk
from .conversation import Conversation
from .message import Message

__all__ = [
    "Base",
    "DocumentStatus",
    "TERMINAL_STATUSES",
    "is_terminal",
    "User",
    "KnowledgeBase",
    "Document",
    "Chunk",
    "Conversation",
    "Message",
]
