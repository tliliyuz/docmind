"""Trace API 接口测试

对齐 TEST_CASES.md §6.14.2 + §6.14.3：
- A9.1 Trace 列表-正常：GET /api/admin/traces
- A9.2 Trace 列表-按 status 筛选
- A9.3 Trace 列表-按 intent_type 筛选
- A9.4 Trace 列表-按时间范围筛选
- A9.5 Trace 列表-按问题搜索
- A9.6 Trace 列表-分页校验
- A9.7 Trace 详情-正常：GET /api/admin/traces/{trace_id}
- A9.8 Trace 详情-不存在
- A9.9 Trace 非 admin 拒绝
- A9.10 统计-trend 聚合：GET /api/admin/stats/traces
- A9.11 统计-latency 分位数
- A9.12 统计-tokens 聚合
- A9.13 统计-intent_distribution
- A9.14 统计-response_distribution
- A9.15 统计-空数据

覆盖 app/api/admin.py 中的 Trace 相关端点
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.trace import (
    TraceDetailResponse,
    TraceIntentDistItem,
    TraceLatencyItem,
    TraceListItem,
    TraceListResponse,
    TraceListSummary,
    TraceResponseDistItem,
    TraceStatsResponse,
    TraceTokenItem,
    TraceTrendItem,
)


# ==================== 辅助函数 ====================


def _make_trace_list_item(
    trace_id="trace-001",
    user_id=1,
    username="testuser",
    conversation_uuid="100000-0000-0000-0000-000000000100",
    kb_uuid="000000-0000-0000-0000-000000000010",
    kb_name="测试KB",
    question="测试问题",
    status="success",
    intent_type="KNOWLEDGE",
    intent_method="regex",
    response_mode="RAG",
    total_duration_ms=1500,
):
    """构造 TraceListItem"""
    return TraceListItem(
        trace_id=trace_id,
        user_id=user_id,
        username=username,
        conversation_uuid=conversation_uuid,
        kb_uuid=kb_uuid,
        kb_name=kb_name,
        question=question,
        status=status,
        intent_type=intent_type,
        intent_method=intent_method,
        response_mode=response_mode,
        total_duration_ms=total_duration_ms,
        created_at=datetime(2026, 6, 12, 10, 0, 0, tzinfo=timezone.utc),
    )


def _make_trace_list_response(total=2, page=1, page_size=20, items=None, summary=None):
    """构造 TraceListResponse"""
    if items is None:
        items = [
            _make_trace_list_item(trace_id="trace-001", username="user1"),
            _make_trace_list_item(trace_id="trace-002", username="user2"),
        ]
    if summary is None and total > 0:
        summary = TraceListSummary(
            success=total,
            error=0,
            running=0,
            success_rate=100.0,
            avg_duration_ms=1500.0,
            p95_duration_ms=1500.0,
        )
    return TraceListResponse(
        total=total, page=page, page_size=page_size, items=items, summary=summary,
    )


def _make_trace_detail(
    trace_id="trace-001",
    status="success",
    intent_type="KNOWLEDGE",
):
    """构造 TraceDetailResponse"""
    return TraceDetailResponse(
        trace_id=trace_id,
        user_id=1,
        username="testuser",
        conversation_uuid="100000-0000-0000-0000-000000000100",
        conversation_title="报销流程咨询",
        kb_uuid="000000-0000-0000-0000-000000000010",
        kb_name="测试KB",
        question="报销需要哪些材料？",
        status=status,
        intent_type=intent_type,
        intent_method="regex",
        response_mode="RAG",
        total_duration_ms=1500,
        intent={
            "span_name": "intent",
            "duration_ms": 50,
            "status": "success",
            "intent_type": intent_type,
            "method": "regex",
            "metadata": {},
        },
        rewrite={
            "span_name": "rewrite",
            "duration_ms": 100,
            "status": "success",
            "original_question": "报销需要哪些材料？",
            "rewritten_question": None,
            "metadata": {},
        },
        retrieve={
            "span_name": "retrieve",
            "duration_ms": 500,
            "status": "success",
            "vector": {"duration_ms": 200, "result_count": 10},
            "bm25": {"duration_ms": 150},
            "fusion": {"duration_ms": 50, "result_count": 10},
            "match_sentence": {"duration_ms": 100},
        },
        rerank={
            "span_name": "rerank",
            "duration_ms": 50,
            "status": "success",
            "input_count": 10,
            "output_count": 5,
            "metadata": {"reranker": "noop"},
        },
        generate={
            "span_name": "generate",
            "duration_ms": 800,
            "status": "success",
            "model": "deepseek-chat",
            "ttft_ms": 200,
            "input_tokens": 1000,
            "output_tokens": 500,
            "finish_reason": "stop",
        },
        error_message=None,
        created_at=datetime(2026, 6, 12, 10, 0, 0, tzinfo=timezone.utc),
    )


def _make_trace_stats():
    """构造 TraceStatsResponse"""
    return TraceStatsResponse(
        trend=[
            TraceTrendItem(date="2026-06-10", success=10, error=2, partial=1),
            TraceTrendItem(date="2026-06-11", success=15, error=0, partial=0),
        ],
        latency=[
            TraceLatencyItem(date="2026-06-10", p50=500, p95=1200, p99=2000),
            TraceLatencyItem(date="2026-06-11", p50=400, p95=1000, p99=1800),
        ],
        tokens=[
            TraceTokenItem(date="2026-06-10", input=5000, output=2000),
            TraceTokenItem(date="2026-06-11", input=6000, output=2500),
        ],
        intent_distribution=[
            TraceIntentDistItem(type="KNOWLEDGE", count=50),
            TraceIntentDistItem(type="CASUAL", count=20),
        ],
        response_distribution=[
            TraceResponseDistItem(mode="RAG", count=40),
            TraceResponseDistItem(mode="CASUAL", count=15),
        ],
    )


# ==================== Trace 列表 API 测试 ====================


class TestTraceListAPI:
    """GET /api/admin/traces — Trace 列表接口"""

    @pytest.mark.asyncio
    async def test_A9_1_Trace列表正常(self, async_client, admin_auth_headers):
        """A9.1：admin 用户获取 Trace 列表成功"""
        with patch("app.api.admin.list_traces", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = _make_trace_list_response()

            resp = await async_client.get(
                "/api/admin/traces",
                headers=admin_auth_headers,
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["code"] == "0"
            assert data["data"]["total"] == 2
            assert len(data["data"]["items"]) == 2
            assert data["data"]["items"][0]["trace_id"] == "trace-001"

    @pytest.mark.asyncio
    async def test_A9_2_Trace列表按status筛选(self, async_client, admin_auth_headers):
        """A9.2：按 status 筛选 Trace"""
        with patch("app.api.admin.list_traces", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = _make_trace_list_response(
                total=1,
                items=[_make_trace_list_item(status="error")],
            )

            resp = await async_client.get(
                "/api/admin/traces?status=error",
                headers=admin_auth_headers,
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["data"]["total"] == 1
            assert data["data"]["items"][0]["status"] == "error"

            # 验证 service 被正确调用
            mock_svc.assert_called_once()
            call_kwargs = mock_svc.call_args
            assert call_kwargs.kwargs.get("status") == "error" or call_kwargs[1].get("status") == "error"

    @pytest.mark.asyncio
    async def test_A9_3_Trace列表按intent_type筛选(self, async_client, admin_auth_headers):
        """A9.3：按 intent_type 筛选 Trace"""
        with patch("app.api.admin.list_traces", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = _make_trace_list_response(
                total=1,
                items=[_make_trace_list_item(intent_type="CASUAL")],
            )

            resp = await async_client.get(
                "/api/admin/traces?intent_type=CASUAL",
                headers=admin_auth_headers,
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["data"]["items"][0]["intent_type"] == "CASUAL"

    @pytest.mark.asyncio
    async def test_A9_4_Trace列表按时间范围筛选(self, async_client, admin_auth_headers):
        """A9.4：按时间范围筛选 Trace"""
        with patch("app.api.admin.list_traces", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = _make_trace_list_response(total=1)

            resp = await async_client.get(
                "/api/admin/traces?start_date=2026-06-01T00:00:00&end_date=2026-06-12T23:59:59",
                headers=admin_auth_headers,
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["data"]["total"] == 1

    @pytest.mark.asyncio
    async def test_A9_5_Trace列表按问题搜索(self, async_client, admin_auth_headers):
        """A9.5：按问题模糊搜索"""
        with patch("app.api.admin.list_traces", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = _make_trace_list_response(
                total=1,
                items=[_make_trace_list_item(question="报销需要哪些材料？")],
            )

            resp = await async_client.get(
                "/api/admin/traces?search=报销",
                headers=admin_auth_headers,
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["data"]["total"] == 1
            assert "报销" in data["data"]["items"][0]["question"]

    @pytest.mark.asyncio
    async def test_A9_6_Trace列表分页(self, async_client, admin_auth_headers):
        """A9.6：分页校验"""
        with patch("app.api.admin.list_traces", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = _make_trace_list_response(
                total=50,
                page=2,
                page_size=5,
                items=[_make_trace_list_item(trace_id=f"trace-{i:03d}") for i in range(6, 11)],
            )

            resp = await async_client.get(
                "/api/admin/traces?page=2&page_size=5",
                headers=admin_auth_headers,
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["data"]["total"] == 50
            assert data["data"]["page"] == 2
            assert data["data"]["page_size"] == 5
            assert len(data["data"]["items"]) == 5


# ==================== Trace 详情 API 测试 ====================


class TestTraceDetailAPI:
    """GET /api/admin/traces/{trace_id} — Trace 详情接口"""

    @pytest.mark.asyncio
    async def test_A9_7_Trace详情正常(self, async_client, admin_auth_headers):
        """A9.7：获取 Trace 详情成功"""
        with patch("app.api.admin.get_trace_detail", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = _make_trace_detail()

            resp = await async_client.get(
                "/api/admin/traces/trace-001",
                headers=admin_auth_headers,
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["code"] == "0"
            assert data["data"]["trace_id"] == "trace-001"
            assert data["data"]["username"] == "testuser"
            assert data["data"]["intent"] is not None
            assert data["data"]["retrieve"] is not None
            assert data["data"]["generate"] is not None

    @pytest.mark.asyncio
    async def test_A9_8_Trace详情不存在(self, async_client, admin_auth_headers):
        """A9.8：Trace 不存在时返回 404"""
        from app.core.exceptions import TraceNotFoundException

        with patch("app.api.admin.get_trace_detail", new_callable=AsyncMock) as mock_svc:
            mock_svc.side_effect = TraceNotFoundException("non-existent")

            resp = await async_client.get(
                "/api/admin/traces/non-existent",
                headers=admin_auth_headers,
            )

            assert resp.status_code == 404
            data = resp.json()
            assert data["code"] == "E7001"


# ==================== Trace 权限测试 ====================


class TestTracePermission:
    """Trace 接口权限校验"""

    @pytest.mark.asyncio
    async def test_A9_9_Trace列表非admin拒绝(self, async_client, auth_headers):
        """A9.9：普通用户访问 Trace 列表被拒绝"""
        resp = await async_client.get(
            "/api/admin/traces",
            headers=auth_headers,
        )

        assert resp.status_code == 403
        data = resp.json()
        assert data["code"] == "E5005"

    @pytest.mark.asyncio
    async def test_Trace详情非admin拒绝(self, async_client, auth_headers):
        """普通用户访问 Trace 详情被拒绝"""
        resp = await async_client.get(
            "/api/admin/traces/trace-001",
            headers=auth_headers,
        )

        assert resp.status_code == 403
        data = resp.json()
        assert data["code"] == "E5005"

    @pytest.mark.asyncio
    async def test_Trace统计非admin拒绝(self, async_client, auth_headers):
        """普通用户访问 Trace 统计被拒绝"""
        resp = await async_client.get(
            "/api/admin/stats/traces",
            headers=auth_headers,
        )

        assert resp.status_code == 403
        data = resp.json()
        assert data["code"] == "E5005"


# ==================== Trace 统计 API 测试 ====================


class TestTraceStatsAPI:
    """GET /api/admin/stats/traces — Trace 统计接口"""

    @pytest.mark.asyncio
    async def test_A9_10_统计trend聚合(self, async_client, admin_auth_headers):
        """A9.10：统计-trend 聚合正确"""
        with patch("app.api.admin.get_trace_stats", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = _make_trace_stats()

            resp = await async_client.get(
                "/api/admin/stats/traces?days=7",
                headers=admin_auth_headers,
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["code"] == "0"
            assert len(data["data"]["trend"]) == 2
            assert data["data"]["trend"][0]["date"] == "2026-06-10"
            assert data["data"]["trend"][0]["success"] == 10
            assert data["data"]["trend"][0]["error"] == 2

    @pytest.mark.asyncio
    async def test_A9_11_统计latency分位数(self, async_client, admin_auth_headers):
        """A9.11：统计-latency 分位数正确"""
        with patch("app.api.admin.get_trace_stats", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = _make_trace_stats()

            resp = await async_client.get(
                "/api/admin/stats/traces?days=7",
                headers=admin_auth_headers,
            )

            assert resp.status_code == 200
            data = resp.json()
            assert len(data["data"]["latency"]) == 2
            assert data["data"]["latency"][0]["p50"] == 500
            assert data["data"]["latency"][0]["p95"] == 1200
            assert data["data"]["latency"][0]["p99"] == 2000

    @pytest.mark.asyncio
    async def test_A9_12_统计tokens聚合(self, async_client, admin_auth_headers):
        """A9.12：统计-tokens 聚合正确"""
        with patch("app.api.admin.get_trace_stats", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = _make_trace_stats()

            resp = await async_client.get(
                "/api/admin/stats/traces?days=7",
                headers=admin_auth_headers,
            )

            assert resp.status_code == 200
            data = resp.json()
            assert len(data["data"]["tokens"]) == 2
            assert data["data"]["tokens"][0]["input"] == 5000
            assert data["data"]["tokens"][0]["output"] == 2000

    @pytest.mark.asyncio
    async def test_A9_13_统计intent_distribution(self, async_client, admin_auth_headers):
        """A9.13：统计-intent_distribution 正确"""
        with patch("app.api.admin.get_trace_stats", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = _make_trace_stats()

            resp = await async_client.get(
                "/api/admin/stats/traces?days=7",
                headers=admin_auth_headers,
            )

            assert resp.status_code == 200
            data = resp.json()
            assert len(data["data"]["intent_distribution"]) == 2
            assert data["data"]["intent_distribution"][0]["type"] == "KNOWLEDGE"
            assert data["data"]["intent_distribution"][0]["count"] == 50

    @pytest.mark.asyncio
    async def test_A9_14_统计response_distribution(self, async_client, admin_auth_headers):
        """A9.14：统计-response_distribution 正确"""
        with patch("app.api.admin.get_trace_stats", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = _make_trace_stats()

            resp = await async_client.get(
                "/api/admin/stats/traces?days=7",
                headers=admin_auth_headers,
            )

            assert resp.status_code == 200
            data = resp.json()
            assert len(data["data"]["response_distribution"]) == 2
            assert data["data"]["response_distribution"][0]["mode"] == "RAG"
            assert data["data"]["response_distribution"][0]["count"] == 40

    @pytest.mark.asyncio
    async def test_A9_15_统计空数据(self, async_client, admin_auth_headers):
        """A9.15：空数据返回空数组"""
        with patch("app.api.admin.get_trace_stats", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = TraceStatsResponse(
                trend=[],
                latency=[],
                tokens=[],
                intent_distribution=[],
                response_distribution=[],
            )

            resp = await async_client.get(
                "/api/admin/stats/traces?days=1",
                headers=admin_auth_headers,
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["code"] == "0"
            assert len(data["data"]["trend"]) == 0
            assert len(data["data"]["latency"]) == 0
            assert len(data["data"]["tokens"]) == 0
            assert len(data["data"]["intent_distribution"]) == 0
            assert len(data["data"]["response_distribution"]) == 0
