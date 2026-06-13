"""会话 CRUD API 接口测试 — 覆盖正常流程 + 错误码（E3001/E3002）+ 权限拒绝

对齐 TEST_CASES.md §6.1：
- C1.1  创建会话 → 201
- C1.2  列表会话（分页）→ 200
- C1.3  会话详情（含消息）→ 200
- C1.4  重命名会话 → 200
- C1.5  删除会话 → 200
- C1.6  会话不存在 → 404 (E3001)
- C1.7  非所有者访问 → 403 (E3002)
- C1.8  非所有者重命名 → 403
- C1.9  非所有者删除 → 403
- C1.10 未认证 → 401
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


def _make_conv_response(conv_id=1, user_id=1, kb_id=1, title="新对话",
                        message_count=0, kb_status="active", kb_name="测试知识库",
                        last_message_at=None, original_kb_id=None, original_kb_name=None):
    return ConversationResponse(
        id=conv_id, user_id=user_id, kb_id=kb_id, title=title,
        message_count=message_count,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        kb_status=kb_status, kb_name=kb_name,
        last_message_at=last_message_at or datetime.now(timezone.utc),
        original_kb_id=original_kb_id, original_kb_name=original_kb_name,
    )


def _make_conv_detail(conv_id=1, user_id=1, kb_id=1, title="新对话",
                      message_count=2, messages=None, kb_status="active",
                      kb_name="测试知识库", last_message_at=None):
    if messages is None:
        messages = [
            MessageResponse(id=1, role="user", content="问题",
                            thinking_content=None, created_at=datetime.now(timezone.utc)),
            MessageResponse(id=2, role="assistant", content="回答",
                            thinking_content=None, created_at=datetime.now(timezone.utc)),
        ]
    return ConversationDetailResponse(
        id=conv_id, user_id=user_id, kb_id=kb_id, title=title,
        message_count=message_count,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        kb_status=kb_status, kb_name=kb_name,
        last_message_at=last_message_at or datetime.now(timezone.utc),
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
                json={"kb_id": 1, "title": "关于报销流程"},
                headers=auth_headers,
            )

        assert response.status_code == 201
        body = response.json()
        assert body["code"] == "0"
        assert body["message"] == "会话创建成功"
        assert body["data"]["title"] == "关于报销流程"
        assert body["data"]["kb_id"] == 1
        assert body["data"]["kb_status"] == "active"
        assert body["data"]["kb_name"] == "测试知识库"
        assert body["data"]["last_message_at"] is not None

    @pytest.mark.asyncio
    async def test_create_default_title(self, async_client, auth_headers):
        """不传 title 时使用默认值"""
        with patch("app.api.conversation.create_conversation", new_callable=AsyncMock) as mock:
            mock.return_value = _make_conv_response(title="新对话")

            response = await async_client.post(
                "/api/conversations",
                json={"kb_id": 1},
                headers=auth_headers,
            )

        assert response.status_code == 201
        assert response.json()["data"]["title"] == "新对话"

    @pytest.mark.asyncio
    async def test_create_unauthenticated(self, async_client):
        response = await async_client.post(
            "/api/conversations",
            json={"kb_id": 1},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_missing_kb_id(self, async_client, auth_headers):
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
                _make_conv_response(conv_id=1, title="会话1"),
                _make_conv_response(conv_id=2, title="会话2"),
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
        assert item["last_message_at"] is not None

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
    """GET /api/conversations/{id} — 会话详情"""

    @pytest.mark.asyncio
    async def test_detail_success(self, async_client, auth_headers):
        with patch("app.api.conversation.get_conversation_detail", new_callable=AsyncMock) as mock:
            mock.return_value = _make_conv_detail(conv_id=1, title="关于报销流程")

            response = await async_client.get(
                "/api/conversations/1",
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "0"
        assert body["data"]["title"] == "关于报销流程"
        assert body["data"]["kb_status"] == "active"
        assert body["data"]["kb_name"] == "测试知识库"
        assert body["data"]["last_message_at"] is not None
        assert len(body["data"]["messages"]) == 2
        assert body["data"]["messages"][0]["role"] == "user"
        assert body["data"]["messages"][1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_detail_not_found(self, async_client, auth_headers):
        with patch("app.api.conversation.get_conversation_detail", new_callable=AsyncMock) as mock:
            mock.side_effect = ConversationNotFoundException(999)

            response = await async_client.get(
                "/api/conversations/999",
                headers=auth_headers,
            )

        assert response.status_code == 404
        assert response.json()["code"] == "E3001"

    @pytest.mark.asyncio
    async def test_detail_access_denied(self, async_client, auth_headers):
        with patch("app.api.conversation.get_conversation_detail", new_callable=AsyncMock) as mock:
            mock.side_effect = ConversationAccessDeniedException()

            response = await async_client.get(
                "/api/conversations/1",
                headers=auth_headers,
            )

        assert response.status_code == 403
        assert response.json()["code"] == "E3002"

    @pytest.mark.asyncio
    async def test_detail_unauthenticated(self, async_client):
        response = await async_client.get("/api/conversations/1")
        assert response.status_code == 401


class TestRenameConversation:
    """PUT /api/conversations/{id} — 重命名会话"""

    @pytest.mark.asyncio
    async def test_rename_success(self, async_client, auth_headers):
        with patch("app.api.conversation.rename_conversation", new_callable=AsyncMock) as mock:
            mock.return_value = _make_conv_response(conv_id=1, title="新标题")

            response = await async_client.put(
                "/api/conversations/1",
                json={"title": "新标题"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert response.json()["data"]["title"] == "新标题"

    @pytest.mark.asyncio
    async def test_rename_not_found(self, async_client, auth_headers):
        with patch("app.api.conversation.rename_conversation", new_callable=AsyncMock) as mock:
            mock.side_effect = ConversationNotFoundException(999)

            response = await async_client.put(
                "/api/conversations/999",
                json={"title": "新标题"},
                headers=auth_headers,
            )

        assert response.status_code == 404
        assert response.json()["code"] == "E3001"

    @pytest.mark.asyncio
    async def test_rename_access_denied(self, async_client, auth_headers):
        with patch("app.api.conversation.rename_conversation", new_callable=AsyncMock) as mock:
            mock.side_effect = ConversationAccessDeniedException()

            response = await async_client.put(
                "/api/conversations/1",
                json={"title": "新标题"},
                headers=auth_headers,
            )

        assert response.status_code == 403
        assert response.json()["code"] == "E3002"

    @pytest.mark.asyncio
    async def test_rename_empty_title(self, async_client, auth_headers):
        response = await async_client.put(
            "/api/conversations/1",
            json={"title": ""},
            headers=auth_headers,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_rename_title_too_long(self, async_client, auth_headers):
        response = await async_client.put(
            "/api/conversations/1",
            json={"title": "a" * 257},
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestDeleteConversation:
    """DELETE /api/conversations/{id} — 删除会话"""

    @pytest.mark.asyncio
    async def test_delete_success(self, async_client, auth_headers):
        with patch("app.api.conversation.delete_conversation", new_callable=AsyncMock) as mock:
            response = await async_client.delete(
                "/api/conversations/1",
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "0"
        assert body["message"] == "会话已删除"
        assert body["data"] is None

    @pytest.mark.asyncio
    async def test_delete_not_found(self, async_client, auth_headers):
        with patch("app.api.conversation.delete_conversation", new_callable=AsyncMock) as mock:
            mock.side_effect = ConversationNotFoundException(999)

            response = await async_client.delete(
                "/api/conversations/999",
                headers=auth_headers,
            )

        assert response.status_code == 404
        assert response.json()["code"] == "E3001"

    @pytest.mark.asyncio
    async def test_delete_access_denied(self, async_client, auth_headers):
        with patch("app.api.conversation.delete_conversation", new_callable=AsyncMock) as mock:
            mock.side_effect = ConversationAccessDeniedException()

            response = await async_client.delete(
                "/api/conversations/1",
                headers=auth_headers,
            )

        assert response.status_code == 403
        assert response.json()["code"] == "E3002"

    @pytest.mark.asyncio
    async def test_delete_unauthenticated(self, async_client):
        response = await async_client.delete("/api/conversations/1")
        assert response.status_code == 401


class TestConversationKbStatus:
    """会话 kb_status / kb_name / last_message_at 字段覆盖"""

    @pytest.mark.asyncio
    async def test_list_orphan_conversation(self, async_client, auth_headers):
        """kb_id=None + original_kb_id 非空（KB 已删除），kb_status="deleted" """
        with patch("app.api.conversation.list_conversations", new_callable=AsyncMock) as mock:
            mock.return_value = _make_list_data(total=1, items=[
                _make_conv_response(conv_id=10, kb_id=None, kb_status="deleted",
                                    kb_name="已删除知识库", original_kb_id=5,
                                    original_kb_name="已删除知识库"),
            ])

            response = await async_client.get("/api/conversations", headers=auth_headers)

        assert response.status_code == 200
        item = response.json()["data"]["items"][0]
        assert item["kb_id"] is None
        assert item["kb_status"] == "deleted"
        assert item["kb_name"] == "已删除知识库"
        assert item["original_kb_id"] == 5
        assert item["original_kb_name"] == "已删除知识库"

    @pytest.mark.asyncio
    async def test_detail_unavailable_kb(self, async_client, auth_headers):
        """KB 为 private 且非 owner 时，kb_status=unavailable"""
        with patch("app.api.conversation.get_conversation_detail", new_callable=AsyncMock) as mock:
            mock.return_value = _make_conv_detail(
                conv_id=20, kb_id=5, kb_status="unavailable", kb_name="私有知识库",
            )

            response = await async_client.get("/api/conversations/20", headers=auth_headers)

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
                _make_conv_response(conv_id=1, title="较新", last_message_at=t1),
                _make_conv_response(conv_id=2, title="较旧", last_message_at=t2),
            ])

            response = await async_client.get("/api/conversations", headers=auth_headers)

        assert response.status_code == 200
        items = response.json()["data"]["items"]
        assert items[0]["last_message_at"] is not None
        assert items[1]["last_message_at"] is not None
