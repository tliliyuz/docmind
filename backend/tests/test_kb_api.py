"""知识库 CRUD API 接口测试 — 覆盖正常流程 + 错误码（E1001/E1002/E5005）"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import (
    KnowledgeBaseNameExistsException,
    KnowledgeBaseNotFoundException,
    PermissionDeniedException,
)
from app.schemas.knowledge_base import (
    KnowledgeBaseDeleteResponse,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
)


def _make_kb_response(kb_id=1, name="测试知识库", description=None, user_id=1,
                      status="active", doc_count=0, chunk_count=0):
    return KnowledgeBaseResponse(
        id=kb_id, name=name, description=description, user_id=user_id,
        status=status, doc_count=doc_count, chunk_count=chunk_count,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )


def _make_list_data(total=1, page=1, page_size=20, items=None):
    if items is None:
        items = [_make_kb_response()]
    return KnowledgeBaseListResponse(total=total, page=page, page_size=page_size, items=items)


def _make_delete_data(kb_id=1, status="deleting"):
    return KnowledgeBaseDeleteResponse(kb_id=kb_id, status=status)


class TestCreateKB:
    """POST /api/knowledge-bases — 创建知识库"""

    @pytest.mark.asyncio
    async def test_create_success(self, async_client, auth_headers):
        with patch("app.api.knowledge_base.create_kb", new_callable=AsyncMock) as mock:
            mock.return_value = _make_kb_response(name="公司知识库", description="测试描述")

            response = await async_client.post(
                "/api/knowledge-bases",
                json={"name": "公司知识库", "description": "测试描述"},
                headers=auth_headers,
            )

        assert response.status_code == 201
        body = response.json()
        assert body["code"] == "0"
        assert body["message"] == "知识库创建成功"
        assert body["data"]["name"] == "公司知识库"
        assert body["data"]["description"] == "测试描述"
        assert body["data"]["status"] == "active"
        assert body["data"]["doc_count"] == 0
        assert body["data"]["chunk_count"] == 0

    @pytest.mark.asyncio
    async def test_create_name_exists(self, async_client, auth_headers):
        with patch("app.api.knowledge_base.create_kb", new_callable=AsyncMock) as mock:
            mock.side_effect = KnowledgeBaseNameExistsException("公司知识库")

            response = await async_client.post(
                "/api/knowledge-bases",
                json={"name": "公司知识库", "description": "测试"},
                headers=auth_headers,
            )

        assert response.status_code == 409
        body = response.json()
        assert body["code"] == "E1002"
        assert body["message"] == "知识库名称已存在"

    @pytest.mark.asyncio
    async def test_create_name_too_short(self, async_client, auth_headers):
        response = await async_client.post(
            "/api/knowledge-bases",
            json={"name": "a", "description": "test"},
            headers=auth_headers,
        )

        assert response.status_code == 422
        assert response.json()["code"] == "E9003"

    @pytest.mark.asyncio
    async def test_create_name_too_long(self, async_client, auth_headers):
        response = await async_client.post(
            "/api/knowledge-bases",
            json={"name": "x" * 129, "description": "test"},
            headers=auth_headers,
        )

        assert response.status_code == 422
        assert response.json()["code"] == "E9003"

    @pytest.mark.asyncio
    async def test_create_missing_name(self, async_client, auth_headers):
        response = await async_client.post(
            "/api/knowledge-bases",
            json={"description": "test"},
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_without_description(self, async_client, auth_headers):
        """创建时不提供 description（可选字段）"""
        with patch("app.api.knowledge_base.create_kb", new_callable=AsyncMock) as mock:
            mock.return_value = _make_kb_response(name="仅名称")

            response = await async_client.post(
                "/api/knowledge-bases",
                json={"name": "仅名称"},
                headers=auth_headers,
            )

        assert response.status_code == 201
        assert response.json()["data"]["name"] == "仅名称"

    @pytest.mark.asyncio
    async def test_create_no_auth(self, async_client):
        """未登录创建知识库应返回 401"""
        response = await async_client.post(
            "/api/knowledge-bases",
            json={"name": "测试", "description": "test"},
        )

        assert response.status_code == 401
        assert response.json()["code"] == "E5004"


class TestListKBs:
    """GET /api/knowledge-bases — 知识库列表"""

    @pytest.mark.asyncio
    async def test_list_empty(self, async_client, auth_headers):
        with patch("app.api.knowledge_base.list_kbs", new_callable=AsyncMock) as mock:
            mock.return_value = _make_list_data(total=0, items=[])

            response = await async_client.get(
                "/api/knowledge-bases",
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "0"
        assert body["data"]["total"] == 0
        assert body["data"]["page"] == 1
        assert body["data"]["page_size"] == 20
        assert body["data"]["items"] == []

    @pytest.mark.asyncio
    async def test_list_with_data(self, async_client, auth_headers):
        items = [
            _make_kb_response(kb_id=1, name="知识库A"),
            _make_kb_response(kb_id=2, name="知识库B"),
        ]
        with patch("app.api.knowledge_base.list_kbs", new_callable=AsyncMock) as mock:
            mock.return_value = _make_list_data(total=2, items=items)

            response = await async_client.get(
                "/api/knowledge-bases",
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["total"] == 2
        assert len(body["data"]["items"]) == 2
        assert body["data"]["items"][0]["name"] == "知识库A"
        assert body["data"]["items"][1]["name"] == "知识库B"

    @pytest.mark.asyncio
    async def test_list_with_pagination(self, async_client, auth_headers):
        with patch("app.api.knowledge_base.list_kbs", new_callable=AsyncMock) as mock:
            mock.return_value = _make_list_data(total=50, page=2, page_size=10, items=[])

            response = await async_client.get(
                "/api/knowledge-bases?page=2&page_size=10",
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["page"] == 2
        assert body["data"]["page_size"] == 10

    @pytest.mark.asyncio
    async def test_list_returns_user_id_in_items(self, async_client, auth_headers):
        """列表 items 中应包含 user_id 字段"""
        with patch("app.api.knowledge_base.list_kbs", new_callable=AsyncMock) as mock:
            mock.return_value = _make_list_data(total=1, items=[_make_kb_response(user_id=1)])

            response = await async_client.get("/api/knowledge-bases", headers=auth_headers)

        assert response.status_code == 200
        assert "user_id" in response.json()["data"]["items"][0]

    @pytest.mark.asyncio
    async def test_list_page_size_zero_rejected(self, async_client, auth_headers):
        """page_size=0 被 Query(ge=1) 拒绝"""
        response = await async_client.get(
            "/api/knowledge-bases?page_size=0",
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_page_size_exceeds_100_rejected(self, async_client, auth_headers):
        """page_size > 100 被 Query(le=100) 拒绝"""
        response = await async_client.get(
            "/api/knowledge-bases?page_size=101",
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_no_auth(self, async_client):
        response = await async_client.get("/api/knowledge-bases")
        assert response.status_code == 401


class TestGetKB:
    """GET /api/knowledge-bases/{kb_id} — 知识库详情"""

    @pytest.mark.asyncio
    async def test_get_success(self, async_client, auth_headers):
        with patch("app.api.knowledge_base.get_kb", new_callable=AsyncMock) as mock:
            mock.return_value = _make_kb_response(name="公司知识库", description="详细描述")

            response = await async_client.get(
                "/api/knowledge-bases/1",
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "0"
        assert body["data"]["id"] == 1
        assert body["data"]["name"] == "公司知识库"
        assert body["data"]["user_id"] == 1
        assert body["data"]["status"] == "active"
        assert body["data"]["doc_count"] == 0
        assert body["data"]["chunk_count"] == 0

    @pytest.mark.asyncio
    async def test_get_not_found(self, async_client, auth_headers):
        with patch("app.api.knowledge_base.get_kb", new_callable=AsyncMock) as mock:
            mock.side_effect = KnowledgeBaseNotFoundException(999)

            response = await async_client.get(
                "/api/knowledge-bases/999",
                headers=auth_headers,
            )

        assert response.status_code == 404
        body = response.json()
        assert body["code"] == "E1001"
        assert body["message"] == "知识库不存在"

    @pytest.mark.asyncio
    async def test_get_permission_denied(self, async_client, auth_headers):
        """非 owner 且非 admin 查看他人知识库时被拒绝"""
        with patch("app.api.knowledge_base.get_kb", new_callable=AsyncMock) as mock:
            mock.side_effect = PermissionDeniedException()

            response = await async_client.get(
                "/api/knowledge-bases/2",
                headers=auth_headers,
            )

        assert response.status_code == 403
        body = response.json()
        assert body["code"] == "E5005"
        assert body["message"] == "无权限执行此操作"

    @pytest.mark.asyncio
    async def test_get_no_auth(self, async_client):
        response = await async_client.get("/api/knowledge-bases/1")
        assert response.status_code == 401


class TestUpdateKB:
    """PUT /api/knowledge-bases/{kb_id} — 更新知识库"""

    @pytest.mark.asyncio
    async def test_update_name(self, async_client, auth_headers):
        with patch("app.api.knowledge_base.update_kb", new_callable=AsyncMock) as mock:
            mock.return_value = _make_kb_response(name="新名称")

            response = await async_client.put(
                "/api/knowledge-bases/1",
                json={"name": "新名称"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "0"
        assert body["message"] == "知识库更新成功"
        assert body["data"]["name"] == "新名称"

    @pytest.mark.asyncio
    async def test_update_description(self, async_client, auth_headers):
        with patch("app.api.knowledge_base.update_kb", new_callable=AsyncMock) as mock:
            mock.return_value = _make_kb_response(name="原名称", description="新描述")

            response = await async_client.put(
                "/api/knowledge-bases/1",
                json={"description": "新描述"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["description"] == "新描述"

    @pytest.mark.asyncio
    async def test_update_not_found(self, async_client, auth_headers):
        with patch("app.api.knowledge_base.update_kb", new_callable=AsyncMock) as mock:
            mock.side_effect = KnowledgeBaseNotFoundException(999)

            response = await async_client.put(
                "/api/knowledge-bases/999",
                json={"name": "新名称"},
                headers=auth_headers,
            )

        assert response.status_code == 404
        assert response.json()["code"] == "E1001"

    @pytest.mark.asyncio
    async def test_update_name_conflict(self, async_client, auth_headers):
        with patch("app.api.knowledge_base.update_kb", new_callable=AsyncMock) as mock:
            mock.side_effect = KnowledgeBaseNameExistsException("重复名称")

            response = await async_client.put(
                "/api/knowledge-bases/1",
                json={"name": "重复名称"},
                headers=auth_headers,
            )

        assert response.status_code == 409
        assert response.json()["code"] == "E1002"

    @pytest.mark.asyncio
    async def test_update_permission_denied(self, async_client, auth_headers):
        """非 owner 且非 admin 修改时被拒绝"""
        with patch("app.api.knowledge_base.update_kb", new_callable=AsyncMock) as mock:
            mock.side_effect = PermissionDeniedException()

            response = await async_client.put(
                "/api/knowledge-bases/2",
                json={"name": "新名称"},
                headers=auth_headers,
            )

        assert response.status_code == 403
        body = response.json()
        assert body["code"] == "E5005"
        assert body["message"] == "无权限执行此操作"

    @pytest.mark.asyncio
    async def test_update_empty_body(self, async_client, auth_headers):
        """name 和 description 都是可选，但至少需要修改一个"""
        with patch("app.api.knowledge_base.update_kb", new_callable=AsyncMock) as mock:
            mock.return_value = _make_kb_response()

            response = await async_client.put(
                "/api/knowledge-bases/1",
                json={},
                headers=auth_headers,
            )

        # 空 body 也应接受（部分更新语义）
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_update_no_auth(self, async_client):
        response = await async_client.put(
            "/api/knowledge-bases/1",
            json={"name": "新名称"},
        )
        assert response.status_code == 401


class TestDeleteKB:
    """DELETE /api/knowledge-bases/{kb_id} — 删除知识库"""

    @pytest.mark.asyncio
    async def test_delete_success(self, async_client, auth_headers):
        with patch("app.api.knowledge_base.delete_kb", new_callable=AsyncMock) as mock:
            mock.return_value = _make_delete_data(kb_id=1, status="deleting")

            response = await async_client.delete(
                "/api/knowledge-bases/1",
                headers=auth_headers,
            )

        assert response.status_code == 202
        body = response.json()
        assert body["code"] == "0"
        assert body["message"] == "知识库删除任务已提交"
        assert body["data"]["kb_id"] == 1
        assert body["data"]["status"] == "deleting"

    @pytest.mark.asyncio
    async def test_delete_not_found(self, async_client, auth_headers):
        with patch("app.api.knowledge_base.delete_kb", new_callable=AsyncMock) as mock:
            mock.side_effect = KnowledgeBaseNotFoundException(999)

            response = await async_client.delete(
                "/api/knowledge-bases/999",
                headers=auth_headers,
            )

        assert response.status_code == 404
        assert response.json()["code"] == "E1001"

    @pytest.mark.asyncio
    async def test_delete_permission_denied(self, async_client, auth_headers):
        """非 owner 且非 admin 删除时被拒绝"""
        with patch("app.api.knowledge_base.delete_kb", new_callable=AsyncMock) as mock:
            mock.side_effect = PermissionDeniedException()

            response = await async_client.delete(
                "/api/knowledge-bases/2",
                headers=auth_headers,
            )

        assert response.status_code == 403
        body = response.json()
        assert body["code"] == "E5005"
        assert body["message"] == "无权限执行此操作"

    @pytest.mark.asyncio
    async def test_delete_no_auth(self, async_client):
        response = await async_client.delete("/api/knowledge-bases/1")
        assert response.status_code == 401
