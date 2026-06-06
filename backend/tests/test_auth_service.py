"""认证 Service 单元测试 — Mock DB session"""
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth_service import register, login
from app.schemas.auth import UserResponse, TokenResponse
from app.core.exceptions import UsernameExistsException, InvalidCredentialsException
from app.models.user import User


@pytest.fixture
def mock_db():
    session = AsyncMock(spec=AsyncSession)
    # Mock refresh 模拟 DB 回填 id/role/created_at
    async def _refresh(instance):
        instance.id = instance.id or 1
        instance.role = instance.role or "user"
        instance.created_at = instance.created_at or datetime.now(timezone.utc)
    session.refresh.side_effect = _refresh
    return session


def _make_mock_result(value):
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=value)
    return result


class TestRegister:
    @pytest.mark.asyncio
    async def test_register_success(self, mock_db):
        mock_db.execute.return_value = _make_mock_result(None)

        result = await register(mock_db, "newuser", "123456")

        assert isinstance(result, UserResponse)
        assert result.username == "newuser"
        assert result.id == 1
        assert result.role == "user"
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()
        mock_db.refresh.assert_called_once()

        added_user = mock_db.add.call_args[0][0]
        assert isinstance(added_user, User)
        assert added_user.username == "newuser"
        assert added_user.password_hash.startswith("$2b$")

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, mock_db):
        existing = User(username="existing", password_hash="xxx")
        mock_db.execute.return_value = _make_mock_result(existing)

        with pytest.raises(UsernameExistsException) as exc:
            await register(mock_db, "existing", "123456")
        assert exc.value.error_code == "E5001"
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_register_strong_password(self, mock_db):
        mock_db.execute.return_value = _make_mock_result(None)

        result = await register(mock_db, "user1", "P@ssw0rd!长密码")

        assert result.username == "user1"
        assert result.id == 1
        mock_db.add.assert_called_once()


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_success(self, mock_db):
        from app.core.security import hash_password
        user = User(username="test", password_hash=hash_password("correct"))
        mock_db.execute.return_value = _make_mock_result(user)

        result = await login(mock_db, "test", "correct")

        assert isinstance(result, TokenResponse)
        assert result.access_token
        assert result.refresh_token
        assert result.token_type == "bearer"
        assert result.expires_in == 15 * 60  # 15 分钟

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, mock_db):
        from app.core.security import hash_password
        user = User(username="test", password_hash=hash_password("correct"))
        mock_db.execute.return_value = _make_mock_result(user)

        with pytest.raises(InvalidCredentialsException) as exc:
            await login(mock_db, "test", "wrong")
        assert exc.value.error_code == "E5002"

    @pytest.mark.asyncio
    async def test_login_user_not_found(self, mock_db):
        mock_db.execute.return_value = _make_mock_result(None)

        with pytest.raises(InvalidCredentialsException) as exc:
            await login(mock_db, "ghost", "any")
        assert exc.value.error_code == "E5002"

    @pytest.mark.asyncio
    async def test_login_token_not_empty(self, mock_db):
        from app.core.security import hash_password
        user = User(username="u", password_hash=hash_password("p"))
        mock_db.execute.return_value = _make_mock_result(user)

        result = await login(mock_db, "u", "p")

        assert result.access_token
        assert len(result.access_token) > 20
        assert "." in result.access_token  # JWT 格式
        assert result.refresh_token
        assert len(result.refresh_token) > 20
        assert "." in result.refresh_token  # JWT 格式
