"""Refresh Token 机制测试 — Service 层 + API 层

对齐 ARCHITECTURE.md §9.2 / ROADMAP.md §6.6。
覆盖：login 返回 refresh_token / refresh Rotation / logout 吊销 / change_password 全部吊销 / 泄露检测。
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jose import jwt

from app.config import settings
from app.core.exceptions import (
    InvalidCredentialsException,
    InvalidRefreshTokenException,
    RefreshTokenExpiredException,
    RefreshTokenRevokedException,
    TokenLeakDetectedException,
)
from app.core.security import (
    create_refresh_token,
    decode_refresh_token,
    hash_token,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import TokenResponse


# ==================== 辅助函数 ====================

def _make_user(user_id=1, username="testuser", role="user"):
    user = MagicMock(spec=User)
    user.id = user_id
    user.username = username
    user.role = role
    user.password_hash = "$2b$12$test_hash"
    return user


def _make_refresh_token(user_id=1, revoked_at=None, expires_delta=timedelta(days=7)):
    rt = MagicMock(spec=RefreshToken)
    rt.id = 1
    rt.user_id = user_id
    rt.token_hash = "test_hash"
    rt.revoked_at = revoked_at
    rt.expires_at = datetime.now(timezone.utc) + expires_delta
    rt.created_at = datetime.now(timezone.utc)
    return rt


def _make_mock_execute(scalar_result=None):
    """构造 mock execute 返回值"""
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_result
    return result


# ==================== Security 层测试 ====================

class TestRefreshTokenSecurity:
    """create_refresh_token / decode_refresh_token / hash_token 测试"""

    def test_create_refresh_token_jwt格式(self):
        token = create_refresh_token(1)
        assert "." in token  # JWT 三段式格式
        # 验证可解码且 sub 正确
        payload = decode_refresh_token(token)
        assert payload["sub"] == "1"
        assert payload["type"] == "refresh"

    def test_decode_refresh_token成功(self):
        token = create_refresh_token(42)
        payload = decode_refresh_token(token)
        assert payload["sub"] == "42"
        assert payload["type"] == "refresh"

    def test_decode_access_token被拒绝(self):
        """access_token 不应被接受为 refresh_token"""
        from app.core.security import create_access_token
        access = create_access_token(1, "user", "user")
        with pytest.raises(Exception):
            decode_refresh_token(access)

    def test_hash_token一致性(self):
        h1 = hash_token("same_token")
        h2 = hash_token("same_token")
        assert h1 == h2

    def test_hash_token不同输入不同输出(self):
        h1 = hash_token("token_a")
        h2 = hash_token("token_b")
        assert h1 != h2

    def test_expired_token被拒绝(self):
        """过期的 refresh_token 应被拒绝"""
        secret = settings.REFRESH_TOKEN_SECRET_KEY or settings.JWT_SECRET_KEY
        expire = datetime.now(timezone.utc) - timedelta(days=1)
        payload = {"sub": "1", "type": "refresh", "exp": expire}
        token = jwt.encode(payload, secret, algorithm=settings.JWT_ALGORITHM)
        with pytest.raises(Exception):
            decode_refresh_token(token)


# ==================== Service 层测试 ====================

class TestLoginRefreshToken:
    """login() 返回值含 refresh_token 测试"""

    @pytest.mark.asyncio
    async def test_login返回refresh_token(self):
        from app.services.auth_service import login
        from app.core.security import hash_password

        user = _make_user()
        user.password_hash = hash_password("correct")

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=_make_mock_execute(user))

        result = await login(mock_db, "testuser", "correct")

        assert isinstance(result, TokenResponse)
        # 验证 token 为可解码 JWT（非仅 truthy 断言）
        access_payload = decode_refresh_token(result.refresh_token)
        assert access_payload["sub"] == "1"
        assert result.expires_in == 15 * 60

    @pytest.mark.asyncio
    async def test_login存入refresh_token哈希(self):
        from app.services.auth_service import login
        from app.core.security import hash_password

        user = _make_user()
        user.password_hash = hash_password("correct")

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=_make_mock_execute(user))

        await login(mock_db, "testuser", "correct")

        # 验证 db.add 被调用（存入 RefreshToken 记录）
        assert mock_db.add.called
        added = mock_db.add.call_args[0][0]
        assert isinstance(added, RefreshToken)
        assert added.user_id == 1
        # token_hash 应该是 SHA-256 哈希（64 字符十六进制）
        assert len(added.token_hash) == 64


class TestRefreshRotation:
    """refresh() Rotation 机制测试"""

    @pytest.mark.asyncio
    async def test_正常刷新返回新token对(self):
        from app.services.auth_service import refresh

        # 先签发一个 token
        token_str = create_refresh_token(1)
        token_hash_val = hash_token(token_str)
        rt = _make_refresh_token(user_id=1)
        rt.token_hash = token_hash_val

        user = _make_user()

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[
            _make_mock_execute(rt),  # 查 refresh_tokens
            MagicMock(),              # revoke_all_user_tokens 的 update
        ])
        mock_db.get = AsyncMock(return_value=user)

        result = await refresh(mock_db, token_str)

        assert isinstance(result, TokenResponse)
        assert result.access_token
        assert result.refresh_token
        # 旧 token 应被吊销
        assert rt.revoked_at is not None
        # 新 token 应是有效 JWT（可解码）
        payload = decode_refresh_token(result.refresh_token)
        assert payload["sub"] == "1"
        assert payload["type"] == "refresh"

    @pytest.mark.asyncio
    async def test_已吊销token触发泄露检测(self):
        from app.services.auth_service import refresh

        token_str = create_refresh_token(1)
        token_hash_val = hash_token(token_str)
        rt = _make_refresh_token(user_id=1, revoked_at=datetime.now(timezone.utc))
        rt.token_hash = token_hash_val

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=_make_mock_execute(rt))

        with pytest.raises(TokenLeakDetectedException) as exc:
            await refresh(mock_db, token_str)
        assert exc.value.error_code == "E5009"

    @pytest.mark.asyncio
    async def test_已过期token被拒绝(self):
        from app.services.auth_service import refresh

        token_str = create_refresh_token(1)
        token_hash_val = hash_token(token_str)
        rt = _make_refresh_token(user_id=1, expires_delta=timedelta(days=-1))
        rt.token_hash = token_hash_val

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=_make_mock_execute(rt))

        with pytest.raises(RefreshTokenExpiredException) as exc:
            await refresh(mock_db, token_str)
        assert exc.value.error_code == "E5006"

    @pytest.mark.asyncio
    async def test_无效token被拒绝(self):
        from app.services.auth_service import refresh

        mock_db = AsyncMock()

        with pytest.raises(InvalidRefreshTokenException):
            await refresh(mock_db, "invalid.jwt.token")

    @pytest.mark.asyncio
    async def test_不存在的token被拒绝(self):
        from app.services.auth_service import refresh

        token_str = create_refresh_token(1)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=_make_mock_execute(None))

        with pytest.raises(InvalidRefreshTokenException):
            await refresh(mock_db, token_str)


class TestLogout:
    """logout() 吊销测试"""

    @pytest.mark.asyncio
    async def test_吊销指定token(self):
        from app.services.auth_service import logout

        token_str = create_refresh_token(1)
        token_hash_val = hash_token(token_str)
        rt = _make_refresh_token(user_id=1)
        rt.token_hash = token_hash_val

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=_make_mock_execute(rt))

        await logout(mock_db, token_str, user_id=1)

        assert rt.revoked_at is not None

    @pytest.mark.asyncio
    async def test_已吊销token不报错(self):
        from app.services.auth_service import logout

        token_str = create_refresh_token(1)
        token_hash_val = hash_token(token_str)
        rt = _make_refresh_token(user_id=1, revoked_at=datetime.now(timezone.utc))
        rt.token_hash = token_hash_val

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=_make_mock_execute(rt))

        # 已吊销的 token 再次 logout 不应报错
        await logout(mock_db, token_str, user_id=1)


class TestChangePassword:
    """change_password() 改密 + 全部吊销测试"""

    @pytest.mark.asyncio
    async def test_改密成功(self):
        from app.services.auth_service import change_password
        from app.core.security import hash_password, verify_password

        user = _make_user()
        user.password_hash = hash_password("old_password")

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=user)

        await change_password(mock_db, 1, "old_password", "new_password")

        # 密码应被更新
        assert verify_password("new_password", user.password_hash)

    @pytest.mark.asyncio
    async def test_旧密码错误(self):
        from app.services.auth_service import change_password
        from app.core.security import hash_password

        user = _make_user()
        user.password_hash = hash_password("correct_password")

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=user)

        with pytest.raises(InvalidCredentialsException):
            await change_password(mock_db, 1, "wrong_password", "new_password")

    @pytest.mark.asyncio
    async def test_改密后全部token被吊销(self):
        from app.services.auth_service import change_password
        from app.core.security import hash_password

        user = _make_user()
        user.password_hash = hash_password("old_password")

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=user)

        await change_password(mock_db, 1, "old_password", "new_password")

        # 验证 execute 被调用（UPDATE refresh_tokens SET revoked_at = now()）
        assert mock_db.execute.called

    @pytest.mark.asyncio
    async def test_新旧密码相同被拒绝(self):
        from app.services.auth_service import change_password
        from app.core.exceptions import PasswordSameAsCurrentException
        from app.core.security import hash_password

        user = _make_user()
        user.password_hash = hash_password("same_password")

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=user)

        with pytest.raises(PasswordSameAsCurrentException):
            await change_password(mock_db, 1, "same_password", "same_password")


# ==================== API 层测试 ====================

class TestRefreshAPI:
    """POST /api/auth/refresh 接口测试"""

    @pytest.mark.asyncio
    async def test_刷新成功(self, async_client):
        with patch("app.api.auth.refresh", new_callable=AsyncMock) as mock:
            mock.return_value = TokenResponse(
                access_token="new-access",
                refresh_token="new-refresh",
                expires_in=900,
            )
            resp = await async_client.post(
                "/api/auth/refresh",
                json={"refresh_token": "old-refresh-token"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "0"
        assert body["data"]["access_token"] == "new-access"
        assert body["data"]["refresh_token"] == "new-refresh"

    @pytest.mark.asyncio
    async def test_刷新失败token过期(self, async_client):
        with patch("app.api.auth.refresh", new_callable=AsyncMock) as mock:
            mock.side_effect = RefreshTokenExpiredException()
            resp = await async_client.post(
                "/api/auth/refresh",
                json={"refresh_token": "expired-token"},
            )
        assert resp.status_code == 401
        body = resp.json()
        assert body["code"] == "E5006"

    @pytest.mark.asyncio
    async def test_泄露检测(self, async_client):
        with patch("app.api.auth.refresh", new_callable=AsyncMock) as mock:
            mock.side_effect = TokenLeakDetectedException()
            resp = await async_client.post(
                "/api/auth/refresh",
                json={"refresh_token": "revoked-token"},
            )
        assert resp.status_code == 401
        body = resp.json()
        assert body["code"] == "E5009"


class TestLogoutAPI:
    """POST /api/auth/logout 接口测试"""

    @pytest.mark.asyncio
    async def test_退出成功(self, async_client, auth_headers):
        with patch("app.api.auth.logout", new_callable=AsyncMock) as mock:
            mock.return_value = None
            resp = await async_client.post(
                "/api/auth/logout",
                json={"refresh_token": "some-token"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "0"
        assert body["message"] == "已退出登录"


class TestChangePasswordAPI:
    """PUT /api/auth/password 接口测试"""

    @pytest.mark.asyncio
    async def test_改密成功(self, async_client, auth_headers):
        with patch("app.api.auth.change_password", new_callable=AsyncMock) as mock:
            mock.return_value = None
            resp = await async_client.put(
                "/api/auth/password",
                json={"old_password": "old123456", "new_password": "new123456"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "0"
        assert "所有设备已下线" in body["message"]

    @pytest.mark.asyncio
    async def test_旧密码错误(self, async_client, auth_headers):
        with patch("app.api.auth.change_password", new_callable=AsyncMock) as mock:
            mock.side_effect = InvalidCredentialsException()
            resp = await async_client.put(
                "/api/auth/password",
                json={"old_password": "wrong123", "new_password": "new123456"},
                headers=auth_headers,
            )
        assert resp.status_code == 401
        body = resp.json()
        assert body["code"] == "E5002"

    @pytest.mark.asyncio
    async def test_未登录返回401(self, async_client):
        resp = await async_client.put(
            "/api/auth/password",
            json={"old_password": "old123456", "new_password": "new123456"},
        )
        assert resp.status_code == 401
