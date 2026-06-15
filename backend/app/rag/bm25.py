"""BM25 关键词检索器 — rank-bm25 + jieba 分词 + Redis 缓存 + 进程内缓存

对齐 ARCHITECTURE.md §5.1.1 / §6.2 / §7.2 / .claude/plans/001-intent-optimization.md P0-2：
- 每个 KB 独立索引，Redis 缓存 tokenized corpus（TTL=300s）
- 进程内 dict 缓存（TTL=60s），cache hit < 10ms
- 异步 Redis 客户端（线程池包装，Windows 兼容性好），避免阻塞事件循环
- 懒加载：查询时未命中则从 MySQL 加载 + jieba 分词 + 写入 Redis
- BM25Okapi 实例化（轻量，纯 NumPy 计算，<50ms）
"""

import json
import logging
import time
from typing import Any, Optional

import jieba
from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import RetrievalServiceException
from app.core.redis_client import get_async_redis, get_redis
from app.models.chunk import Chunk
from app.rag.retriever import RetrievalOutput, RetrievalResult

from app.config import settings

logger = logging.getLogger(__name__)

# Redis key 模式：bm25_tokens:{kb_id}
BM25_CACHE_KEY_PREFIX = "bm25_tokens"

# 进程内缓存：{kb_id: (bm25, doc_ids, contents, expire_at)}
_local_cache: dict[int, tuple[BM25Okapi | None, list, list, float]] = {}
_LOCAL_TTL = settings.BM25_LOCAL_CACHE_TTL  # 进程内缓存 TTL（秒）


def _build_cache_key(kb_id: int) -> str:
    """构建 Redis 缓存 key"""
    return f"{BM25_CACHE_KEY_PREFIX}:{kb_id}"


def _tokenize(text: str) -> list[str]:
    """jieba 中文分词"""
    return jieba.lcut(text)


def _get_local_cache(kb_id: int) -> tuple[BM25Okapi | None, list, list] | None:
    """从进程内缓存获取，过期返回 None"""
    if kb_id in _local_cache:
        bm25, doc_ids, contents, expire_at = _local_cache[kb_id]
        if time.time() < expire_at:
            return bm25, doc_ids, contents
        else:
            del _local_cache[kb_id]
    return None


def _set_local_cache(
    kb_id: int,
    bm25: BM25Okapi | None,
    doc_ids: list,
    contents: list,
) -> None:
    """写入进程内缓存"""
    _local_cache[kb_id] = (bm25, doc_ids, contents, time.time() + _LOCAL_TTL)


