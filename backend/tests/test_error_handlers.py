"""全局异常处理器测试 — 错误码映射 + 生产环境堆栈屏蔽

对齐 ARCHITECTURE.md §9.1 / ROADMAP.md §6.6。
"""

from unittest.mock import patch, AsyncMock
import pytest
from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    KnowledgeBaseNotFoundException,
    InvalidCredentialsException,
    PermissionDeniedException,
    UsernameExistsException,
    AppException,
)


class TestExceptionToStatusCode:
    """各异常类 → HTTP 状态码 + 错误码映射"""

    @pytest.mark.asyncio
    async def test_422参数校验失败(self, async_client):
        """缺少必填字段 → 422 + E9003"""
        resp = await async_client.post(
            "/api/auth/register",
            json={"username": "a", "password": "123456"},
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["code"] == "E9003"
        assert body["message"] == "请求参数校验失败"

    @pytest.mark.asyncio
    async def test_409用户名已存在(self, async_client):
        """业务异常通过 AppException handler 返回正确状态码"""
        with patch("app.api.auth.register", new_callable=AsyncMock) as mock:
            mock.side_effect = UsernameExistsException("existing")
            resp = await async_client.post(
                "/api/auth/register",
                json={"username": "existing", "password": "123456"},
            )
        assert resp.status_code == 409
        body = resp.json()
        assert body["code"] == "E5001"

    @pytest.mark.asyncio
    async def test_401凭证错误(self, async_client):
        with patch("app.api.auth.login", new_callable=AsyncMock) as mock:
            mock.side_effect = InvalidCredentialsException()
            resp = await async_client.post(
                "/api/auth/login",
                json={"username": "testuser", "password": "wrongpwd"},
            )
        assert resp.status_code == 401
        body = resp.json()
        assert body["code"] == "E5002"

    @pytest.mark.asyncio
    async def test_404知识库不存在(self, async_client, auth_headers):
        with patch("app.api.knowledge_base.get_kb", new_callable=AsyncMock) as mock:
            mock.side_effect = KnowledgeBaseNotFoundException(999)
            resp = await async_client.get(
                "/api/knowledge-bases/999",
                headers=auth_headers,
            )
        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "E1001"

    @pytest.mark.asyncio
    async def test_403权限不足(self, async_client, auth_headers):
        with patch("app.api.knowledge_base.get_kb", new_callable=AsyncMock) as mock:
            mock.side_effect = PermissionDeniedException()
            resp = await async_client.get(
                "/api/knowledge-bases/1",
                headers=auth_headers,
            )
        assert resp.status_code == 403
        body = resp.json()
        assert body["code"] == "E5005"

    def test_appexception状态码映射(self):
        """验证 AppException 子类的 status_code 与 API.md 错误码一致"""
        test_cases = [
            (KnowledgeBaseNotFoundException(1), 404, "E1001"),
            (InvalidCredentialsException(), 401, "E5002"),
            (PermissionDeniedException(), 403, "E5005"),
        ]
        for exc, expected_status, expected_code in test_cases:
            assert exc.status_code == expected_status, f"{expected_code} 状态码不匹配"
            assert exc.error_code == expected_code

    def test_未知异常handler_生产模式屏蔽堆栈(self):
        """生产模式下 global_exception_handler 返回通用提示"""
        from app.main import global_exception_handler
        # 直接测试 handler 逻辑：生产模式 detail 不泄露内部信息
        with patch("app.main.settings") as mock_settings:
            mock_settings.DEBUG = False
            # handler 是 async 函数，需要 asyncio.run
            import asyncio
            request = AsyncMock(spec=Request)
            request.method = "GET"
            request.url.path = "/api/test"
            exc = RuntimeError("secret_password_leaked")
            resp = asyncio.run(global_exception_handler(request, exc))
            body = resp.body.decode()
            assert "secret_password" not in body
            assert "请联系管理员" in body

    def test_未知异常handler_开发模式返回详情(self):
        """开发模式下 global_exception_handler 返回完整错误信息"""
        from app.main import global_exception_handler
        import asyncio
        request = AsyncMock(spec=Request)
        request.method = "GET"
        request.url.path = "/api/test"
        exc = RuntimeError("detailed error info")
        resp = asyncio.run(global_exception_handler(request, exc))
        body = resp.body.decode()
        assert "detailed error info" in body
