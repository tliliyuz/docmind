"""UUID↔ID 转换工具测试 — 覆盖 uuid_helpers.py 全部公开函数

对齐 TEST_CASES.md §6.17.2 + §6.17.3：
- U16.10-U16.15: resolve_uuid_to_id / get_by_uuid 正常 + 不存在 + 无效格式
- U16.20-U16.24: ORM 模型 uuid 字段存在性 + 唯一性 + id 自增

附加覆盖：validate_uuid_format 纯函数 + _get_not_found_exception 模型映射
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import (
    ConversationNotFoundException,
    DocumentNotFoundException,
    KnowledgeBaseNotFoundException,
)
from app.core.uuid_helpers import (
    _get_not_found_exception,
    get_by_uuid,
    resolve_uuid_to_id,
    validate_uuid_format,
)
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase


# ==================== 辅助常量 ====================

VALID_UUID = "550e8400-e29b-41d4-a716-446655440000"
VALID_UUID_2 = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"  # UUID v1，用于格式对比


# ==================== validate_uuid_format 纯函数测试 ====================


class TestValidateUuidFormat:
    """validate_uuid_format — UUID v4 格式校验（纯函数，无 mock）"""

    def test_valid_uuid_v4(self):
        """合法 UUID v4 → True"""
        assert validate_uuid_format("550e8400-e29b-41d4-a716-446655440000") is True

    def test_valid_uuid_v4_uppercase(self):
        """大写 UUID v4 → True（regex IGNORECASE）"""
        assert validate_uuid_format("550E8400-E29B-41D4-A716-446655440000") is True

    def test_valid_uuid_v4_mixed_case(self):
        """混合大小写 → True"""
        assert validate_uuid_format("550e8400-E29B-41d4-a716-446655440000") is True

    def test_invalid_not_uuid(self):
        """非 UUID 字符串 'abc' → False"""
        assert validate_uuid_format("abc") is False

    def test_invalid_empty_string(self):
        """空字符串 → False"""
        assert validate_uuid_format("") is False

    def test_valid_uuid_v1(self):
        """UUID v1（MySQL UUID() 生成）→ True（对齐 uuid_helpers 支持 RFC 4122 v1/v3/v4/v5）"""
        assert validate_uuid_format("6ba7b810-9dad-11d1-80b4-00c04fd430c8") is True

    def test_invalid_no_hyphens(self):
        """无连字符的 32 位 hex → False"""
        assert validate_uuid_format("550e8400e29b41d4a716446655440000") is False

    def test_invalid_too_short(self):
        """过短字符串 → False"""
        assert validate_uuid_format("550e8400-e29b") is False

    def test_valid_non_rfc4122_variant(self):
        """variant 字段首字符为 'c'（RFC 4122 Microsoft 向后兼容变体）→ True"""
        assert validate_uuid_format("550e8400-e29b-41d4-c716-446655440000") is True

    def test_valid_edge_case_variant_a(self):
        """variant 字段首字符为 'a' → True"""
        assert validate_uuid_format("550e8400-e29b-41d4-a716-446655440000") is True

    def test_valid_edge_case_variant_b(self):
        """variant 字段首字符为 'b' → True"""
        assert validate_uuid_format("550e8400-e29b-41d4-b716-446655440000") is True


# ==================== _get_not_found_exception 映射测试 ====================


class TestGetNotFoundException:
    """_get_not_found_exception — 模型类 → 异常类映射"""

    def test_knowledge_base_maps_to_kb_exception(self):
        exc_cls = _get_not_found_exception(KnowledgeBase)
        assert exc_cls is KnowledgeBaseNotFoundException

    def test_document_maps_to_doc_exception(self):
        exc_cls = _get_not_found_exception(Document)
        assert exc_cls is DocumentNotFoundException

    def test_conversation_maps_to_conv_exception(self):
        exc_cls = _get_not_found_exception(Conversation)
        assert exc_cls is ConversationNotFoundException

    def test_unknown_model_defaults_to_kb_exception(self):
        """未知模型类默认返回 KnowledgeBaseNotFoundException"""
        exc_cls = _get_not_found_exception(str)
        assert exc_cls is KnowledgeBaseNotFoundException


# ==================== resolve_uuid_to_id 测试 ====================


class TestResolveUuidToId:
    """resolve_uuid_to_id — UUID 字符串 → integer ID 转换（Mock DB）"""

    @pytest.mark.asyncio
    async def test_normal_returns_integer_id(self):
        """U16.10: 有效 uuid + 存在记录 → 返回对应 integer id"""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 42
        mock_db.execute.return_value = mock_result

        result = await resolve_uuid_to_id(mock_db, KnowledgeBase, VALID_UUID)

        assert result == 42

    @pytest.mark.asyncio
    async def test_not_found_raises_kb_exception(self):
        """U16.11: 有效 uuid + 无匹配记录 → 抛出 KnowledgeBaseNotFoundException"""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(KnowledgeBaseNotFoundException):
            await resolve_uuid_to_id(mock_db, KnowledgeBase, VALID_UUID)

    @pytest.mark.asyncio
    async def test_invalid_uuid_raises_exception(self):
        """U16.12: 非法 uuid 字符串 'abc' → 抛出 NotFoundException"""
        mock_db = AsyncMock()

        with pytest.raises(KnowledgeBaseNotFoundException):
            await resolve_uuid_to_id(mock_db, KnowledgeBase, "abc")

        # DB 不应被调用
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_string_raises_exception(self):
        """空字符串 → 抛出 NotFoundException，不查 DB"""
        mock_db = AsyncMock()

        with pytest.raises(KnowledgeBaseNotFoundException):
            await resolve_uuid_to_id(mock_db, KnowledgeBase, "")

        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_document_model_uses_doc_exception(self):
        """Document 模型 → DocumentNotFoundException"""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(DocumentNotFoundException):
            await resolve_uuid_to_id(mock_db, Document, VALID_UUID)

    @pytest.mark.asyncio
    async def test_conversation_model_uses_conv_exception(self):
        """Conversation 模型 → ConversationNotFoundException"""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ConversationNotFoundException):
            await resolve_uuid_to_id(mock_db, Conversation, VALID_UUID)

    @pytest.mark.asyncio
    async def test_document_valid_uuid_returns_id(self):
        """Document 模型有效 uuid → 返回 integer id"""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 99
        mock_db.execute.return_value = mock_result

        result = await resolve_uuid_to_id(mock_db, Document, VALID_UUID)
        assert result == 99

    @pytest.mark.asyncio
    async def test_conversation_valid_uuid_returns_id(self):
        """Conversation 模型有效 uuid → 返回 integer id"""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 77
        mock_db.execute.return_value = mock_result

        result = await resolve_uuid_to_id(mock_db, Conversation, VALID_UUID)
        assert result == 77


# ==================== get_by_uuid 测试 ====================


class TestGetByUuid:
    """get_by_uuid — 通过 UUID 获取 ORM 模型实例（Mock DB）"""

    @pytest.mark.asyncio
    async def test_normal_returns_orm_instance(self):
        """U16.13: 有效 uuid → 返回 ORM 模型实例"""
        mock_db = AsyncMock()
        mock_instance = MagicMock()
        mock_instance.uuid = VALID_UUID
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_instance
        mock_db.execute.return_value = mock_result

        result = await get_by_uuid(mock_db, KnowledgeBase, VALID_UUID)

        assert result is mock_instance
        assert result.uuid == VALID_UUID

    @pytest.mark.asyncio
    async def test_not_found_raises_exception(self):
        """U16.14: 不存在的 uuid → 抛出 NotFoundException"""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(KnowledgeBaseNotFoundException):
            await get_by_uuid(mock_db, KnowledgeBase, VALID_UUID)

    @pytest.mark.asyncio
    async def test_invalid_uuid_raises_exception(self):
        """U16.15: 非法 uuid 字符串 → 抛出 NotFoundException"""
        mock_db = AsyncMock()

        with pytest.raises(KnowledgeBaseNotFoundException):
            await get_by_uuid(mock_db, KnowledgeBase, "not-a-uuid")

        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_document_model_returns_instance(self):
        """Document 模型有效 uuid → 返回 Document 实例"""
        mock_db = AsyncMock()
        mock_instance = MagicMock()
        mock_instance.uuid = VALID_UUID
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_instance
        mock_db.execute.return_value = mock_result

        result = await get_by_uuid(mock_db, Document, VALID_UUID)
        assert result is mock_instance

    @pytest.mark.asyncio
    async def test_conversation_not_found_uses_conv_exception(self):
        """Conversation 模型不存在 → ConversationNotFoundException"""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ConversationNotFoundException):
            await get_by_uuid(mock_db, Conversation, VALID_UUID)


# ==================== ORM 模型 uuid 字段测试 ====================


class TestModelUuidField:
    """ORM 模型 uuid 字段存在性与配置验证（U16.20-U16.24）"""

    def test_kb_has_uuid_column(self):
        """U16.20: KnowledgeBase 模型有 uuid 列"""
        col = KnowledgeBase.__table__.columns.get("uuid")
        assert col is not None
        assert str(col.type) == "VARCHAR(36)"
        assert col.unique is True
        assert col.nullable is False

    def test_document_has_uuid_column(self):
        """U16.21: Document 模型有 uuid 列"""
        col = Document.__table__.columns.get("uuid")
        assert col is not None
        assert str(col.type) == "VARCHAR(36)"
        assert col.unique is True
        assert col.nullable is False

    def test_conversation_has_uuid_column(self):
        """U16.22: Conversation 模型有 uuid 列"""
        col = Conversation.__table__.columns.get("uuid")
        assert col is not None
        assert str(col.type) == "VARCHAR(36)"
        assert col.unique is True
        assert col.nullable is False

    def test_uuid_unique_constraint(self):
        """U16.23: uuid 列有唯一约束（UNIQUE INDEX idx_uuid）"""
        for model in [KnowledgeBase, Document, Conversation]:
            col = model.__table__.columns.get("uuid")
            assert col.unique is True, f"{model.__name__}.uuid 应有 unique=True"

    def test_id_still_autoincrement(self):
        """U16.24: id 字段仍为自增主键"""
        for model in [KnowledgeBase, Document, Conversation]:
            col = model.__table__.columns.get("id")
            assert col.autoincrement is True
            assert col.primary_key is True

    def test_conversation_has_original_kb_uuid(self):
        """Conversation 模型有 original_kb_uuid 列（孤儿会话审计）"""
        col = Conversation.__table__.columns.get("original_kb_uuid")
        assert col is not None
        assert str(col.type) == "VARCHAR(36)"
        assert col.nullable is True

    def test_document_has_kb_uuid_property(self):
        """Document 模型有 kb_uuid 计算属性"""
        assert hasattr(Document, "kb_uuid")
        # 验证是 property 而非普通属性
        assert isinstance(Document.__dict__.get("kb_uuid"), property)

    def test_conversation_has_kb_uuid_property(self):
        """Conversation 模型有 kb_uuid 计算属性"""
        assert hasattr(Conversation, "kb_uuid")
        assert isinstance(Conversation.__dict__.get("kb_uuid"), property)
