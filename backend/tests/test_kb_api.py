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

VALID_KB_UUID = "550e8400-e29b-41d4-a716-446655440000"
VALID_KB_UUID_2 = "6ba7b811-9dad-41d4-80b4-00c04fd430c8"
NOW = datetime.now(timezone.utc)


def _make_kb_response(kb_uuid=VALID_KB_UUID, name="测试知识库", description=None, user_id=1,
                      status="active", visibility="private", doc_count=0, chunk_count=0):
    return KnowledgeBaseResponse(
        uuid=kb_uuid, name=name, description=description, user_id=user_id,
        visibility=visibility, status=status, doc_count=doc_count, chunk_count=chunk_count,
        created_at=NOW, updated_at=NOW,
    )


def _make_list_data(total=1, page=1, page_size=20, items=None):
    if items is None:
        items = [_make_kb_response()]
    return KnowledgeBaseListResponse(total=total, page=page, page_size=page_size, items=items)


def _make_delete_data(kb_uuid=VALID_KB_UUID, status="deleting"):
    return KnowledgeBaseDeleteResponse(kb_uuid=kb_uuid, status=status)


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
            _make_kb_response(kb_uuid=VALID_KB_UUID, name="知识库A"),
            _make_kb_response(kb_uuid=VALID_KB_UUID_2, name="知识库B"),
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
        # UUID 字段
        assert "uuid" in body["data"]["items"][0]
        assert "id" not in body["data"]["items"][0]

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
    """GET /api/knowledge-bases/{kb_uuid} — 知识库详情"""

    @pytest.mark.asyncio
    async def test_get_success(self, async_client, auth_headers):
        with patch("app.api.knowledge_base.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.knowledge_base.get_kb", new_callable=AsyncMock) as mock:
            mock_resolve.return_value = 1
            mock.return_value = _make_kb_response(name="公司知识库", description="详细描述")

            response = await async_client.get(
                f"/api/knowledge-bases/{VALID_KB_UUID}",
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "0"
        assert body["data"]["uuid"] == VALID_KB_UUID
        assert "id" not in body["data"]
        assert body["data"]["name"] == "公司知识库"
        assert body["data"]["user_id"] == 1
        assert body["data"]["status"] == "active"
        assert body["data"]["doc_count"] == 0
        assert body["data"]["chunk_count"] == 0

    @pytest.mark.asyncio
    async def test_get_not_found(self, async_client, auth_headers):
        with patch("app.api.knowledge_base.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve:
            mock_resolve.side_effect = KnowledgeBaseNotFoundException(VALID_KB_UUID)

            response = await async_client.get(
                f"/api/knowledge-bases/{VALID_KB_UUID}",
                headers=auth_headers,
            )

        assert response.status_code == 404
        body = response.json()
        assert body["code"] == "E1001"
        assert body["message"] == "知识库不存在"

    @pytest.mark.asyncio
    async def test_get_permission_denied(self, async_client, auth_headers):
        """非 owner 且非 admin 查看他人知识库时被拒绝"""
        with patch("app.api.knowledge_base.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.knowledge_base.get_kb", new_callable=AsyncMock) as mock:
            mock_resolve.return_value = 2
            mock.side_effect = PermissionDeniedException()

            response = await async_client.get(
                f"/api/knowledge-bases/{VALID_KB_UUID_2}",
                headers=auth_headers,
            )

        assert response.status_code == 403
        body = response.json()
        assert body["code"] == "E5005"
        assert body["message"] == "无权限执行此操作"

    @pytest.mark.asyncio
    async def test_get_no_auth(self, async_client):
        response = await async_client.get(f"/api/knowledge-bases/{VALID_KB_UUID}")
        assert response.status_code == 401


class TestUpdateKB:
    """PUT /api/knowledge-bases/{kb_uuid} — 更新知识库"""

    @pytest.mark.asyncio
    async def test_update_name(self, async_client, auth_headers):
        with patch("app.api.knowledge_base.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.knowledge_base.update_kb", new_callable=AsyncMock) as mock:
            mock_resolve.return_value = 1
            mock.return_value = _make_kb_response(name="新名称")

            response = await async_client.put(
                f"/api/knowledge-bases/{VALID_KB_UUID}",
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
        with patch("app.api.knowledge_base.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.knowledge_base.update_kb", new_callable=AsyncMock) as mock:
            mock_resolve.return_value = 1
            mock.return_value = _make_kb_response(name="原名称", description="新描述")

            response = await async_client.put(
                f"/api/knowledge-bases/{VALID_KB_UUID}",
                json={"description": "新描述"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["description"] == "新描述"

    @pytest.mark.asyncio
    async def test_update_not_found(self, async_client, auth_headers):
        with patch("app.api.knowledge_base.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve:
            mock_resolve.side_effect = KnowledgeBaseNotFoundException(VALID_KB_UUID)

            response = await async_client.put(
                f"/api/knowledge-bases/{VALID_KB_UUID}",
                json={"name": "新名称"},
                headers=auth_headers,
            )

        assert response.status_code == 404
        assert response.json()["code"] == "E1001"

    @pytest.mark.asyncio
    async def test_update_name_conflict(self, async_client, auth_headers):
        with patch("app.api.knowledge_base.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.knowledge_base.update_kb", new_callable=AsyncMock) as mock:
            mock_resolve.return_value = 1
            mock.side_effect = KnowledgeBaseNameExistsException("重复名称")

            response = await async_client.put(
                f"/api/knowledge-bases/{VALID_KB_UUID}",
                json={"name": "重复名称"},
                headers=auth_headers,
            )

        assert response.status_code == 409
        assert response.json()["code"] == "E1002"

    @pytest.mark.asyncio
    async def test_update_permission_denied(self, async_client, auth_headers):
        """非 owner 且非 admin 修改时被拒绝"""
        with patch("app.api.knowledge_base.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.knowledge_base.update_kb", new_callable=AsyncMock) as mock:
            mock_resolve.return_value = 2
            mock.side_effect = PermissionDeniedException()

            response = await async_client.put(
                f"/api/knowledge-bases/{VALID_KB_UUID_2}",
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
        with patch("app.api.knowledge_base.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.knowledge_base.update_kb", new_callable=AsyncMock) as mock:
            mock_resolve.return_value = 1
            mock.return_value = _make_kb_response()

            response = await async_client.put(
                f"/api/knowledge-bases/{VALID_KB_UUID}",
                json={},
                headers=auth_headers,
            )

        # 空 body 也应接受（部分更新语义）
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_update_no_auth(self, async_client):
        response = await async_client.put(
            f"/api/knowledge-bases/{VALID_KB_UUID}",
            json={"name": "新名称"},
        )
        assert response.status_code == 401


class TestDeleteKB:
    """DELETE /api/knowledge-bases/{kb_uuid} — 删除知识库"""

    @pytest.mark.asyncio
    async def test_delete_success(self, async_client, auth_headers):
        with patch("app.api.knowledge_base.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.knowledge_base.delete_kb", new_callable=AsyncMock) as mock:
            mock_resolve.return_value = 1
            mock.return_value = _make_delete_data(kb_uuid=VALID_KB_UUID, status="deleting")

            response = await async_client.delete(
                f"/api/knowledge-bases/{VALID_KB_UUID}",
                headers=auth_headers,
            )

        assert response.status_code == 202
        body = response.json()
        assert body["code"] == "0"
        assert body["message"] == "知识库删除任务已提交"
        assert body["data"]["kb_uuid"] == VALID_KB_UUID
        assert body["data"]["status"] == "deleting"

    @pytest.mark.asyncio
    async def test_delete_not_found(self, async_client, auth_headers):
        with patch("app.api.knowledge_base.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve:
            mock_resolve.side_effect = KnowledgeBaseNotFoundException(VALID_KB_UUID)

            response = await async_client.delete(
                f"/api/knowledge-bases/{VALID_KB_UUID}",
                headers=auth_headers,
            )

        assert response.status_code == 404
        assert response.json()["code"] == "E1001"

    @pytest.mark.asyncio
    async def test_delete_permission_denied(self, async_client, auth_headers):
        """非 owner 且非 admin 删除时被拒绝"""
        with patch("app.api.knowledge_base.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.knowledge_base.delete_kb", new_callable=AsyncMock) as mock:
            mock_resolve.return_value = 2
            mock.side_effect = PermissionDeniedException()

            response = await async_client.delete(
                f"/api/knowledge-bases/{VALID_KB_UUID_2}",
                headers=auth_headers,
            )

        assert response.status_code == 403
        body = response.json()
        assert body["code"] == "E5005"
        assert body["message"] == "无权限执行此操作"

    @pytest.mark.asyncio
    async def test_delete_no_auth(self, async_client):
        response = await async_client.delete(f"/api/knowledge-bases/{VALID_KB_UUID}")
        assert response.status_code == 401


class TestVisibilityPermissionMatrix:
    """Phase 2.5 — KB 权限矩阵接口测试（A6.1-A6.6）"""

    @pytest.mark.asyncio
    async def test_public_kb_readable_by_other_user(self, async_client, other_user_auth_headers):
        """A6.1: public KB 允许非 owner 读取"""
        with patch("app.api.knowledge_base.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.knowledge_base.get_kb", new_callable=AsyncMock) as mock:
            mock_resolve.return_value = 2
            mock.return_value = _make_kb_response(kb_uuid=VALID_KB_UUID_2, user_id=99, visibility="public")

            response = await async_client.get(
                f"/api/knowledge-bases/{VALID_KB_UUID_2}",
                headers=other_user_auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "0"
        assert body["data"]["visibility"] == "public"
        assert body["data"]["user_id"] == 99

    @pytest.mark.asyncio
    async def test_private_kb_denied_to_other_user(self, async_client, other_user_auth_headers):
        """A6.2: private KB 非 owner 拒绝访问"""
        with patch("app.api.knowledge_base.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.knowledge_base.get_kb", new_callable=AsyncMock) as mock:
            mock_resolve.return_value = 2
            mock.side_effect = PermissionDeniedException()

            response = await async_client.get(
                f"/api/knowledge-bases/{VALID_KB_UUID_2}",
                headers=other_user_auth_headers,
            )

        assert response.status_code == 403
        assert response.json()["code"] == "E5005"

    @pytest.mark.asyncio
    async def test_public_kb_not_writable_by_other_user(self, async_client, other_user_auth_headers):
        """A6.3: public KB 非 owner 不可修改（ownership 控制写）"""
        with patch("app.api.knowledge_base.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.knowledge_base.update_kb", new_callable=AsyncMock) as mock:
            mock_resolve.return_value = 2
            mock.side_effect = PermissionDeniedException()

            response = await async_client.put(
                f"/api/knowledge-bases/{VALID_KB_UUID_2}",
                json={"visibility": "private"},
                headers=other_user_auth_headers,
            )

        assert response.status_code == 403
        assert response.json()["code"] == "E5005"

    @pytest.mark.asyncio
    async def test_admin_can_read_private_kb(self, async_client, admin_auth_headers):
        """A6.4: admin 可查看他人 private KB（审计）"""
        with patch("app.api.knowledge_base.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.knowledge_base.get_kb", new_callable=AsyncMock) as mock:
            mock_resolve.return_value = 2
            mock.return_value = _make_kb_response(kb_uuid=VALID_KB_UUID_2, user_id=99, visibility="private")

            response = await async_client.get(
                f"/api/knowledge-bases/{VALID_KB_UUID_2}",
                headers=admin_auth_headers,
            )

        assert response.status_code == 200
        assert response.json()["code"] == "0"

    @pytest.mark.asyncio
    async def test_admin_can_update_any_kb_visibility(self, async_client, admin_auth_headers):
        """A6.5: admin 可修正任意 KB 的 visibility"""
        with patch("app.api.knowledge_base.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.knowledge_base.update_kb", new_callable=AsyncMock) as mock:
            mock_resolve.return_value = 2
            mock.return_value = _make_kb_response(kb_uuid=VALID_KB_UUID_2, user_id=99, visibility="public")

            response = await async_client.put(
                f"/api/knowledge-bases/{VALID_KB_UUID_2}",
                json={"visibility": "public"},
                headers=admin_auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "0"
        assert body["data"]["visibility"] == "public"

    @pytest.mark.asyncio
    async def test_owner_can_update_visibility(self, async_client, auth_headers):
        """A6.6: owner 可修改自己 KB 的 visibility"""
        with patch("app.api.knowledge_base.resolve_uuid_to_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.api.knowledge_base.update_kb", new_callable=AsyncMock) as mock:
            mock_resolve.return_value = 1
            mock.return_value = _make_kb_response(kb_uuid=VALID_KB_UUID, user_id=1, visibility="public")

            response = await async_client.put(
                f"/api/knowledge-bases/{VALID_KB_UUID}",
                json={"visibility": "public"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert response.json()["data"]["visibility"] == "public"


class TestPublicKbList:
    """Phase 2.5 — 公共 KB 列表接口测试（A7.1-A7.7）"""

    @pytest.mark.asyncio
    async def test_list_public_kbs_success(self, async_client, auth_headers):
        """A7.1: 公共列表返回 public+active KB"""
        with patch("app.api.knowledge_base.list_public_kbs", new_callable=AsyncMock) as mock:
            mock.return_value = _make_list_data(total=1, items=[
                _make_kb_response(kb_uuid=VALID_KB_UUID_2, user_id=99, visibility="public"),
            ])

            response = await async_client.get(
                "/api/knowledge-bases/public",
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["total"] == 1
        assert body["data"]["items"][0]["visibility"] == "public"

    @pytest.mark.asyncio
    async def test_list_public_pagination(self, async_client, auth_headers):
        """A7.4: 公共列表分页"""
        with patch("app.api.knowledge_base.list_public_kbs", new_callable=AsyncMock) as mock:
            mock.return_value = _make_list_data(total=50, page=2, page_size=5, items=[])

            response = await async_client.get(
                "/api/knowledge-bases/public?page=2&page_size=5",
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["page"] == 2
        assert body["data"]["page_size"] == 5

    @pytest.mark.asyncio
    async def test_list_public_includes_username(self, async_client, auth_headers):
        """A7.5: 公共列表返回 owner 用户名"""
        with patch("app.api.knowledge_base.list_public_kbs", new_callable=AsyncMock) as mock:
            from app.schemas.knowledge_base import PublicKnowledgeBaseListResponse, PublicKnowledgeBaseResponse
            mock.return_value = PublicKnowledgeBaseListResponse(
                total=1, page=1, page_size=20,
                items=[PublicKnowledgeBaseResponse(
                    uuid=VALID_KB_UUID_2, name="公共KB", description=None,
                    user_id=99, username="otheruser", visibility="public",
                    status="active", doc_count=5, chunk_count=100,
                    created_at=NOW, updated_at=NOW,
                )],
            )

            response = await async_client.get(
                "/api/knowledge-bases/public",
                headers=auth_headers,
            )

        assert response.status_code == 200
        item = response.json()["data"]["items"][0]
        assert item["username"] == "otheruser"
        assert item["visibility"] == "public"

    @pytest.mark.asyncio
    async def test_list_public_no_auth(self, async_client):
        """A7.6: 未认证拒绝"""
        response = await async_client.get("/api/knowledge-bases/public")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_public_empty(self, async_client, auth_headers):
        """A7.7: 无 public KB 时返回空列表"""
        with patch("app.api.knowledge_base.list_public_kbs", new_callable=AsyncMock) as mock:
            mock.return_value = _make_list_data(total=0, items=[])

            response = await async_client.get(
                "/api/knowledge-bases/public",
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert response.json()["data"]["total"] == 0
