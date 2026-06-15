"""Celery 幂等锁 — 基于 Redis SET NX 实现，防止同一文档重复入队

幂等键格式: doc_lock:{doc_id}（ingest/delete 共享互斥锁）
锁 TTL: 600s（与 Celery soft_time_limit 对齐）

触发规则（对齐 ARCHITECTURE.md §4.5）:
- 无锁 → 正常创建任务
- 有锁 + 运行中 → 拒绝，返回 E2011「文档正在处理中」
- 有锁 + Worker crash → 等待锁过期后自动允许重新触发
- 终态 + 无锁 + reprocess → 允许重新触发（清理旧数据）
"""

from app.core.redis_client import get_redis

from app.config import settings

# 幂等键前缀
IDEMPOTENCY_KEY_PREFIX = "doc_lock"


def _build_lock_key(doc_id: int, task_type: str) -> str:
    """构建幂等锁 Redis key（ingest/delete 共享同一锁，确保互斥）"""
    return f"{IDEMPOTENCY_KEY_PREFIX}:{doc_id}"


def acquire_idempotency_lock(
    doc_id: int, task_type: str, ttl: int = settings.IDEMPOTENCY_LOCK_TTL
) -> bool:
    """尝试获取幂等锁（原子操作 SET key value EX ttl NX）。

    Args:
        doc_id: 文档 ID
        task_type: 任务类型（如 ingest、delete）
        ttl: 锁过期时间（秒），默认 600s

    Returns:
        True: 获取成功，可继续执行
        False: 锁已被占用，应拒绝重复入队（→ E2011）
    """
    key = _build_lock_key(doc_id, task_type)
    return bool(get_redis().set(key, "locked", ex=ttl, nx=True))


def release_idempotency_lock(doc_id: int, task_type: str) -> None:
    """释放幂等锁（任务完成/失败后调用，幂等操作）"""
    key = _build_lock_key(doc_id, task_type)
    get_redis().delete(key)


def check_idempotency_lock(doc_id: int, task_type: str) -> bool:
    """检查是否存在幂等锁。

    Returns:
        True: 已锁定（任务正在处理中）
        False: 未锁定
    """
    key = _build_lock_key(doc_id, task_type)
    return get_redis().exists(key) > 0


async def acquire_idempotency_lock_async(
    doc_id: int, task_type: str, ttl: int = settings.IDEMPOTENCY_LOCK_TTL
) -> bool:
    """异步版幂等锁获取，供 async 上下文使用（避免阻塞事件循环）。"""
    from app.core.redis_client import get_async_redis

    key = _build_lock_key(doc_id, task_type)
    redis_client = await get_async_redis()
    return bool(await redis_client.set(key, "locked", ex=ttl, nx=True))


async def release_idempotency_lock_async(doc_id: int, task_type: str) -> None:
    """异步版幂等锁释放，供 async 上下文使用（避免阻塞事件循环）。"""
    from app.core.redis_client import get_async_redis

    key = _build_lock_key(doc_id, task_type)
    redis_client = await get_async_redis()
    await redis_client.delete(key)
