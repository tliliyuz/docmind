"""Pydantic Schema 校验测试"""
import pytest
from pydantic import ValidationError

from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse


class TestRegisterRequest:
    def test_valid_input(self):
        req = RegisterRequest(username="test", password="123456")
        assert req.username == "test"
        assert req.password == "123456"

    def test_username_too_short(self):
        with pytest.raises(ValidationError) as exc:
            RegisterRequest(username="a", password="123456")
        errors = exc.value.errors()
        assert any("string_too_short" == e.get("type", "") for e in errors)

    def test_password_too_short(self):
        with pytest.raises(ValidationError) as exc:
            RegisterRequest(username="test", password="123")
        errors = exc.value.errors()
        assert any("string_too_short" == e.get("type", "") for e in errors)

    def test_username_too_long(self):
        with pytest.raises(ValidationError) as exc:
            RegisterRequest(username="x" * 65, password="123456")
        errors = exc.value.errors()
        assert any("string_too_long" == e.get("type", "") for e in errors)

    def test_missing_username(self):
        with pytest.raises(ValidationError):
            RegisterRequest(password="123456")

    def test_missing_password(self):
        with pytest.raises(ValidationError):
            RegisterRequest(username="test")


class TestLoginRequest:
    def test_valid_input(self):
        req = LoginRequest(username="test", password="123456")
        assert req.username == "test"

    def test_empty_username_rejected(self):
        """LoginRequest username 设 min_length=2，空字符串应被拒绝"""
        with pytest.raises(ValidationError):
            LoginRequest(username="", password="123456")

    def test_missing_username(self):
        with pytest.raises(ValidationError):
            LoginRequest(password="123456")


class TestTokenResponse:
    def test_default_token_type(self):
        resp = TokenResponse(access_token="abc", expires_in=86400)
        assert resp.token_type == "bearer"

    def test_model_dump(self):
        resp = TokenResponse(access_token="abc", expires_in=3600)
        data = resp.model_dump()
        assert "access_token" in data
        assert "token_type" in data
        assert data["expires_in"] == 3600

    def test_custom_token_type(self):
        resp = TokenResponse(access_token="abc", token_type="jwt", expires_in=60)
        assert resp.token_type == "jwt"
