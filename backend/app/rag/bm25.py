"""BM25 关键词检索器 — rank-bm25 + jieba 分词 + Redis 缓存

对齐 ARCHITECTURE.md §5.1.1 / §6.2 / §7.2：
- 每个 KB 独立索引，Redis 缓存 tokenized corpus（TTL=300s）
- 懒加载：查询时未命中则从 MySQL 加载 + jieba 分词 + 写入 Redis
- BM25Okapi 实例化（轻量，纯 NumPy 计算，<50ms）
"""

import json
import logging

import jieba
import redis
from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import RetrievalServiceException
from app.models.chunk import Chunk
from app.rag.retriever import RetrievalOutput, RetrievalResult

from app.config import settings

logger = logging.getLogger(__name__)

# Redis key 模式：bm25_tokens:{kb_id}
BM25_CACHE_KEY_PREFIX = "bm25_tokens"


def _build_cache_key(kb_id: int) -> str:
    """构建 Redis 缓存 key"""
    return f"{BM25_CACHE_KEY_PREFIX}:{kb_id}"


def _tokenize(text: str) -> list[str]:
    """jieba 中文分词"""
    return jieba.lcut(text)


class BM25Retriever:
    """BM25 关键词检索器

    流程：查询分词 → 获取 BM25 索引（Redis 缓存 / MySQL 懒加载）→ BM25Okapi 评分 → 返回 top_k
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        session_factory: async_sessionmaker[AsyncSession],
    ):
        self._redis = redis_client
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
            RetrievalOutput: 标准化检索结果
        """
        if not query or not query.strip():
            logger.warning("查询内容为空，跳过 BM25 检索")
            return RetrievalOutput()

        try:
            # 1. 查询分词
            query_tokens = _tokenize(query)

            # 2. 获取 BM25 索引（Redis 缓存 + MySQL 懒加载）
            bm25, doc_ids, chunk_contents = await self._get_bm25_index(kb_id)

            if not doc_ids or bm25 is None:
                logger.info("KB %d 无文档数据，BM25 检索返回空", kb_id)
                return RetrievalOutput()

            # 3. BM25 评分
            scores = bm25.get_scores(query_tokens)

            # 4. 按分数降序排列
            ranked_indices = sorted(
                range(len(scores)), key=lambda i: scores[i], reverse=True
            )

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
            return RetrievalOutput(results=results, total=len(results))

        except RetrievalServiceException:
            raise
        except Exception as e:
            logger.exception("BM25 检索异常: kb_id=%d", kb_id)
            raise RetrievalServiceException(f"BM25 检索失败: {e}") from e

    async def _get_bm25_index(
        self, kb_id: int
    ) -> tuple[BM25Okapi | None, list[tuple[int, int]], list[str]]:
        """获取 BM25Okapi 实例 + 文档元数据。

        优先从 Redis 缓存加载；未命中则从 MySQL 懒加载并回填缓存。

        Returns:
            (bm25实例|None(空语料), [(doc_id, chunk_index), ...], [chunk_content, ...])
        """
        cache_key = _build_cache_key(kb_id)

        # 尝试从 Redis 缓存加载
        try:
            cached = self._redis.get(cache_key)
            if cached is not None:
                data = json.loads(cached)
                tokens = data["tokens"]
                doc_ids = [tuple(pair) for pair in data["doc_ids"]]
                contents = data.get("contents", [])
                bm25 = BM25Okapi(tokens)
                logger.debug("BM25 缓存命中: kb_id=%d, %d chunks", kb_id, len(tokens))
                return bm25, doc_ids, contents
        except Exception as e:
            logger.warning("Redis 读取 BM25 缓存失败（降级为直查）: %s", e)

        # 缓存未命中 → 从 MySQL 加载
        return await self._load_and_cache(kb_id, cache_key)

    async def _load_and_cache(
        self, kb_id: int, cache_key: str
    ) -> tuple[BM25Okapi | None, list[tuple[int, int]], list[str]]:
        """从 MySQL 加载 chunks → jieba 分词 → 缓存到 Redis → 构建 BM25Okapi。"""
        async with self._session_factory() as db:
            result = await db.execute(
                select(Chunk.doc_id, Chunk.chunk_index, Chunk.content)
                .where(Chunk.kb_id == kb_id)
                .order_by(Chunk.doc_id, Chunk.chunk_index)
            )
            rows = result.all()

        if not rows:
            logger.info("KB %d 无 chunk 数据", kb_id)
            # 空结果也缓存（避免反复查 MySQL），短 TTL
            try:
                self._redis.setex(cache_key, 60, json.dumps({
                    "doc_ids": [], "tokens": [], "contents": [],
                }))
            except Exception:
                pass
            # BM25Okapi 不接受空语料，返回 None + 空列表
            return None, [], []

        # jieba 分词（最昂贵步骤）
        doc_ids: list[tuple[int, int]] = []
        tokenized_corpus: list[list[str]] = []
        contents: list[str] = []
        for row in rows:
            doc_ids.append((row.doc_id, row.chunk_index))
            tokenized_corpus.append(_tokenize(row.content))
            contents.append(row.content)

        # 写入 Redis 缓存
        try:
            cache_data = json.dumps({
                "doc_ids": doc_ids,
                "tokens": tokenized_corpus,
                "contents": contents,
            }, ensure_ascii=False)
            self._redis.setex(cache_key, settings.BM25_CACHE_TTL, cache_data)
            logger.info("BM25 缓存已写入: kb_id=%d, %d chunks", kb_id, len(doc_ids))
        except Exception as e:
            logger.warning("Redis 写入 BM25 缓存失败（不影响检索）: %s", e)

        bm25 = BM25Okapi(tokenized_corpus)
        return bm25, doc_ids, contents


def invalidate_bm25_cache(redis_client: redis.Redis, kb_id: int) -> None:
    """清除指定 KB 的 BM25 缓存。

    在文档入库完成 / 文档删除完成后由 Celery 任务调用。
    """
    cache_key = _build_cache_key(kb_id)
    try:
        redis_client.delete(cache_key)
        logger.info("BM25 缓存已清除: kb_id=%d", kb_id)
    except Exception as e:
        logger.warning("BM25 缓存清除失败（非致命）: kb_id=%d, error=%s", kb_id, e)
