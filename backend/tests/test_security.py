"""JWT & 密码哈希单元测试"""
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)


class TestPasswordHashing:
    def test_hash_returns_bcrypt_string(self):
        result = hash_password("test123")
        assert result.startswith("$2b$")

    def test_verify_correct_password(self):
        hashed = hash_password("test123")
        assert verify_password("test123", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("test123")
        assert verify_password("wrong", hashed) is False

    def test_same_password_different_salt(self):
        h1 = hash_password("test123")
        h2 = hash_password("test123")
        assert h1 != h2

    def test_verify_empty_password(self):
        hashed = hash_password("test123")
        assert verify_password("", hashed) is False


class TestJWT:
    def test_create_token_contains_claims(self):
        token = create_access_token(1, "user1", "user")
        payload = decode_access_token(token)
        assert payload["sub"] == "1"
        assert payload["username"] == "user1"
        assert payload["role"] == "user"
        assert "exp" in payload

    def test_decode_valid_token(self):
        token = create_access_token(1, "test", "admin")
        payload = decode_access_token(token)
        assert payload["role"] == "admin"

    def test_decode_invalid_token(self):
        payload = decode_access_token("invalid.token.here")
        assert payload == {}

    def test_decode_empty_string(self):
        payload = decode_access_token("")
        assert payload == {}

    def test_decode_garbled_text(self):
        payload = decode_access_token("这不是JWT")
        assert payload == {}

    def test_token_exp_uses_utc(self):
        """验证 token 过期时间在 now + TTL 附近（UTC）"""
        import time
        from app.config import settings
        token = create_access_token(1, "u", "user")
        payload = decode_access_token(token)
        expected_exp = int(time.time()) + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        # 允许 5 秒误差（测试执行耗时）
        assert abs(payload["exp"] - expected_exp) < 5
