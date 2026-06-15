"""Redis 客户端 — 同步/异步双客户端，供锁/缓存/会话等模块复用

- 同步客户端：Celery 任务使用（lock.py / tasks.py），全平台统一
- 异步客户端：FastAPI 路由/Service 使用（bm25.py 等），避免阻塞事件循环

异步客户端根据运行环境自动选择实现：
- **Linux（Docker 容器）**：原生 `redis.asyncio.Redis` + `ConnectionPool`，性能最优
- **Windows（开发环境）**：`redis.Redis` 同步客户端 + `asyncio.to_thread()` 线程池包装，
  规避 `redis.asyncio` 在 Windows 下的连接超时和稳定性问题
"""

import asyncio
import logging
import sys
import redis
from typing import Any, Optional

from app.config import settings

logger = logging.getLogger(__name__)

# ── 异步客户端：根据平台自动选择实现 ──
_IS_LINUX = sys.platform != "win32"

if _IS_LINUX:
    # Linux（Docker 生产环境）：原生 redis.asyncio
    import redis.asyncio as aioredis

    _async_client: aioredis.Redis | None = None
    _async_pool: aioredis.ConnectionPool | None = None
else:
    # Windows（开发环境）：线程池包装
    _threaded_client: Optional["ThreadedRedisClient"] = None

# ── 同步客户端：Celery 任务使用（lock.py / tasks.py），全平台统一 ──
_sync_client: redis.Redis | None = None


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

    async def set(
        self, key: str, value: str,
        ex: int | None = None, nx: bool = False,
    ) -> Any:
        """异步 SET，支持 EX/NX 参数（用于幂等锁）"""
        return await asyncio.to_thread(self._sync.set, key, value, ex=ex, nx=nx)

    async def setex(self, key: str, ttl: int, value: str) -> Any:
        """异步 SETEX"""
        return await asyncio.to_thread(self._sync.setex, key, ttl, value)

    async def delete(self, key: str) -> Any:
        """异步 DELETE"""
        return await asyncio.to_thread(self._sync.delete, key)

    async def incr(self, key: str) -> int:
        """异步 INCR（原子递增）"""
        return await asyncio.to_thread(self._sync.incr, key)

    async def expire(self, key: str, ttl: int) -> Any:
        """异步 EXPIRE（设置过期时间）"""
        return await asyncio.to_thread(self._sync.expire, key, ttl)

    async def eval(self, script: str, numkeys: int, *args: Any) -> Any:
        """异步 EVAL（执行 Lua 脚本）"""
        return await asyncio.to_thread(self._sync.eval, script, numkeys, *args)

    async def ping(self) -> Any:
        """异步 PING"""
        return await asyncio.to_thread(self._sync.ping)

    async def close(self) -> None:
        """关闭（同步客户端不需要显式关闭）"""
        pass


async def get_async_redis():
    """获取 Redis 异步客户端（懒加载单例）。

    - Linux（Docker 生产环境）：原生 redis.asyncio + ConnectionPool，性能最优
    - Windows（开发环境）：同步客户端 + asyncio.to_thread() 线程池包装，
      规避 redis.asyncio 在 Windows 下的连接稳定性问题
    """
    if _IS_LINUX:
        global _async_client, _async_pool
        if _async_client is None:
            logger.info("ASYNC_REDIS: 创建原生 redis.asyncio 客户端（Linux 生产模式）")
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
            try:
                await _async_client.ping()
                logger.info("ASYNC_REDIS: 原生 async 客户端连接验证成功")
            except Exception as e:
                logger.warning("ASYNC_REDIS: 原生 async 客户端连接验证失败: %s", e)
        else:
            logger.debug("ASYNC_REDIS: 复用现有原生 async 客户端")
        return _async_client
    else:
        global _threaded_client
        if _threaded_client is None:
            logger.info("ASYNC_REDIS: 创建线程池包装客户端（Windows 开发模式）")
            sync_client = get_redis()
            _threaded_client = ThreadedRedisClient(sync_client)
            logger.info("ASYNC_REDIS: 线程池包装客户端创建成功")
        else:
            logger.debug("ASYNC_REDIS: 复用现有线程池包装客户端")
        return _threaded_client


async def close_async_redis() -> None:
    """优雅关闭异步 Redis 客户端（应用退出时调用）。"""
    if _IS_LINUX:
        global _async_client, _async_pool
        if _async_client is not None:
            logger.info("ASYNC_REDIS: 关闭原生 redis.asyncio 客户端")
            await _async_client.aclose()
            if _async_pool is not None:
                await _async_pool.aclose()
            _async_client = None
            _async_pool = None
    else:
        global _threaded_client
        if _threaded_client is not None:
            logger.info("ASYNC_REDIS: 关闭线程池包装客户端")
            await _threaded_client.close()
            _threaded_client = None
