"""Admin API — 用户管理接口测试

对齐 TEST_CASES.md §6.15.2：
- A9.20 用户列表-正常：GET /api/admin/users
- A9.21 用户列表-筛选：role/status 组合筛选
- A9.22 用户列表-搜索：search 模糊搜索
- A9.23 用户详情-正常：GET /api/admin/users/{user_id}
- A9.24 用户详情-不存在：404
- A9.27 禁用用户-正常：PUT /api/admin/users/{user_id}/status
- A9.28 启用用户-正常
- A9.29 重置密码-正常：POST /api/admin/users/{user_id}/reset-password
- A9.30 重置密码-密码过短：422
- A9.31 用户管理-非 admin 拒绝：权限矩阵

覆盖 app/api/admin.py 用户管理接口层 + dependencies.require_admin 权限校验
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.admin import (
    AdminUserDetailResponse,
    AdminUserItem,
    AdminUserListResponse,
    AdminUserResetPasswordResponse,
    AdminUserStatusResponse,
)


# ==================== 辅助函数 ====================


def _make_user_list(total=2, page=1, page_size=20) -> AdminUserListResponse:
    """构造用户列表响应"""
    items = [
        AdminUserItem(
            id=i, username=f"user_{i}", role="user", status="active",
            kb_count=2, doc_count=10, conversation_count=5,
            last_active_at=datetime(2026, 6, 12, tzinfo=timezone.utc),
            created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        )
        for i in range(1, total + 1)
    ]
    return AdminUserListResponse(total=total, page=page, page_size=page_size, items=items)


def _make_user_detail(user_id=3) -> AdminUserDetailResponse:
    """构造用户详情响应"""
    return AdminUserDetailResponse(
        id=user_id, username="zhangsan", role="user", status="active",
        kb_count=2, doc_count=15, conversation_count=28, message_count=156,
        total_input_tokens=524000, total_output_tokens=128000,
        last_active_at=datetime(2026, 6, 12, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 6, tzinfo=timezone.utc),
    )


# ==================== 用户列表接口测试 ====================


class TestAdminUserListAPI:
    """GET /api/admin/users — 用户列表

    对齐 TEST_CASES.md §6.15.2：A9.20-A9.22
    """

    @pytest.mark.asyncio
    async def test_admin获取用户列表成功(self, async_client, admin_auth_headers):
        """A9.20：admin 可获取用户列表，含统计字段"""
        with patch("app.api.admin.list_users", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = _make_user_list()
            response = await async_client.get(
                "/api/admin/users", headers=admin_auth_headers,
            )
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "0"
        assert body["data"]["total"] == 2
        assert len(body["data"]["items"]) == 2
        item = body["data"]["items"][0]
        assert item["username"] == "user_1"
        assert item["role"] == "user"
        assert item["status"] == "active"
        assert item["kb_count"] == 2

    @pytest.mark.asyncio
    async def test_admin获取用户列表_筛选参数(self, async_client, admin_auth_headers):
        """A9.21/A9.22：筛选参数 role/status/search 正确传递给 service"""
        with patch("app.api.admin.list_users", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = _make_user_list(total=0)
            response = await async_client.get(
                "/api/admin/users",
                params={"role": "admin", "status": "disabled", "search": "zhang"},
                headers=admin_auth_headers,
            )
        assert response.status_code == 200
        mock_svc.assert_called_once()
        call_kwargs = mock_svc.call_args
        assert call_kwargs.kwargs.get("role") == "admin"

    @pytest.mark.asyncio
    async def test_普通用户获取用户列表被拒绝(self, async_client, auth_headers):
        """普通用户访问 /api/admin/users 返回 403"""
        response = await async_client.get(
            "/api/admin/users", headers=auth_headers,
        )
        assert response.status_code == 403
        assert response.json()["code"] == "E5005"


# ==================== 用户详情接口测试 ====================


class TestAdminUserDetailAPI:
    """GET /api/admin/users/{user_id} — 用户详情

    对齐 TEST_CASES.md §6.15.2：A9.23-A9.24
    """

    @pytest.mark.asyncio
    async def test_admin获取用户详情成功(self, async_client, admin_auth_headers):
        """A9.23：admin 可获取用户详情，含 token 统计"""
        with patch("app.api.admin.get_user_detail", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = _make_user_detail(user_id=3)
            response = await async_client.get(
                "/api/admin/users/3", headers=admin_auth_headers,
            )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["id"] == 3
        assert data["username"] == "zhangsan"
        assert data["message_count"] == 156
        assert data["total_input_tokens"] == 524000
        assert data["total_output_tokens"] == 128000

    @pytest.mark.asyncio
    async def test_用户不存在返回404(self, async_client, admin_auth_headers):
        """A9.24：查询不存在的用户返回 E7002"""
        from app.core.exceptions import UserNotFoundException
        with patch("app.api.admin.get_user_detail", new_callable=AsyncMock) as mock_svc:
            mock_svc.side_effect = UserNotFoundException(999)
            response = await async_client.get(
                "/api/admin/users/999", headers=admin_auth_headers,
            )
        assert response.status_code == 404
        assert response.json()["code"] == "E7002"

    @pytest.mark.asyncio
    async def test_普通用户获取详情被拒绝(self, async_client, auth_headers):
        """普通用户访问 /api/admin/users/3 返回 403"""
        response = await async_client.get(
            "/api/admin/users/3", headers=auth_headers,
        )
        assert response.status_code == 403


# ==================== 用户状态管理接口测试 ====================


class TestAdminUserStatusAPI:
    """PUT /api/admin/users/{user_id}/status — 禁用/启用

    对齐 TEST_CASES.md §6.15.2：A9.27-A9.28
    """

    @pytest.mark.asyncio
    async def test_禁用用户成功(self, async_client, admin_auth_headers):
        """A9.27：admin 禁用用户成功"""
        with patch("app.api.admin.change_user_status", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = AdminUserStatusResponse(id=3, username="zhangsan", status="disabled")
            response = await async_client.put(
                "/api/admin/users/3/status",
                json={"status": "disabled"},
                headers=admin_auth_headers,
            )
        assert response.status_code == 200
        assert response.json()["message"] == "用户已禁用"
        assert response.json()["data"]["status"] == "disabled"

    @pytest.mark.asyncio
    async def test_启用用户成功(self, async_client, admin_auth_headers):
        """A9.28：admin 启用用户成功"""
        with patch("app.api.admin.change_user_status", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = AdminUserStatusResponse(id=3, username="zhangsan", status="active")
            response = await async_client.put(
                "/api/admin/users/3/status",
                json={"status": "active"},
                headers=admin_auth_headers,
            )
        assert response.status_code == 200
        assert response.json()["message"] == "用户已启用"
        assert response.json()["data"]["status"] == "active"

    @pytest.mark.asyncio
    async def test_不能禁用自己(self, async_client, admin_auth_headers):
        """admin 不能修改自己的状态，返回 E7003"""
        response = await async_client.put(
            "/api/admin/users/2/status",
            json={"status": "disabled"},
            headers=admin_auth_headers,
        )
        assert response.status_code == 400
        assert response.json()["code"] == "E7003"


# ==================== 重置密码接口测试 ====================


class TestAdminUserResetPasswordAPI:
    """POST /api/admin/users/{user_id}/reset-password — 重置密码

    对齐 TEST_CASES.md §6.15.2：A9.29-A9.30
    """

    @pytest.mark.asyncio
    async def test_重置密码成功(self, async_client, admin_auth_headers):
        """A9.29：admin 重置用户密码成功"""
        with patch("app.api.admin.reset_user_password", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = AdminUserResetPasswordResponse(id=3, username="zhangsan")
            response = await async_client.post(
                "/api/admin/users/3/reset-password",
                json={"new_password": "NewPass123!"},
                headers=admin_auth_headers,
            )
        assert response.status_code == 200
        assert response.json()["message"] == "密码重置成功"
        assert response.json()["data"]["id"] == 3

    @pytest.mark.asyncio
    async def test_密码过短被拒绝(self, async_client, admin_auth_headers):
        """A9.30：密码长度 < 6 被 Pydantic 校验拒绝"""
        response = await async_client.post(
            "/api/admin/users/3/reset-password",
            json={"new_password": "12345"},
            headers=admin_auth_headers,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_用户不存在返回404(self, async_client, admin_auth_headers):
        """重置不存在用户的密码返回 E7002"""
        from app.core.exceptions import UserNotFoundException
        with patch("app.api.admin.reset_user_password", new_callable=AsyncMock) as mock_svc:
            mock_svc.side_effect = UserNotFoundException(999)
            response = await async_client.post(
                "/api/admin/users/999/reset-password",
                json={"new_password": "NewPass123!"},
                headers=admin_auth_headers,
            )
        assert response.status_code == 404
        assert response.json()["code"] == "E7002"

    @pytest.mark.asyncio
    async def test_新密码与原密码相同返回400(self, async_client, admin_auth_headers):
        """新密码与原密码相同时返回 E7004"""
        from app.core.exceptions import PasswordSameAsCurrentException
        with patch("app.api.admin.reset_user_password", new_callable=AsyncMock) as mock_svc:
            mock_svc.side_effect = PasswordSameAsCurrentException()
            response = await async_client.post(
                "/api/admin/users/3/reset-password",
                json={"new_password": "OldPass123!"},
                headers=admin_auth_headers,
            )
        assert response.status_code == 400
        assert response.json()["code"] == "E7004"
        assert response.json()["message"] == "新密码不能与原密码相同"


# ==================== 用户管理权限矩阵 ====================


class TestAdminUserPermissionMatrix:
    """A9.31：用户管理端点权限矩阵

    对齐 TEST_CASES.md §6.15.2：所有用户管理端点对普通用户返回 403，未认证返回 401
    """

    USER_ENDPOINTS = [
        ("GET", "/api/admin/users"),
        ("GET", "/api/admin/users/3"),
        ("PUT", "/api/admin/users/3/status"),
        ("POST", "/api/admin/users/3/reset-password"),
    ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,endpoint", USER_ENDPOINTS)
    async def test_普通用户被拒绝(self, async_client, auth_headers, method, endpoint):
        """普通用户访问所有用户管理端点返回 403"""
        kwargs = {"headers": auth_headers}
        if method == "PUT":
            kwargs["json"] = {"status": "disabled"}
        elif method == "POST":
            kwargs["json"] = {"new_password": "NewPass123!"}

        response = await getattr(async_client, method.lower())(endpoint, **kwargs)
        assert response.status_code == 403, f"普通用户应被拒绝访问 {method} {endpoint}"
        assert response.json()["code"] == "E5005"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,endpoint", USER_ENDPOINTS)
    async def test_未认证被拒绝(self, async_client, method, endpoint):
        """未认证用户访问所有用户管理端点返回 401"""
        kwargs = {}
        if method == "PUT":
            kwargs["json"] = {"status": "disabled"}
        elif method == "POST":
            kwargs["json"] = {"new_password": "NewPass123!"}

        response = await getattr(async_client, method.lower())(endpoint, **kwargs)
        assert response.status_code == 401, f"未认证应被拒绝访问 {method} {endpoint}"
