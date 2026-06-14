"""UUID 解析工具 — API 边界 UUID↔ID 转换

对齐 ARCHITECTURE.md §8.11：外部资源 UUID 化。
service 层内部继续用 integer id，仅在 API 边界做 UUID→ID 转换。
"""

import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConversationNotFoundException,
    DocumentNotFoundException,
    KnowledgeBaseNotFoundException,
)

# UUID 格式校验（RFC 4122，支持 v1/v3/v4/v5）
# MySQL UUID() 生成 v1，不能用仅 v4 的正则

_UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE,
)


def validate_uuid_format(uuid_str: str) -> bool:
    """校验 UUID 字符串格式是否合法（RFC 4122，支持 v1/v3/v4/v5）"""
    if not _UUID_PATTERN.match(uuid_str):
        return False
    try:
        UUID(uuid_str)
        return True
    except (ValueError, AttributeError):
        return False


def _get_not_found_exception(model_class):
    """根据模型类选择对应的 NotFoundException"""
    from app.models.knowledge_base import KnowledgeBase
    from app.models.document import Document
    from app.models.conversation import Conversation

    _EXCEPTION_MAP = {
        KnowledgeBase: KnowledgeBaseNotFoundException,
        Document: DocumentNotFoundException,
        Conversation: ConversationNotFoundException,
    }
    return _EXCEPTION_MAP.get(model_class, KnowledgeBaseNotFoundException)


async def resolve_uuid_to_id(
    db: AsyncSession,
    model_class,
    uuid_str: str,
) -> int:
    """将 UUID 字符串解析为 integer ID。

    Args:
        db: 数据库会话
        model_class: ORM 模型类（KnowledgeBase / Document / Conversation）
        uuid_str: UUID 字符串

    Returns:
        对应的 integer primary key

    Raises:
        对应的 NotFoundException: UUID 格式无效或记录不存在
    """
    if not uuid_str or not validate_uuid_format(uuid_str):
        exc_cls = _get_not_found_exception(model_class)
        raise exc_cls(uuid_str)

    result = await db.execute(
        select(model_class.id).where(model_class.uuid == uuid_str)
    )
    row = result.scalar_one_or_none()
    if row is None:
        exc_cls = _get_not_found_exception(model_class)
        raise exc_cls(uuid_str)
    return row


async def get_by_uuid(
    db: AsyncSession,
    model_class,
    uuid_str: str,
):
    """通过 UUID 获取 ORM 模型实例。

    Args:
        db: 数据库会话
        model_class: ORM 模型类
        uuid_str: UUID 字符串

    Returns:
        ORM 模型实例

    Raises:
        对应的 NotFoundException: UUID 格式无效或记录不存在
    """
    if not uuid_str or not validate_uuid_format(uuid_str):
        exc_cls = _get_not_found_exception(model_class)
        raise exc_cls(uuid_str)

    result = await db.execute(
        select(model_class).where(model_class.uuid == uuid_str)
    )
    instance = result.scalar_one_or_none()
    if instance is None:
        exc_cls = _get_not_found_exception(model_class)
        raise exc_cls(uuid_str)
    return instance
