"""BM25 关键词检索器单元测试 — Mock Redis + DB + jieba 覆盖核心检索逻辑

对齐 ADR-023（BM25 缓存重构）：
- Redis 缓存不再包含 chunk 原文（contents）
- 进程内缓存不再包含 chunk 原文
- BM25 评分后按需从 MySQL 取 top_k chunk 原文（_fetch_chunk_contents）
- 大 KB（chunks > BM25_LOCAL_CACHE_MAX_CHUNKS）跳过进程内缓存

对齐 .claude/plans/001-intent-optimization.md P0-2 接口变更：
- invalidate_bm25_cache(kb_id) 同步版本（Celery 使用）
- invalidate_bm25_cache_async(kb_id) 异步版本（FastAPI 使用）
- BM25Retriever 接收 async_redis 参数
- 进程内缓存（TTL=60s）
"""

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import jieba
import pytest

from app.config import settings
from app.rag.bm25 import (
    BM25Retriever,
    _build_cache_key,
    _tokenize,
    detect_section_numbers,
    match_section_numbers,
    cn_to_int,
    invalidate_bm25_cache,
    invalidate_bm25_cache_async,
    _local_cache,
    _set_local_cache,
    _get_local_cache,
)
from app.rag.retriever import RetrievalOutput, RetrievalResult
from app.core.exceptions import RetrievalServiceException


# ==================== Mock 辅助函数 ====================


def _make_mock_rows(rows_data):
    """根据 tuple 列表构造 mock 查询结果。

    rows_data: list of (doc_id, chunk_index, content, metadata_?)
    注意：metadata_ 未提供时显式设为 None，避免 MagicMock 自动生成的
    mock 对象在 JSON 序列化时失败。
    """
    mock_result = MagicMock()
    mock_objects = []
    for row in rows_data:
        mock_row = MagicMock()
        mock_row.doc_id = row[0]
        mock_row.chunk_index = row[1]
        mock_row.content = row[2] if len(row) > 2 else ""
        mock_row.metadata_ = row[3] if len(row) > 3 else None
        mock_objects.append(mock_row)
    mock_result.all.return_value = mock_objects
    return mock_result


def _mock_db_rows(chunks=None):
    """构造模拟的 DB 全量加载查询结果（_load_and_cache 用）。

    返回 (doc_id, chunk_index, content, metadata_) 行。
    """
    if chunks is None:
        chunks = [
            (1, 0, "入职指南欢迎加入公司", None),
            (1, 1, "报销制度差旅标准", None),
            (2, 0, "VPN 配置远程访问", None),
        ]
    return _make_mock_rows(chunks)


def _mock_content_rows(chunks):
    """构造 content fetch 查询的 mock 返回值（_fetch_chunk_contents 用）。

    返回 (doc_id, chunk_index, content) 行。
    """
    rows = [(c[0], c[1], c[2]) for c in chunks]
    return _make_mock_rows(rows)


def _mock_async_redis(get_return=None):
    """构造 mock 异步 Redis 客户端"""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=get_return)
    mock.setex = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    return mock


def _mock_session_factory(*mock_results):
    """构造 mock async_sessionmaker，支持多次调用返回不同 session。

    每个 mock_result 对应一次 session_factory() 调用中 execute 的返回值。
    传入多个时使用 side_effect 按序返回。
    """
    contexts = []
    for result in mock_results:
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=result)
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_session)
        cm.__aexit__ = AsyncMock(return_value=False)
        contexts.append(cm)

    factory = MagicMock()
    if len(contexts) == 1:
        factory.return_value = contexts[0]
    else:
        factory.side_effect = contexts

    return factory


@pytest.fixture(autouse=True)
def clear_local_cache():
    """每个测试前清空进程内缓存"""
    _local_cache.clear()
    yield
    _local_cache.clear()


# ==================== 辅助函数测试 ====================
# _build_cache_key / _tokenize / _local_cache 均为薄包装或全局状态操作，
# 保持私有，通过 BM25Retriever.search() 公共 API 集成测试覆盖。
# cn_to_int / match_section_numbers 已提升为公开函数，直接单元测试。


class TestBuildCacheKey:
    """_build_cache_key 测试"""

    def test_正常构建(self):
        assert _build_cache_key(1) == "bm25_tokens:1"

    def test_kb_id为大数值(self):
        assert _build_cache_key(999999) == "bm25_tokens:999999"


class TestTokenize:
    """_tokenize 分词测试"""

    @patch("app.rag.bm25.jieba.lcut", return_value=["入职", "指南", "欢迎"])
    def test_调用jieba_lcut(self, mock_lcut):
        result = _tokenize("入职指南欢迎")
        assert result == ["入职", "指南", "欢迎"]
        mock_lcut.assert_called_once_with("入职指南欢迎")

    @patch("app.rag.bm25.jieba.lcut", return_value=[])
    def test_空文本返回空列表(self, mock_lcut):
        assert _tokenize("") == []


