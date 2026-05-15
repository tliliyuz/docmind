"""共享枚举 — DocumentStatus 统一管理，前后端共用定义来源"""
from enum import Enum


class DocumentStatus(str, Enum):
    """文档入库状态机（对齐 API.md §4.0）"""
    UPLOADED = "uploaded"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    VECTOR_STORING = "vector_storing"
    COMPLETED = "completed"
    SUCCESS_WITH_WARNINGS = "success_with_warnings"
    PARTIAL_FAILED = "partial_failed"
    FAILED = "failed"
    DELETING = "deleting"


TERMINAL_STATUSES: frozenset[str] = frozenset({
    DocumentStatus.COMPLETED,
    DocumentStatus.SUCCESS_WITH_WARNINGS,
    DocumentStatus.PARTIAL_FAILED,
    DocumentStatus.FAILED,
})


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATUSES
