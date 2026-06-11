"""Redis 客户端 — 同步/异步双客户端，供锁/缓存/会话等模块复用

对齐 .claude/plans/001-intent-optimization.md P0-2：
- 同步客户端：Celery 任务使用（lock.py / tasks.py）
- 异步客户端：FastAPI 路由/Service 使用（bm25.py 等），避免阻塞事件循环

实现说明：
- **开发环境（Windows）**：`redis.Redis` 同步客户端 + `asyncio.to_thread()` 线程池包装
- **生产环境（Linux）**：建议切换到原生 `redis.asyncio.Redis` + `ConnectionPool`

生产环境切换参考代码（保留在此供参考）：
```python
import redis.asyncio as aioredis

_async_client: Optional[aioredis.Redis] = None
_async_pool: Optional[aioredis.ConnectionPool] = None

async def get_async_redis() -> aioredis.Redis:
    global _async_client, _async_pool
    if _async_client is None:
        _async_pool = aioredis.ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=20,
            socket_connect_timeout=5.0,
            socket_timeout=10.0,
            retry_on_timeout=True,
            health_check_interval=30,
        )
        _async_client = aioredis.Redis(connection_pool=_async_pool)
        await _async_client.ping()
    return _async_client
```
"""

import asyncio
import logging
import redis
from typing import Any, Optional

from app.config import settings

logger = logging.getLogger(__name__)

# 同步客户端：Celery 任务使用（lock.py / tasks.py）
_sync_client: redis.Redis | None = None

# 包装后的异步客户端：同步客户端 + 线程池
_threaded_client: Optional["ThreadedRedisClient"] = None


def get_redis() -> redis.Redis:
    """获取 Redis 同步客户端（懒加载单例，线程安全）。

    用于 Celery 任务等同步上下文。
    """
    global _sync_client
    if _sync_client is None:
        logger.info("SYNC_REDIS: 创建新的同步客户端实例")
        _sync_client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5.0,
            socket_timeout=10.0,
            retry_on_timeout=True,
            max_connections=20,
        )
        # 验证连接
        try:
            _sync_client.ping()
            logger.info("SYNC_REDIS: 连接验证成功")
        except Exception as e:
            logger.warning("SYNC_REDIS: 连接验证失败（Redis 可能未启动）: %s", e)
    return _sync_client


class ThreadedRedisClient:
    """同步 Redis 客户端的线程池包装器，提供异步接口。

    在 Windows 上，redis.asyncio 有时有问题，用这种方式更稳定。
    """

    def __init__(self, sync_client: redis.Redis):
        self._sync = sync_client

    async def get(self, key: str) -> Optional[str]:
        """异步 GET"""
        return await asyncio.to_thread(self._sync.get, key)

    async def setex(self, key: str, ttl: int, value: str) -> Any:
        """异步 SETEX"""
        return await asyncio.to_thread(self._sync.setex, key, ttl, value)

    async def delete(self, key: str) -> Any:
        """异步 DELETE"""
        return await asyncio.to_thread(self._sync.delete, key)

    async def ping(self) -> Any:
        """异步 PING"""
        return await asyncio.to_thread(self._sync.ping)

    async def close(self) -> None:
        """关闭（同步客户端不需要显式关闭）"""
        pass


async def get_async_redis() -> ThreadedRedisClient:
    """获取 Redis 异步客户端（懒加载单例）。

    实际上是「同步客户端 + 线程池」的包装，Windows 兼容性更好。
    """
    global _threaded_client
    if _threaded_client is None:
        logger.info("ASYNC_REDIS: 创建新的异步客户端实例（线程池包装）")

        # 获取同步客户端
        sync_client = get_redis()

        # 包装为异步接口
        _threaded_client = ThreadedRedisClient(sync_client)

        logger.info("ASYNC_REDIS: 客户端创建成功")
    else:
        logger.debug("ASYNC_REDIS: 复用现有异步客户端实例")
    return _threaded_client


async def close_async_redis() -> None:
    """优雅关闭异步 Redis 客户端（应用退出时调用）。"""
    global _threaded_client
    if _threaded_client is not None:
        logger.info("ASYNC_REDIS: 关闭异步客户端")
        await _threaded_client.close()
        _threaded_client = None
