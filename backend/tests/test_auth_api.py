"""认证 API 接口测试 — 使用 TestClient 走完整 HTTP 链路"""
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

import pytest

from app.schemas.auth import UserResponse, TokenResponse
from app.core.exceptions import UsernameExistsException, InvalidCredentialsException


def _make_user_response(username="testuser"):
    return UserResponse(
        id=1, username=username, role="user",
        created_at=datetime.now(timezone.utc)
    )


def _make_token_response():
    return TokenResponse(access_token="fake-token", refresh_token="fake-refresh-token", expires_in=900)


class TestRegisterAPI:
    @pytest.mark.asyncio
    async def test_register_success(self, async_client):
        with patch("app.api.auth.register", new_callable=AsyncMock) as mock_reg:
            mock_reg.return_value = _make_user_response("newuser")

            response = await async_client.post(
                "/api/auth/register",
                json={"username": "newuser", "password": "123456"}
            )

        assert response.status_code == 201
        body = response.json()
        assert body["code"] == "0"
        assert body["message"] == "注册成功"
        assert body["data"]["username"] == "newuser"
        assert body["data"]["role"] == "user"

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, async_client):
        with patch("app.api.auth.register", new_callable=AsyncMock) as mock_reg:
            mock_reg.side_effect = UsernameExistsException("existing")

            response = await async_client.post(
                "/api/auth/register",
                json={"username": "existing", "password": "123456"}
            )

        assert response.status_code == 409
        body = response.json()
        assert body["code"] == "E5001"

    @pytest.mark.asyncio
    async def test_register_username_too_short(self, async_client):
        response = await async_client.post(
            "/api/auth/register",
            json={"username": "a", "password": "123456"}
        )
        assert response.status_code == 422
        body = response.json()
        assert body["code"] == "E9003"

    @pytest.mark.asyncio
    async def test_register_password_too_short(self, async_client):
        response = await async_client.post(
            "/api/auth/register",
            json={"username": "test", "password": "123"}
        )
        assert response.status_code == 422
        assert response.json()["code"] == "E9003"

    @pytest.mark.asyncio
    async def test_register_missing_username(self, async_client):
        response = await async_client.post(
            "/api/auth/register",
            json={"password": "123456"}
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_missing_password(self, async_client):
        response = await async_client.post(
            "/api/auth/register",
            json={"username": "test"}
        )
        assert response.status_code == 422


class TestLoginAPI:
    @pytest.mark.asyncio
    async def test_login_success(self, async_client):
        with patch("app.api.auth.login", new_callable=AsyncMock) as mock_login:
            mock_login.return_value = _make_token_response()

            response = await async_client.post(
                "/api/auth/login",
                json={"username": "testuser", "password": "correct"}
            )

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "0"
        assert body["message"] == "登录成功"
        assert body["data"]["access_token"] == "fake-token"
        assert body["data"]["refresh_token"] == "fake-refresh-token"
        assert body["data"]["token_type"] == "bearer"
        assert body["data"]["expires_in"] == 900

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, async_client):
        with patch("app.api.auth.login", new_callable=AsyncMock) as mock_login:
            mock_login.side_effect = InvalidCredentialsException()

            response = await async_client.post(
                "/api/auth/login",
                json={"username": "testuser", "password": "wrongpw"}
            )

        assert response.status_code == 401
        body = response.json()
        assert body["code"] == "E5002"

    @pytest.mark.asyncio
    async def test_login_empty_username(self, async_client):
        """空用户名被 LoginRequest min_length=2 拒绝"""
        response = await async_client.post(
            "/api/auth/login",
            json={"username": "", "password": "correct"}
        )

        assert response.status_code == 422
        assert response.json()["code"] == "E9003"

    @pytest.mark.asyncio
    async def test_login_missing_password(self, async_client):
        response = await async_client.post(
            "/api/auth/login",
            json={"username": "test"}
        )
        assert response.status_code == 422


class TestAuthMiddleware:
    @pytest.mark.asyncio
    async def test_no_auth_header_returns_401(self, async_client):
        response = await async_client.get("/api/knowledge-bases")
        assert response.status_code == 401
        body = response.json()
        assert body["code"] == "E5004"

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self, async_client):
        response = await async_client.get(
            "/api/knowledge-bases",
            headers={"Authorization": "Bearer invalid.token.here"}
        )
        assert response.status_code == 401
        body = response.json()
        assert body["code"] == "E5004"

    @pytest.mark.asyncio
    async def test_public_route_skips_middleware(self, async_client):
        """公开路由 OPTIONS /api/auth/login 被中间件放行（不要求 Token）"""
        response = await async_client.options("/api/auth/login")
        # OPTIONS 被中间件直接放行，FastAPI 返回 405 Method Not Allowed（因为没有注册 OPTIONS 路由）
        assert response.status_code == 405

    @pytest.mark.asyncio
    async def test_options_preflight_skipped(self, async_client):
        """OPTIONS 预检请求被中间件直接放行"""
        response = await async_client.options("/api/knowledge-bases")
        # OPTIONS 放行后进入路由系统，该路由可能返回 405（未注册 OPTIONS）或 404
        assert response.status_code in (200, 404, 405)
