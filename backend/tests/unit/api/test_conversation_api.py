"""会话 CRUD API 接口测试 — 覆盖正常流程 + 错误码（E3001/E3002）+ 权限拒绝

对齐 TEST_CASES.md §6.1：
- A5.1  创建会话 → 201
- A5.2  越权访问会话 → 403, E3002
- A5.3  会话列表排序
- A5.4  会话列表仅返回自己
- A5.5  孤儿会话字段
- A5.6  不可访问 KB 会话
- A5.7  last_message_at 字段
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import (
    ConversationAccessDeniedException,
    ConversationNotFoundException,
)
from app.schemas.conversation import (
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationResponse,
    MessageResponse,
)

# UUID 化后，辅助函数使用 uuid/kb_uuid 字段
VALID_CONV_UUID = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
VALID_KB_UUID = "550e8400-e29b-41d4-a716-446655440000"
NOW = datetime.now(timezone.utc)


def _make_conv_response(conv_uuid=VALID_CONV_UUID, user_id=1, kb_uuid=VALID_KB_UUID,
                        title="新对话", message_count=0, kb_status="active",
                        kb_name="测试知识库", last_message_at=None,
                        original_kb_uuid=None, original_kb_name=None):
    return ConversationResponse(
        uuid=conv_uuid, user_id=user_id, kb_uuid=kb_uuid, title=title,
        message_count=message_count,
        created_at=NOW, updated_at=NOW,
        kb_status=kb_status, kb_name=kb_name,
        last_message_at=last_message_at or NOW,
        original_kb_uuid=original_kb_uuid, original_kb_name=original_kb_name,
    )


def _make_conv_detail(conv_uuid=VALID_CONV_UUID, user_id=1, kb_uuid=VALID_KB_UUID,
                      title="新对话", message_count=2, messages=None, kb_status="active",
                      kb_name="测试知识库", last_message_at=None):
    if messages is None:
        messages = [
            MessageResponse(id=1, role="user", content="问题",
                            thinking_content=None, created_at=NOW),
            MessageResponse(id=2, role="assistant", content="回答",
                            thinking_content=None, created_at=NOW),
        ]
    return ConversationDetailResponse(
        uuid=conv_uuid, user_id=user_id, kb_uuid=kb_uuid, title=title,
        message_count=message_count,
        created_at=NOW, updated_at=NOW,
        kb_status=kb_status, kb_name=kb_name,
        last_message_at=last_message_at or NOW,
        messages=messages,
    )


def _make_list_data(total=1, page=1, page_size=20, items=None):
    if items is None:
        items = [_make_conv_response()]
    return ConversationListResponse(total=total, page=page, page_size=page_size, items=items)


class TestCreateConversation:
    """POST /api/conversations — 创建会话"""

    @pytest.mark.asyncio
    async def test_create_success(self, async_client, auth_headers):
        with patch("app.api.conversation.create_conversation", new_callable=AsyncMock) as mock:
            mock.return_value = _make_conv_response(title="关于报销流程")

            response = await async_client.post(
                "/api/conversations",
                json={"kb_uuid": VALID_KB_UUID, "title": "关于报销流程"},
                headers=auth_headers,
            )

        assert response.status_code == 201
        body = response.json()
        assert body["code"] == "0"
        assert body["message"] == "会话创建成功"
        assert body["data"]["title"] == "关于报销流程"
        assert body["data"]["kb_uuid"] == VALID_KB_UUID
        assert body["data"]["kb_status"] == "active"
        assert body["data"]["kb_name"] == "测试知识库"
        assert "T" in body["data"]["last_message_at"]

    @pytest.mark.asyncio
    async def test_create_default_title(self, async_client, auth_headers):
        """不传 title 时使用默认值"""
        with patch("app.api.conversation.create_conversation", new_callable=AsyncMock) as mock:
            mock.return_value = _make_conv_response(title="新对话")

            response = await async_client.post(
                "/api/conversations",
                json={"kb_uuid": VALID_KB_UUID},
                headers=auth_headers,
            )

        assert response.status_code == 201
        assert response.json()["data"]["title"] == "新对话"

    @pytest.mark.asyncio
    async def test_create_unauthenticated(self, async_client):
        response = await async_client.post(
            "/api/conversations",
            json={"kb_uuid": VALID_KB_UUID},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_missing_kb_uuid(self, async_client, auth_headers):
        response = await async_client.post(
            "/api/conversations",
            json={"title": "测试"},
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestListConversations:
    """GET /api/conversations — 列表会话"""

    @pytest.mark.asyncio
    async def test_list_success(self, async_client, auth_headers):
        with patch("app.api.conversation.list_conversations", new_callable=AsyncMock) as mock:
            mock.return_value = _make_list_data(total=2, items=[
                _make_conv_response(conv_uuid="conv-uuid-1", title="会话1"),
                _make_conv_response(conv_uuid="conv-uuid-2", title="会话2"),
            ])

            response = await async_client.get(
                "/api/conversations",
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "0"
        assert body["data"]["total"] == 2
        assert len(body["data"]["items"]) == 2
        # 新字段断言
        item = body["data"]["items"][0]
        assert item["kb_status"] == "active"
        assert item["kb_name"] == "测试知识库"
        assert "T" in item["last_message_at"]
        # UUID 字段断言
        assert "uuid" in item
        assert "id" not in item

    @pytest.mark.asyncio
    async def test_list_unauthenticated(self, async_client):
        response = await async_client.get("/api/conversations")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_pagination(self, async_client, auth_headers):
        with patch("app.api.conversation.list_conversations", new_callable=AsyncMock) as mock:
            mock.return_value = _make_list_data(total=30, page=2, page_size=10, items=[])

            response = await async_client.get(
                "/api/conversations?page=2&page_size=10",
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["page"] == 2
        assert body["data"]["page_size"] == 10


class TestGetConversationDetail:
    """GET /api/conversations/{conv_uuid} — 会话详情"""

    @pytest.mark.asyncio
    async def test_detail_success(self, async_client, auth_headers):
        with patch("app.api.conversation.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.conversation.get_conversation_detail", new_callable=AsyncMock) as mock:
            mock_resolve.return_value = 1
            mock.return_value = _make_conv_detail(title="关于报销流程")

            response = await async_client.get(
                f"/api/conversations/{VALID_CONV_UUID}",
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "0"
        assert body["data"]["title"] == "关于报销流程"
        assert body["data"]["kb_status"] == "active"
        assert body["data"]["kb_name"] == "测试知识库"
        assert "T" in body["data"]["last_message_at"]
        assert len(body["data"]["messages"]) == 2
        assert body["data"]["messages"][0]["role"] == "user"
        assert body["data"]["messages"][1]["role"] == "assistant"
        # UUID 字段
        assert body["data"]["uuid"] == VALID_CONV_UUID
        assert "id" not in body["data"]

    @pytest.mark.asyncio
    async def test_detail_not_found(self, async_client, auth_headers):
        with patch("app.api.conversation.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve:
            mock_resolve.side_effect = ConversationNotFoundException(999)

            response = await async_client.get(
                f"/api/conversations/{VALID_CONV_UUID}",
                headers=auth_headers,
            )

        assert response.status_code == 404
        assert response.json()["code"] == "E3001"

    @pytest.mark.asyncio
    async def test_detail_access_denied(self, async_client, auth_headers):
        with patch("app.api.conversation.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.conversation.get_conversation_detail", new_callable=AsyncMock) as mock:
            mock_resolve.return_value = 1
            mock.side_effect = ConversationAccessDeniedException()

            response = await async_client.get(
                f"/api/conversations/{VALID_CONV_UUID}",
                headers=auth_headers,
            )

        assert response.status_code == 403
        assert response.json()["code"] == "E3002"

    @pytest.mark.asyncio
    async def test_detail_unauthenticated(self, async_client):
        response = await async_client.get(f"/api/conversations/{VALID_CONV_UUID}")
        assert response.status_code == 401


class TestRenameConversation:
    """PUT /api/conversations/{conv_uuid} — 重命名会话"""

    @pytest.mark.asyncio
    async def test_rename_success(self, async_client, auth_headers):
        with patch("app.api.conversation.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.conversation.rename_conversation", new_callable=AsyncMock) as mock:
            mock_resolve.return_value = 1
            mock.return_value = _make_conv_response(title="新标题")

            response = await async_client.put(
                f"/api/conversations/{VALID_CONV_UUID}",
                json={"title": "新标题"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert response.json()["data"]["title"] == "新标题"

    @pytest.mark.asyncio
    async def test_rename_not_found(self, async_client, auth_headers):
        with patch("app.api.conversation.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve:
            mock_resolve.side_effect = ConversationNotFoundException(999)

            response = await async_client.put(
                f"/api/conversations/{VALID_CONV_UUID}",
                json={"title": "新标题"},
                headers=auth_headers,
            )

        assert response.status_code == 404
        assert response.json()["code"] == "E3001"

    @pytest.mark.asyncio
    async def test_rename_access_denied(self, async_client, auth_headers):
        with patch("app.api.conversation.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.conversation.rename_conversation", new_callable=AsyncMock) as mock:
            mock_resolve.return_value = 1
            mock.side_effect = ConversationAccessDeniedException()

            response = await async_client.put(
                f"/api/conversations/{VALID_CONV_UUID}",
                json={"title": "新标题"},
                headers=auth_headers,
            )

        assert response.status_code == 403
        assert response.json()["code"] == "E3002"

    @pytest.mark.asyncio
    async def test_rename_empty_title(self, async_client, auth_headers):
        with patch("app.api.conversation.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = 1
            response = await async_client.put(
                f"/api/conversations/{VALID_CONV_UUID}",
                json={"title": ""},
                headers=auth_headers,
            )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_rename_title_too_long(self, async_client, auth_headers):
        with patch("app.api.conversation.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = 1
            response = await async_client.put(
                f"/api/conversations/{VALID_CONV_UUID}",
                json={"title": "a" * 257},
                headers=auth_headers,
            )
        assert response.status_code == 422


class TestDeleteConversation:
    """DELETE /api/conversations/{conv_uuid} — 删除会话"""

    @pytest.mark.asyncio
    async def test_delete_success(self, async_client, auth_headers):
        with patch("app.api.conversation.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.conversation.delete_conversation", new_callable=AsyncMock) as mock:
            mock_resolve.return_value = 1

            response = await async_client.delete(
                f"/api/conversations/{VALID_CONV_UUID}",
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "0"
        assert body["message"] == "会话已删除"
        assert body["data"] is None

    @pytest.mark.asyncio
    async def test_delete_not_found(self, async_client, auth_headers):
        with patch("app.api.conversation.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve:
            mock_resolve.side_effect = ConversationNotFoundException(999)

            response = await async_client.delete(
                f"/api/conversations/{VALID_CONV_UUID}",
                headers=auth_headers,
            )

        assert response.status_code == 404
        assert response.json()["code"] == "E3001"

    @pytest.mark.asyncio
    async def test_delete_access_denied(self, async_client, auth_headers):
        with patch("app.api.conversation.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.conversation.delete_conversation", new_callable=AsyncMock) as mock:
            mock_resolve.return_value = 1
            mock.side_effect = ConversationAccessDeniedException()

            response = await async_client.delete(
                f"/api/conversations/{VALID_CONV_UUID}",
                headers=auth_headers,
            )

        assert response.status_code == 403
        assert response.json()["code"] == "E3002"

    @pytest.mark.asyncio
    async def test_delete_unauthenticated(self, async_client):
        response = await async_client.delete(f"/api/conversations/{VALID_CONV_UUID}")
        assert response.status_code == 401


class TestConversationKbStatus:
    """会话 kb_status / kb_name / last_message_at 字段覆盖"""

    @pytest.mark.asyncio
    async def test_list_orphan_conversation(self, async_client, auth_headers):
        """kb_uuid=None + original_kb_uuid 非空（KB 已删除），kb_status="deleted" """
        with patch("app.api.conversation.list_conversations", new_callable=AsyncMock) as mock:
            mock.return_value = _make_list_data(total=1, items=[
                _make_conv_response(conv_uuid="orphan-conv-uuid", kb_uuid=None, kb_status="deleted",
                                    kb_name="已删除知识库", original_kb_uuid="old-kb-uuid",
                                    original_kb_name="已删除知识库"),
            ])

            response = await async_client.get("/api/conversations", headers=auth_headers)

        assert response.status_code == 200
        item = response.json()["data"]["items"][0]
        assert item["kb_uuid"] is None
        assert item["kb_status"] == "deleted"
        assert item["kb_name"] == "已删除知识库"
        assert item["original_kb_uuid"] == "old-kb-uuid"
        assert item["original_kb_name"] == "已删除知识库"

    @pytest.mark.asyncio
    async def test_detail_unavailable_kb(self, async_client, auth_headers):
        """KB 为 private 且非 owner 时，kb_status=unavailable"""
        with patch("app.api.conversation.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.conversation.get_conversation_detail", new_callable=AsyncMock) as mock:
            mock_resolve.return_value = 20
            mock.return_value = _make_conv_detail(
                conv_uuid="unavail-conv-uuid", kb_uuid="private-kb-uuid",
                kb_status="unavailable", kb_name="私有知识库",
            )

            response = await async_client.get(
                "/api/conversations/unavail-conv-uuid", headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["kb_status"] == "unavailable"
        assert data["kb_name"] == "私有知识库"

    @pytest.mark.asyncio
    async def test_list_last_message_at_ordering(self, async_client, auth_headers):
        """列表 items 包含 last_message_at 字段"""
        with patch("app.api.conversation.list_conversations", new_callable=AsyncMock) as mock:
            t1 = datetime(2026, 6, 13, 10, 0, 0, tzinfo=timezone.utc)
            t2 = datetime(2026, 6, 13, 8, 0, 0, tzinfo=timezone.utc)
            mock.return_value = _make_list_data(total=2, items=[
                _make_conv_response(conv_uuid="conv-new", title="较新", last_message_at=t1),
                _make_conv_response(conv_uuid="conv-old", title="较旧", last_message_at=t2),
            ])

            response = await async_client.get("/api/conversations", headers=auth_headers)

        assert response.status_code == 200
        items = response.json()["data"]["items"]
        assert items[0]["last_message_at"] >= items[1]["last_message_at"]
