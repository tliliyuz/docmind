"""BM25 关键词检索器 — rank-bm25 + jieba 分词 + Redis 缓存 + 进程内缓存

对齐 ARCHITECTURE.md §5.1.1 / §6.2 / §7.2 / .claude/plans/001-intent-optimization.md P0-2：
- 每个 KB 独立索引，Redis 缓存 tokenized corpus（TTL=300s）
- 进程内 dict 缓存（TTL=60s），cache hit < 10ms
- 异步 Redis 客户端（线程池包装，Windows 兼容性好），避免阻塞事件循环
- 懒加载：查询时未命中则从 MySQL 加载 + jieba 分词 + 写入 Redis
- BM25Okapi 实例化（轻量，纯 NumPy 计算，<50ms）

对齐 ROADMAP.md §8.8（章节号 BM25 增强）：
- detect_section_numbers(): 检测用户提问中的章节号模式
- 搜索时对 section_title/section_path 匹配的 chunk 做 BM25 分数加权
- 缓存结构新增 section_info 列表，存储每个 chunk 的章节元数据

内存优化（ADR-023 BM25 缓存重构，2026-06-18）：
- Redis 缓存：仅存 tokens + doc_ids + section_info，**不存 chunk 原文**
- 进程内缓存：仅存 BM25Okapi + doc_ids + section_info，**不存 chunk 原文**
- chunk 原文在 BM25 评分后按需从 MySQL 取 top_k 条（O(1) vs O(N)）
- 大知识库保护：chunk 数超过 BM25_LOCAL_CACHE_MAX_CHUNKS 时跳过进程内缓存
"""

import json
import logging
import os
import re
import time
from typing import Any

import jieba
from rank_bm25 import BM25Okapi
from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.core.exceptions import RetrievalServiceException
from app.core.redis_client import get_async_redis, get_redis
from app.models.chunk import Chunk
from app.rag.retriever import RetrievalOutput, RetrievalResult

logger = logging.getLogger(__name__)

# ==================== §8.8 章节号检测正则 ====================

# § 符号引导的章节号（§3.2, § 4.7, §8.2.1, §6.1.2）
_SECTION_SYMBOL_PATTERN = re.compile(r'§\s*(\d+(?:\.\d+)*)')

# 中文章节表述（第四章, 第三节, 第十二章）
_CN_CHAPTER_PATTERN = re.compile(r'第([一二三四五六七八九十百千]+)[章节]')

# 显式节编号（"第4.7节", "第8.2.1节", "第3.2 节"）
_EXPLICIT_SECTION_PATTERN = re.compile(r'第\s*(\d+(?:\.\d+)+)\s*节')

# 裸数字章节号（4.7, 8.2.1）— 至少 2 段数字，避免匹配单版本号如 "3.0"
# 且不包含字母前缀（排除 v4.7.0 等版本号）
_BARE_SECTION_NUM_PATTERN = re.compile(r'(?<![a-zA-Z§第])(\d+\.[\d.]+)(?![a-zA-Z])')

# 中文数字 → int 转换表
_CN_DIGIT_MAP = {
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
    '百': 100, '千': 1000,
}

# Redis key 模式：bm25_tokens:{kb_id}
BM25_CACHE_KEY_PREFIX = "bm25_tokens"

# 进程内缓存：{kb_id: (bm25, doc_ids, section_info, expire_at)}
# 注意：不再缓存 chunk 原文（contents），BM25 评分后按需从 MySQL 取 top_k 条
_local_cache: dict[int, tuple[BM25Okapi | None, list, list, float]] = {}
_LOCAL_TTL = settings.BM25_LOCAL_CACHE_TTL  # 进程内缓存 TTL（秒）
# 注意：_MAX_CHUNKS 不在模块加载时固化，_set_local_cache 内从 settings 实时读取，
# 以便测试中 monkeypatch settings.BM25_LOCAL_CACHE_MAX_CHUNKS 生效

# psutil 按需加载（内存监控用，仅在大 KB 加载时打印）


def _get_memory_mb() -> float:
    """返回当前进程 RSS 内存（MB），psutil 不可用时返回 -1"""
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except Exception:
        return -1.0


