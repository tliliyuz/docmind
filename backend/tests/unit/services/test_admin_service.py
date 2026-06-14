"""Admin Service 单元测试

对齐 TEST_CASES.md §6.8：
- A7.1 Admin KB 列表：验证分页/筛选/跨用户视图
- A7.2 Admin 文档列表：验证分页/筛选/排序/跨 KB 视图
- A7.3 Admin 统计：验证统计聚合数据正确性
- A7.5 visibility 筛选：验证按 visibility 过滤正确
- A7.6 status 筛选：验证按 status 过滤正确

覆盖 app/services/admin_service.py 中的 get_stats / list_all_kbs / list_all_documents
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import text


# ==================== 辅助函数 ====================


def _make_kb_row(kb_id=1, name="测试KB", description="描述", visibility="private",
                 user_id=1, status="active", doc_count=0, chunk_count=0):
    """构造 KB + username JOIN 查询结果行"""
    kb = MagicMock()
    kb.id = kb_id
    kb.uuid = f"kb-uuid-{kb_id:04d}-0000-0000-000000000000"
    kb.name = name
    kb.description = description
    kb.visibility = visibility
    kb.user_id = user_id
    kb.status = status
    kb.doc_count = doc_count
    kb.chunk_count = chunk_count
    kb.created_at = datetime(2026, 6, 1, tzinfo=timezone.utc)
    kb.updated_at = datetime(2026, 6, 10, tzinfo=timezone.utc)
    username = f"user_{user_id}"
    return (kb, username)


def _make_doc_row(doc_id=1, kb_id=1, filename="测试文档.pdf", file_type="pdf",
                  file_size=1024, status="completed", current_stage=None,
                  chunk_count=5, error_msg=None):
    """构造 Document + KB + User JOIN 查询结果行（6 值：doc, kb_name, kb_uuid, kb_visibility, owner_id, owner_username）"""
    doc = MagicMock()
    doc.id = doc_id
    doc.uuid = f"doc-uuid-{doc_id:04d}-0000-0000-000000000000"
    doc.kb_id = kb_id
    doc.filename = filename
    doc.file_type = file_type
    doc.file_size = file_size
    doc.status = status
    doc.current_stage = current_stage
    doc.chunk_count = chunk_count
    doc.error_msg = error_msg
    doc.created_at = datetime(2026, 6, 1, tzinfo=timezone.utc)
    doc.updated_at = datetime(2026, 6, 10, tzinfo=timezone.utc)
    kb_name = f"KB_{kb_id}"
    kb_uuid = f"kb-uuid-{kb_id:04d}-0000-0000-000000000000"
    kb_visibility = "private" if kb_id % 2 == 0 else "public"
    owner_id = kb_id * 10
    owner_username = f"owner_{kb_id}"
    return (doc, kb_name, kb_uuid, kb_visibility, owner_id, owner_username)


# ==================== get_stats 测试 ====================


class TestGetStats:
    """GET /api/admin/stats — 系统全局统计概览"""

    @pytest.mark.asyncio
    async def test_统计数据正确聚合(self):
        """A7.3：返回正确的统计聚合数据（用户数/KB数/文档数/存储量等）"""
        from app.services.admin_service import get_stats

        db = AsyncMock()

        # 模拟 6 次 count 查询的 scalar 返回值
        scalar_results = [10, 25, 100, 500, 30, 200, 1048576]
        call_count = 0

        async def execute_side_effect(stmt):
            nonlocal call_count
            m = MagicMock()
            if call_count < len(scalar_results):
                m.scalar.return_value = scalar_results[call_count]
            else:
                m.scalar.return_value = 0
            call_count += 1
            return m

        db.execute = AsyncMock(side_effect=execute_side_effect)

        result = await get_stats(db)

        assert result.user_count == 10
        assert result.kb_count == 25
        assert result.doc_count == 100
        assert result.chunk_count == 500
        assert result.conversation_count == 30
        assert result.message_count == 200
        assert result.storage_bytes == 1048576

    @pytest.mark.asyncio
    async def test_空数据库统计返回零值(self):
        """数据库无数据时各项统计返回 0，不抛异常"""
        from app.services.admin_service import get_stats

        db = AsyncMock()

        async def execute_side_effect(stmt):
            m = MagicMock()
            m.scalar.return_value = 0
            return m

        db.execute = AsyncMock(side_effect=execute_side_effect)

        result = await get_stats(db)

        assert result.user_count == 0
        assert result.kb_count == 0
        assert result.doc_count == 0
        assert result.chunk_count == 0
        assert result.conversation_count == 0
        assert result.message_count == 0
        assert result.storage_bytes == 0

    @pytest.mark.asyncio
    async def test_scalar返回None时回退为0(self):
        """当 func.count() 返回 None 时（极端情况），回退为 0"""
        from app.services.admin_service import get_stats

        db = AsyncMock()

        async def execute_side_effect(stmt):
            m = MagicMock()
            m.scalar.return_value = None
            return m

        db.execute = AsyncMock(side_effect=execute_side_effect)

        result = await get_stats(db)

        # 所有字段都有 `or 0` 保护
        assert result.user_count == 0
        assert result.kb_count == 0
        assert result.doc_count == 0
        assert result.storage_bytes == 0


# ==================== list_all_kbs 测试 ====================


class TestListAllKBs:
    """GET /api/admin/knowledge-bases — 全量知识库列表"""

    @pytest.mark.asyncio
    async def test_基本分页查询(self):
        """A7.1：默认分页返回 KB 列表，含 owner 用户名"""
        from app.services.admin_service import list_all_kbs

        db = AsyncMock()
        rows = [_make_kb_row(i, f"KB_{i}") for i in range(1, 4)]  # 3 条

        # 第一次 execute：count 查询
        count_mock = MagicMock()
        count_mock.scalar.return_value = 3
        # 第二次 execute：数据查询
        data_mock = MagicMock()
        data_mock.all.return_value = rows

        db.execute = AsyncMock(side_effect=[count_mock, data_mock])

        result = await list_all_kbs(db, page=1, page_size=20)

        assert result.total == 3
        assert result.page == 1
        assert result.page_size == 20
        assert len(result.items) == 3
        # 验证第一条数据结构
        assert result.items[0].uuid == "kb-uuid-0001-0000-0000-000000000000"
        assert result.items[0].name == "KB_1"
        assert result.items[0].username == "user_1"
        assert result.items[0].visibility == "private"
        assert result.items[0].status == "active"

    @pytest.mark.asyncio
    async def test_空列表返回total为0(self):
        """无 KB 时返回 total=0，items=[]"""
        from app.services.admin_service import list_all_kbs

        db = AsyncMock()

        count_mock = MagicMock()
        count_mock.scalar.return_value = 0
        data_mock = MagicMock()
        data_mock.all.return_value = []

        db.execute = AsyncMock(side_effect=[count_mock, data_mock])

        result = await list_all_kbs(db)

        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_按visibility筛选(self):
        """A7.5：按 visibility=private 筛选，仅返回匹配 KB"""
        from app.services.admin_service import list_all_kbs

        db = AsyncMock()
        rows = [_make_kb_row(1, "私有KB", visibility="private")]

        count_mock = MagicMock()
        count_mock.scalar.return_value = 1
        data_mock = MagicMock()
        data_mock.all.return_value = rows

        db.execute = AsyncMock(side_effect=[count_mock, data_mock])

        result = await list_all_kbs(db, visibility="private")

        assert result.total == 1
        assert result.items[0].visibility == "private"

    @pytest.mark.asyncio
    async def test_按status筛选(self):
        """按 status=deleting 筛选，仅返回匹配 KB"""
        from app.services.admin_service import list_all_kbs

        db = AsyncMock()
        rows = [_make_kb_row(1, "删除中KB", status="deleting")]

        count_mock = MagicMock()
        count_mock.scalar.return_value = 1
        data_mock = MagicMock()
        data_mock.all.return_value = rows

        db.execute = AsyncMock(side_effect=[count_mock, data_mock])

        result = await list_all_kbs(db, status="deleting")

        assert result.total == 1
        assert result.items[0].status == "deleting"

    @pytest.mark.asyncio
    async def test_按user_id筛选(self):
        """按 user_id 筛选，仅返回该用户的 KB"""
        from app.services.admin_service import list_all_kbs

        db = AsyncMock()
        rows = [_make_kb_row(1, "用户5的KB", user_id=5)]

        count_mock = MagicMock()
        count_mock.scalar.return_value = 1
        data_mock = MagicMock()
        data_mock.all.return_value = rows

        db.execute = AsyncMock(side_effect=[count_mock, data_mock])

        result = await list_all_kbs(db, user_id=5)

        assert result.total == 1
        assert result.items[0].user_id == 5

    @pytest.mark.asyncio
    async def test_按名称模糊搜索(self):
        """按 search 参数模糊匹配 KB 名称"""
        from app.services.admin_service import list_all_kbs

        db = AsyncMock()
        rows = [_make_kb_row(1, "公司报销制度")]

        count_mock = MagicMock()
        count_mock.scalar.return_value = 1
        data_mock = MagicMock()
        data_mock.all.return_value = rows

        db.execute = AsyncMock(side_effect=[count_mock, data_mock])

        result = await list_all_kbs(db, search="报销")

        assert result.total == 1
        assert "报销" in result.items[0].name

    @pytest.mark.asyncio
    async def test_分页第二页(self):
        """分页参数正确计算 offset"""
        from app.services.admin_service import list_all_kbs

        db = AsyncMock()
        rows = [_make_kb_row(21, "KB_21")]

        count_mock = MagicMock()
        count_mock.scalar.return_value = 25
        data_mock = MagicMock()
        data_mock.all.return_value = rows

        db.execute = AsyncMock(side_effect=[count_mock, data_mock])

        result = await list_all_kbs(db, page=2, page_size=20)

        assert result.total == 25
        assert result.page == 2
        assert result.page_size == 20
        assert len(result.items) == 1

    @pytest.mark.asyncio
    async def test_多条件组合筛选(self):
        """同时使用 user_id + visibility + status 组合筛选"""
        from app.services.admin_service import list_all_kbs

        db = AsyncMock()
        rows = [_make_kb_row(1, "KB", user_id=5, visibility="public", status="active")]

        count_mock = MagicMock()
        count_mock.scalar.return_value = 1
        data_mock = MagicMock()
        data_mock.all.return_value = rows

        db.execute = AsyncMock(side_effect=[count_mock, data_mock])

        result = await list_all_kbs(
            db, user_id=5, visibility="public", status="active"
        )

        assert result.total == 1


# ==================== list_all_documents 测试 ====================


class TestListAllDocuments:
    """GET /api/admin/documents — 全量文档列表"""

    @pytest.mark.asyncio
    async def test_基本分页查询(self):
        """A7.2：默认分页返回文档列表，含 KB 名称和 owner 信息"""
        from app.services.admin_service import list_all_documents

        db = AsyncMock()
        rows = [
            _make_doc_row(1, 1, "文档A.pdf", "pdf", 1024, "completed", chunk_count=5),
            _make_doc_row(2, 2, "文档B.md", "md", 512, "uploaded", chunk_count=0),
        ]

        count_mock = MagicMock()
        count_mock.scalar.return_value = 2
        data_mock = MagicMock()
        data_mock.all.return_value = rows

        db.execute = AsyncMock(side_effect=[count_mock, data_mock])

        result = await list_all_documents(db, page=1, page_size=20)

        assert result.total == 2
        assert result.page == 1
        assert result.page_size == 20
        assert len(result.items) == 2

        # 第一条：completed 文档
        assert result.items[0].uuid == "doc-uuid-0001-0000-0000-000000000000"
        assert result.items[0].kb_uuid == "kb-uuid-0001-0000-0000-000000000000"
        assert result.items[0].kb_name == "KB_1"
        assert result.items[0].owner_username == "owner_1"
        assert result.items[0].filename == "文档A.pdf"
        assert result.items[0].file_type == "pdf"
        assert result.items[0].file_size == 1024
        assert result.items[0].status == "completed"
        assert result.items[0].chunk_count == 5

        # 第二条：uploaded 文档
        assert result.items[1].uuid == "doc-uuid-0002-0000-0000-000000000000"
        assert result.items[1].status == "uploaded"
        assert result.items[1].chunk_count == 0

    @pytest.mark.asyncio
    async def test_空列表返回total为0(self):
        """无文档时返回 total=0，items=[]"""
        from app.services.admin_service import list_all_documents

        db = AsyncMock()

        count_mock = MagicMock()
        count_mock.scalar.return_value = 0
        data_mock = MagicMock()
        data_mock.all.return_value = []

        db.execute = AsyncMock(side_effect=[count_mock, data_mock])

        result = await list_all_documents(db)

        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_按status筛选(self):
        """A7.6：按 status=partial_failed 筛选，仅返回匹配文档"""
        from app.services.admin_service import list_all_documents

        db = AsyncMock()
        rows = [_make_doc_row(1, 1, "失败文档.pdf", status="partial_failed")]

        count_mock = MagicMock()
        count_mock.scalar.return_value = 1
        data_mock = MagicMock()
        data_mock.all.return_value = rows

        db.execute = AsyncMock(side_effect=[count_mock, data_mock])

        result = await list_all_documents(db, status="partial_failed")

        assert result.total == 1
        assert result.items[0].status == "partial_failed"

    @pytest.mark.asyncio
    async def test_按kb_id筛选(self):
        """按 kb_id 筛选，仅返回该知识库的文档"""
        from app.services.admin_service import list_all_documents

        db = AsyncMock()
        rows = [
            _make_doc_row(doc_id=1, kb_id=3, filename="KB3文档.pdf"),
            _make_doc_row(doc_id=2, kb_id=3, filename="KB3文档2.md"),
        ]

        count_mock = MagicMock()
        count_mock.scalar.return_value = 2
        data_mock = MagicMock()
        data_mock.all.return_value = rows

        db.execute = AsyncMock(side_effect=[count_mock, data_mock])

        result = await list_all_documents(db, kb_id=3)

        assert result.total == 2
        assert all(item.kb_uuid == "kb-uuid-0003-0000-0000-000000000000" for item in result.items)

    @pytest.mark.asyncio
    async def test_按文件名模糊搜索(self):
        """按 filename 参数模糊匹配文件名"""
        from app.services.admin_service import list_all_documents

        db = AsyncMock()
        rows = [_make_doc_row(1, 1, "公司报销制度v2.pdf")]

        count_mock = MagicMock()
        count_mock.scalar.return_value = 1
        data_mock = MagicMock()
        data_mock.all.return_value = rows

        db.execute = AsyncMock(side_effect=[count_mock, data_mock])

        result = await list_all_documents(db, filename="报销")

        assert result.total == 1
        assert "报销" in result.items[0].filename

    @pytest.mark.asyncio
    async def test_排序_按file_size升序(self):
        """按 file_size 升序排列"""
        from app.services.admin_service import list_all_documents

        db = AsyncMock()
        rows = [
            _make_doc_row(1, 1, "小文件.txt", file_size=100),
            _make_doc_row(2, 1, "大文件.pdf", file_size=10000),
        ]

        count_mock = MagicMock()
        count_mock.scalar.return_value = 2
        data_mock = MagicMock()
        data_mock.all.return_value = rows

        db.execute = AsyncMock(side_effect=[count_mock, data_mock])

        result = await list_all_documents(db, sort_by="file_size", order="asc")

        assert result.total == 2
        # 小文件应在前
        assert result.items[0].file_size == 100
        assert result.items[1].file_size == 10000

    @pytest.mark.asyncio
    async def test_排序_按filename降序(self):
        """按 filename 降序排列"""
        from app.services.admin_service import list_all_documents

        db = AsyncMock()
        rows = [
            _make_doc_row(1, 1, "Z文件.pdf"),
            _make_doc_row(2, 1, "A文件.pdf"),
        ]

        count_mock = MagicMock()
        count_mock.scalar.return_value = 2
        data_mock = MagicMock()
        data_mock.all.return_value = rows

        db.execute = AsyncMock(side_effect=[count_mock, data_mock])

        result = await list_all_documents(db, sort_by="filename", order="desc")

        assert result.total == 2

    @pytest.mark.asyncio
    async def test_排序_无效字段回退created_at(self):
        """sort_by 为无效字段时回退到 created_at 排序，不崩溃"""
        from app.services.admin_service import list_all_documents

        db = AsyncMock()
        rows = [_make_doc_row(1, 1, "doc.pdf")]

        count_mock = MagicMock()
        count_mock.scalar.return_value = 1
        data_mock = MagicMock()
        data_mock.all.return_value = rows

        db.execute = AsyncMock(side_effect=[count_mock, data_mock])

        # 不会抛异常
        result = await list_all_documents(db, sort_by="invalid_field")

        assert result.total == 1

    @pytest.mark.asyncio
    async def test_分页超出范围返回空items(self):
        """page 超出数据范围时返回空 items，total 不变"""
        from app.services.admin_service import list_all_documents

        db = AsyncMock()

        count_mock = MagicMock()
        count_mock.scalar.return_value = 10
        data_mock = MagicMock()
        data_mock.all.return_value = []

        db.execute = AsyncMock(side_effect=[count_mock, data_mock])

        result = await list_all_documents(db, page=100, page_size=20)

        assert result.total == 10
        assert result.items == []

    @pytest.mark.asyncio
    async def test_文档含错误信息字段(self):
        """failed 文档的 error_message 字段正确返回"""
        from app.services.admin_service import list_all_documents

        db = AsyncMock()
        rows = [
            _make_doc_row(1, 1, "失败文档.pdf", status="failed",
                          error_msg="解析失败：PDF 文件已损坏"),
        ]

        count_mock = MagicMock()
        count_mock.scalar.return_value = 1
        data_mock = MagicMock()
        data_mock.all.return_value = rows

        db.execute = AsyncMock(side_effect=[count_mock, data_mock])

        result = await list_all_documents(db)

        assert result.total == 1
        assert result.items[0].status == "failed"
        assert result.items[0].error_message == "解析失败：PDF 文件已损坏"
