"""Admin API 接口测试

对齐 TEST_CASES.md §6.8：
- A7.1 Admin KB 列表：GET /api/admin/knowledge-bases
- A7.2 Admin 文档列表：GET /api/admin/documents
- A7.3 Admin 统计：GET /api/admin/stats
- A7.4 非 Admin 拒绝：所有 admin 端点对普通用户返回 403
- A7.5 visibility 筛选：按 visibility 参数过滤 KB
- A7.6 status 筛选：按 status 参数过滤文档
- A7.7 ECharts 统计：trend/latency/tokens 图表数据

覆盖 app/api/admin.py 接口层 + dependencies.require_admin 权限校验
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import PermissionDeniedException
from app.schemas.admin import (
    AdminDocItem,
    AdminDocListResponse,
    AdminKBItem,
    AdminKBListResponse,
    AdminStatsResponse,
    StatsChartsData,
)
from app.schemas.trace import TraceLatencyItem, TraceTokenItem, TraceTrendItem


# ==================== 辅助函数 ====================


def _make_stats(charts: StatsChartsData | None = None) -> AdminStatsResponse:
    """构造统计响应"""
    return AdminStatsResponse(
        user_count=10,
        kb_count=25,
        doc_count=100,
        chunk_count=500,
        conversation_count=30,
        message_count=200,
        storage_bytes=1048576,
        charts=charts or StatsChartsData(),
    )


def _make_kb_list(total=3, page=1, page_size=20, items=None) -> AdminKBListResponse:
    """构造 KB 列表响应。items 可为 list[AdminKBItem] | int（生成 N 条） | None（默认 3 条）"""
    if items is None:
        items = 3  # 默认生成 3 条
    if isinstance(items, int):
        items = [
            AdminKBItem(
                id=i, name=f"KB_{i}", description=f"描述{i}",
                visibility="private" if i % 2 == 0 else "public",
                user_id=i * 10, username=f"user_{i}",
                status="active", doc_count=5, chunk_count=100,
                created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
                updated_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
            )
            for i in range(1, items + 1)
        ]
    return AdminKBListResponse(total=total, page=page, page_size=page_size, items=items)


def _make_doc_list(total=2, page=1, page_size=20, items=None) -> AdminDocListResponse:
    """构造文档列表响应"""
    if items is None:
        items = [
            AdminDocItem(
                id=1, kb_id=1, kb_name="KB_1", kb_visibility="private",
                owner_id=10, owner_username="owner1",
                filename="文档A.pdf", file_type="pdf", file_size=102400,
                status="completed", current_stage=None, chunk_count=10,
                error_message=None,
                created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
                updated_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
            ),
            AdminDocItem(
                id=2, kb_id=2, kb_name="KB_2", kb_visibility="public",
                owner_id=20, owner_username="owner2",
                filename="文档B.md", file_type="md", file_size=51200,
                status="uploaded", current_stage=None, chunk_count=0,
                error_message=None,
                created_at=datetime(2026, 6, 2, tzinfo=timezone.utc),
                updated_at=datetime(2026, 6, 9, tzinfo=timezone.utc),
            ),
        ]
    return AdminDocListResponse(total=total, page=page, page_size=page_size, items=items)


# ==================== Admin Stats API 测试 ====================


class TestAdminStatsAPI:
    """GET /api/admin/stats — 系统统计接口"""

    @pytest.mark.asyncio
    async def test_admin获取统计成功(self, async_client, admin_auth_headers):
        """A7.3：admin 用户获取统计成功，返回完整统计数据"""
        with patch("app.api.admin.get_stats", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = _make_stats()

            response = await async_client.get(
                "/api/admin/stats",
                headers=admin_auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "0"
        assert body["message"] == "ok"
        data = body["data"]
        assert data["user_count"] == 10
        assert data["kb_count"] == 25
        assert data["doc_count"] == 100
        assert data["chunk_count"] == 500
        assert data["conversation_count"] == 30
        assert data["message_count"] == 200
        assert data["storage_bytes"] == 1048576

    @pytest.mark.asyncio
    async def test_普通用户获取统计被拒绝(self, async_client, auth_headers):
        """A7.4：普通用户（role=user）访问 admin 端点返回 403"""
        response = await async_client.get(
            "/api/admin/stats",
            headers=auth_headers,
        )

        assert response.status_code == 403
        body = response.json()
        assert body["code"] == "E5005"
        assert body["message"] == "无权限执行此操作"

    @pytest.mark.asyncio
    async def test_未认证用户获取统计被拒绝(self, async_client):
        """未认证（无 Token）访问 admin 端点返回 401"""
        response = await async_client.get("/api/admin/stats")

        assert response.status_code == 401
        body = response.json()
        assert body["code"] == "E5004"


# ==================== Admin KB List API 测试 ====================


class TestAdminKBListAPI:
    """GET /api/admin/knowledge-bases — KB 列表接口"""

    @pytest.mark.asyncio
    async def test_admin获取KB列表成功(self, async_client, admin_auth_headers):
        """A7.1：admin 获取 KB 列表成功，返回分页数据"""
        with patch("app.api.admin.list_all_kbs", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = _make_kb_list(total=3, items=3)

            response = await async_client.get(
                "/api/admin/knowledge-bases",
                headers=admin_auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "0"
        data = body["data"]
        assert data["total"] == 3
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert len(data["items"]) == 3
        # 验证 item 含必要字段
        item = data["items"][0]
        assert "id" in item
        assert "name" in item
        assert "username" in item
        assert "visibility" in item
        assert "status" in item
        assert "doc_count" in item
        assert "chunk_count" in item

    @pytest.mark.asyncio
    async def test_admin获取KB列表_分页参数(self, async_client, admin_auth_headers):
        """分页参数 page=2&page_size=10 正确传递到 service"""
        with patch("app.api.admin.list_all_kbs", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = _make_kb_list(total=25, page=2, page_size=10)

            response = await async_client.get(
                "/api/admin/knowledge-bases?page=2&page_size=10",
                headers=admin_auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["page"] == 2
        assert body["data"]["page_size"] == 10
        # 验证 service 层被正确调用
        call_kwargs = mock_svc.call_args.kwargs
        assert call_kwargs["page"] == 2
        assert call_kwargs["page_size"] == 10

    @pytest.mark.asyncio
    async def test_admin获取KB列表_按visibility筛选(self, async_client, admin_auth_headers):
        """A7.5：按 visibility=private 筛选"""
        with patch("app.api.admin.list_all_kbs", new_callable=AsyncMock) as mock_svc:
            items = [
                AdminKBItem(
                    id=1, name="私有KB", visibility="private",
                    user_id=10, username="user1", status="active",
                    doc_count=0, chunk_count=0,
                    created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
                    updated_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
                )
            ]
            mock_svc.return_value = AdminKBListResponse(
                total=1, page=1, page_size=20, items=items
            )

            response = await async_client.get(
                "/api/admin/knowledge-bases?visibility=private",
                headers=admin_auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["total"] == 1
        assert body["data"]["items"][0]["visibility"] == "private"
        # 验证 service 层被正确调用
        call_kwargs = mock_svc.call_args.kwargs
        assert call_kwargs["visibility"] == "private"

    @pytest.mark.asyncio
    async def test_admin获取KB列表_组合筛选(self, async_client, admin_auth_headers):
        """多条件组合筛选：user_id + status + visibility + search"""
        with patch("app.api.admin.list_all_kbs", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = AdminKBListResponse(
                total=0, page=1, page_size=20, items=[]
            )

            response = await async_client.get(
                "/api/admin/knowledge-bases?user_id=5&status=active&visibility=public&search=报销",
                headers=admin_auth_headers,
            )

        assert response.status_code == 200
        call_kwargs = mock_svc.call_args.kwargs
        assert call_kwargs["user_id"] == 5
        assert call_kwargs["status"] == "active"
        assert call_kwargs["visibility"] == "public"
        assert call_kwargs["search"] == "报销"

    @pytest.mark.asyncio
    async def test_普通用户获取KB列表被拒绝(self, async_client, auth_headers):
        """A7.4：普通用户访问 admin KB 列表返回 403"""
        response = await async_client.get(
            "/api/admin/knowledge-bases",
            headers=auth_headers,
        )

        assert response.status_code == 403
        body = response.json()
        assert body["code"] == "E5005"

    @pytest.mark.asyncio
    async def test_未认证获取KB列表被拒绝(self, async_client):
        """未认证访问 admin KB 列表返回 401"""
        response = await async_client.get("/api/admin/knowledge-bases")

        assert response.status_code == 401
        body = response.json()
        assert body["code"] == "E5004"

    @pytest.mark.asyncio
    async def test_page参数校验_page小于1(self, async_client, admin_auth_headers):
        """page < 1 时 FastAPI Query 校验返回 422"""
        response = await async_client.get(
            "/api/admin/knowledge-bases?page=0",
            headers=admin_auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_page_size参数超限(self, async_client, admin_auth_headers):
        """page_size > 100 时 FastAPI Query 校验返回 422"""
        response = await async_client.get(
            "/api/admin/knowledge-bases?page_size=101",
            headers=admin_auth_headers,
        )

        assert response.status_code == 422


# ==================== Admin Document List API 测试 ====================


class TestAdminDocListAPI:
    """GET /api/admin/documents — 文档列表接口"""

    @pytest.mark.asyncio
    async def test_admin获取文档列表成功(self, async_client, admin_auth_headers):
        """A7.2：admin 获取文档列表成功，返回含 KB 名称和 owner 信息的分页数据"""
        with patch("app.api.admin.list_all_documents", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = _make_doc_list()

            response = await async_client.get(
                "/api/admin/documents",
                headers=admin_auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "0"
        data = body["data"]
        assert data["total"] == 2
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert len(data["items"]) == 2
        # 验证 item 含跨 KB 视图字段
        item = data["items"][0]
        assert item["id"] == 1
        assert item["kb_id"] == 1
        assert item["kb_name"] == "KB_1"
        assert item["kb_visibility"] == "private"
        assert item["owner_id"] == 10
        assert item["owner_username"] == "owner1"
        assert item["filename"] == "文档A.pdf"
        assert item["file_type"] == "pdf"
        assert item["status"] == "completed"
        assert item["chunk_count"] == 10

    @pytest.mark.asyncio
    async def test_admin获取文档列表_按status筛选(self, async_client, admin_auth_headers):
        """A7.6：按 status=partial_failed 筛选文档"""
        with patch("app.api.admin.list_all_documents", new_callable=AsyncMock) as mock_svc:
            items = [
                AdminDocItem(
                    id=3, kb_id=1, kb_name="KB_1", kb_visibility="private",
                    owner_id=10, owner_username="owner1",
                    filename="失败文档.pdf", file_type="pdf", file_size=100,
                    status="partial_failed", chunk_count=0,
                    created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
                    updated_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
                )
            ]
            mock_svc.return_value = AdminDocListResponse(
                total=1, page=1, page_size=20, items=items
            )

            response = await async_client.get(
                "/api/admin/documents?status=partial_failed",
                headers=admin_auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["total"] == 1
        assert body["data"]["items"][0]["status"] == "partial_failed"
        # 验证 service 调用参数
        call_kwargs = mock_svc.call_args.kwargs
        assert call_kwargs["status"] == "partial_failed"

    @pytest.mark.asyncio
    async def test_admin获取文档列表_排序参数(self, async_client, admin_auth_headers):
        """sort_by 和 order 参数正确传递到 service"""
        with patch("app.api.admin.list_all_documents", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = _make_doc_list()

            response = await async_client.get(
                "/api/admin/documents?sort_by=file_size&order=asc",
                headers=admin_auth_headers,
            )

        assert response.status_code == 200
        call_kwargs = mock_svc.call_args.kwargs
        assert call_kwargs["sort_by"] == "file_size"
        assert call_kwargs["order"] == "asc"

    @pytest.mark.asyncio
    async def test_admin获取文档列表_默认排序(self, async_client, admin_auth_headers):
        """不传 sort_by 和 order 时使用默认值"""
        with patch("app.api.admin.list_all_documents", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = _make_doc_list()

            response = await async_client.get(
                "/api/admin/documents",
                headers=admin_auth_headers,
            )

        assert response.status_code == 200
        call_kwargs = mock_svc.call_args.kwargs
        assert call_kwargs["sort_by"] == "created_at"
        assert call_kwargs["order"] == "desc"

    @pytest.mark.asyncio
    async def test_admin获取文档列表_组合筛选(self, async_client, admin_auth_headers):
        """按 kb_id + status + filename 组合筛选"""
        with patch("app.api.admin.list_all_documents", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = AdminDocListResponse(
                total=0, page=1, page_size=20, items=[]
            )

            response = await async_client.get(
                "/api/admin/documents?kb_id=1&status=completed&filename=报销",
                headers=admin_auth_headers,
            )

        assert response.status_code == 200
        call_kwargs = mock_svc.call_args.kwargs
        assert call_kwargs["kb_id"] == 1
        assert call_kwargs["status"] == "completed"
        assert call_kwargs["filename"] == "报销"

    @pytest.mark.asyncio
    async def test_普通用户获取文档列表被拒绝(self, async_client, auth_headers):
        """A7.4：普通用户访问 admin 文档列表返回 403"""
        response = await async_client.get(
            "/api/admin/documents",
            headers=auth_headers,
        )

        assert response.status_code == 403
        body = response.json()
        assert body["code"] == "E5005"

    @pytest.mark.asyncio
    async def test_未认证获取文档列表被拒绝(self, async_client):
        """未认证访问 admin 文档列表返回 401"""
        response = await async_client.get("/api/admin/documents")

        assert response.status_code == 401
        body = response.json()
        assert body["code"] == "E5004"


# ==================== Admin 端点全面权限测试 ====================


class TestAdminPermissionMatrix:
    """权限矩阵：所有 admin 端点的权限验证"""

    ADMIN_ENDPOINTS = [
        "/api/admin/stats",
        "/api/admin/knowledge-bases",
        "/api/admin/documents",
    ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("endpoint", ADMIN_ENDPOINTS)
    async def test_admin用户可访问(self, async_client, admin_auth_headers, endpoint):
        """admin 用户可以访问所有 admin 端点（前提是 service 返回数据）"""
        # 不同端点需要 mock 不同的 service 函数
        with patch("app.api.admin.get_stats", new_callable=AsyncMock) as mock_stats, \
             patch("app.api.admin.list_all_kbs", new_callable=AsyncMock) as mock_kbs, \
             patch("app.api.admin.list_all_documents", new_callable=AsyncMock) as mock_docs:
            mock_stats.return_value = _make_stats()
            mock_kbs.return_value = _make_kb_list(total=0, items=[])
            mock_docs.return_value = _make_doc_list(total=0, items=[])

            response = await async_client.get(endpoint, headers=admin_auth_headers)

            assert response.status_code == 200, f"admin 应能访问 {endpoint}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("endpoint", ADMIN_ENDPOINTS)
    async def test_普通用户被拒绝(self, async_client, auth_headers, endpoint):
        """A7.4：普通用户（role=user）访问所有 admin 端点返回 403"""
        response = await async_client.get(endpoint, headers=auth_headers)

        assert response.status_code == 403, f"普通用户应被拒绝访问 {endpoint}"
        body = response.json()
        assert body["code"] == "E5005"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("endpoint", ADMIN_ENDPOINTS)
    async def test_未认证用户被拒绝(self, async_client, endpoint):
        """未认证用户访问所有 admin 端点返回 401"""
        response = await async_client.get(endpoint)

        assert response.status_code == 401, f"未认证用户应被拒绝访问 {endpoint}"
        body = response.json()
        assert body["code"] == "E5004"


# ==================== ECharts 统计接口测试 ====================


class TestAdminStatsChartsAPI:
    """GET /api/admin/stats — ECharts 图表数据

    对齐 TEST_CASES.md §6.14.3：ECharts 统计接口测试（7 用例）
    - A7.7.1 stats 响应含 charts 字段
    - A7.7.2 charts.trend 为空时返回空数组
    - A7.7.3 charts.latency P50 正确
    - A7.7.4 charts.latency P95 正确
    - A7.7.5 charts.latency P99 正确
    - A7.7.6 charts.tokens input 正确
    - A7.7.7 charts.tokens output 正确
    """

    @pytest.mark.asyncio
    async def test_stats响应含charts字段(self, async_client, admin_auth_headers):
        """A7.7.1：stats 响应包含 charts 字段，含 trend/latency/tokens"""
        charts = StatsChartsData(
            trend=[TraceTrendItem(date="2026-06-12", success=10, error=1, partial=0)],
            latency=[TraceLatencyItem(date="2026-06-12", p50=800, p95=2000, p99=3500)],
            tokens=[TraceTokenItem(date="2026-06-12", input=50000, output=15000)],
        )
        with patch("app.api.admin.get_stats", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = _make_stats(charts=charts)

            response = await async_client.get(
                "/api/admin/stats",
                headers=admin_auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        data = body["data"]
        # charts 字段存在
        assert "charts" in data
        charts_data = data["charts"]
        assert "trend" in charts_data
        assert "latency" in charts_data
        assert "tokens" in charts_data
        # trend 数据
        assert len(charts_data["trend"]) == 1
        assert charts_data["trend"][0]["date"] == "2026-06-12"
        assert charts_data["trend"][0]["success"] == 10
        # latency 数据
        assert len(charts_data["latency"]) == 1
        assert charts_data["latency"][0]["p50"] == 800
        # tokens 数据
        assert len(charts_data["tokens"]) == 1
        assert charts_data["tokens"][0]["input"] == 50000

    @pytest.mark.asyncio
    async def test_charts_trend为空时返回空数组(self, async_client, admin_auth_headers):
        """A7.7.2：无 trace 数据时，charts.trend 返回空数组"""
        charts = StatsChartsData(trend=[], latency=[], tokens=[])
        with patch("app.api.admin.get_stats", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = _make_stats(charts=charts)

            response = await async_client.get(
                "/api/admin/stats",
                headers=admin_auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        charts_data = body["data"]["charts"]
        assert charts_data["trend"] == []
        assert charts_data["latency"] == []
        assert charts_data["tokens"] == []

    @pytest.mark.asyncio
    async def test_charts_latency_p50正确(self, async_client, admin_auth_headers):
        """A7.7.3：latency P50 分位数计算正确"""
        charts = StatsChartsData(
            trend=[],
            latency=[TraceLatencyItem(date="2026-06-12", p50=820, p95=2100, p99=3800)],
            tokens=[],
        )
        with patch("app.api.admin.get_stats", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = _make_stats(charts=charts)

            response = await async_client.get(
                "/api/admin/stats",
                headers=admin_auth_headers,
            )

        assert response.status_code == 200
        latency = response.json()["data"]["charts"]["latency"]
        assert len(latency) == 1
        assert latency[0]["p50"] == 820

    @pytest.mark.asyncio
    async def test_charts_latency_p95正确(self, async_client, admin_auth_headers):
        """A7.7.4：latency P95 分位数计算正确"""
        charts = StatsChartsData(
            trend=[],
            latency=[TraceLatencyItem(date="2026-06-12", p50=820, p95=2100, p99=3800)],
            tokens=[],
        )
        with patch("app.api.admin.get_stats", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = _make_stats(charts=charts)

            response = await async_client.get(
                "/api/admin/stats",
                headers=admin_auth_headers,
            )

        assert response.status_code == 200
        latency = response.json()["data"]["charts"]["latency"]
        assert latency[0]["p95"] == 2100

    @pytest.mark.asyncio
    async def test_charts_latency_p99正确(self, async_client, admin_auth_headers):
        """A7.7.5：latency P99 分位数计算正确"""
        charts = StatsChartsData(
            trend=[],
            latency=[TraceLatencyItem(date="2026-06-12", p50=820, p95=2100, p99=3800)],
            tokens=[],
        )
        with patch("app.api.admin.get_stats", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = _make_stats(charts=charts)

            response = await async_client.get(
                "/api/admin/stats",
                headers=admin_auth_headers,
            )

        assert response.status_code == 200
        latency = response.json()["data"]["charts"]["latency"]
        assert latency[0]["p99"] == 3800

    @pytest.mark.asyncio
    async def test_charts_tokens_input正确(self, async_client, admin_auth_headers):
        """A7.7.6：tokens input 统计正确"""
        charts = StatsChartsData(
            trend=[],
            latency=[],
            tokens=[TraceTokenItem(date="2026-06-12", input=152000, output=45000)],
        )
        with patch("app.api.admin.get_stats", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = _make_stats(charts=charts)

            response = await async_client.get(
                "/api/admin/stats",
                headers=admin_auth_headers,
            )

        assert response.status_code == 200
        tokens = response.json()["data"]["charts"]["tokens"]
        assert len(tokens) == 1
        assert tokens[0]["input"] == 152000

    @pytest.mark.asyncio
    async def test_charts_tokens_output正确(self, async_client, admin_auth_headers):
        """A7.7.7：tokens output 统计正确"""
        charts = StatsChartsData(
            trend=[],
            latency=[],
            tokens=[TraceTokenItem(date="2026-06-12", input=152000, output=45000)],
        )
        with patch("app.api.admin.get_stats", new_callable=AsyncMock) as mock_svc:
            mock_svc.return_value = _make_stats(charts=charts)

            response = await async_client.get(
                "/api/admin/stats",
                headers=admin_auth_headers,
            )

        assert response.status_code == 200
        tokens = response.json()["data"]["charts"]["tokens"]
        assert tokens[0]["output"] == 45000
