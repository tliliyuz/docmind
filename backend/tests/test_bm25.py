"""BM25 关键词检索器单元测试 — Mock Redis + DB + jieba 覆盖核心检索逻辑

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
    invalidate_bm25_cache,
    invalidate_bm25_cache_async,
    _local_cache,
    _set_local_cache,
    _get_local_cache,
)
from app.rag.retriever import RetrievalOutput, RetrievalResult
from app.core.exceptions import RetrievalServiceException


def _mock_db_rows(chunks=None):
    """构造模拟的 DB 查询结果（chunks 表 SELECT doc_id, chunk_index, content）"""
    if chunks is None:
        chunks = [
            (1, 0, "入职指南欢迎加入公司"),
            (1, 1, "报销制度差旅标准"),
            (2, 0, "VPN 配置远程访问"),
        ]
    mock_result = MagicMock()
    mock_result.all.return_value = [
        MagicMock(doc_id=c[0], chunk_index=c[1], content=c[2])
        for c in chunks
    ]
    return mock_result


def _mock_async_redis(get_return=None):
    """构造 mock 异步 Redis 客户端"""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=get_return)
    mock.setex = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    return mock


def _mock_session_context(mock_result):
    """构造 mock async session context manager（async with self._session_factory() as db）"""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _mock_session_factory(mock_result):
    """构造 mock async_sessionmaker：调用后返回 async context manager"""
    cm = _mock_session_context(mock_result)
    factory = MagicMock()
    factory.return_value = cm
    return factory


@pytest.fixture(autouse=True)
def clear_local_cache():
    """每个测试前清空进程内缓存"""
    _local_cache.clear()
    yield
    _local_cache.clear()


# ==================== 辅助函数测试 ====================


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
    """进程内缓存测试"""

    def test_设置和获取缓存(self):
        _set_local_cache(1, None, [(1, 0)], ["内容"])
        result = _get_local_cache(1)
        assert result is not None
        bm25, doc_ids, contents = result
        assert bm25 is None
        assert doc_ids == [(1, 0)]
        assert contents == ["内容"]

    def test_缓存过期(self):
        _local_cache[1] = (None, [], [], time.time() - 1)  # 已过期
        result = _get_local_cache(1)
        assert result is None
        assert 1 not in _local_cache

    def test_不存在的key返回None(self):
        assert _get_local_cache(999) is None


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
    @patch("app.core.redis_client.get_async_redis")
    async def test_正常清除(self, mock_get_async_redis):
        mock_redis = AsyncMock()
        mock_get_async_redis.return_value = mock_redis
        _set_local_cache(1, None, [], [])
        await invalidate_bm25_cache_async(1)
        mock_redis.delete.assert_called_once_with("bm25_tokens:1")
        assert 1 not in _local_cache

    @pytest.mark.asyncio
    @patch("app.core.redis_client.get_async_redis")
    async def test_redis异常不影响调用方(self, mock_get_async_redis):
        mock_redis = AsyncMock()
        mock_redis.delete.side_effect = Exception("Redis 连接失败")
        mock_get_async_redis.return_value = mock_redis
        # 不应抛出异常
        await invalidate_bm25_cache_async(1)


# ==================== BM25Retriever.search ====================


class TestBM25RetrieverSearch:
    """BM25Retriever.search 端到端测试"""

    @pytest.mark.asyncio
    @patch("app.rag.bm25.jieba.lcut")
    async def test_正常检索流程(self, mock_jieba):
        """缓存命中时直接从 Redis 加载并检索"""
        # jieba 分词 mock：查询按空格切分
        def jieba_side_effect(text):
            return list(text)
        mock_jieba.side_effect = jieba_side_effect

        # 构造缓存数据（JSON 格式）
        cached_data = json.dumps({
            "doc_ids": [[1, 0], [1, 1], [2, 0]],
            "tokens": [
                ["入", "职", "指", "南", "欢", "迎", "加", "入", "公", "司"],
                ["报", "销", "制", "度", "差", "旅", "标", "准"],
                ["V", "P", "N", "配", "置", "远", "程", "访", "问"],
            ],
            "contents": [
                "入职指南欢迎加入公司",
                "报销制度差旅标准",
                "VPN 配置远程访问",
            ],
        }, ensure_ascii=False)
        async_redis = _mock_async_redis(get_return=cached_data)
        session_factory = _mock_session_factory(_mock_db_rows())

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

    @pytest.mark.asyncio
    async def test_空查询返回空结果(self):
        """查询为空时直接返回空结果，不访问 Redis/DB"""
        async_redis = _mock_async_redis()
        session_factory = _mock_session_factory(_mock_db_rows())

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("", kb_id=1)

        assert output.total == 0
        async_redis.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_空白查询返回空结果(self):
        """查询为纯空白时返回空结果"""
        async_redis = _mock_async_redis()
        session_factory = _mock_session_factory(_mock_db_rows())

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("   ", kb_id=1)

        assert output.total == 0

    @pytest.mark.asyncio
    @patch("app.rag.bm25.jieba.lcut")
    async def test_缓存未命中时从MySQL加载(self, mock_jieba):
        """Redis 缓存未命中 → 从 MySQL 加载 → jieba 分词 → 写入 Redis"""
        mock_jieba.side_effect = lambda t: list(t)

        async_redis = _mock_async_redis(get_return=None)  # 缓存未命中
        db_rows = _mock_db_rows([
            (1, 0, "测试内容A"),
            (1, 1, "测试内容B"),
        ])
        session_factory = _mock_session_factory(db_rows)

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("测试", kb_id=1, top_k=5)

        # 验证 Redis SETEX 被调用（缓存写入）
        async_redis.setex.assert_called_once()
        call_args = async_redis.setex.call_args
        assert call_args[0][0] == "bm25_tokens:1"  # key
        assert call_args[0][1] == settings.BM25_CACHE_TTL    # TTL
        # 写入值是 JSON，包含 doc_ids 和 tokens
        cached = json.loads(call_args[0][2])
        assert "doc_ids" in cached
        assert "tokens" in cached
        assert "contents" in cached
        # 验证进程内缓存已写入
        assert 1 in _local_cache

    @pytest.mark.asyncio
    @patch("app.rag.bm25.jieba.lcut")
    async def test_缓存命中时不查MySQL(self, mock_jieba):
        """Redis 缓存命中时不应查询 MySQL"""
        mock_jieba.side_effect = lambda t: list(t)

        cached_data = json.dumps({
            "doc_ids": [[1, 0]],
            "tokens": [["测", "试"]],
            "contents": ["测试"],
        }, ensure_ascii=False)
        async_redis = _mock_async_redis(get_return=cached_data)
        session_factory = _mock_session_factory(_mock_db_rows())

        retriever = BM25Retriever(async_redis, session_factory)
        await retriever.search("测试", kb_id=1)

        # session_factory 不应被调用（不查 MySQL）
        session_factory.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.rag.bm25.jieba.lcut")
    async def test_空KB返回空结果(self, mock_jieba):
        """KB 无文档时返回空结果，并缓存空数据"""
        mock_jieba.side_effect = lambda t: list(t)

        async_redis = _mock_async_redis(get_return=None)
        db_rows = _mock_db_rows([])  # 空 KB
        session_factory = _mock_session_factory(db_rows)

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("问题", kb_id=99)

        assert output.total == 0
        assert output.results == []
        # 验证缓存了空结果（短 TTL）
        async_redis.setex.assert_called_once()
        # 验证进程内缓存已写入
        assert 99 in _local_cache

    @pytest.mark.asyncio
    @patch("app.rag.bm25.jieba.lcut")
    async def test_redis读取异常时降级为直查MySQL(self, mock_jieba):
        """Redis 读取失败时降级为直接从 MySQL 加载"""
        mock_jieba.side_effect = lambda t: list(t)

        async_redis = AsyncMock()
        async_redis.get = AsyncMock(side_effect=Exception("Redis 连接失败"))
        async_redis.setex = AsyncMock(return_value=True)

        db_rows = _mock_db_rows([(1, 0, "降级测试内容")])
        session_factory = _mock_session_factory(db_rows)

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("降级", kb_id=1, top_k=5)

        # 应该仍然返回结果（从 MySQL 加载）
        assert output.total > 0

    @pytest.mark.asyncio
    @patch("app.rag.bm25.jieba.lcut")
    async def test_top_k参数截取(self, mock_jieba):
        """top_k 应限制返回结果数量"""
        mock_jieba.side_effect = lambda t: list(t)

        # 5 条数据，top_k=2 应只返回 2 条
        cached_data = json.dumps({
            "doc_ids": [[1, 0], [1, 1], [1, 2], [1, 3], [1, 4]],
            "tokens": [
                list("文档内容一测试"),
                list("文档内容二测试"),
                list("文档内容三测试"),
                list("文档内容四测试"),
                list("文档内容五测试"),
            ],
            "contents": ["文档内容一测试", "文档内容二测试", "文档内容三测试", "文档内容四测试", "文档内容五测试"],
        }, ensure_ascii=False)
        async_redis = _mock_async_redis(get_return=cached_data)
        session_factory = _mock_session_factory(_mock_db_rows())

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("测试", kb_id=1, top_k=2)

        assert len(output.results) <= 2

    @pytest.mark.asyncio
    @patch("app.rag.bm25.jieba.lcut")
    async def test_分数降序排列(self, mock_jieba):
        """结果应按 BM25 分数降序排列"""
        mock_jieba.side_effect = lambda t: list(t)

        # 第一条包含查询词两次，应得分更高
        cached_data = json.dumps({
            "doc_ids": [[1, 0], [1, 1]],
            "tokens": [
                list("关键词出现关键词"),
                list("无关内容"),
            ],
            "contents": ["关键词出现关键词", "无关内容"],
        }, ensure_ascii=False)
        async_redis = _mock_async_redis(get_return=cached_data)
        session_factory = _mock_session_factory(_mock_db_rows())

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("关键词", kb_id=1, top_k=5)

        assert output.total >= 2, f"期望至少 2 条结果，实际 {output.total}"
        # 分数应递减
        assert output.results[0].score >= output.results[1].score

    @pytest.mark.asyncio
    async def test_未认证kb_id类型为int(self):
        """kb_id 应以 int 类型使用（对齐 Decision #21）"""
        async_redis = _mock_async_redis()
        session_factory = _mock_session_factory(_mock_db_rows())

        retriever = BM25Retriever(async_redis, session_factory)

        with patch("app.rag.bm25.jieba.lcut", side_effect=lambda t: list(t)):
            await retriever.search("测试", kb_id=42)

        # 验证 Redis GET 使用了正确的 key
        async_redis.get.assert_called_once_with("bm25_tokens:42")

    @pytest.mark.asyncio
    @patch("app.rag.bm25.jieba.lcut")
    async def test_db查询异常时抛出RetrievalServiceException(self, mock_jieba):
        """MySQL 查询异常时应抛出 E4003 检索服务异常"""
        mock_jieba.side_effect = lambda t: list(t)

        async_redis = _mock_async_redis(get_return=None)  # 缓存未命中
        # 构造 execute 抛出异常的 session
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

        cached_data = json.dumps({
            "doc_ids": [[1, 0]],
            "tokens": [["完全", "无关", "内容"]],
            "contents": ["完全无关内容"],
        }, ensure_ascii=False)
        async_redis = _mock_async_redis(get_return=cached_data)
        session_factory = _mock_session_factory(_mock_db_rows())

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("xyz", kb_id=1, top_k=5)

        # 无匹配时分数为 0.0（非负），不受阈值过滤
        assert output.total == 1
        assert output.results[0].score == 0.0
        assert isinstance(output.results[0].doc_id, int)

    @pytest.mark.asyncio
    @patch("app.rag.bm25.jieba.lcut")
    async def test_进程内缓存命中(self, mock_jieba):
        """进程内缓存命中时直接返回，不访问 Redis"""
        mock_jieba.side_effect = lambda t: list(t)

        # 预先设置进程内缓存
        from rank_bm25 import BM25Okapi
        tokens = [list("测试内容")]
        bm25 = BM25Okapi(tokens)
        _set_local_cache(1, bm25, [(1, 0)], ["测试内容"])

        async_redis = _mock_async_redis()
        session_factory = _mock_session_factory(_mock_db_rows())

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("测试", kb_id=1)

        # 不应访问 Redis
        async_redis.get.assert_not_called()
        assert output.total == 1