def _build_cache_key(kb_id: int) -> str:
    """构建 Redis 缓存 key"""
    return f"{BM25_CACHE_KEY_PREFIX}:{kb_id}"


def _tokenize(text: str) -> list[str]:
    """jieba 中文分词"""
    return jieba.lcut(text)


def cn_to_int(cn: str) -> int:
    """中文字数字 → 整数（如 '四'→4, '十二'→12, '一百零三'→103）。

    纯计算逻辑，包含多位数、进位、零的处理等边界条件。
    """
    result = 0
    current = 0
    for ch in cn:
        val = _CN_DIGIT_MAP.get(ch)
        if val is None:
            continue
        if val >= 10:
            if current == 0:
                current = 1
            result += current * val
            current = 0
        else:
            current = val
    result += current
    return result


def detect_section_numbers(question: str) -> list[str]:
    """检测用户提问中的章节号模式。

    对齐 ROADMAP.md §8.8：
    - §3.2 → ["3.2"]
    - 第四章 → ["4"]
    - 第4.7节 → ["4.7"]
    - 8.2.1 → ["8.2.1"]
    - 同时含多种模式时返回所有匹配

    Args:
        question: 用户问题

    Returns:
        检测到的章节号列表（数字格式，如 "3.2"、"4"、"8.2.1"），去重
    """
    if not question:
        return []

    numbers: list[str] = []

    # § 符号引导（§3.2, §8.2.1）
    for m in _SECTION_SYMBOL_PATTERN.finditer(question):
        numbers.append(m.group(1))

    # 显式节编号（第4.7节, 第8.2.1节）
    for m in _EXPLICIT_SECTION_PATTERN.finditer(question):
        numbers.append(m.group(1))

    # 中文章节（第四章, 第三节）
    for m in _CN_CHAPTER_PATTERN.finditer(question):
        try:
            num = str(cn_to_int(m.group(1)))
            numbers.append(num)
        except (ValueError, KeyError):
            pass

    # 裸数字章节号（4.7, 8.2.1）— 排除版本号
    for m in _BARE_SECTION_NUM_PATTERN.finditer(question):
        numbers.append(m.group(1))

    # 去重并保持顺序
    seen: set[str] = set()
    result: list[str] = []
    for n in numbers:
        if n not in seen:
            seen.add(n)
            result.append(n)

    if result:
        logger.info("检测到章节号: %s", result)

    return result


def match_section_numbers(
    section_title: str | None,
    section_path: str | None,
    target_numbers: list[str],
) -> bool:
    """检查章节元数据是否匹配目标章节号。

    匹配策略（§8.8 章节号增强核心业务规则）：
    - 完整匹配：section_title 包含目标编号（如 "4.7" 匹配 "§4.7 限流"）
    - 层级匹配：section_path 中任一层级包含目标编号
    - 单个数字匹配：短编号（如 "4"）同时匹配 section_title 中以该数字开头的标题

    Args:
        section_title: chunk 所属章节标题
        section_path: chunk 所属章节路径
        target_numbers: 目标章节号列表

    Returns:
        是否匹配
    """
    if not target_numbers:
        return False

    search_text = ""
    if section_title:
        search_text += section_title + " "
    if section_path:
        search_text += section_path

    if not search_text.strip():
        return False

    for num in target_numbers:
        if num in search_text:
            return True
        # 单个数字：同时检查以 "§数字" 或 ".数字" 开头的片段
        if '.' not in num:
            if f"§{num}" in search_text or f".{num}" in search_text or f" {num}." in search_text or f" {num} " in search_text or search_text.startswith(f"{num} "):
                return True

    return False


def _get_local_cache(kb_id: int) -> tuple[BM25Okapi | None, list, list] | None:
    """从进程内缓存获取，过期返回 None。

    Returns:
        (bm25, doc_ids, section_info) 或 None
    """
    if kb_id in _local_cache:
        bm25, doc_ids, section_info, expire_at = _local_cache[kb_id]
        if time.time() < expire_at:
            return bm25, doc_ids, section_info
        else:
            del _local_cache[kb_id]
    return None


