"""Redis 客户端 — 懒加载单例，供锁/缓存/会话等模块复用"""

import redis

from app.config import settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """获取 Redis 客户端（懒加载单例，线程安全）"""
    global _client
    if _client is None:
        _client = redis.Redis.from_url(
            settings.REDIS_URL, decode_responses=True
        )
    return _client
