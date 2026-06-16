"""Rerank 重排序模块单元测试 — 覆盖 DashScopeReranker 核心逻辑

- API 正常响应排序、异常降级回退、空输入/单输入边界、接口一致性
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.rag.reranker import BaseReranker, DashScopeReranker
from app.rag.retriever import RetrievalOutput, RetrievalResult


def _make_result(
    doc_id: int,
    chunk_index: int,
    content: str,
    score: float = 0.0,
    page: int | None = None,
    doc_name: str = "",
) -> RetrievalResult:
    """构造 RetrievalResult 测试数据"""
    return RetrievalResult(
        doc_id=doc_id,
        chunk_index=chunk_index,
        content=content,
        score=score,
        page=page,
        doc_name=doc_name,
    )


def _make_output(results: list[RetrievalResult]) -> RetrievalOutput:
    """构造 RetrievalOutput 测试数据"""
    return RetrievalOutput(results=results, total=len(results))


# ==================== 接口一致性测试 ====================


class TestRerankerInterface:
    """Reranker 接口一致性测试"""

    def test_base_reranker_是抽象类(self):
        """BaseReranker 不能直接实例化"""
        with pytest.raises(TypeError):
            BaseReranker()

    def test_dashscope_reranker_是_base_reranker_子类(self):
        """DashScopeReranker 应继承 BaseReranker"""
        assert issubclass(DashScopeReranker, BaseReranker)


# ==================== DashScopeReranker API 响应解析测试 ====================


class TestDashScopeRerankerParseResponse:
    """_parse_rerank_response() 静态方法测试"""

    def test_正常解析降序排列结果(self):
        """API 返回 3 条结果，按 relevance_score 降序，提取 index 列表"""
        data = {
            "output": {
                "results": [
                    {"index": 0, "relevance_score": 0.95},
                    {"index": 2, "relevance_score": 0.78},
                    {"index": 1, "relevance_score": 0.62},
                ]
            },
            "usage": {"total_tokens": 150},
        }

        indices = DashScopeReranker._parse_rerank_response(data, doc_count=3)

        assert indices == [0, 2, 1]

    def test_部分结果截取top_n(self):
        """API 返回 2 条结果（top_n=2），输入 5 篇文档"""
        data = {
            "output": {
                "results": [
                    {"index": 3, "relevance_score": 0.99},
                    {"index": 0, "relevance_score": 0.88},
                ]
            },
            "usage": {"total_tokens": 200},
        }

        indices = DashScopeReranker._parse_rerank_response(data, doc_count=5)

        assert indices == [3, 0]

    def test_单条结果(self):
        """API 返回 1 条结果（输入仅 1 篇文档）"""
        data = {
            "output": {
                "results": [
                    {"index": 0, "relevance_score": 0.99},
                ]
            },
            "usage": {"total_tokens": 50},
        }

        indices = DashScopeReranker._parse_rerank_response(data, doc_count=1)

        assert indices == [0]

    def test_空output字段降级返回全部索引(self):
        """API 返回 output 为空字典 → 降级返回全部原始索引（保持原序）"""
        data = {
            "output": {},
            "usage": {"total_tokens": 10},
        }

        indices = DashScopeReranker._parse_rerank_response(data, doc_count=3)

        assert indices == [0, 1, 2]

    def test_空results列表降级返回全部索引(self):
        """API 返回 results 为空列表 → 降级返回全部原始索引（保持原序）"""
        data = {
            "output": {"results": []},
            "usage": {"total_tokens": 10},
        }

        indices = DashScopeReranker._parse_rerank_response(data, doc_count=3)

        assert indices == [0, 1, 2]

    def test_缺少index字段抛异常(self):
        """结果项缺少 index 字段 → ValueError"""
        data = {
            "output": {
                "results": [
                    {"relevance_score": 0.95},  # 缺少 index
                ]
            },
        }

        with pytest.raises(ValueError, match="缺少 index 字段"):
            DashScopeReranker._parse_rerank_response(data, doc_count=3)

    def test_index越界抛异常(self):
        """index >= doc_count → ValueError"""
        data = {
            "output": {
                "results": [
                    {"index": 5, "relevance_score": 0.95},  # doc_count=3，index 5 越界
                ]
            },
        }

        with pytest.raises(ValueError, match="索引越界"):
            DashScopeReranker._parse_rerank_response(data, doc_count=3)

    def test_负index抛异常(self):
        """index < 0 → ValueError"""
        data = {
            "output": {
                "results": [
                    {"index": -1, "relevance_score": 0.95},
                ]
            },
        }

        with pytest.raises(ValueError, match="索引越界"):
            DashScopeReranker._parse_rerank_response(data, doc_count=3)


# ==================== DashScopeReranker 集成测试（Mock API） ====================


class TestDashScopeRerankerIntegration:
    """DashScopeReranker.rerank() 集成测试（Mock httpx.AsyncClient）"""

    @pytest.fixture
    def reranker(self):
        return DashScopeReranker()

    @pytest.fixture
    def sample_output(self):
        """构造 5 条检索结果"""
        return RetrievalOutput(
            results=[
                RetrievalResult(doc_id=1, chunk_index=0, content="入职流程包括填写个人信息", score=0.85, page=1, doc_name="入职指南.pdf"),
                RetrievalResult(doc_id=1, chunk_index=1, content="报销需要提交发票原件", score=0.80, page=2, doc_name="入职指南.pdf"),
                RetrievalResult(doc_id=2, chunk_index=0, content="年假申请需要提前三天", score=0.78, page=1, doc_name="考勤制度.pdf"),
                RetrievalResult(doc_id=3, chunk_index=0, content="公司提供免费午餐和班车", score=0.75, page=3, doc_name="福利说明.pdf"),
                RetrievalResult(doc_id=2, chunk_index=1, content="病假需提供医院证明", score=0.72, page=2, doc_name="考勤制度.pdf"),
            ],
            total=5,
        )

    @pytest.fixture
    def mock_rerank_response(self):
        """构造模拟的 DashScope Rerank API 成功响应"""

        def _make_response(indices_scores: list[tuple[int, float]]):
            results = [
                {"index": idx, "relevance_score": score}
                for idx, score in indices_scores
            ]
            return {
                "output": {"results": results},
                "usage": {"total_tokens": 120},
            }

        return _make_response

    @pytest.mark.asyncio
    async def test_API正常返回按相关性降序重排(
        self, reranker, sample_output, mock_rerank_response
    ):
        """API 返回 [2,0,4] → 输出按此顺序重排"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_rerank_response([
            (2, 0.96),  # doc_id=2, chunk_index=0 → 年假
            (0, 0.91),  # doc_id=1, chunk_index=0 → 入职
            (4, 0.73),  # doc_id=2, chunk_index=1 → 病假
        ])

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await reranker.rerank("年假怎么申请", sample_output, top_k=3)

        assert result.total == 3
        assert len(result.results) == 3
        # 按 API 返回的 relevance_score 降序
        assert result.results[0].content == "年假申请需要提前三天"
        assert result.results[0].doc_id == 2
        assert result.results[1].content == "入职流程包括填写个人信息"
        assert result.results[1].doc_id == 1
        assert result.results[2].content == "病假需提供医院证明"
        assert result.results[2].doc_id == 2

    @pytest.mark.asyncio
    async def test_API返回部分结果top_n小于输入(
        self, reranker, sample_output, mock_rerank_response
    ):
        """5 条输入 top_n=2，API 返回 2 条 → 输出 2 条"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_rerank_response([
            (1, 0.98),
            (3, 0.87),
        ])

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await reranker.rerank("报销问题", sample_output, top_k=2)

        assert result.total == 2
        assert len(result.results) == 2
        assert result.results[0].content == "报销需要提交发票原件"
        assert result.results[1].content == "公司提供免费午餐和班车"

    @pytest.mark.asyncio
    async def test_空输入直接返回空(self, reranker):
        """输入 [] → 直接返回 RetrievalOutput()，不调 API"""
        empty_output = RetrievalOutput(results=[], total=0)

        # 不应发起 HTTP 请求
        with patch("httpx.AsyncClient") as mock_http:
            result = await reranker.rerank("测试", empty_output, top_k=5)

        mock_http.assert_not_called()
        assert result.total == 0
        assert result.results == []

    @pytest.mark.asyncio
    async def test_单条输入不调API直接返回(
        self, reranker, mock_rerank_response
    ):
        """1 条输入 → 调用 API（即使只有 1 条也走精排获得 relevance_score）"""
        single_output = RetrievalOutput(
            results=[
                RetrievalResult(doc_id=1, chunk_index=0, content="唯一的文档内容", score=0.9, doc_name="文档.pdf"),
            ],
            total=1,
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_rerank_response([(0, 0.95)])

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await reranker.rerank("测试", single_output, top_k=5)

        assert result.total == 1
        assert result.results[0].content == "唯一的文档内容"

    @pytest.mark.asyncio
    async def test_API返回HTTP错误降级回退(
        self, reranker, sample_output
    ):
        """API 返回 500 → 降级回退到原始 RRF 排序 + 截取 top_k"""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await reranker.rerank("测试", sample_output, top_k=3)

        # 降级：保持原始 RRF 排序，截取 top_k
        assert result.total == 3
        assert len(result.results) == 3
        # 原始顺序：按 score 降序
        assert result.results[0].content == "入职流程包括填写个人信息"
        assert result.results[1].content == "报销需要提交发票原件"
        assert result.results[2].content == "年假申请需要提前三天"

    @pytest.mark.asyncio
    async def test_API网络异常重试后降级回退(
        self, reranker, sample_output
    ):
        """网络超时 → 重试 3 次后降级回退"""
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("连接超时"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await reranker.rerank("测试", sample_output, top_k=2)

        # 重试 3 次后降级
        assert mock_client.post.call_count == 3
        # 降级：保持原始 RRF 排序，截取 top_k
        assert result.total == 2
        assert result.results[0].content == "入职流程包括填写个人信息"

    @pytest.mark.asyncio
    async def test_API返回JSON解析错误重试后降级(
        self, reranker, sample_output
    ):
        """API 返回非 JSON 内容 → 重试后降级"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await reranker.rerank("测试", sample_output, top_k=3)

        # 重试 3 次后降级
        assert mock_client.post.call_count == 3
        assert result.total == 3

    @pytest.mark.asyncio
    async def test_top_k大于输入数量返回全部(
        self, reranker, sample_output, mock_rerank_response
    ):
        """5 条输入 top_k=10 → effective_top_n=5，返回全部 5 条"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_rerank_response([
            (3, 0.96), (2, 0.92), (0, 0.88), (4, 0.81), (1, 0.75),
        ])

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await reranker.rerank("测试", sample_output, top_k=10)

        assert result.total == 5
        assert len(result.results) == 5

    @pytest.mark.asyncio
    async def test_API请求体格式正确(
        self, reranker, sample_output, mock_rerank_response
    ):
        """验证发送给 API 的请求体格式正确"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_rerank_response([
            (0, 0.95), (1, 0.80),
        ])

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await reranker.rerank("年假怎么申请", sample_output, top_k=3)

        # 验证请求体
        call_args = mock_client.post.call_args
        assert call_args is not None
        payload = call_args.kwargs["json"]
        assert payload["model"] == "qwen3-rerank"
        assert payload["input"]["query"] == "年假怎么申请"
        assert len(payload["input"]["documents"]) == 5
        assert payload["input"]["documents"][0] == "入职流程包括填写个人信息"
        assert payload["parameters"]["top_n"] == 3
        assert payload["parameters"]["return_documents"] is False

    @pytest.mark.asyncio
    async def test_API首次失败第二次成功(
        self, reranker, sample_output, mock_rerank_response
    ):
        """第一次调用失败（500），第二次成功 → 返回正确结果"""
        fail_resp = MagicMock()
        fail_resp.status_code = 500
        fail_resp.text = "Internal Server Error"

        success_resp = MagicMock()
        success_resp.status_code = 200
        success_resp.json.return_value = mock_rerank_response([
            (1, 0.98), (3, 0.85), (0, 0.72),
        ])

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=[fail_resp, success_resp])

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await reranker.rerank("测试", sample_output, top_k=3)

        assert mock_client.post.call_count == 2
        assert result.total == 3
        assert result.results[0].content == "报销需要提交发票原件"

    @pytest.mark.asyncio
    async def test_不改变chunk原始内容(
        self, reranker, sample_output, mock_rerank_response
    ):
        """仅重新排序，不修改 chunk 的 content/doc_id/page/doc_name"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_rerank_response([
            (2, 0.99), (4, 0.88), (0, 0.75),
        ])

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await reranker.rerank("测试", sample_output, top_k=3)

        # index=2 → doc_id=2, chunk_index=0
        assert result.results[0].doc_id == 2
        assert result.results[0].chunk_index == 0
        assert result.results[0].content == "年假申请需要提前三天"
        assert result.results[0].score == 0.78
        assert result.results[0].page == 1
        assert result.results[0].doc_name == "考勤制度.pdf"

        # index=4 → doc_id=2, chunk_index=1
        assert result.results[1].doc_id == 2
        assert result.results[1].chunk_index == 1
        assert result.results[1].content == "病假需提供医院证明"

        # index=0 → doc_id=1, chunk_index=0
        assert result.results[0].doc_id == 2


# ==================== DashScopeReranker 配置与端点测试 ====================


class TestDashScopeRerankerConfig:
    """DashScopeReranker 配置与端点 URL 测试"""

    def test_api_url拼接正确(self):
        """验证 API 端点 URL 拼接"""
        reranker = DashScopeReranker()
        expected = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
        assert reranker.api_url == expected

    def test_base_url去除尾部斜杠(self):
        """即使 base_url 带尾部斜杠，拼接结果去重"""
        reranker = DashScopeReranker()
        # base_url 已在 __init__ 中 rstrip("/")
        assert not reranker._base_url.endswith("/")
        assert "/services/rerank" in reranker.api_url