def _set_local_cache(
    kb_id: int,
    bm25: BM25Okapi | None,
    doc_ids: list,
    section_info: list[dict] | None = None,
) -> None:
    """写入进程内缓存。

    注意：不再缓存 chunk 原文（contents），BM25 评分后按需从 MySQL 取 top_k 条。
    超过 BM25_LOCAL_CACHE_MAX_CHUNKS 阈值的 KB 不写入进程内缓存。
    """
    # 大 KB 保护：超过阈值不写入进程内缓存（阈值从 settings 实时读取，便于测试 monkeypatch）
    if len(doc_ids) > settings.BM25_LOCAL_CACHE_MAX_CHUNKS:
        logger.info(
            "BM25 跳过进程内缓存（chunks=%d > max=%d）: kb_id=%d",
            len(doc_ids), settings.BM25_LOCAL_CACHE_MAX_CHUNKS, kb_id,
        )
        return

    _local_cache[kb_id] = (
        bm25, doc_ids,
        section_info if section_info is not None else [],
        time.time() + _LOCAL_TTL,
    )


class BM25Retriever:
    """BM25 关键词检索器

    流程：查询分词 → 获取 BM25 索引（进程内缓存 → Redis 缓存 → MySQL 懒加载）
    → BM25Okapi 评分 → 按需取 top_k chunk 原文 → 返回 top_k
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
            #    注意：不再返回 chunk 原文，只返回 bm25 + doc_ids + section_info
            bm25, doc_ids, section_info_list, cache_type = await self._get_bm25_index(kb_id)
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

            # 3.5 章节号检测 + BM25 加权 boost（§8.8）
            # 注意：小语料下 BM25 IDF 可能为负导致总分为负，
            # 负分 × boost 会更负（排名下降），因此：
            # - 正分 → × boost（提升排名）
            # - 负分 → ÷ boost（向零靠近，减少惩罚）
            section_numbers = detect_section_numbers(query)
            boosted_count = 0
            if section_numbers and section_info_list:
                boost = settings.BM25_SECTION_BOOST_FACTOR
                for i in range(len(scores)):
                    si = section_info_list[i] if i < len(section_info_list) else {}
                    if match_section_numbers(
                        si.get("section_title") or None,
                        si.get("section_path") or None,
                        section_numbers,
                    ):
                        base = float(scores[i])
                        if base > 0:
                            scores[i] = base * boost
                        elif base < 0:
                            scores[i] = base / boost
                        boosted_count += 1
                if boosted_count:
                    logger.info(
                        "BM25 章节号 boost: %d/%d chunks 加权 (x%.1f/÷%.1f), 章节号=%s",
                        boosted_count, len(scores), boost, boost, section_numbers,
                    )

            # 4. 按分数降序排列，过滤低于阈值的 chunk
            ranked_indices = sorted(
                range(len(scores)), key=lambda i: scores[i], reverse=True
            )

            candidate_count = len(scores)
            top_k_pairs: list[tuple[int, int]] = []
            top_k_scores: list[float] = []
            top_k_section_info: list[dict] = []
            for idx in ranked_indices:
                score = float(scores[idx])
                if score < min_score:
                    continue
                if len(top_k_pairs) >= top_k:
                    break
                top_k_pairs.append(doc_ids[idx])
                top_k_scores.append(score)
                si = section_info_list[idx] if idx < len(section_info_list) else {}
                top_k_section_info.append(si)

            # 5. 按需从 MySQL 取 top_k chunk 原文（O(1) 而非 O(N)）
            t_before_fetch = time.perf_counter()
            content_map = await self._fetch_chunk_contents(top_k_pairs) if top_k_pairs else {}
            t_fetch = time.perf_counter()

            # 6. 组装结果
            results: list[RetrievalResult] = []
            for (doc_id, chunk_index), score, si in zip(top_k_pairs, top_k_scores, top_k_section_info):
                results.append(RetrievalResult(
                    doc_id=doc_id,
                    chunk_index=chunk_index,
                    content=content_map.get((doc_id, chunk_index), ""),
                    score=score,
                    section_title=si.get("section_title") or None,
                    section_path=si.get("section_path") or None,
                ))

            logger.info("BM25 检索完成: kb_id=%d, %d 条结果", kb_id, len(results))
            return RetrievalOutput(
                results=results,
                total=len(results),
                stats={
                    "redis_cache": cache_type,
                    "tokenize_ms": int((t_tokenize - t0) * 1000),
                    "score_ms": int((t_score - t_index) * 1000),
                    "fetch_ms": int((t_fetch - t_before_fetch) * 1000),
                    "candidate_count": candidate_count,
                    "result_count": len(results),
                },
            )

        except RetrievalServiceException:
            raise
        except Exception as e:
            logger.exception("BM25 检索异常: kb_id=%d", kb_id)
            raise RetrievalServiceException(f"BM25 检索失败: {e}") from e

    async def _fetch_chunk_contents(
        self, pairs: list[tuple[int, int]]
    ) -> dict[tuple[int, int], str]:
        """从 MySQL 按 (doc_id, chunk_index) 批量取 chunk 原文。

        仅在 BM25 评分后调用，只取 top_k 条（通常 ≤10），
        避免加载全库 chunk 原文到内存。

        Args:
            pairs: [(doc_id, chunk_index), ...] 需要取内容的 chunk 标识

        Returns:
            {(doc_id, chunk_index): content} 映射
        """
        if not pairs:
            return {}

        async with self._session_factory() as db:
            result = await db.execute(
                select(Chunk.doc_id, Chunk.chunk_index, Chunk.content)
                .where(tuple_(Chunk.doc_id, Chunk.chunk_index).in_(pairs))
            )
            rows = result.all()

        content_map: dict[tuple[int, int], str] = {}
        for row in rows:
            content_map[(row.doc_id, row.chunk_index)] = row.content

        # 补全未查到的 pair（理论上不应发生，但做防御性处理）
        for pair in pairs:
            if pair not in content_map:
                content_map[pair] = ""

        return content_map

    async def _get_bm25_index(
        self, kb_id: int
    ) -> tuple[BM25Okapi | None, list[tuple[int, int]], list[dict], str]:
        """获取 BM25Okapi 实例 + 文档元数据。

        优先级：进程内缓存 → Redis 缓存 → MySQL 懒加载。

        注意：不再返回 chunk 原文列表，BM25 评分后按需从 MySQL 取 top_k 条。

        Returns:
            (bm25实例|None, [(doc_id, chunk_index), ...], [section_info, ...], cache_type)
        """
        t0 = time.perf_counter()

        # 1. 尝试进程内缓存（<1ms）
        local = _get_local_cache(kb_id)
        if local is not None:
            bm25, doc_ids, section_info = local
            t_local = time.perf_counter()
            logger.info(
                "BM25_PERF cache=local_hit chunks=%d cost=%.3fms",
                len(doc_ids), (t_local - t0) * 1000,
            )
            return bm25, doc_ids, section_info, "local_hit"

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
                # section_info 向后兼容旧缓存（无此字段时默认空列表）
                section_info = data.get("section_info", [])
                bm25 = BM25Okapi(tokens) if tokens else None
                t_build = time.perf_counter()

                # 回填进程内缓存（仅 doc_ids + section_info，无 chunk 原文）
                _set_local_cache(kb_id, bm25, doc_ids, section_info)

                logger.info(
                    "BM25_PERF cache=redis_hit chunks=%d redis_get=%.3fs deserialize=%.3fs build=%.3fs total=%.3fs",
                    len(tokens),
                    t_redis_get - t_redis_start,
                    t_deserialize - t_redis_get,
                    t_build - t_deserialize,
                    t_build - t0,
                )
                return bm25, doc_ids, section_info, "redis_hit"
        except Exception as e:
            logger.warning("Redis 读取 BM25 缓存失败（降级为直查）: %s", e)

        # 3. 缓存未命中 → 从 MySQL 加载
        result = await self._load_and_cache(kb_id, cache_key)
        t_end = time.perf_counter()
        logger.info("BM25_PERF cache=miss total=%.3fs", t_end - t0)
        return (*result, "miss")

    async def _load_and_cache(
        self, kb_id: int, cache_key: str
    ) -> tuple[BM25Okapi | None, list[tuple[int, int]], list[dict]]:
        """从 MySQL 加载 chunks → jieba 分词 → 缓存到 Redis + 进程内 → 构建 BM25Okapi。

        内存优化（ADR-023）：
        - Redis 缓存仅存 tokens + doc_ids + section_info，**不存 chunk 原文**
        - 进程内缓存仅存 BM25Okapi + doc_ids + section_info，超阈值则跳过
        - 添加 psutil 内存监控日志，用于 OOM 诊断

        Returns:
            (bm25实例|None, doc_ids, section_info)
        """
        t0 = time.perf_counter()
        mem0 = _get_memory_mb()
        logger.info("BM25_LOAD_START kb_id=%d mem=%.1fMB", kb_id, mem0)

        async with self._session_factory() as db:
            result = await db.execute(
                select(Chunk.doc_id, Chunk.chunk_index, Chunk.content, Chunk.metadata_)
                .where(Chunk.kb_id == kb_id)
                .order_by(Chunk.doc_id, Chunk.chunk_index)
            )
            rows = result.all()
        t_mysql = time.perf_counter()
        mem_mysql = _get_memory_mb()
        logger.info(
            "BM25_LOAD mysql_done kb_id=%d rows=%d time=%.3fs mem=%.1fMB",
            kb_id, len(rows), t_mysql - t0, mem_mysql,
        )

        if not rows:
            logger.info("KB %d 无 chunk 数据", kb_id)
            # 空结果也缓存（避免反复查 MySQL），短 TTL
            try:
                await self._async_redis.setex(cache_key, 60, json.dumps({
                    "doc_ids": [], "tokens": [], "section_info": [],
                }))
            except Exception:
                pass
            # BM25Okapi 不接受空语料，返回 None + 空列表
            _set_local_cache(kb_id, None, [], [])
            return None, [], []

        # jieba 分词（最昂贵步骤）
        doc_ids: list[tuple[int, int]] = []
        tokenized_corpus: list[list[str]] = []
        section_info: list[dict] = []
        for row in rows:
            doc_ids.append((row.doc_id, row.chunk_index))
            tokenized_corpus.append(_tokenize(row.content))
            meta = row.metadata_ or {}
            section_info.append({
                "section_title": meta.get("section_title", ""),
                "section_path": meta.get("section_path", ""),
            })
        t_jieba = time.perf_counter()
        mem_jieba = _get_memory_mb()
        logger.info(
            "BM25_LOAD jieba_done kb_id=%d chunks=%d time=%.3fs mem=%.1fMB",
            kb_id, len(doc_ids), t_jieba - t_mysql, mem_jieba,
        )

        # 写入 Redis 缓存（仅 tokens + doc_ids + section_info，不存 chunk 原文）
        try:
            cache_data = json.dumps({
                "doc_ids": doc_ids,
                "tokens": tokenized_corpus,
                "section_info": section_info,
            }, ensure_ascii=False)
            await self._async_redis.setex(cache_key, settings.BM25_CACHE_TTL, cache_data)
            logger.info("BM25 缓存已写入: kb_id=%d, %d chunks", kb_id, len(doc_ids))
        except Exception as e:
            logger.warning("Redis 写入 BM25 缓存失败（不影响检索）: %s", e)
        t_redis = time.perf_counter()

        bm25 = BM25Okapi(tokenized_corpus)
        t_build = time.perf_counter()
        mem_build = _get_memory_mb()
        logger.info(
            "BM25_LOAD bm25_done kb_id=%d chunks=%d time=%.3fs mem=%.1fMB",
            kb_id, len(doc_ids), t_build - t_redis, mem_build,
        )

        # 写入进程内缓存（超阈值则跳过，仅存 BM25Okapi + doc_ids + section_info）
        _set_local_cache(kb_id, bm25, doc_ids, section_info)

        logger.info(
            "BM25_LOAD done kb_id=%d chunks=%d "
            "mysql=%.3fs jieba=%.3fs redis_write=%.3fs build=%.3fs total=%.3fs "
            "mem_start=%.1fMB mem_end=%.1fMB delta=%.1fMB",
            kb_id, len(rows),
            t_mysql - t0,
            t_jieba - t_mysql,
            t_redis - t_jieba,
            t_build - t_redis,
            t_build - t0,
            mem0, mem_build, mem_build - mem0,
        )
        return bm25, doc_ids, section_info


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