class BM25Retriever:
    """BM25 关键词检索器

    流程：查询分词 → 获取 BM25 索引（进程内缓存 → Redis 缓存 → MySQL 懒加载）→ BM25Okapi 评分 → 返回 top_k
    """

    def __init__(
        self,
        async_redis: Any,  # ThreadedRedisClient 或 aioredis.Redis
        session_factory: async_sessionmaker[AsyncSession],
    ):
        self._async_redis = async_redis
        self._session_factory = session_factory

    async def search(
        self,
        query: str,
        kb_id: int,
        top_k: int = settings.BM25_TOP_K,
        min_score: float = settings.BM25_MIN_SCORE,
    ) -> RetrievalOutput:
        """执行 BM25 关键词检索。

        Args:
            query: 用户问题
            kb_id: 目标知识库 ID
            top_k: 返回结果数量上限
            min_score: 最低分数阈值，低于此值的 chunk 不进入召回结果

        Returns:
            RetrievalOutput: 标准化检索结果（含 stats 性能统计）
        """
        if not query or not query.strip():
            logger.warning("查询内容为空，跳过 BM25 检索")
            return RetrievalOutput()

        try:
            t0 = time.perf_counter()

            # 1. 查询分词
            query_tokens = _tokenize(query)
            t_tokenize = time.perf_counter()

            # 2. 获取 BM25 索引（进程内缓存 → Redis 缓存 → MySQL 懒加载）
            bm25, doc_ids, chunk_contents, cache_type = await self._get_bm25_index(kb_id)
            t_index = time.perf_counter()

            if not doc_ids or bm25 is None:
                logger.info("KB %d 无文档数据，BM25 检索返回空", kb_id)
                return RetrievalOutput(stats={
                    "redis_cache": cache_type,
                    "tokenize_ms": int((t_tokenize - t0) * 1000),
                })

            # 3. BM25 评分
            scores = bm25.get_scores(query_tokens)
            t_score = time.perf_counter()

            # 4. 按分数降序排列
            ranked_indices = sorted(
                range(len(scores)), key=lambda i: scores[i], reverse=True
            )

            candidate_count = len(scores)
            results: list[RetrievalResult] = []
            for idx in ranked_indices:
                score = float(scores[idx])
                # 过滤低于阈值的 chunk：小语料下 IDF 可能为负，极端负分表示完全无关
                if score < min_score:
                    continue
                doc_id, chunk_index = doc_ids[idx]
                results.append(RetrievalResult(
                    doc_id=doc_id,
                    chunk_index=chunk_index,
                    content=chunk_contents[idx],
                    score=score,
                ))

            # 5. 截取 top_k
            results = results[:top_k]

            logger.info("BM25 检索完成: kb_id=%d, %d 条结果", kb_id, len(results))
            return RetrievalOutput(
                results=results,
                total=len(results),
                stats={
                    "redis_cache": cache_type,
                    "tokenize_ms": int((t_tokenize - t0) * 1000),
                    "score_ms": int((t_score - t_index) * 1000),
                    "candidate_count": candidate_count,
                    "result_count": len(results),
                },
            )

        except RetrievalServiceException:
            raise
        except Exception as e:
            logger.exception("BM25 检索异常: kb_id=%d", kb_id)
            raise RetrievalServiceException(f"BM25 检索失败: {e}") from e

    async def _get_bm25_index(
        self, kb_id: int
    ) -> tuple[BM25Okapi | None, list[tuple[int, int]], list[str], str]:
        """获取 BM25Okapi 实例 + 文档元数据。

        优先级：进程内缓存 → Redis 缓存 → MySQL 懒加载。

        Returns:
            (bm25实例|None(空语料), [(doc_id, chunk_index), ...], [chunk_content, ...], cache_type)
        """
        t0 = time.perf_counter()

        # 1. 尝试进程内缓存（<1ms）
        local = _get_local_cache(kb_id)
        if local is not None:
            bm25, doc_ids, contents = local
            t_local = time.perf_counter()
            logger.info(
                "BM25_PERF cache=local_hit chunks=%d cost=%.3fms",
                len(doc_ids), (t_local - t0) * 1000,
            )
            return bm25, doc_ids, contents, "local_hit"

        # 2. 尝试 Redis 缓存
        cache_key = _build_cache_key(kb_id)
        try:
            t_redis_start = time.perf_counter()
            cached = await self._async_redis.get(cache_key)
            t_redis_get = time.perf_counter()
            logger.info(
                "BM25_REDIS_GET key=%s time=%.3fs cached=%s",
                cache_key,
                t_redis_get - t_redis_start,
                cached is not None,
            )
            if cached is not None:
                data = json.loads(cached)
                t_deserialize = time.perf_counter()
                tokens = data["tokens"]
                doc_ids = [tuple(pair) for pair in data["doc_ids"]]
                contents = data.get("contents", [])
                bm25 = BM25Okapi(tokens) if tokens else None
                t_build = time.perf_counter()

                # 回填进程内缓存
                _set_local_cache(kb_id, bm25, doc_ids, contents)

                logger.info(
                    "BM25_PERF cache=redis_hit chunks=%d redis_get=%.3fs deserialize=%.3fs build=%.3fs total=%.3fs",
                    len(tokens),
                    t_redis_get - t_redis_start,
                    t_deserialize - t_redis_get,
                    t_build - t_deserialize,
                    t_build - t0,
                )
                return bm25, doc_ids, contents, "redis_hit"
        except Exception as e:
            logger.warning("Redis 读取 BM25 缓存失败（降级为直查）: %s", e)

        # 3. 缓存未命中 → 从 MySQL 加载
        result = await self._load_and_cache(kb_id, cache_key)
        t_end = time.perf_counter()
        logger.info("BM25_PERF cache=miss total=%.3fs", t_end - t0)
        return (*result, "miss")

    async def _load_and_cache(
        self, kb_id: int, cache_key: str
    ) -> tuple[BM25Okapi | None, list[tuple[int, int]], list[str]]:
        """从 MySQL 加载 chunks → jieba 分词 → 缓存到 Redis + 进程内 → 构建 BM25Okapi。"""
        t0 = time.perf_counter()
        async with self._session_factory() as db:
            result = await db.execute(
                select(Chunk.doc_id, Chunk.chunk_index, Chunk.content)
                .where(Chunk.kb_id == kb_id)
                .order_by(Chunk.doc_id, Chunk.chunk_index)
            )
            rows = result.all()
        t_mysql = time.perf_counter()

        if not rows:
            logger.info("KB %d 无 chunk 数据", kb_id)
            # 空结果也缓存（避免反复查 MySQL），短 TTL
            try:
                await self._async_redis.setex(cache_key, 60, json.dumps({
                    "doc_ids": [], "tokens": [], "contents": [],
                }))
            except Exception:
                pass
            # BM25Okapi 不接受空语料，返回 None + 空列表
            _set_local_cache(kb_id, None, [], [])
            return None, [], []

        # jieba 分词（最昂贵步骤）
        doc_ids: list[tuple[int, int]] = []
        tokenized_corpus: list[list[str]] = []
        contents: list[str] = []
        for row in rows:
            doc_ids.append((row.doc_id, row.chunk_index))
            tokenized_corpus.append(_tokenize(row.content))
            contents.append(row.content)
        t_jieba = time.perf_counter()

        # 写入 Redis 缓存
        try:
            cache_data = json.dumps({
                "doc_ids": doc_ids,
                "tokens": tokenized_corpus,
                "contents": contents,
            }, ensure_ascii=False)
            await self._async_redis.setex(cache_key, settings.BM25_CACHE_TTL, cache_data)
            logger.info("BM25 缓存已写入: kb_id=%d, %d chunks", kb_id, len(doc_ids))
        except Exception as e:
            logger.warning("Redis 写入 BM25 缓存失败（不影响检索）: %s", e)
        t_redis = time.perf_counter()

        bm25 = BM25Okapi(tokenized_corpus)
        t_build = time.perf_counter()

        # 写入进程内缓存
        _set_local_cache(kb_id, bm25, doc_ids, contents)

        logger.info(
            "BM25_LOAD chunks=%d mysql=%.3fs jieba=%.3fs redis_write=%.3fs build=%.3fs total=%.3fs",
            len(rows),
            t_mysql - t0,
            t_jieba - t_mysql,
            t_redis - t_jieba,
            t_build - t_redis,
            t_build - t0,
        )
        return bm25, doc_ids, contents


