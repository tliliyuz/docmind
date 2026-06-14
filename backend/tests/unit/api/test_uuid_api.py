"""API 接口 UUID 路径参数测试 — 验证所有端点正确使用 UUID

对齐 TEST_CASES.md §6.17.5（A10.1-A10.21）：
- KB 端点：GET/PUT/DELETE /{uuid} + 权限校验不变
- Document 端点：GET/POST/DELETE /{kb_uuid}/documents/{doc_uuid}
- Conversation 端点：GET/PUT/DELETE /{conv_uuid}
- Chat 端点：POST /api/chat kb_id=UUID / conversation_id=UUID
- Selectable 端点：GET /selectable 返回 uuid 不含 id
- Trace 端点：GET /admin/traces 不含自增 id
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.responses import StreamingResponse

from app.core.exceptions import (
    KnowledgeBaseNotFoundException,
    PermissionDeniedException,
)
from app.schemas.conversation import ConversationResponse
from app.schemas.document import (
    DocumentDeleteResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadResponse,
)
from app.schemas.knowledge_base import (
    KnowledgeBaseDeleteResponse,
    KnowledgeBaseResponse,
)
from app.schemas.trace import TraceDetailResponse, TraceListItem, TraceListResponse


# ==================== 辅助常量 ====================

VALID_KB_UUID = "550e8400-e29b-41d4-a716-446655440000"
VALID_DOC_UUID = "6ba7b811-9dad-41d4-80b4-00c04fd430c8"
VALID_CONV_UUID = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
INVALID_UUID = "not-a-uuid"
NOW = datetime.now(timezone.utc)


# ==================== 辅助函数 ====================


def _make_kb_response(uuid=VALID_KB_UUID, name="测试KB", user_id=1,
                      visibility="private", status="active"):
    return KnowledgeBaseResponse(
        uuid=uuid, name=name, description=None, user_id=user_id,
        visibility=visibility, status=status, doc_count=0, chunk_count=0,
        created_at=NOW, updated_at=NOW,
    )


def _make_doc_response(uuid=VALID_DOC_UUID, kb_uuid=VALID_KB_UUID, filename="test.pdf"):
    return DocumentResponse(
        uuid=uuid, kb_uuid=kb_uuid, filename=filename, file_type="pdf",
        status="completed", chunk_count=10, created_at=NOW, updated_at=NOW,
    )


def _make_conv_response(uuid=VALID_CONV_UUID, user_id=1, kb_uuid=VALID_KB_UUID, title="新对话"):
    return ConversationResponse(
        uuid=uuid, user_id=user_id, kb_uuid=kb_uuid,
        title=title, message_count=0,
        created_at=NOW, updated_at=NOW, last_message_at=NOW,
    )


def _make_doc_list(items=None):
    if items is None:
        items = [_make_doc_response()]
    return DocumentListResponse(total=len(items), page=1, page_size=20, items=items)


# ==================== KB UUID API 测试 ====================


class TestKBUuidAPI:
    """KB 端点 UUID 路径参数测试"""

    @pytest.mark.asyncio
    async def test_get_kb_by_uuid(self, async_client, auth_headers):
        """A10.1: GET /{uuid} 有效 uuid → 200 + 响应含 uuid 不含 id"""
        with patch("app.api.knowledge_base.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.knowledge_base.get_kb", new_callable=AsyncMock) as mock_get:
            mock_resolve.return_value = 1
            mock_get.return_value = _make_kb_response()

            response = await async_client.get(
                f"/api/knowledge-bases/{VALID_KB_UUID}",
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["uuid"] == VALID_KB_UUID
        assert "id" not in body["data"]

    @pytest.mark.asyncio
    async def test_get_kb_invalid_uuid(self, async_client, auth_headers):
        """A10.2: GET /{uuid} 无效 uuid 'invalid' → 404"""
        response = await async_client.get(
            "/api/knowledge-bases/invalid",
            headers=auth_headers,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_kb_nonexistent_uuid(self, async_client, auth_headers):
        """A10.3: GET /{uuid} 合法格式但不存在 → 404, E1001"""
        with patch("app.api.knowledge_base.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve:
            mock_resolve.side_effect = KnowledgeBaseNotFoundException(VALID_KB_UUID)

            response = await async_client.get(
                f"/api/knowledge-bases/{VALID_KB_UUID}",
                headers=auth_headers,
            )

        assert response.status_code == 404
        body = response.json()
        assert body["code"] == "E1001"

    @pytest.mark.asyncio
    async def test_update_kb_by_uuid(self, async_client, auth_headers):
        """A10.4: PUT /{uuid} 有效 uuid → 200"""
        with patch("app.api.knowledge_base.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.knowledge_base.update_kb", new_callable=AsyncMock) as mock_update:
            mock_resolve.return_value = 1
            mock_update.return_value = _make_response = _make_kb_response(name="更新后KB")

            response = await async_client.put(
                f"/api/knowledge-bases/{VALID_KB_UUID}",
                json={"name": "更新后KB"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["uuid"] == VALID_KB_UUID

    @pytest.mark.asyncio
    async def test_delete_kb_by_uuid(self, async_client, auth_headers):
        """A10.5: DELETE /{uuid} 有效 uuid → 202"""
        with patch("app.api.knowledge_base.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.knowledge_base.delete_kb", new_callable=AsyncMock) as mock_delete:
            mock_resolve.return_value = 1
            mock_delete.return_value = KnowledgeBaseDeleteResponse(
                kb_uuid=VALID_KB_UUID, status="deleting",
            )

            response = await async_client.delete(
                f"/api/knowledge-bases/{VALID_KB_UUID}",
                headers=auth_headers,
            )

        assert response.status_code == 202
        body = response.json()
        assert body["data"]["kb_uuid"] == VALID_KB_UUID

    @pytest.mark.asyncio
    async def test_private_kb_non_owner_denied(self, async_client, other_user_auth_headers):
        """A10.20: GET /{uuid} private KB 非 owner → 403, E5005"""
        with patch("app.api.knowledge_base.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.knowledge_base.get_kb", new_callable=AsyncMock) as mock_get:
            mock_resolve.return_value = 1
            mock_get.side_effect = PermissionDeniedException()

            response = await async_client.get(
                f"/api/knowledge-bases/{VALID_KB_UUID}",
                headers=other_user_auth_headers,
            )

        assert response.status_code == 403
        body = response.json()
        assert body["code"] == "E5005"

    @pytest.mark.asyncio
    async def test_admin_can_access_any_kb(self, async_client, admin_auth_headers):
        """A10.21: GET /{uuid} admin 访问他人 KB → 200"""
        with patch("app.api.knowledge_base.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.knowledge_base.get_kb", new_callable=AsyncMock) as mock_get:
            mock_resolve.return_value = 1
            mock_get.return_value = _make_kb_response(user_id=999, visibility="private")

            response = await async_client.get(
                f"/api/knowledge-bases/{VALID_KB_UUID}",
                headers=admin_auth_headers,
            )

        assert response.status_code == 200


# ==================== Document UUID API 测试 ====================


class TestDocumentUuidAPI:
    """Document 端点 UUID 路径参数测试"""

    @pytest.mark.asyncio
    async def test_list_docs_by_kb_uuid(self, async_client, auth_headers):
        """A10.6: GET /{kb_uuid}/documents 有效 kb_uuid → 200"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.document.list_documents", new_callable=AsyncMock) as mock_list:
            mock_resolve.return_value = 1
            mock_list.return_value = _make_doc_list()

            response = await async_client.get(
                f"/api/knowledge-bases/{VALID_KB_UUID}/documents",
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["items"][0]["uuid"] == VALID_DOC_UUID
        assert "id" not in body["data"]["items"][0]

    @pytest.mark.asyncio
    async def test_get_doc_by_uuid(self, async_client, auth_headers):
        """A10.7: GET /{kb_uuid}/documents/{doc_uuid} 有效 → 200 + 响应含 uuid"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.document.get_document", new_callable=AsyncMock) as mock_get:
            mock_resolve.side_effect = [1, 10]  # kb_id, doc_id
            mock_get.return_value = _make_doc_response()

            response = await async_client.get(
                f"/api/knowledge-bases/{VALID_KB_UUID}/documents/{VALID_DOC_UUID}",
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["uuid"] == VALID_DOC_UUID
        assert body["data"]["kb_uuid"] == VALID_KB_UUID

    @pytest.mark.asyncio
    async def test_delete_doc_by_uuid(self, async_client, auth_headers):
        """A10.9: DELETE /{kb_uuid}/documents/{doc_uuid} → 202"""
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.document.delete_document", new_callable=AsyncMock) as mock_delete:
            mock_resolve.side_effect = [1, 10]
            mock_delete.return_value = DocumentDeleteResponse(
                doc_uuid=VALID_DOC_UUID, status="deleting",
            )

            response = await async_client.delete(
                f"/api/knowledge-bases/{VALID_KB_UUID}/documents/{VALID_DOC_UUID}",
                headers=auth_headers,
            )

        assert response.status_code == 202
        body = response.json()
        assert body["data"]["doc_uuid"] == VALID_DOC_UUID

    @pytest.mark.asyncio
    async def test_upload_doc_with_kb_uuid(self, async_client, auth_headers):
        """A10.8: POST /{kb_uuid}/documents multipart → 201 + 响应含 uuid"""
        mock_upload_response = DocumentUploadResponse(
            uuid=VALID_DOC_UUID,
            kb_uuid=VALID_KB_UUID,
            filename="test.pdf",
            file_type="pdf",
            file_size=1024,
            status="uploaded",
        )
        with patch("app.api.document.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.document.upload_document", new_callable=AsyncMock) as mock_upload:
            mock_resolve.return_value = 1
            mock_upload.return_value = mock_upload_response

            # httpx multipart 上传
            response = await async_client.post(
                f"/api/knowledge-bases/{VALID_KB_UUID}/documents",
                files={"file": ("test.pdf", b"fake pdf content", "application/pdf")},
                data={"force": "false"},
                headers=auth_headers,
            )

        assert response.status_code == 201
        body = response.json()
        assert body["data"]["uuid"] == VALID_DOC_UUID
        assert body["data"]["kb_uuid"] == VALID_KB_UUID
        assert body["data"]["filename"] == "test.pdf"
        assert body["data"]["status"] == "uploaded"
        assert "id" not in body["data"]


# ==================== Conversation UUID API 测试 ====================


class TestConversationUuidAPI:
    """Conversation 端点 UUID 路径参数测试"""

    @pytest.mark.asyncio
    async def test_get_conv_by_uuid(self, async_client, auth_headers):
        """A10.10: GET /{conv_uuid} 有效 → 200 + 响应含 uuid"""
        with patch("app.api.conversation.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.conversation.get_conversation_detail", new_callable=AsyncMock) as mock_get:
            mock_resolve.return_value = 1
            mock_get.return_value = _make_conv_response()

            response = await async_client.get(
                f"/api/conversations/{VALID_CONV_UUID}",
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["uuid"] == VALID_CONV_UUID
        assert "id" not in body["data"]

    @pytest.mark.asyncio
    async def test_rename_conv_by_uuid(self, async_client, auth_headers):
        """A10.11: PUT /{conv_uuid} 有效 → 200"""
        with patch("app.api.conversation.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.conversation.rename_conversation", new_callable=AsyncMock) as mock_rename:
            mock_resolve.return_value = 1
            mock_rename.return_value = _make_conv_response(title="新标题")

            response = await async_client.put(
                f"/api/conversations/{VALID_CONV_UUID}",
                json={"title": "新标题"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["title"] == "新标题"

    @pytest.mark.asyncio
    async def test_delete_conv_by_uuid(self, async_client, auth_headers):
        """A10.12: DELETE /{conv_uuid} 有效 → 200"""
        with patch("app.api.conversation.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.conversation.delete_conversation", new_callable=AsyncMock) as mock_delete:
            mock_resolve.return_value = 1
            mock_delete.return_value = None

            response = await async_client.delete(
                f"/api/conversations/{VALID_CONV_UUID}",
                headers=auth_headers,
            )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_conv_invalid_uuid(self, async_client, auth_headers):
        """GET /{conv_uuid} 无效 uuid → 404"""
        response = await async_client.get(
            "/api/conversations/invalid-uuid",
            headers=auth_headers,
        )
        assert response.status_code == 404


# ==================== Chat UUID API 测试 ====================


class TestChatUuidAPI:
    """Chat 端点 UUID 参数测试"""

    @staticmethod
    async def _sse_event_gen(events):
        """构造 SSE 事件生成器"""
        for event in events:
            yield event

    @pytest.mark.asyncio
    async def test_chat_with_kb_uuid(self, async_client, auth_headers):
        """A10.13: POST /api/chat kb_id=UUID → SSE 流正常"""
        sse_events = [
            'event: meta\ndata: {"conversation_id": "' + VALID_CONV_UUID + '", "task_id": "t1"}\n\n',
            'event: message\ndata: {"delta": "回答"}\n\n',
            'event: finish\ndata: {"message_id": 1, "title": "测试", "token_usage": {"prompt": 10, "completion": 5, "total": 15}}\n\n',
        ]
        with patch("app.api.chat.chat") as mock_chat:
            mock_chat.return_value = StreamingResponse(
                self._sse_event_gen(sse_events),
                media_type="text/event-stream",
            )

            async with async_client.stream(
                "POST", "/api/chat",
                json={"kb_id": VALID_KB_UUID, "question": "测试问题"},
                headers=auth_headers,
            ) as response:
                assert response.status_code == 200
                content_type = response.headers.get("content-type", "")
                assert "text/event-stream" in content_type

    @pytest.mark.asyncio
    async def test_chat_meta_event_has_uuid(self, async_client, auth_headers):
        """A10.16: SSE meta 事件 conversation_id 为 UUID 格式"""
        sse_events = [
            'event: meta\ndata: {"conversation_id": "' + VALID_CONV_UUID + '", "task_id": "t1"}\n\n',
            'event: finish\ndata: {"message_id": 1, "token_usage": {"prompt": 0, "completion": 0, "total": 0}}\n\n',
        ]
        with patch("app.api.chat.chat") as mock_chat:
            mock_chat.return_value = StreamingResponse(
                self._sse_event_gen(sse_events),
                media_type="text/event-stream",
            )

            collected = []
            async with async_client.stream(
                "POST", "/api/chat",
                json={"kb_id": VALID_KB_UUID, "question": "测试"},
                headers=auth_headers,
            ) as response:
                async for line in response.aiter_lines():
                    collected.append(line)

        # 验证 meta 事件中的 conversation_id 是 UUID 格式
        all_text = "\n".join(collected)
        assert VALID_CONV_UUID in all_text

    @pytest.mark.asyncio
    async def test_chat_invalid_kb_uuid(self, async_client, auth_headers):
        """A10.15: POST /api/chat kb_id='invalid' → 404"""
        with patch("app.api.chat.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = KnowledgeBaseNotFoundException("invalid")

            response = await async_client.post(
                "/api/chat",
                json={"kb_id": "invalid", "question": "测试"},
                headers=auth_headers,
            )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_chat_with_conversation_id_uuid(self, async_client, auth_headers):
        """A10.14: POST /api/chat conversation_id=UUID → 加载历史 + SSE 流正常"""
        sse_events = [
            'event: meta\ndata: {"conversation_id": "' + VALID_CONV_UUID + '", "task_id": "t2"}\n\n',
            'event: message\ndata: {"delta": "基于历史回答"}\n\n',
            'event: finish\ndata: {"message_id": 2, "title": None, "token_usage": {"prompt": 20, "completion": 5, "total": 25}}\n\n',
        ]
        with patch("app.api.chat.chat") as mock_chat:
            mock_chat.return_value = StreamingResponse(
                self._sse_event_gen(sse_events),
                media_type="text/event-stream",
            )

            async with async_client.stream(
                "POST", "/api/chat",
                json={
                    "kb_id": VALID_KB_UUID,
                    "question": "追问问题",
                    "conversation_id": VALID_CONV_UUID,
                },
                headers=auth_headers,
            ) as response:
                assert response.status_code == 200
                content_type = response.headers.get("content-type", "")
                assert "text/event-stream" in content_type

        # 验证 mock_chat 收到正确的 conversation_id（UUID 字符串）
        mock_chat.assert_called_once()
        call_kwargs = mock_chat.call_args.kwargs
        assert call_kwargs["conversation_id"] == VALID_CONV_UUID


# ==================== Selectable KB UUID 测试 ====================


class TestSelectableKBUUID:
    """A10.17: GET /selectable — 返回 uuid 不含 id"""

    @pytest.mark.asyncio
    async def test_selectable_returns_uuid(self, async_client, auth_headers):
        """返回 mine/public 分组中每项含 uuid 不含 id"""
        mock_data = {
            "mine": [
                {"uuid": VALID_KB_UUID, "name": "我的KB", "visibility": "private", "doc_count": 5},
            ],
            "public": [
                {"uuid": "aaa-bbb-ccc", "name": "公共KB", "visibility": "public", "doc_count": 10, "username": "other"},
            ],
        }
        with patch("app.api.knowledge_base.get_selectable_kbs", new_callable=AsyncMock) as mock:
            mock.return_value = mock_data

            response = await async_client.get(
                "/api/knowledge-bases/selectable",
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        # 验证 mine 中含 uuid
        assert body["data"]["mine"][0]["uuid"] == VALID_KB_UUID
        assert "id" not in body["data"]["mine"][0]
        # 验证 public 中含 uuid
        assert "id" not in body["data"]["public"][0]


# ==================== Trace 响应无自增 id 测试 ====================


class TestTraceUUIDClean:
    """A10.18-A10.19: Trace 端点 — 响应不含自增 id"""

    @pytest.mark.asyncio
    async def test_trace_list_no_auto_id(self, async_client, admin_auth_headers):
        """A10.18: GET /admin/traces → 响应不含自增 id"""
        mock_trace = TraceListItem(
            trace_id="trace-abc-123", user_id=1, username="testuser",
            question="测试问题", status="success", created_at=NOW,
        )
        mock_data = TraceListResponse(total=1, page=1, page_size=20, items=[mock_trace])

        with patch("app.api.admin.list_traces", new_callable=AsyncMock) as mock:
            mock.return_value = mock_data

            response = await async_client.get(
                "/api/admin/traces",
                headers=admin_auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        item = body["data"]["items"][0]
        assert "id" not in item
        assert item["trace_id"] == "trace-abc-123"

    @pytest.mark.asyncio
    async def test_trace_detail_no_auto_id(self, async_client, admin_auth_headers):
        """A10.19: GET /admin/traces/{trace_id} → 响应不含自增 id"""
        mock_detail = TraceDetailResponse(
            trace_id="trace-abc-123", user_id=1, username="testuser",
            question="测试问题", status="success", created_at=NOW,
        )

        with patch("app.api.admin.get_trace_detail", new_callable=AsyncMock) as mock:
            mock.return_value = mock_detail

            response = await async_client.get(
                "/api/admin/traces/trace-abc-123",
                headers=admin_auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert "id" not in body["data"]
        assert body["data"]["trace_id"] == "trace-abc-123"
