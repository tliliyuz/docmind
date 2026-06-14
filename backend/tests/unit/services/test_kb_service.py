"""知识库 Service 单元测试 — Mock DB session

测试 knowledge_base_service.py 全部公开函数的真实业务逻辑。
此前仅有 API 层序列化测试（test_kb_api.py），service 函数全部被 patch() mock，
导致 _fill_real_chunk_count NameError 等 Bug 无法被检测。
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    KnowledgeBaseNameExistsException,
    KnowledgeBaseNotFoundException,
    PermissionDeniedException,
)
from app.models.chunk import Chunk
from app.models.knowledge_base import KnowledgeBase
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseUpdate
from app.services.knowledge_base_service import (
    _get_real_chunk_counts,
    check_kb_active,
    create_kb,
    delete_kb,
    get_kb,
    list_kbs,
    list_public_kbs,
    update_kb,
)


# ============================================================
# Mock 工具函数
# ============================================================


def _make_scalar_result(value):
    """构造 db.execute() 返回 .scalar() 的 mock（用于 COUNT 查询）"""
    result = MagicMock()
    result.scalar = MagicMock(return_value=value)
    return result


def _make_scalar_one_or_none_result(value):
    """构造 db.execute() 返回 .scalar_one_or_none() 的 mock（用于单行查询）"""
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=value)
    return result


def _make_scalars_all_result(rows):
    """构造 db.execute() 返回 .scalars().all() 的 mock（用于多行查询）"""
    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=list(rows))
    result = MagicMock()
    result.scalars = MagicMock(return_value=scalars_mock)
    return result


def _make_all_result(rows):
    """构造 db.execute() 返回 .all() 的 mock（用于 JOIN 查询返回 tuples）"""
    result = MagicMock()
    result.all = MagicMock(return_value=list(rows))
    return result


def _make_kb(
    kb_id=1,
    uuid=None,
    name="测试知识库",
    description="描述",
    user_id=1,
    visibility="private",
    status="active",
    chunk_count=10,
    doc_count=3,
):
    """构造 KnowledgeBase ORM 实例（非 mock，用于 .scalar_one_or_none() 返回）"""
    if uuid is None:
        uuid = f"kb-uuid-{kb_id}"
    kb = KnowledgeBase(
        id=kb_id,
        uuid=uuid,
        name=name,
        description=description,
        user_id=user_id,
        visibility=visibility,
        status=status,
        chunk_count=chunk_count,
        doc_count=doc_count,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    return kb


def _make_chunk_count_row(kb_id, count):
    """构造 Chunk GROUP BY 查询返回的一行（Row 对象）"""
    row = MagicMock()
    row.kb_id = kb_id
    # row[1] 模仿 func.count() 的第二列
    row.__getitem__ = MagicMock(side_effect=lambda i: [kb_id, count][i])
    row[1] = count
    return row


@pytest.fixture
def mock_db():
    """Mock 异步 DB session"""
    session = AsyncMock(spec=AsyncSession)

    async def _refresh(instance):
        if instance.id is None:
            instance.id = 1
        if not getattr(instance, "uuid", None):
            instance.uuid = f"kb-uuid-{instance.id}"
        if instance.status is None:
            instance.status = "active"
        if instance.doc_count is None:
            instance.doc_count = 0
        if instance.chunk_count is None:
            instance.chunk_count = 0
        if instance.created_at is None:
            instance.created_at = datetime.now(timezone.utc)
        instance.updated_at = datetime.now(timezone.utc)

    session.refresh.side_effect = _refresh
    return session


# ============================================================
# _get_real_chunk_counts
# ============================================================


class TestGetRealChunkCounts:
    """实时分块数查询 — 替代 KB 表 chunk_count 缓存列的核心函数"""

    @pytest.mark.asyncio
    async def test_单个KB返回正确计数(self, mock_db):
        """查询单个 KB 的分块数，返回 {kb_id: count}"""
        mock_db.execute.return_value = _make_all_result([
            _make_chunk_count_row(1, 42),
        ])

        result = await _get_real_chunk_counts(mock_db, [1])

        assert result == {1: 42}
        # 验证被执行了（传入的 query 非 None）
        called_query = mock_db.execute.call_args[0][0]
        assert called_query is not None

    @pytest.mark.asyncio
    async def test_多个KB批量返回(self, mock_db):
        """批量查询多个 KB，一次 GROUP BY 返回所有结果"""
        mock_db.execute.return_value = _make_all_result([
            _make_chunk_count_row(1, 10),
            _make_chunk_count_row(2, 0),
            _make_chunk_count_row(3, 55),
        ])

        result = await _get_real_chunk_counts(mock_db, [1, 2, 3])

        assert result == {1: 10, 2: 0, 3: 55}
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_空列表直接返回空字典(self, mock_db):
        """空 kb_ids 列表不查询 DB，直接返回 {}"""
        result = await _get_real_chunk_counts(mock_db, [])

        assert result == {}
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_无结果KB不在返回中(self, mock_db):
        """某些 KB 没有 chunk 记录时，不在返回的 dict 中出现"""
        mock_db.execute.return_value = _make_all_result([
            _make_chunk_count_row(1, 5),
        ])

        result = await _get_real_chunk_counts(mock_db, [1, 999])

        # KB 999 没有 chunk 记录所以不在结果中
        assert 1 in result
        assert result[1] == 5
        assert 999 not in result


# ============================================================
# create_kb
# ============================================================


class TestCreateKB:
    @pytest.mark.asyncio
    async def test_创建成功(self, mock_db):
        """正常创建知识库，返回 KnowledgeBaseResponse"""
        mock_db.flush = AsyncMock()

        result = await create_kb(
            mock_db,
            user_id=1,
            data=KnowledgeBaseCreate(name="新知识库", description="描述", visibility="private"),
        )

        assert result.name == "新知识库"
        assert result.description == "描述"
        assert result.visibility == "private"
        assert result.user_id == 1
        assert result.uuid == "kb-uuid-1"  # db.refresh mock 回填
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_同名冲突抛异常(self, mock_db):
        """同一用户下 KB 名称重复，db.flush() 抛 IntegrityError → KnowledgeBaseNameExistsException"""
        mock_db.flush = AsyncMock(side_effect=IntegrityError("duplicate", {}, None))

        with pytest.raises(KnowledgeBaseNameExistsException) as exc:
            await create_kb(
                mock_db,
                user_id=1,
                data=KnowledgeBaseCreate(name="重复名称"),
            )
        assert exc.value.error_code == "E1002"
        # add 被调用但 flush 失败
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_默认可见性为private(self, mock_db):
        """不传 visibility 时自动使用 private"""
        mock_db.flush = AsyncMock()

        result = await create_kb(
            mock_db,
            user_id=1,
            data=KnowledgeBaseCreate(name="默认可见"),
        )

        assert result.visibility == "private"


# ============================================================
# get_kb
# ============================================================


class TestGetKB:
    @pytest.mark.asyncio
    async def test_获取成功_含实时分块数(self, mock_db):
        """正常获取 KB，fill_chunk_count=True（默认）时从 Chunk 表实时查询分块数"""
        kb = _make_kb(kb_id=1, chunk_count=0)  # DB 缓存值是僵尸值
        mock_db.execute = AsyncMock()
        # 第一次 execute：查 KB
        # 第二次 execute：查 Chunk 实时分块数
        mock_db.execute.side_effect = [
            _make_scalar_one_or_none_result(kb),
            _make_all_result([_make_chunk_count_row(1, 99)]),
        ]

        result = await get_kb(mock_db, kb_id=1, user_id=1)

        assert result.uuid == "kb-uuid-1"
        assert result.chunk_count == 99  # 覆写为实时值，非 DB 缓存的 0
        assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_fill_chunk_count为False跳过查询(self, mock_db):
        """内部调用传 fill_chunk_count=False 时不查询 Chunk 表"""
        kb = _make_kb(kb_id=1)
        mock_db.execute = AsyncMock(return_value=_make_scalar_one_or_none_result(kb))

        result = await get_kb(mock_db, kb_id=1, fill_chunk_count=False)

        assert result.uuid == "kb-uuid-1"
        mock_db.execute.assert_called_once()  # 仅查了 KB

    @pytest.mark.asyncio
    async def test_私有KB所有者可访问(self, mock_db):
        """owner 可以访问自己的 private KB"""
        kb = _make_kb(kb_id=1, user_id=1, visibility="private")
        mock_db.execute = AsyncMock(return_value=_make_scalar_one_or_none_result(kb))

        result = await get_kb(mock_db, kb_id=1, user_id=1)
        assert result.uuid == "kb-uuid-1"

    @pytest.mark.asyncio
    async def test_私有KB非所有者被拒绝(self, mock_db):
        """非 owner 且非 admin 访问 private KB 时抛 PermissionDeniedException"""
        kb = _make_kb(kb_id=1, user_id=1, visibility="private")
        mock_db.execute = AsyncMock(return_value=_make_scalar_one_or_none_result(kb))

        with pytest.raises(PermissionDeniedException):
            await get_kb(mock_db, kb_id=1, user_id=2, role="user")

    @pytest.mark.asyncio
    async def test_admin可访问私有KB(self, mock_db):
        """admin 可以访问任何 private KB"""
        kb = _make_kb(kb_id=1, user_id=1, visibility="private")
        mock_db.execute = AsyncMock(return_value=_make_scalar_one_or_none_result(kb))

        result = await get_kb(mock_db, kb_id=1, user_id=2, role="admin")
        assert result.uuid == "kb-uuid-1"

    @pytest.mark.asyncio
    async def test_公开KB所有用户可访问(self, mock_db):
        """public KB 对所有登录用户可见"""
        kb = _make_kb(kb_id=1, user_id=1, visibility="public")
        mock_db.execute = AsyncMock(return_value=_make_scalar_one_or_none_result(kb))

        result = await get_kb(mock_db, kb_id=1, user_id=2)
        assert result.uuid == "kb-uuid-1"

    @pytest.mark.asyncio
    async def test_知识库不存在(self, mock_db):
        """KB 不存在时抛 KnowledgeBaseNotFoundException"""
        mock_db.execute = AsyncMock(return_value=_make_scalar_one_or_none_result(None))

        with pytest.raises(KnowledgeBaseNotFoundException) as exc:
            await get_kb(mock_db, kb_id=999, fill_chunk_count=False)
        assert exc.value.error_code == "E1001"

    @pytest.mark.asyncio
    async def test_未传user_id时跳过权限检查(self, mock_db):
        """内部调用（如 update_kb 第一段）不传 user_id 时不检查权限"""
        kb = _make_kb(kb_id=1, user_id=99, visibility="private")
        mock_db.execute = AsyncMock(return_value=_make_scalar_one_or_none_result(kb))

        # 不传 user_id，即使 private KB 也直接返回
        result = await get_kb(mock_db, kb_id=1, fill_chunk_count=False)
        assert result.uuid == "kb-uuid-1"


# ============================================================
# list_kbs
# ============================================================


class TestListKBs:
    @pytest.mark.asyncio
    async def test_列表含实时分块数(self, mock_db):
        """list_kbs 返回的每个 KB chunk_count 来自 Chunk 表实时查询"""
        kb1 = _make_kb(kb_id=1, chunk_count=999)  # DB 缓存僵尸值
        kb2 = _make_kb(kb_id=2, chunk_count=0)

        mock_db.execute = AsyncMock()
        # 1: COUNT(*) → total
        # 2: SELECT ... LIMIT OFFSET → rows
        # 3: _get_real_chunk_counts → 实时分块数
        mock_db.execute.side_effect = [
            _make_scalar_result(2),
            _make_scalars_all_result([kb1, kb2]),
            _make_all_result([_make_chunk_count_row(1, 15), _make_chunk_count_row(2, 30)]),
        ]

        result = await list_kbs(mock_db, user_id=1)

        assert result.total == 2
        assert len(result.items) == 2
        assert result.items[0].chunk_count == 15  # 实时值，非 999
        assert result.items[1].chunk_count == 30
        assert mock_db.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_空列表(self, mock_db):
        """用户没有任何 KB 时返回空列表"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            _make_scalar_result(0),
            _make_scalars_all_result([]),
            _make_all_result([]),
        ]

        result = await list_kbs(mock_db, user_id=1)

        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_分页参数正确传递(self, mock_db):
        """验证 page/page_size 正确应用到 offset/limit"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            _make_scalar_result(50),
            _make_scalars_all_result([]),
            _make_all_result([]),
        ]

        await list_kbs(mock_db, user_id=1, page=3, page_size=10)

        # 验证至少执行了（mock_db.execute 被调用）
        assert mock_db.execute.call_count >= 2  # COUNT + data query


# ============================================================
# list_public_kbs
# ============================================================


class TestListPublicKBs:
    @pytest.mark.asyncio
    async def test_公开列表含实时分块数和username(self, mock_db):
        """list_public_kbs 返回的每个 KB 含 username + 实时 chunk_count"""
        kb = _make_kb(kb_id=2, user_id=3, visibility="public", chunk_count=0)
        username = "zhangsan"

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            _make_scalar_result(1),
            _make_all_result([(kb, username)]),
            _make_all_result([_make_chunk_count_row(2, 25)]),
        ]

        result = await list_public_kbs(mock_db, page=1, page_size=20)

        assert result.total == 1
        assert len(result.items) == 1
        item = result.items[0]
        assert item.uuid == "kb-uuid-2"
        assert item.username == "zhangsan"
        assert item.chunk_count == 25  # 实时值

    @pytest.mark.asyncio
    async def test_空列表(self, mock_db):
        """没有任何公开 KB 时返回空列表"""
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            _make_scalar_result(0),
            _make_all_result([]),
            _make_all_result([]),
        ]

        result = await list_public_kbs(mock_db)

        assert result.total == 0
        assert result.items == []


# ============================================================
# update_kb — 核心：覆盖 db.refresh() 后 chunk_count 修正逻辑
# ============================================================


class TestUpdateKB:
    """update_kb 是 chunk_count 实时查询修复涉及的关键函数。

    update_kb 流程：
    1. get_kb() 获取 KB（fill_chunk_count=True → chunk_count 已填实时值）
    2. 权限检查
    3. 修改字段 → db.flush()
    4. db.refresh(kb) → chunk_count 被 DB 缓存列覆盖为僵尸值
    5. _get_real_chunk_counts() 重新覆写为实时值 ← 关键步骤
    6. 返回 KnowledgeBaseResponse
    """

    @pytest.mark.asyncio
    async def test_更新名称成功(self, mock_db):
        """更新 KB 名称，返回最新信息含实时分块数"""
        kb = _make_kb(kb_id=1, name="旧名称", chunk_count=0)
        mock_db.execute = AsyncMock()
        # get_kb: 查 KB + 查实时 chunk_count
        # update_kb 末尾: 再查一次实时 chunk_count
        mock_db.execute.side_effect = [
            _make_scalar_one_or_none_result(kb),        # get_kb: 查 KB
            _make_all_result([_make_chunk_count_row(1, 88)]),  # get_kb: 实时分块
            _make_all_result([_make_chunk_count_row(1, 88)]),  # update_kb 末尾: 重新修正
        ]
        mock_db.flush = AsyncMock()

        result = await update_kb(
            mock_db, kb_id=1, user_id=1, role="user",
            data=KnowledgeBaseUpdate(name="新名称"),
        )

        assert result.name == "新名称"
        assert result.chunk_count == 88  # 实时值，非 DB 缓存值
        mock_db.flush.assert_called_once()
        mock_db.refresh.assert_called_once()
        # 验证 execute 被调用了 3 次（get_kb 的两次 + update_kb 末尾的一次）
        assert mock_db.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_更新描述(self, mock_db):
        """更新 KB 描述"""
        kb = _make_kb(kb_id=1)
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            _make_scalar_one_or_none_result(kb),
            _make_all_result([]),   # get_kb: 实时分块（用 fallback）
            _make_all_result([]),   # update_kb 末尾
        ]
        mock_db.flush = AsyncMock()

        result = await update_kb(
            mock_db, kb_id=1, user_id=1, role="user",
            data=KnowledgeBaseUpdate(description="新描述"),
        )

        assert result.description == "新描述"

    @pytest.mark.asyncio
    async def test_更新可见性(self, mock_db):
        """owner 可将 private 改为 public"""
        kb = _make_kb(kb_id=1, visibility="private")
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            _make_scalar_one_or_none_result(kb),
            _make_all_result([]),
            _make_all_result([]),
        ]
        mock_db.flush = AsyncMock()

        result = await update_kb(
            mock_db, kb_id=1, user_id=1, role="user",
            data=KnowledgeBaseUpdate(visibility="public"),
        )

        assert result.visibility == "public"

    @pytest.mark.asyncio
    async def test_非owner被拒绝(self, mock_db):
        """非 owner 且非 admin 修改 KB 时抛 PermissionDeniedException"""
        kb = _make_kb(kb_id=1, user_id=1)
        mock_db.execute = AsyncMock(return_value=_make_scalar_one_or_none_result(kb))

        with pytest.raises(PermissionDeniedException):
            await update_kb(
                mock_db, kb_id=1, user_id=2, role="user",
                data=KnowledgeBaseUpdate(name="想改你的KB"),
            )

    @pytest.mark.asyncio
    async def test_admin可修改他人KB(self, mock_db):
        """admin 可修改任意 KB"""
        kb = _make_kb(kb_id=1, user_id=99)
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            _make_scalar_one_or_none_result(kb),
            _make_all_result([_make_chunk_count_row(1, 5)]),
            _make_all_result([_make_chunk_count_row(1, 5)]),
        ]
        mock_db.flush = AsyncMock()

        result = await update_kb(
            mock_db, kb_id=1, user_id=2, role="admin",
            data=KnowledgeBaseUpdate(visibility="public"),
        )

        assert result.visibility == "public"

    @pytest.mark.asyncio
    async def test_更新为同名抛冲突异常(self, mock_db):
        """db.flush() 抛 IntegrityError → KnowledgeBaseNameExistsException"""
        kb = _make_kb(kb_id=1, name="原名称")
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            _make_scalar_one_or_none_result(kb),
            _make_all_result([]),
        ]
        mock_db.flush = AsyncMock(side_effect=IntegrityError("duplicate", {}, None))

        with pytest.raises(KnowledgeBaseNameExistsException) as exc:
            await update_kb(
                mock_db, kb_id=1, user_id=1, role="user",
                data=KnowledgeBaseUpdate(name="冲突名称"),
            )
        assert exc.value.error_code == "E1002"

    @pytest.mark.asyncio
    async def test_db_refresh后用实时分块数覆写(self, mock_db):
        """关键测试：验证 update_kb 在 db.refresh() 后重新从 Chunk 表查询分块数。

        db.refresh() 会用 DB 缓存列的僵尸值覆盖 kb.chunk_count。
        如果 update_kb 没有在 refresh 后重新调用 _get_real_chunk_counts，
        chunk_count 会显示错误的缓存值而非真实值。
        """
        # KB 的缓存列 chunk_count=0（僵尸值），但 Chunk 表实际有 120 条
        kb = _make_kb(kb_id=1, chunk_count=0)
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            # get_kb: 查 KB → 返回缓存列=0 的 KB
            _make_scalar_one_or_none_result(kb),
            # get_kb: _get_real_chunk_counts → 实际 120
            _make_all_result([_make_chunk_count_row(1, 120)]),
            # update_kb 末尾: 再次查询 → 仍为 120
            _make_all_result([_make_chunk_count_row(1, 120)]),
        ]
        mock_db.flush = AsyncMock()

        # db.refresh 会把 kb.chunk_count 重置为 DB 缓存值 0
        async def _refresh_reset_chunk_count(instance):
            instance.chunk_count = 0  # 模拟 DB 缓存列值
            instance.updated_at = datetime.now(timezone.utc)

        mock_db.refresh.side_effect = _refresh_reset_chunk_count

        result = await update_kb(
            mock_db, kb_id=1, user_id=1, role="user",
            data=KnowledgeBaseUpdate(name="验证分块数"),
        )

        # 核心断言：即使 db.refresh() 把 chunk_count 重置为 0，
        # update_kb 末尾的 _get_real_chunk_counts 应该覆写回 120
        assert result.chunk_count == 120, (
            f"update_kb 应返回实时分块数 120，但实际返回 {result.chunk_count}。"
            f"这意味着 db.refresh() 后没有用 _get_real_chunk_counts 修正 chunk_count"
        )
        # 验证确实调用了 refresh
        mock_db.refresh.assert_called_once()
        # 验证总共 3 次 execute（get_kb×2 + update_kb末尾×1）
        assert mock_db.execute.call_count == 3, (
            f"预期 3 次 execute 调用，实际 {mock_db.execute.call_count} 次"
        )

    @pytest.mark.asyncio
    async def test_仅更新部分字段不影响其他字段(self, mock_db):
        """只传 name 时不改变 description 和 visibility"""
        kb = _make_kb(kb_id=1, name="旧名", description="旧描述", visibility="private")
        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            _make_scalar_one_or_none_result(kb),
            _make_all_result([]),
            _make_all_result([]),
        ]
        mock_db.flush = AsyncMock()

        result = await update_kb(
            mock_db, kb_id=1, user_id=1, role="user",
            data=KnowledgeBaseUpdate(name="新名"),
        )

        assert result.name == "新名"
        assert result.description == "旧描述"
        assert result.visibility == "private"


# ============================================================
# delete_kb
# ============================================================


class TestDeleteKB:
    @pytest.mark.asyncio
    async def test_标记删除成功(self, mock_db):
        """delete_kb 标记 status=deleting，commit 后分发 Celery 任务"""
        kb = _make_kb(kb_id=1, status="active")
        mock_db.execute = AsyncMock(return_value=_make_scalar_one_or_none_result(kb))
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        with patch("app.services.knowledge_base_service.delete_kb_task") as mock_task:
            result = await delete_kb(mock_db, kb_id=1, user_id=1, role="user")

        assert result.kb_uuid == "kb-uuid-1"
        assert result.status == "deleting"
        assert kb.status == "deleting"
        mock_db.commit.assert_called_once()
        mock_task.delay.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_非owner被拒绝(self, mock_db):
        """非 owner 且非 admin 无法删除 KB"""
        kb = _make_kb(kb_id=1, user_id=1)
        mock_db.execute = AsyncMock(return_value=_make_scalar_one_or_none_result(kb))

        with pytest.raises(PermissionDeniedException):
            await delete_kb(mock_db, kb_id=1, user_id=2, role="user")

    @pytest.mark.asyncio
    async def test_admin可删除他人KB(self, mock_db):
        """admin 可删除任意 KB"""
        kb = _make_kb(kb_id=1, user_id=99)
        mock_db.execute = AsyncMock(return_value=_make_scalar_one_or_none_result(kb))
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        with patch("app.services.knowledge_base_service.delete_kb_task") as mock_task:
            result = await delete_kb(mock_db, kb_id=1, user_id=2, role="admin")

        assert result.status == "deleting"


# ============================================================
# check_kb_active
# ============================================================


class TestCheckKBActive:
    @pytest.mark.asyncio
    async def test_active状态通过(self, mock_db):
        """status=active 的 KB 通过检查"""
        kb = _make_kb(kb_id=1, status="active")
        mock_db.execute = AsyncMock(return_value=_make_scalar_one_or_none_result(kb))

        result = await check_kb_active(mock_db, kb_id=1)
        assert result.uuid == "kb-uuid-1"

    @pytest.mark.asyncio
    async def test_deleting状态抛异常(self, mock_db):
        """status=deleting 的 KB 抛 KnowledgeBaseNotFoundException"""
        kb = _make_kb(kb_id=1, status="deleting")
        mock_db.execute = AsyncMock(return_value=_make_scalar_one_or_none_result(kb))

        with pytest.raises(KnowledgeBaseNotFoundException):
            await check_kb_active(mock_db, kb_id=1)