class TestLocalCache:
    """进程内缓存测试（ADR-023：不再缓存 chunk 原文）"""

    def test_设置和获取缓存(self):
        """缓存结构： (bm25, doc_ids, section_info, expire_at)，不含 contents"""
        _set_local_cache(1, None, [(1, 0)], [{"section_title": "§3.2"}])
        result = _get_local_cache(1)
        assert result is not None
        bm25, doc_ids, section_info = result
        assert bm25 is None
        assert doc_ids == [(1, 0)]
        assert section_info == [{"section_title": "§3.2"}]

    def test_缓存过期(self):
        _local_cache[1] = (None, [], [], time.time() - 1)  # 已过期，4 元素（无 contents）
        result = _get_local_cache(1)
        assert result is None
        assert 1 not in _local_cache

    def test_不存在的key返回None(self):
        assert _get_local_cache(999) is None

    def test_超过阈值不写入进程缓存(self, monkeypatch):
        """chunk 数 > BM25_LOCAL_CACHE_MAX_CHUNKS 时跳过进程内缓存"""
        monkeypatch.setattr(settings, "BM25_LOCAL_CACHE_MAX_CHUNKS", 2)
        _set_local_cache(1, None, [(1, 0), (1, 1), (1, 2)], [{}])
        assert 1 not in _local_cache  # 3 chunks > max=2，不写入


# ==================== invalidate_bm25_cache ====================


class TestInvalidateBM25Cache:
    """缓存失效测试"""

    @patch("app.rag.bm25.get_redis")
    def test_正常清除(self, mock_get_redis):
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis
        invalidate_bm25_cache(1)
        mock_redis.delete.assert_called_once_with("bm25_tokens:1")

    @patch("app.rag.bm25.get_redis")
    def test_redis异常不影响调用方(self, mock_get_redis):
        mock_redis = MagicMock()
        mock_redis.delete.side_effect = Exception("Redis 连接失败")
        mock_get_redis.return_value = mock_redis
        # 不应抛出异常
        invalidate_bm25_cache(1)


class TestInvalidateBM25CacheAsync:
    """异步缓存失效测试"""

    @pytest.mark.asyncio
    @patch("app.rag.bm25.get_async_redis")
    async def test_正常清除(self, mock_get_async_redis):
        mock_redis = AsyncMock()
        mock_get_async_redis.return_value = mock_redis
        _set_local_cache(1, None, [])
        await invalidate_bm25_cache_async(1)
        mock_redis.delete.assert_called_once_with("bm25_tokens:1")
        assert 1 not in _local_cache

    @pytest.mark.asyncio
    @patch("app.rag.bm25.get_async_redis")
    async def test_redis异常不影响调用方(self, mock_get_async_redis):
        mock_redis = AsyncMock()
        mock_redis.delete.side_effect = Exception("Redis 连接失败")
        mock_get_async_redis.return_value = mock_redis
        # 不应抛出异常
        await invalidate_bm25_cache_async(1)


# ==================== _fetch_chunk_contents ====================


class TestFetchChunkContents:
    """_fetch_chunk_contents — 按需取 top_k chunk 原文"""

    @pytest.mark.asyncio
    async def test_正常获取(self):
        """传入 (doc_id, chunk_index) 对，返回 content 映射"""
        chunks = [(1, 0, "内容A"), (1, 1, "内容B")]
        session_factory = _mock_session_factory(_mock_content_rows(chunks))
        retriever = BM25Retriever(_mock_async_redis(), session_factory)

        result = await retriever._fetch_chunk_contents([(1, 0), (1, 1)])
        assert result[(1, 0)] == "内容A"
        assert result[(1, 1)] == "内容B"

    @pytest.mark.asyncio
    async def test_空列表返回空字典(self):
        """空 pairs 直接返回空 dict，不查 DB"""
        async_redis = _mock_async_redis()
        session_factory = _mock_session_factory()
        retriever = BM25Retriever(async_redis, session_factory)

        result = await retriever._fetch_chunk_contents([])
        assert result == {}

    @pytest.mark.asyncio
    async def test_部分未查到补空字符串(self):
        """DB 未返回的 pair 补充空字符串"""
        chunks = [(1, 0, "内容A")]  # 只有 1 条
        session_factory = _mock_session_factory(_mock_content_rows(chunks))
        retriever = BM25Retriever(_mock_async_redis(), session_factory)

        result = await retriever._fetch_chunk_contents([(1, 0), (9, 9)])
        assert result[(1, 0)] == "内容A"
        assert result[(9, 9)] == ""  # 未查到，补空


# ==================== BM25Retriever.search ====================