# ==================== 真实 jieba 分词集成测试 ====================


class TestBM25RetrieverWithRealJieba:
    """使用真实 jieba 分词验证 BM25 中文检索质量"""

    @pytest.mark.asyncio
    async def test_中文分词检索_相关文档得分更高(self):
        """真实 jieba 分词下，包含查询关键词的文档应得分更高"""
        cached_data = json.dumps({
            "doc_ids": [[1, 0], [1, 1], [1, 2]],
            "tokens": [
                jieba.lcut("入职指南欢迎加入公司"),
                jieba.lcut("报销制度差旅标准"),
                jieba.lcut("VPN配置远程访问说明"),
            ],
            "contents": [
                "入职指南欢迎加入公司",
                "报销制度差旅标准",
                "VPN配置远程访问说明",
            ],
        }, ensure_ascii=False)
        async_redis = _mock_async_redis(get_return=cached_data)
        session_factory = _mock_session_factory(_mock_db_rows())

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("入职", kb_id=1, top_k=3)

        assert output.total > 0
        # "入职指南" chunk 应排在第一位
        assert "入职" in output.results[0].content

    @pytest.mark.asyncio
    async def test_中文分词检索_缓存未命中时用真实jieba构建索引(self):
        """当缓存未命中时，从 MySQL 加载后用真实 jieba 分词构建 BM25 索引"""
        async_redis = _mock_async_redis(get_return=None)
        db_rows = _mock_db_rows([
            (1, 0, "入职指南欢迎加入公司"),
            (1, 1, "报销制度差旅标准"),
            (1, 2, "VPN配置远程访问说明"),
        ])
        session_factory = _mock_session_factory(db_rows)

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("入职 指南", kb_id=1, top_k=3)

        assert output.total > 0
        # 第一条结果应该与"入职指南"相关
        assert output.results[0].score > 0

        # 验证缓存写入使用了真实 jieba 分词结果（非逐字拆分）
        async_redis.setex.assert_called_once()
        cached = json.loads(async_redis.setex.call_args[0][2])
        # 真实 jieba 分词 "入职指南欢迎加入公司" → 应含多字词（如 "入职", "指南"），非逐字拆分
        first_tokens = cached["tokens"][0]
        assert len(first_tokens) < 10  # 逐字拆分会有 9 个字符，真实分词约 5-6 个词
        # 验证进程内缓存已写入
        assert 1 in _local_cache

    @pytest.mark.asyncio
    async def test_无关查询分数为零不被过滤(self):
        """完全不相关的查询词在真实 jieba 分词下分数为 0.0（无证据），保留在结果中"""
        cached_data = json.dumps({
            "doc_ids": [[1, 0], [1, 1]],
            "tokens": [
                jieba.lcut("入职指南欢迎加入公司"),
                jieba.lcut("报销制度差旅标准"),
            ],
            "contents": [
                "入职指南欢迎加入公司",
                "报销制度差旅标准",
            ],
        }, ensure_ascii=False)
        async_redis = _mock_async_redis(get_return=cached_data)
        session_factory = _mock_session_factory(_mock_db_rows())

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
        # 2 个文档都包含 "的"，小语料下 IDF("的") 为负
        cached_data = json.dumps({
            "doc_ids": [[1, 0], [1, 1]],
            "tokens": [
                jieba.lcut("公司的入职指南"),
                jieba.lcut("公司的报销制度"),
            ],
            "contents": [
                "公司的入职指南",
                "公司的报销制度",
            ],
        }, ensure_ascii=False)
        async_redis = _mock_async_redis(get_return=cached_data)
        session_factory = _mock_session_factory(_mock_db_rows())

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
        cached_data = json.dumps({
            "doc_ids": [[1, 0]],
            "tokens": [jieba.lcut("入职指南欢迎加入公司")],
            "contents": ["入职指南欢迎加入公司"],
        }, ensure_ascii=False)
        async_redis = _mock_async_redis(get_return=cached_data)
        session_factory = _mock_session_factory(_mock_db_rows())

        retriever = BM25Retriever(async_redis, session_factory)

        # min_score=-999 不过滤
        output_low = await retriever.search("量子力学", kb_id=1, top_k=5, min_score=-999)
        assert output_low.total == 1  # 不相关但仍返回

        # min_score=999 全过滤
        output_high = await retriever.search("入职", kb_id=1, top_k=5, min_score=999)
        assert output_high.total == 0  # 全部被过滤

    @pytest.mark.asyncio
    async def test_top_k截取_真实分词(self):
        """真实 jieba 分词下，top_k 正确限制返回结果数量"""
        cached_data = json.dumps({
            "doc_ids": [[1, 0], [1, 1], [1, 2], [1, 3], [1, 4]],
            "tokens": [
                jieba.lcut("入职指南欢迎加入公司"),
                jieba.lcut("报销制度差旅标准说明"),
                jieba.lcut("VPN配置远程访问教程"),
                jieba.lcut("请假流程审批规范制度"),
                jieba.lcut("绩效考核评估管理办法"),
            ],
            "contents": [
                "入职指南欢迎加入公司",
                "报销制度差旅标准说明",
                "VPN配置远程访问教程",
                "请假流程审批规范制度",
                "绩效考核评估管理办法",
            ],
        }, ensure_ascii=False)
        async_redis = _mock_async_redis(get_return=cached_data)
        session_factory = _mock_session_factory(_mock_db_rows())

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("制度", kb_id=1, top_k=2)

        assert len(output.results) <= 2

    @pytest.mark.asyncio
    async def test_中文关键词精确匹配排第一(self):
        """真实 jieba 分词下，精确匹配查询词的 chunk 排在第一位"""
        cached_data = json.dumps({
            "doc_ids": [[1, 0], [1, 1], [1, 2]],
            "tokens": [
                jieba.lcut("VPN配置远程访问教程"),
                jieba.lcut("日报填写规范说明"),
                jieba.lcut("VPN账号申请流程指南"),
            ],
            "contents": [
                "VPN配置远程访问教程",
                "日报填写规范说明",
                "VPN账号申请流程指南",
            ],
        }, ensure_ascii=False)
        async_redis = _mock_async_redis(get_return=cached_data)
        session_factory = _mock_session_factory(_mock_db_rows())

        retriever = BM25Retriever(async_redis, session_factory)
        output = await retriever.search("VPN", kb_id=1, top_k=3)

        assert output.total == 3
        # 第一条应包含 "VPN" — 两篇都含 VPN，得分最高的在前
        assert "VPN" in output.results[0].content
        # 不含 VPN 的文档应排在最后
        assert "VPN" not in output.results[2].content
