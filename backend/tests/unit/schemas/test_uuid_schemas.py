"""Pydantic Schema UUID 字段测试 — 验证响应/请求模型正确使用 UUID

对齐 TEST_CASES.md §6.17.4：
- U16.30: KnowledgeBaseResponse 含 uuid 不含 id
- U16.31: DocumentResponse 含 uuid + kb_uuid 不含 id/kb_id
- U16.32: ConversationResponse 含 uuid 不含 id
- U16.33: ChatRequest kb_id 为 UUID 字符串
- U16.34: ChatRequest kb_id 缺失 → ValidationError
- U16.35: ChatRequest conversation_id 为 UUID 字符串
- U16.36: TraceListItem 不含自增 id（已有 trace_id）
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.chat import ChatRequest, SelectableKBItem
from app.schemas.conversation import ConversationCreate, ConversationResponse
from app.schemas.document import (
    DocumentDeleteResponse,
    DocumentReprocessResponse,
    DocumentResponse,
    DocumentUploadResponse,
)
from app.schemas.knowledge_base import KnowledgeBaseResponse
from app.schemas.trace import TraceDetailResponse, TraceListItem


# ==================== 辅助常量 ====================

VALID_UUID = "550e8400-e29b-41d4-a716-446655440000"
VALID_UUID_2 = "6ba7b811-9dad-41d1-80b4-00c04fd430c8"
NOW = datetime.now(timezone.utc)


# ==================== KnowledgeBaseResponse ====================


class TestKnowledgeBaseResponseSchema:
    """U16.30: KnowledgeBaseResponse — 含 uuid 不含 id"""

    def test_contains_uuid_field(self):
        """序列化输出含 uuid 字段"""
        resp = KnowledgeBaseResponse(
            uuid=VALID_UUID, name="测试KB", description="desc",
            user_id=1, visibility="private", status="active",
            doc_count=5, chunk_count=100, created_at=NOW,
        )
        data = resp.model_dump()
        assert data["uuid"] == VALID_UUID

    def test_does_not_contain_id_field(self):
        """序列化输出不含 id 字段"""
        resp = KnowledgeBaseResponse(
            uuid=VALID_UUID, name="测试KB", description=None,
            user_id=1, visibility="private", status="active",
            doc_count=0, chunk_count=0, created_at=NOW,
        )
        data = resp.model_dump()
        assert "id" not in data


# ==================== DocumentResponse ====================


class TestDocumentResponseSchema:
    """U16.31: DocumentResponse — 含 uuid + kb_uuid 不含 id/kb_id"""

    def test_contains_uuid_and_kb_uuid(self):
        """序列化输出含 uuid + kb_uuid"""
        resp = DocumentResponse(
            uuid=VALID_UUID, kb_uuid=VALID_UUID_2,
            filename="test.pdf", file_type="pdf",
            status="completed", created_at=NOW,
        )
        data = resp.model_dump()
        assert data["uuid"] == VALID_UUID
        assert data["kb_uuid"] == VALID_UUID_2

    def test_does_not_contain_id_or_kb_id(self):
        """序列化输出不含 id / kb_id"""
        resp = DocumentResponse(
            uuid=VALID_UUID, kb_uuid=VALID_UUID_2,
            filename="test.pdf", file_type="pdf",
            status="uploaded", created_at=NOW,
        )
        data = resp.model_dump()
        assert "id" not in data
        assert "kb_id" not in data

    def test_upload_response_has_uuid(self):
        """DocumentUploadResponse 含 uuid + kb_uuid"""
        resp = DocumentUploadResponse(
            uuid=VALID_UUID, kb_uuid=VALID_UUID_2,
            filename="test.pdf", file_type="pdf",
            status="uploaded",
        )
        data = resp.model_dump()
        assert "uuid" in data
        assert "kb_uuid" in data
        assert "id" not in data

    def test_delete_response_has_doc_uuid(self):
        """DocumentDeleteResponse 含 doc_uuid"""
        resp = DocumentDeleteResponse(
            doc_uuid=VALID_UUID, status="deleting",
        )
        data = resp.model_dump()
        assert data["doc_uuid"] == VALID_UUID

    def test_reprocess_response_has_doc_uuid(self):
        """DocumentReprocessResponse 含 doc_uuid"""
        resp = DocumentReprocessResponse(
            doc_uuid=VALID_UUID, status="uploaded",
        )
        data = resp.model_dump()
        assert data["doc_uuid"] == VALID_UUID


# ==================== ConversationResponse ====================


class TestConversationResponseSchema:
    """U16.32: ConversationResponse — 含 uuid 不含 id"""

    def test_contains_uuid_field(self):
        """序列化输出含 uuid"""
        resp = ConversationResponse(
            uuid=VALID_UUID, user_id=1, title="新对话",
            message_count=0, created_at=NOW, updated_at=NOW,
        )
        data = resp.model_dump()
        assert data["uuid"] == VALID_UUID

    def test_does_not_contain_id_field(self):
        """序列化输出不含 id"""
        resp = ConversationResponse(
            uuid=VALID_UUID, user_id=1, title="新对话",
            message_count=0, created_at=NOW, updated_at=NOW,
        )
        data = resp.model_dump()
        assert "id" not in data

    def test_contains_kb_uuid(self):
        """含 kb_uuid 字段"""
        resp = ConversationResponse(
            uuid=VALID_UUID, user_id=1, kb_uuid=VALID_UUID_2,
            title="新对话", message_count=0, created_at=NOW, updated_at=NOW,
        )
        data = resp.model_dump()
        assert data["kb_uuid"] == VALID_UUID_2

    def test_contains_original_kb_uuid(self):
        """含 original_kb_uuid 字段（孤儿会话审计）"""
        resp = ConversationResponse(
            uuid=VALID_UUID, user_id=1,
            kb_uuid=None, kb_status="deleted", kb_name="已删除知识库",
            original_kb_uuid=VALID_UUID_2, original_kb_name="旧KB",
            title="孤儿会话", message_count=2, created_at=NOW, updated_at=NOW,
        )
        data = resp.model_dump()
        assert data["original_kb_uuid"] == VALID_UUID_2

    def test_conversation_create_has_kb_uuid(self):
        """ConversationCreate 请求含 kb_uuid"""
        req = ConversationCreate(kb_uuid=VALID_UUID)
        assert req.kb_uuid == VALID_UUID

    def test_conversation_create_kb_uuid_required(self):
        """ConversationCreate 不传 kb_uuid → ValidationError"""
        with pytest.raises(ValidationError):
            ConversationCreate(title="测试")


# ==================== ChatRequest ====================


class TestChatRequestSchema:
    """U16.33-U16.35: ChatRequest — kb_id 为 UUID 字符串"""

    def test_kb_id_accepts_uuid_string(self):
        """U16.33: kb_id='550e8400-...' → 校验通过"""
        req = ChatRequest(kb_id=VALID_UUID, question="测试问题")
        assert req.kb_id == VALID_UUID

    def test_kb_id_missing_raises_validation_error(self):
        """U16.34: 不传 kb_id → ValidationError"""
        with pytest.raises(ValidationError):
            ChatRequest(question="测试问题")

    def test_conversation_id_accepts_uuid_string(self):
        """U16.35: conversation_id='550e8400-...' → 校验通过，类型为字符串"""
        req = ChatRequest(
            kb_id=VALID_UUID,
            conversation_id=VALID_UUID_2,
            question="测试问题",
        )
        assert req.conversation_id == VALID_UUID_2

    def test_conversation_id_none_by_default(self):
        """conversation_id 默认为 None"""
        req = ChatRequest(kb_id=VALID_UUID, question="测试问题")
        assert req.conversation_id is None


# ==================== SelectableKBItem ====================


class TestSelectableKBItemSchema:
    """SelectableKBItem — 含 uuid 不含 id"""

    def test_contains_uuid_not_id(self):
        item = SelectableKBItem(uuid=VALID_UUID, name="测试KB")
        data = item.model_dump()
        assert data["uuid"] == VALID_UUID
        assert "id" not in data


# ==================== Trace 响应 ====================


class TestTraceResponseSchema:
    """U16.36: TraceListItem / TraceDetailResponse — 不含自增 id"""

    def test_trace_list_item_no_id_field(self):
        """TraceListItem 不含自增 id 字段"""
        item = TraceListItem(
            trace_id="abc-123", user_id=1, username="testuser",
            question="测试", status="success", created_at=NOW,
        )
        data = item.model_dump()
        assert "id" not in data
        assert data["trace_id"] == "abc-123"

    def test_trace_detail_no_id_field(self):
        """TraceDetailResponse 不含自增 id 字段"""
        detail = TraceDetailResponse(
            trace_id="abc-123", user_id=1, username="testuser",
            question="测试", status="success", created_at=NOW,
        )
        data = detail.model_dump()
        assert "id" not in data
        assert data["trace_id"] == "abc-123"

    def test_trace_detail_has_conversation_uuid(self):
        """TraceDetailResponse 含 conversation_uuid"""
        detail = TraceDetailResponse(
            trace_id="abc-123", user_id=1, username="testuser",
            conversation_uuid=VALID_UUID,
            question="测试", status="success", created_at=NOW,
        )
        data = detail.model_dump()
        assert data["conversation_uuid"] == VALID_UUID