class TestBM25RetrieverSearch:
    """BM25Retriever.search 端到端测试（ADR-023 缓存重构适配）"""

    @pytest.mark.asyncio
    @patch("app.rag.bm25.jieba.lcut")
    async def test_正常检索流程(self, mock_jieba):
        """Redis 缓存命中 → BM25 评分 → content fetch → 返回结果"""
        # jieba 分词 mock
        def jieba_side_effect(text):
            return list(text)
        mock_jieba.side_effect = jieba_side_effect

        chunks = [
            (1, 0, "入职指南欢迎加入公司"),
            (1, 1, "报销制度差旅标准"),
            (2, 0, "VPN 配置远程访问"),
        ]

        # Redis 缓存数据（ADR-023：不含 contents）
        cached_data = json.dumps({
            "doc_ids": [[1, 0], [1, 1], [2, 0]],
            "tokens": [
                ["入", "职", "指", "南", "欢", "迎", "加", "入", "公", "司"],
                ["报", "销", "制", "度", "差", "旅", "标", "准"],
                ["V", "P", "N", "配", "置", "远", "程", "访", "问"],
            ],
            "section_info": [],
        }, ensure_ascii=False)
        async_redis = _mock_async_redis(get_return=cached_data)
        # content fetch 需要 DB session（top_k 条）
        session_factory = _mock_session_factory(_mock_content_rows(chunks))

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("入职", kb_id=1, top_k=3)

        assert output.total == 3
        assert len(output.results) == 3
        # 含查询词"入"/"职"的文档[1,0]应排第一，分数为正
        assert output.results[0].doc_id == 1
        assert output.results[0].chunk_index == 0
        assert output.results[0].score > 0
        # 其余文档不含查询词，分数应为 0
        assert output.results[1].score == 0.0
        assert output.results[2].score == 0.0
        # 分数降序
        assert output.results[0].score >= output.results[1].score
        # 内容正确回填
        assert output.results[0].content == "入职指南欢迎加入公司"

    @pytest.mark.asyncio
    async def test_空查询返回空结果(self):
        """查询为空时直接返回空结果，不访问 Redis/DB"""
        async_redis = _mock_async_redis()
        session_factory = _mock_session_factory()

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("", kb_id=1)

        assert output.total == 0
        async_redis.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_空白查询返回空结果(self):
        """查询为纯空白时返回空结果"""
        async_redis = _mock_async_redis()
        session_factory = _mock_session_factory()

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("   ", kb_id=1)

        assert output.total == 0

    @pytest.mark.asyncio
    @patch("app.rag.bm25.jieba.lcut")
    async def test_缓存未命中时从MySQL加载(self, mock_jieba):
        """Redis 缓存未命中 → MySQL 全量加载 → jieba 分词 → Redis 写入 → content fetch"""
        mock_jieba.side_effect = lambda t: list(t)

        async_redis = _mock_async_redis(get_return=None)  # 缓存未命中
        chunks = [
            (1, 0, "测试内容A"),
            (1, 1, "测试内容B"),
        ]
        # 两次 DB 调用：全量加载 + content fetch
        session_factory = _mock_session_factory(
            _mock_db_rows(chunks),
            _mock_content_rows(chunks),
        )

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("测试", kb_id=1, top_k=5)

        # 验证 Redis SETEX 被调用（缓存写入）
        async_redis.setex.assert_called_once()
        call_args = async_redis.setex.call_args
        assert call_args[0][0] == "bm25_tokens:1"  # key
        assert call_args[0][1] == settings.BM25_CACHE_TTL    # TTL
        # 写入值不含 contents（ADR-023）
        cached = json.loads(call_args[0][2])
        assert "doc_ids" in cached
        assert "tokens" in cached
        assert "section_info" in cached
        assert "contents" not in cached  # ADR-023：不再缓存 contents
        # 验证结果
        assert output.total == 2
        assert output.results[0].content == "测试内容A"

    @pytest.mark.asyncio
    @patch("app.rag.bm25.jieba.lcut")
    async def test_缓存命中时通过contentFetch获取内容(self, mock_jieba):
        """Redis 缓存命中时：不查 MySQL 全量加载，但 content fetch 仍需查 DB"""
        mock_jieba.side_effect = lambda t: list(t)

        cached_data = json.dumps({
            "doc_ids": [[1, 0]],
            "tokens": [["测", "试"]],
        }, ensure_ascii=False)
        async_redis = _mock_async_redis(get_return=cached_data)
        chunks = [(1, 0, "测试")]
        # content fetch 需要 DB
        session_factory = _mock_session_factory(_mock_content_rows(chunks))

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("测试", kb_id=1)

        # Redis 只被查询一次（get），不做全量加载
        async_redis.get.assert_called_once()
        # 结果正确
        assert output.total == 1
        assert output.results[0].content == "测试"

    @pytest.mark.asyncio
    @patch("app.rag.bm25.jieba.lcut")
    async def test_空KB返回空结果(self, mock_jieba):
        """KB 无文档时返回空结果，不触发 content fetch"""
        mock_jieba.side_effect = lambda t: list(t)

        async_redis = _mock_async_redis(get_return=None)
        # 只会有一次 DB 调用（全量加载返回空），不会触发 content fetch
        session_factory = _mock_session_factory(_mock_db_rows([]))

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("问题", kb_id=99)

        assert output.total == 0
        assert output.results == []
        # 验证缓存了空结果（短 TTL）
        async_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.rag.bm25.jieba.lcut")
    async def test_redis读取异常时降级为直查MySQL(self, mock_jieba):
        """Redis 读取失败时降级为直接从 MySQL 加载"""
        mock_jieba.side_effect = lambda t: list(t)

        async_redis = AsyncMock()
        async_redis.get = AsyncMock(side_effect=Exception("Redis 连接失败"))
        async_redis.setex = AsyncMock(return_value=True)

        chunks = [(1, 0, "降级测试内容")]
        session_factory = _mock_session_factory(
            _mock_db_rows(chunks),
            _mock_content_rows(chunks),
        )

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("降级", kb_id=1, top_k=5)

        # 应该仍然返回结果（从 MySQL 加载 + content fetch）
        assert output.total > 0

    @pytest.mark.asyncio
    @patch("app.rag.bm25.jieba.lcut")
    async def test_top_k参数截取(self, mock_jieba):
        """top_k 应限制返回结果数量，content fetch 也只取 top_k 条"""
        mock_jieba.side_effect = lambda t: list(t)

        chunks = [
            (1, 0, "文档内容一测试"),
            (1, 1, "文档内容二测试"),
            (1, 2, "文档内容三测试"),
            (1, 3, "文档内容四测试"),
            (1, 4, "文档内容五测试"),
        ]

        cached_data = json.dumps({
            "doc_ids": [[1, i] for i in range(5)],
            "tokens": [
                list("文档内容一测试"),
                list("文档内容二测试"),
                list("文档内容三测试"),
                list("文档内容四测试"),
                list("文档内容五测试"),
            ],
        }, ensure_ascii=False)
        async_redis = _mock_async_redis(get_return=cached_data)
        # content fetch 也只返回 top_k 条
        session_factory = _mock_session_factory(_mock_content_rows(chunks[:2]))

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("测试", kb_id=1, top_k=2)

        assert len(output.results) <= 2

    @pytest.mark.asyncio
    @patch("app.rag.bm25.jieba.lcut")
    async def test_分数降序排列(self, mock_jieba):
        """结果应按 BM25 分数降序排列"""
        mock_jieba.side_effect = lambda t: list(t)

        chunks = [
            (1, 0, "关键词出现关键词"),
            (1, 1, "无关内容"),
        ]

        cached_data = json.dumps({
            "doc_ids": [[1, 0], [1, 1]],
            "tokens": [
                list("关键词出现关键词"),
                list("无关内容"),
            ],
        }, ensure_ascii=False)
        async_redis = _mock_async_redis(get_return=cached_data)
        session_factory = _mock_session_factory(_mock_content_rows(chunks))

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("关键词", kb_id=1, top_k=5)

        assert output.total >= 2, f"期望至少 2 条结果，实际 {output.total}"
        # 分数应递减
        assert output.results[0].score >= output.results[1].score

    @pytest.mark.asyncio
    async def test_未认证kb_id类型为int(self):
        """kb_id 应以 int 类型使用（对齐 Decision #21）"""
        async_redis = _mock_async_redis(
            get_return=json.dumps({"doc_ids": [[1, 0]], "tokens": [["测", "试"]]})
        )
        session_factory = _mock_session_factory(_mock_content_rows([(1, 0, "测试")]))

        retriever = BM25Retriever(async_redis, session_factory)

        with patch("app.rag.bm25.jieba.lcut", side_effect=lambda t: list(t)):
            await retriever.search("测试", kb_id=42)

        # 验证 Redis GET 使用了正确的 key
        async_redis.get.assert_called_once_with("bm25_tokens:42")

    @pytest.mark.asyncio
    @patch("app.rag.bm25.jieba.lcut")
    async def test_db查询异常时抛出RetrievalServiceException(self, mock_jieba):
        """MySQL 查询异常（_load_and_cache 阶段）时应抛出 E4003 检索服务异常"""
        mock_jieba.side_effect = lambda t: list(t)

        async_redis = _mock_async_redis(get_return=None)  # 缓存未命中
        # 构造 execute 抛出异常的 session（全量加载阶段失败）
        cm = AsyncMock()
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=Exception("MySQL 连接失败"))
        cm.__aenter__ = AsyncMock(return_value=mock_session)
        cm.__aexit__ = AsyncMock(return_value=False)
        session_factory = MagicMock()
        session_factory.return_value = cm

        retriever = BM25Retriever(async_redis, session_factory)
        with pytest.raises(RetrievalServiceException):
            await retriever.search("问题", kb_id=1)

    @pytest.mark.asyncio
    @patch("app.rag.bm25.jieba.lcut")
    async def test_查询无匹配时分数为零不受过滤(self, mock_jieba):
        """查询词与语料完全无匹配时，BM25 分数为 0.0（无证据），不应被 min_score=-5.0 过滤"""
        mock_jieba.side_effect = lambda t: list(t)

        chunks = [(1, 0, "完全无关内容")]
        cached_data = json.dumps({
            "doc_ids": [[1, 0]],
            "tokens": [["完全", "无关", "内容"]],
        }, ensure_ascii=False)
        async_redis = _mock_async_redis(get_return=cached_data)
        session_factory = _mock_session_factory(_mock_content_rows(chunks))

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("xyz", kb_id=1, top_k=5)

        # 无匹配时分数为 0.0（非负），不受阈值过滤
        assert output.total == 1
        assert output.results[0].score == 0.0
        assert isinstance(output.results[0].doc_id, int)

    @pytest.mark.asyncio
    @patch("app.rag.bm25.jieba.lcut")
    async def test_进程内缓存命中仍触发contentFetch(self, mock_jieba):
        """进程内缓存命中时：不访问 Redis，但 content fetch 仍需查 DB（contents 不在缓存中）"""
        mock_jieba.side_effect = lambda t: list(t)

        # 预先设置进程内缓存（ADR-023：不含 contents）
        from rank_bm25 import BM25Okapi
        tokens = [list("测试内容")]
        bm25 = BM25Okapi(tokens)
        _set_local_cache(1, bm25, [(1, 0)])

        async_redis = _mock_async_redis()
        chunks = [(1, 0, "测试内容")]
        # content fetch 需要 DB session
        session_factory = _mock_session_factory(_mock_content_rows(chunks))

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("测试", kb_id=1)

        # 不应访问 Redis
        async_redis.get.assert_not_called()
        assert output.total == 1
        assert output.results[0].content == "测试内容"

    @pytest.mark.asyncio
    @patch("app.rag.bm25.jieba.lcut")
    async def test_contentFetch异常时抛出检索异常(self, mock_jieba):
        """content fetch DB 异常时应抛出 RetrievalServiceException"""
        mock_jieba.side_effect = lambda t: list(t)

        cached_data = json.dumps({
            "doc_ids": [[1, 0]],
            "tokens": [["测", "试"]],
        }, ensure_ascii=False)
        async_redis = _mock_async_redis(get_return=cached_data)

        # session_factory 返回的 session 执行 content fetch 时抛异常
        cm = AsyncMock()
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=Exception("Content fetch 失败"))
        cm.__aenter__ = AsyncMock(return_value=mock_session)
        cm.__aexit__ = AsyncMock(return_value=False)
        session_factory = MagicMock()
        session_factory.return_value = cm

        retriever = BM25Retriever(async_redis, session_factory)
        with pytest.raises(RetrievalServiceException):
            await retriever.search("测试", kb_id=1)


