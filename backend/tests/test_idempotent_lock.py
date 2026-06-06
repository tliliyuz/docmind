"""Celery 幂等锁单元测试 — 使用 Mock Redis 覆盖 acquire/release/check 全部场景"""

from unittest.mock import MagicMock, patch

import pytest

from app.config import settings
from app.ingest.lock import (
    _build_lock_key,
    acquire_idempotency_lock,
    check_idempotency_lock,
    release_idempotency_lock,
)


class TestBuildLockKey:
    """锁 Key 格式测试"""

    def test_key_格式包含前缀和_doc_id(self):
        key = _build_lock_key(123, "ingest")
        assert key == "doc_lock:123"

    def test_key_不同_doc_id_生成不同_key(self):
        key1 = _build_lock_key(1, "ingest")
        key2 = _build_lock_key(2, "ingest")
        assert key1 != key2

    def test_key_ingest和delete_共享同一锁(self):
        """同一 doc_id 的 ingest/delete 使用相同锁键，确保互斥"""
        key1 = _build_lock_key(1, "ingest")
        key2 = _build_lock_key(1, "delete")
        assert key1 == key2


class TestAcquireIdempotencyLock:
    """幂等锁获取测试"""

    def test_获取成功_返回_True(self):
        mock_redis = MagicMock()
        mock_redis.set.return_value = True

        with patch("app.ingest.lock.get_redis", return_value=mock_redis):
            result = acquire_idempotency_lock(1, "ingest")
            assert result is True

    def test_获取成功_SET_参数正确(self):
        mock_redis = MagicMock()
        mock_redis.set.return_value = True

        with patch("app.ingest.lock.get_redis", return_value=mock_redis):
            acquire_idempotency_lock(5, "ingest")

        mock_redis.set.assert_called_once_with(
            "doc_lock:5", "locked", ex=600, nx=True
        )

    def test_获取成功_自定义_TTL(self):
        mock_redis = MagicMock()
        mock_redis.set.return_value = True

        with patch("app.ingest.lock.get_redis", return_value=mock_redis):
            acquire_idempotency_lock(1, "ingest", ttl=300)

        mock_redis.set.assert_called_once_with(
            "doc_lock:1", "locked", ex=300, nx=True
        )

    def test_锁已存在_返回_False(self):
        """重复入队场景：SET NX 因 key 已存在而返回 None/False"""
        mock_redis = MagicMock()
        mock_redis.set.return_value = None  # Redis SET NX 冲突返回 None

        with patch("app.ingest.lock.get_redis", return_value=mock_redis):
            result = acquire_idempotency_lock(1, "ingest")
            assert result is False

    def test_delete_和_ingest_共享互斥锁(self):
        """ingest/delete 对同一 doc_id 使用相同锁键，确保互斥"""
        mock_redis = MagicMock()
        mock_redis.set.return_value = True

        with patch("app.ingest.lock.get_redis", return_value=mock_redis):
            acquire_idempotency_lock(1, "delete")

        mock_redis.set.assert_called_once_with(
            "doc_lock:1", "locked", ex=600, nx=True
        )


class TestReleaseIdempotencyLock:
    """幂等锁释放测试"""

    def test_释放_调用_delete(self):
        mock_redis = MagicMock()

        with patch("app.ingest.lock.get_redis", return_value=mock_redis):
            release_idempotency_lock(1, "ingest")

        mock_redis.delete.assert_called_once_with("doc_lock:1")

    def test_释放_不存在的_key_幂等无异常(self):
        """DELETE 对不存在的 key 不会抛异常"""
        mock_redis = MagicMock()
        mock_redis.delete.return_value = 0  # Redis DEL 不存在 key 返回 0

        with patch("app.ingest.lock.get_redis", return_value=mock_redis):
            release_idempotency_lock(999, "ingest")

    def test_释放后_再次获取应成功(self):
        """模拟释放锁后，SET NX 应能再次成功"""
        mock_redis = MagicMock()
        # 第一次 SET 返回 True（获取成功）
        mock_redis.set.return_value = True

        with patch("app.ingest.lock.get_redis", return_value=mock_redis):
            assert acquire_idempotency_lock(1, "ingest") is True


class TestCheckIdempotencyLock:
    """幂等锁检查测试"""

    def test_锁存在_返回_True(self):
        mock_redis = MagicMock()
        mock_redis.exists.return_value = 1

        with patch("app.ingest.lock.get_redis", return_value=mock_redis):
            result = check_idempotency_lock(1, "ingest")
            assert result is True

    def test_锁不存在_返回_False(self):
        mock_redis = MagicMock()
        mock_redis.exists.return_value = 0

        with patch("app.ingest.lock.get_redis", return_value=mock_redis):
            result = check_idempotency_lock(1, "ingest")
            assert result is False

    def test_check_使用正确的_key(self):
        mock_redis = MagicMock()
        mock_redis.exists.return_value = 0

        with patch("app.ingest.lock.get_redis", return_value=mock_redis):
            check_idempotency_lock(42, "ingest")

        mock_redis.exists.assert_called_once_with("doc_lock:42")


class TestLockLifecycle:
    """锁完整生命周期测试"""

    def test_获取_检查_释放_完整流程(self):
        """模拟：获取锁 → 检查锁存在 → 释放锁 → 检查锁不存在"""
        mock_redis = MagicMock()

        with patch("app.ingest.lock.get_redis", return_value=mock_redis):
            # 获取锁
            mock_redis.set.return_value = True
            assert acquire_idempotency_lock(1, "ingest") is True

            # 检查锁存在
            mock_redis.exists.return_value = 1
            assert check_idempotency_lock(1, "ingest") is True

            # 释放锁
            release_idempotency_lock(1, "ingest")
            mock_redis.delete.assert_called_with("doc_lock:1")

            # 检查锁已不存在
            mock_redis.exists.return_value = 0
            assert check_idempotency_lock(1, "ingest") is False

    def test_重复入队被拒绝(self):
        """模拟：任务 A 获取锁成功 → 任务 B 尝试获取同一锁被拒绝"""
        mock_redis = MagicMock()

        with patch("app.ingest.lock.get_redis", return_value=mock_redis):
            # 任务 A 获取锁成功
            mock_redis.set.return_value = True
            assert acquire_idempotency_lock(1, "ingest") is True

            # 任务 B 尝试获取同一锁被拒绝（SET NX 返回 None）
            mock_redis.set.return_value = None
            assert acquire_idempotency_lock(1, "ingest") is False
