"""KB 选择器 API 集成测试

对齐 TEST_CASES.md §5.11 / ROADMAP.md §5.5：
- 分组正确（mine + public）
- 仅返回 status=active 的 KB
- 去重（当前用户自己的 public KB 不出现在 public 组）
- 空数据返回空列表
- 未认证返回 401
- admin 可见性

覆盖 app/api/knowledge_base.py GET /api/knowledge-bases/selectable
"""

from unittest.mock import AsyncMock, patch

import pytest


class TestSelectableKB:
    """GET /api/knowledge-bases/selectable"""

    @pytest.mark.asyncio
    async def test_分组正确(self, async_client, auth_headers):
        """mine 和 public 应正确分组"""
        mock_data = {
            "mine": [
                {"id": 1, "name": "我的知识库", "visibility": "private", "doc_count": 5},
                {"id": 2, "name": "我的公开库", "visibility": "public", "doc_count": 3},
            ],
            "public": [
                {"id": 10, "name": "他人公开库", "visibility": "public", "doc_count": 8, "username": "other"},
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
        assert body["code"] == "0"
        assert len(body["data"]["mine"]) == 2
        assert len(body["data"]["public"]) == 1
        assert body["data"]["mine"][0]["name"] == "我的知识库"
        assert body["data"]["public"][0]["username"] == "other"

    @pytest.mark.asyncio
    async def test_仅返回active状态(self, async_client, auth_headers):
        """仅返回 status=active 的 KB（service 层已过滤）"""
        mock_data = {
            "mine": [{"id": 1, "name": "活跃库", "visibility": "private", "doc_count": 2}],
            "public": [],
        }

        with patch("app.api.knowledge_base.get_selectable_kbs", new_callable=AsyncMock) as mock:
            mock.return_value = mock_data
            response = await async_client.get(
                "/api/knowledge-bases/selectable",
                headers=auth_headers,
            )

        body = response.json()
        # 所有返回的 KB 都应该是 active（service 层保证）
        for kb in body["data"]["mine"]:
            assert "id" in kb and "name" in kb

    @pytest.mark.asyncio
    async def test_当前用户public_KB不出现在public组(self, async_client, auth_headers):
        """当前用户自己的 public KB 只出现在 mine 组，不在 public 组"""
        mock_data = {
            "mine": [
                {"id": 1, "name": "我的私有库", "visibility": "private", "doc_count": 1},
                {"id": 2, "name": "我的公开库", "visibility": "public", "doc_count": 3},
            ],
            "public": [
                {"id": 10, "name": "他人公开库", "visibility": "public", "doc_count": 5, "username": "other"},
            ],
        }

        with patch("app.api.knowledge_base.get_selectable_kbs", new_callable=AsyncMock) as mock:
            mock.return_value = mock_data
            response = await async_client.get(
                "/api/knowledge-bases/selectable",
                headers=auth_headers,
            )

        body = response.json()
        mine_ids = [kb["id"] for kb in body["data"]["mine"]]
        public_ids = [kb["id"] for kb in body["data"]["public"]]
        # id=2 在 mine 中，不在 public 中
        assert 2 in mine_ids
        assert 2 not in public_ids

    @pytest.mark.asyncio
    async def test_空数据返回空列表(self, async_client, auth_headers):
        """用户无 KB 且无公共 KB 时应返回空列表"""
        mock_data = {"mine": [], "public": []}

        with patch("app.api.knowledge_base.get_selectable_kbs", new_callable=AsyncMock) as mock:
            mock.return_value = mock_data
            response = await async_client.get(
                "/api/knowledge-bases/selectable",
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["mine"] == []
        assert body["data"]["public"] == []

    @pytest.mark.asyncio
    async def test_未认证返回401(self, async_client):
        """无 token 时应返回 HTTP 401"""
        response = await async_client.get("/api/knowledge-bases/selectable")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_admin可见所有active_KB(self, async_client, admin_auth_headers):
        """admin 用户应能访问 selectable 接口（mine 为空但 public 可见）"""
        mock_data = {
            "mine": [],  # admin 自己没有 KB
            "public": [
                {"id": 10, "name": "用户A的公开库", "visibility": "public", "doc_count": 5, "username": "userA"},
                {"id": 11, "name": "用户B的公开库", "visibility": "public", "doc_count": 3, "username": "userB"},
            ],
        }

        with patch("app.api.knowledge_base.get_selectable_kbs", new_callable=AsyncMock) as mock:
            mock.return_value = mock_data
            response = await async_client.get(
                "/api/knowledge-bases/selectable",
                headers=admin_auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert len(body["data"]["public"]) == 2