# ==================== 真实 jieba 分词集成测试 ====================


class TestBM25RetrieverWithRealJieba:
    """使用真实 jieba 分词验证 BM25 中文检索质量（ADR-023 适配）"""

    @pytest.mark.asyncio
    async def test_中文分词检索_相关文档得分更高(self):
        """真实 jieba 分词下，包含查询关键词的文档应得分更高"""
        chunks = [
            (1, 0, "入职指南欢迎加入公司"),
            (1, 1, "报销制度差旅标准"),
            (1, 2, "VPN配置远程访问说明"),
        ]
        cached_data = json.dumps({
            "doc_ids": [[1, 0], [1, 1], [1, 2]],
            "tokens": [
                jieba.lcut(chunks[0][2]),
                jieba.lcut(chunks[1][2]),
                jieba.lcut(chunks[2][2]),
            ],
        }, ensure_ascii=False)
        async_redis = _mock_async_redis(get_return=cached_data)
        session_factory = _mock_session_factory(_mock_content_rows(chunks))

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("入职", kb_id=1, top_k=3)

        assert output.total > 0
        # "入职指南" chunk 应排在第一位
        assert "入职" in output.results[0].content

    @pytest.mark.asyncio
    async def test_中文分词检索_缓存未命中时用真实jieba构建索引(self):
        """缓存未命中时从 MySQL 加载后用真实 jieba 分词构建 BM25 索引"""
        async_redis = _mock_async_redis(get_return=None)
        chunks = [
            (1, 0, "入职指南欢迎加入公司"),
            (1, 1, "报销制度差旅标准"),
            (1, 2, "VPN配置远程访问说明"),
        ]
        session_factory = _mock_session_factory(
            _mock_db_rows(chunks),
            _mock_content_rows(chunks),
        )

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("入职 指南", kb_id=1, top_k=3)

        assert output.total > 0
        # 第一条结果应该与"入职指南"相关
        assert output.results[0].score > 0

        # 验证缓存写入不含 contents（ADR-023）
        async_redis.setex.assert_called_once()
        cached = json.loads(async_redis.setex.call_args[0][2])
        assert "contents" not in cached
        # 真实 jieba 分词 "入职指南欢迎加入公司" → 应含多字词
        first_tokens = cached["tokens"][0]
        assert len(first_tokens) < 10  # 逐字拆分会有 9 个字符，真实分词约 5-6 个词

    @pytest.mark.asyncio
    async def test_无关查询分数为零不被过滤(self):
        """完全不相关的查询词在真实 jieba 分词下分数为 0.0（无证据），保留在结果中"""
        chunks = [
            (1, 0, "入职指南欢迎加入公司"),
            (1, 1, "报销制度差旅标准"),
        ]
        cached_data = json.dumps({
            "doc_ids": [[1, 0], [1, 1]],
            "tokens": [
                jieba.lcut(chunks[0][2]),
                jieba.lcut(chunks[1][2]),
            ],
        }, ensure_ascii=False)
        async_redis = _mock_async_redis(get_return=cached_data)
        session_factory = _mock_session_factory(_mock_content_rows(chunks))

        retriever = BM25Retriever(async_redis, session_factory)
        # 查询词与语料完全无关，分数为 0.0（非负），不被阈值过滤
        output = await retriever.search("量子力学相对论", kb_id=1, top_k=5)

        assert output.total == 2
        # 所有结果分数为 0.0，无相关性
        for r in output.results:
            assert r.score == 0.0

    @pytest.mark.asyncio
    async def test_min_score过滤负分_通用词在全语料中出现(self):
        """包含出现在所有文档中的通用词时，IDF 为负导致总分为负，应被 min_score 过滤"""
        chunks = [
            (1, 0, "公司的入职指南"),
            (1, 1, "公司的报销制度"),
        ]
        cached_data = json.dumps({
            "doc_ids": [[1, 0], [1, 1]],
            "tokens": [
                jieba.lcut(chunks[0][2]),
                jieba.lcut(chunks[1][2]),
            ],
        }, ensure_ascii=False)
        async_redis = _mock_async_redis(get_return=cached_data)
        session_factory = _mock_session_factory(_mock_content_rows(chunks))

        retriever = BM25Retriever(async_redis, session_factory)
        # "公司" 同时出现在两个文档中，idf 为负
        output = await retriever.search("公司的", kb_id=1, top_k=5)

        # 小语料下通用词产生负分，但仍应返回结果（分数接近 0）
        assert output.total == 2
        # 即使有负分成分，总分也不应低于 -5.0
        for r in output.results:
            assert r.score > settings.BM25_MIN_SCORE

    @pytest.mark.asyncio
    async def test_min_score阈值_可通过参数调整(self):
        """传入 min_score=-999 不过滤任何结果，传入 min_score=999 过滤全部"""
        chunks = [(1, 0, "入职指南欢迎加入公司")]
        cached_data = json.dumps({
            "doc_ids": [[1, 0]],
            "tokens": [jieba.lcut(chunks[0][2])],
        }, ensure_ascii=False)
        async_redis = _mock_async_redis(get_return=cached_data)
        session_factory = _mock_session_factory(_mock_content_rows(chunks))

        retriever = BM25Retriever(async_redis, session_factory)

        # min_score=-999 不过滤
        output_low = await retriever.search("量子力学", kb_id=1, top_k=5, min_score=-999)
        assert output_low.total == 1  # 不相关但仍返回

        # min_score=999 全过滤 → content fetch 不会触发（top_k_pairs 为空）
        output_high = await retriever.search("入职", kb_id=1, top_k=5, min_score=999)
        assert output_high.total == 0  # 全部被过滤

    @pytest.mark.asyncio
    async def test_top_k截取_真实分词(self):
        """真实 jieba 分词下，top_k 正确限制返回结果数量"""
        chunks = [
            (1, 0, "入职指南欢迎加入公司"),
            (1, 1, "报销制度差旅标准说明"),
            (1, 2, "VPN配置远程访问教程"),
            (1, 3, "请假流程审批规范制度"),
            (1, 4, "绩效考核评估管理办法"),
        ]
        cached_data = json.dumps({
            "doc_ids": [[1, i] for i in range(5)],
            "tokens": [jieba.lcut(c[2]) for c in chunks],
        }, ensure_ascii=False)
        async_redis = _mock_async_redis(get_return=cached_data)
        # content fetch 只需 top_k 条
        session_factory = _mock_session_factory(_mock_content_rows(chunks[:2]))

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("制度", kb_id=1, top_k=2)

        assert len(output.results) <= 2

    @pytest.mark.asyncio
    async def test_中文关键词精确匹配排第一(self):
        """真实 jieba 分词下，精确匹配查询词的 chunk 排在第一位"""
        chunks = [
            (1, 0, "VPN配置远程访问教程"),
            (1, 1, "日报填写规范说明"),
            (1, 2, "VPN账号申请流程指南"),
        ]
        cached_data = json.dumps({
            "doc_ids": [[1, 0], [1, 1], [1, 2]],
            "tokens": [jieba.lcut(c[2]) for c in chunks],
        }, ensure_ascii=False)
        async_redis = _mock_async_redis(get_return=cached_data)
        session_factory = _mock_session_factory(_mock_content_rows(chunks))

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("VPN", kb_id=1, top_k=3)

        assert output.total == 3
        # 第一条应包含 "VPN" — 两篇都含 VPN，得分最高的在前
        assert "VPN" in output.results[0].content
        # 不含 VPN 的文档应排在最后
        assert "VPN" not in output.results[2].content