async def invalidate_bm25_cache_async(kb_id: int) -> None:
    """清除指定 KB 的 BM25 缓存（异步版本，用于 FastAPI 上下文）。

    同时清除进程内缓存和 Redis 缓存。
    """
    # 清除进程内缓存
    if kb_id in _local_cache:
        del _local_cache[kb_id]
        logger.info("BM25 进程内缓存已清除: kb_id=%d", kb_id)

    # 清除 Redis 缓存
    try:
        async_redis = await get_async_redis()
        cache_key = _build_cache_key(kb_id)
        await async_redis.delete(cache_key)
        logger.info("BM25 Redis 缓存已清除: kb_id=%d", kb_id)
    except Exception as e:
        logger.warning("BM25 Redis 缓存清除失败（非致命）: kb_id=%d, error=%s", kb_id, e)


def invalidate_bm25_cache(kb_id: int) -> None:
    """清除指定 KB 的 BM25 缓存（同步版本，用于 Celery 任务）。

    仅清除 Redis 缓存（进程内缓存由 FastAPI 进程管理，Celery 进程无需清除）。
    """
    cache_key = _build_cache_key(kb_id)
    try:
        sync_redis = get_redis()
        sync_redis.delete(cache_key)
        logger.info("BM25 Redis 缓存已清除（同步）: kb_id=%d", kb_id)
    except Exception as e:
        logger.warning("BM25 Redis 缓存清除失败（非致命）: kb_id=%d, error=%s", kb_id, e)