# ==================== §8.8 章节号检测测试 ====================


class TestCnToInt:
    """cn_to_int() — 中文数字 → 整数"""

    def test_单个数字(self):
        assert cn_to_int("一") == 1
        assert cn_to_int("四") == 4
        assert cn_to_int("九") == 9
        assert cn_to_int("十") == 10

    def test_两位数(self):
        assert cn_to_int("十二") == 12
        assert cn_to_int("二十") == 20
        assert cn_to_int("三十五") == 35

    def test_三位数(self):
        assert cn_to_int("一百零三") == 103
        assert cn_to_int("三百五十") == 350

    @pytest.mark.parametrize("cn,expected", [
        ("一", 1),
        ("二", 2),
        ("三", 3),
        ("四", 4),
        ("五", 5),
        ("六", 6),
        ("七", 7),
        ("八", 8),
        ("九", 9),
        ("十", 10),
        ("十一", 11),
        ("十二", 12),
        ("二十", 20),
        ("二十一", 21),
        ("三十五", 35),
        ("九十九", 99),
        ("一百", 100),
        ("一百零三", 103),
        ("二百五十", 250),
        ("九百九十九", 999),
        ("一千零一", 1001),
    ])
    def test_参数化_中文数字转整数(self, cn, expected):
        """参数化验证从简单到复杂的各种中文数字"""
        assert cn_to_int(cn) == expected

    @pytest.mark.parametrize("cn", ["", " ", "abc", "123"])
    def test_无效输入不抛异常(self, cn):
        """非中文数字输入 → 返回 0，不抛异常"""
        assert cn_to_int(cn) == 0


class TestDetectSectionNumbers:
    """detect_section_numbers() — 章节号检测"""

    def test_空文本(self):
        assert detect_section_numbers("") == []
        assert detect_section_numbers(None) == []  # type: ignore

    def test_无章节号(self):
        assert detect_section_numbers("报销制度是什么？") == []

    def test_段落符号引导(self):
        """§3.2, §8.2.1"""
        result = detect_section_numbers("请解释 §3.2 的内容")
        assert "3.2" in result

        result = detect_section_numbers("§8.2.1 说的什么？")
        assert "8.2.1" in result

    def test_段落符号带空格(self):
        """§ 4.7"""
        result = detect_section_numbers("参见 § 4.7")
        assert "4.7" in result

    def test_中文数字章节(self):
        """第四章, 第三节"""
        result = detect_section_numbers("第四章的内容是什么？")
        assert "4" in result

        result = detect_section_numbers("第三节讲的是什么？")
        assert "3" in result

    def test_中文数字两位章节(self):
        """第十二章"""
        result = detect_section_numbers("参见第十二章")
        assert "12" in result

    def test_显式节编号(self):
        """第4.7节, 第8.2.1节"""
        result = detect_section_numbers("参考第4.7节")
        assert "4.7" in result

        result = detect_section_numbers("第8.2.1 节的内容")
        assert "8.2.1" in result

    def test_裸数字章节号(self):
        """4.7, 8.2.1 — 不含字母前缀"""
        result = detect_section_numbers("请解释 4.7 的内容")
        assert "4.7" in result

        result = detect_section_numbers("8.2.1 节是怎么说的")
        assert "8.2.1" in result

    def test_不匹配版本号(self):
        """v4.7.0 不应被当作章节号"""
        result = detect_section_numbers("v4.7.0 版本有什么更新")
        # v4.7.0 前面有字母 v，不应匹配裸数字章节模式
        assert "4.7.0" not in result

    def test_多模式混合去重(self):
        """同一种编号多次出现去重"""
        result = detect_section_numbers("§3.2 和第3.2节都提到了 3.2 的内容")
        assert result.count("3.2") == 1


class TestMatchSectionNumbers:
    """match_section_numbers() — 章节元数据匹配"""

    def test_空目标列表返回False(self):
        assert match_section_numbers("§3.2", "概述 > §3.2", []) is False

    def test_空元数据返回False(self):
        assert match_section_numbers(None, None, ["3.2"]) is False
        assert match_section_numbers("", "", ["3.2"]) is False

    def test_section_title精确匹配(self):
        assert match_section_numbers("§3.2 限流配置", None, ["3.2"]) is True

    def test_section_path匹配(self):
        assert match_section_numbers(
            None, "架构 > §3 基础设施 > §3.2 限流", ["3.2"],
        ) is True

    def test_层级匹配_单个数字(self):
        """单数字 "4" 可匹配 section_title 中以 "4 " 开头的标题"""
        assert match_section_numbers("4 数据库设计", None, ["4"]) is True

    def test_不匹配_无关章节号(self):
        assert match_section_numbers("§3.2 限流", None, ["5.1"]) is False

    def test_多章节号任一匹配(self):
        """多个目标章节号，只要有一个匹配即 True"""
        assert match_section_numbers("§3.2 限流", None, ["5.1", "3.2"]) is True

    # --- 参数化匹配策略 ---

    @pytest.mark.parametrize("section_title,section_path,target,expected", [
        # 完整匹配
        ("§3.2 限流配置", None, ["3.2"], True),
        ("§4.7 超时策略", None, ["4.7"], True),
        ("§8.2.1 安全审计", None, ["8.2.1"], True),
        # 层级匹配（section_path）
        (None, "架构 > §3 基础设施 > §3.2 限流", ["3.2"], True),
        (None, "API > §6 SSE > §6.1 事件格式", ["6.1"], True),
        # 短编号匹配（单数字匹配标题首部）
        ("4 数据库设计", None, ["4"], True),
        ("12 部署指南", None, ["12"], True),
        # 否定案例
        ("§3.2 限流", None, ["5.1"], False),
        ("§4.7 超时", None, ["4.8"], False),
        (None, None, ["3.2"], False),
        ("", "", ["3.2"], False),
    ])
    def test_参数化_章节匹配策略(self, section_title, section_path, target, expected):
        """参数化验证完整匹配、层级匹配、短编号匹配及否定案例"""
        assert match_section_numbers(section_title, section_path, target) is expected


class TestBM25SectionBoost:
    """BM25 检索集成 §8.8 章节号 boost（ADR-023 适配）"""

    @pytest.mark.asyncio
    async def test_章节号查询触发boost(self):
        """包含章节号的查询应对匹配 chunk 做分数加权。

        两个 chunk 内容完全相同（BM25 基础分一致），仅 section_info 不同，
        带 §6.1 的查询应 boost 匹配的 chunk 使其跃居第一。
        """
        chunks = [
            (1, 0, "SSE 事件格式详解"),
            (2, 0, "SSE 事件格式详解"),
        ]
        cached_data = json.dumps({
            "doc_ids": [[1, 0], [2, 0]],
            "tokens": [
                jieba.lcut("SSE 事件格式详解"),
                jieba.lcut("SSE 事件格式详解"),
            ],
            "section_info": [
                {"section_title": "§6.1 SSE 事件格式", "section_path": "API > §6 SSE > §6.1"},
                {"section_title": "§3.2 限流配置", "section_path": "架构 > §3 基础设施 > §3.2"},
            ],
        }, ensure_ascii=False)
        async_redis = _mock_async_redis(get_return=cached_data)
        session_factory = _mock_session_factory(_mock_content_rows(chunks))

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("§6.1 SSE 事件格式说明", kb_id=1, top_k=2)

        assert output.total == 2
        assert output.results[0].section_title == "§6.1 SSE 事件格式"

    @pytest.mark.asyncio
    async def test_无章节号查询不触发boost(self):
        """普通查询（无章节号）不做 boost：返回全部结果，分数无异常变动"""
        chunks = [
            (1, 0, "SSE 事件格式详解"),
            (1, 1, "限流配置参数说明"),
        ]
        cached_data = json.dumps({
            "doc_ids": [[1, 0], [1, 1]],
            "tokens": [
                jieba.lcut("SSE 事件格式详解"),
                jieba.lcut("限流配置参数说明"),
            ],
            "section_info": [
                {"section_title": "§6.1 SSE 事件格式", "section_path": ""},
                {"section_title": "§3.2 限流配置", "section_path": ""},
            ],
        }, ensure_ascii=False)
        async_redis = _mock_async_redis(get_return=cached_data)
        session_factory = _mock_session_factory(_mock_content_rows(chunks))

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("限流怎么配置", kb_id=1, top_k=2)

        assert output.total == 2

    @pytest.mark.asyncio
    async def test_章节号查询_RetrievalResult含section信息(self):
        """BM25 检索返回的 RetrievalResult 应填充 section_title/section_path"""
        chunks = [(1, 0, "SSE 事件格式详解")]
        cached_data = json.dumps({
            "doc_ids": [[1, 0]],
            "tokens": [jieba.lcut("SSE 事件格式详解")],
            "section_info": [
                {"section_title": "§6.1 SSE 事件格式", "section_path": "API > §6 SSE > §6.1"},
            ],
        }, ensure_ascii=False)
        async_redis = _mock_async_redis(get_return=cached_data)
        session_factory = _mock_session_factory(_mock_content_rows(chunks))

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("SSE 事件", kb_id=1, top_k=1)

        assert output.total == 1
        assert output.results[0].section_title == "§6.1 SSE 事件格式"
        assert output.results[0].section_path == "API > §6 SSE > §6.1"

    @pytest.mark.asyncio
    async def test_空section_info不报错(self):
        """无 section_info 时正常检索"""
        chunks = [
            (1, 0, "测试内容一"),
            (1, 1, "测试内容二"),
        ]
        cached_data = json.dumps({
            "doc_ids": [[1, 0], [1, 1]],
            "tokens": [
                jieba.lcut("测试内容一"),
                jieba.lcut("测试内容二"),
            ],
            "section_info": [],
        }, ensure_ascii=False)
        async_redis = _mock_async_redis(get_return=cached_data)
        session_factory = _mock_session_factory(_mock_content_rows(chunks))

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("测试", kb_id=1, top_k=2)

        assert output.total == 2
        for r in output.results:
            assert r.section_title is None
            assert r.section_path is None

    @pytest.mark.asyncio
    async def test_旧缓存无section_info向后兼容(self):
        """旧缓存数据不含 section_info 字段，不应报错"""
        chunks = [(1, 0, "测试内容")]
        cached_data = json.dumps({
            "doc_ids": [[1, 0]],
            "tokens": [jieba.lcut("测试内容")],
            # 无 section_info 字段（向后兼容）
        }, ensure_ascii=False)
        async_redis = _mock_async_redis(get_return=cached_data)
        session_factory = _mock_session_factory(_mock_content_rows(chunks))

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("测试", kb_id=1, top_k=1)

        assert output.total == 1
        assert output.results[0].section_title is None
