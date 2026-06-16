"""Admin Service — 用户管理单元测试

对齐 TEST_CASES.md §6.15.1：
- U15.1 用户列表-正常：分页列表含统计字段
- U15.2 用户列表-按 role 筛选
- U15.3 用户列表-按 status 筛选
- U15.4 用户列表-搜索
- U15.5 用户详情-正常：含跨表聚合统计
- U15.6 用户详情-不存在
- U15.9 禁用用户
- U15.10 启用用户
- U15.11 重置密码
- U15.12 重置密码-用户不存在

覆盖 app/services/admin_service.py 中的 list_users / get_user_detail / change_user_status / reset_user_password
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ==================== 辅助函数 ====================


def _make_user(user_id=1, username="testuser", role="user", status="active"):
    """构造 User ORM 对象 mock"""
    user = MagicMock()
    user.id = user_id
    user.username = username
    user.role = role
    user.status = status
    user.password_hash = "$2b$12$abcdefghij"
    user.created_at = datetime(2026, 5, 1, tzinfo=timezone.utc)
    user.updated_at = datetime(2026, 6, 10, tzinfo=timezone.utc)
    return user


def _make_scalar_mock(value):
    """构造 scalar() 返回指定值的 execute 结果 mock"""
    m = MagicMock()
    m.scalar.return_value = value
    return m


def _make_scalars_all_mock(items):
    """构造 scalars().all() 返回列表的 execute 结果 mock"""
    m = MagicMock()
    m.scalars.return_value.all.return_value = items
    return m


# ==================== list_users 测试 ====================


class TestListUsers:
    """list_users — 用户列表 Service 测试

    对齐 TEST_CASES.md §6.15.1：U15.1-U15.4
    """

    @pytest.mark.asyncio
    async def test_用户列表正常分页(self):
        """U15.1：多用户返回分页列表，含 username/role/status/kb_count/doc_count/conversation_count"""
        from app.services.admin_service import list_users

        db = AsyncMock()
        users = [_make_user(1, "alice"), _make_user(2, "bob", role="admin")]

        # execute 调用顺序：count → data → 每个用户 4 次聚合查询
        effects = [
            _make_scalar_mock(2),                   # count 查询 total=2
            _make_scalars_all_mock(users),          # data 查询返回 2 个 user
            # user 1 (alice) 的 4 次聚合
            _make_scalar_mock(3),                   # kb_count=3
            _make_scalar_mock(15),                  # doc_count=15
            _make_scalar_mock(10),                  # conversation_count=10
            _make_scalar_mock(datetime(2026, 6, 12, tzinfo=timezone.utc)),
            # user 2 (bob) 的 4 次聚合
            _make_scalar_mock(5),                   # kb_count=5
            _make_scalar_mock(25),                  # doc_count=25
            _make_scalar_mock(20),                  # conversation_count=20
            _make_scalar_mock(datetime(2026, 6, 11, tzinfo=timezone.utc)),
        ]
        db.execute = AsyncMock(side_effect=effects)

        result = await list_users(db, page=1, page_size=20)

        assert result.total == 2
        assert result.page == 1
        assert result.page_size == 20
        assert len(result.items) == 2

        # 验证 user 1
        assert result.items[0].id == 1
        assert result.items[0].username == "alice"
        assert result.items[0].role == "user"
        assert result.items[0].status == "active"
        assert result.items[0].kb_count == 3
        assert result.items[0].doc_count == 15
        assert result.items[0].conversation_count == 10

        # 验证 user 2
        assert result.items[1].id == 2
        assert result.items[1].username == "bob"
        assert result.items[1].role == "admin"
        assert result.items[1].kb_count == 5

    @pytest.mark.asyncio
    async def test_用户列表按role筛选(self):
        """U15.2：按 role="admin" 筛选，仅返回 admin 用户"""
        from app.services.admin_service import list_users

        db = AsyncMock()
        admin_user = _make_user(2, "admin_user", role="admin")

        effects = [
            _make_scalar_mock(1),                   # count=1
            _make_scalars_all_mock([admin_user]),   # 仅 1 个 admin
            _make_scalar_mock(0),                   # kb_count
            _make_scalar_mock(0),                   # doc_count
            _make_scalar_mock(0),                   # conversation_count
            _make_scalar_mock(None),                # last_active_at
        ]
        db.execute = AsyncMock(side_effect=effects)

        result = await list_users(db, role="admin")

        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].role == "admin"
        assert result.items[0].username == "admin_user"

    @pytest.mark.asyncio
    async def test_用户列表按status筛选(self):
        """U15.3：按 status="disabled" 筛选，仅返回 disabled 用户"""
        from app.services.admin_service import list_users

        db = AsyncMock()
        disabled_user = _make_user(3, "banned_user", status="disabled")

        effects = [
            _make_scalar_mock(1),
            _make_scalars_all_mock([disabled_user]),
            _make_scalar_mock(1),                   # kb_count
            _make_scalar_mock(2),                   # doc_count
            _make_scalar_mock(3),                   # conversation_count
            _make_scalar_mock(None),                # last_active_at
        ]
        db.execute = AsyncMock(side_effect=effects)

        result = await list_users(db, status="disabled")

        assert result.total == 1
        assert result.items[0].status == "disabled"
        assert result.items[0].username == "banned_user"

    @pytest.mark.asyncio
    async def test_用户列表按用户名搜索(self):
        """U15.4：按 search="zhang" 模糊搜索，仅返回用户名含 zhang 的用户"""
        from app.services.admin_service import list_users

        db = AsyncMock()
        user = _make_user(4, "zhangsan")

        effects = [
            _make_scalar_mock(1),
            _make_scalars_all_mock([user]),
            _make_scalar_mock(2),                   # kb_count
            _make_scalar_mock(8),                   # doc_count
            _make_scalar_mock(5),                   # conversation_count
            _make_scalar_mock(datetime(2026, 6, 10, tzinfo=timezone.utc)),
        ]
        db.execute = AsyncMock(side_effect=effects)

        result = await list_users(db, search="zhang")

        assert result.total == 1
        assert result.items[0].username == "zhangsan"

    @pytest.mark.asyncio
    async def test_用户列表空结果(self):
        """无匹配用户时返回 total=0, items=[]"""
        from app.services.admin_service import list_users

        db = AsyncMock()

        effects = [
            _make_scalar_mock(0),
            _make_scalars_all_mock([]),
        ]
        db.execute = AsyncMock(side_effect=effects)

        result = await list_users(db)

        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_用户列表聚合统计为零(self):
        """用户无任何关联数据时，kb_count/doc_count/conversation_count/last_active_at 均为 0/None"""
        from app.services.admin_service import list_users

        db = AsyncMock()
        user = _make_user(5, "new_user")

        effects = [
            _make_scalar_mock(1),
            _make_scalars_all_mock([user]),
            _make_scalar_mock(None),                # kb_count → None → or 0
            _make_scalar_mock(None),                # doc_count
            _make_scalar_mock(None),                # conversation_count
            _make_scalar_mock(None),                # last_active_at
        ]
        db.execute = AsyncMock(side_effect=effects)

        result = await list_users(db)

        assert result.items[0].kb_count == 0
        assert result.items[0].doc_count == 0
        assert result.items[0].conversation_count == 0
        assert result.items[0].last_active_at is None


# ==================== get_user_detail 测试 ====================


class TestGetUserDetail:
    """get_user_detail — 用户详情 Service 测试

    对齐 TEST_CASES.md §6.15.1：U15.5-U15.6
    """

    @pytest.mark.asyncio
    async def test_用户详情正常返回(self):
        """U15.5：返回含 kb_count/doc_count/conversation_count/message_count/token 统计"""
        from app.services.admin_service import get_user_detail

        db = AsyncMock()
        user = _make_user(3, "zhangsan")
        db.get = AsyncMock(return_value=user)

        # execute 调用顺序：kb_count / doc_count / conversation_count / message_count / token_stats
        token_execute_mock = MagicMock()
        token_execute_mock.one.return_value = (5000, 2000, datetime(2026, 6, 12, tzinfo=timezone.utc))

        effects = [
            _make_scalar_mock(2),                   # kb_count
            _make_scalar_mock(15),                  # doc_count
            _make_scalar_mock(28),                  # conversation_count
            _make_scalar_mock(156),                 # message_count
            token_execute_mock,                     # token_stats (用 .one())
        ]
        db.execute = AsyncMock(side_effect=effects)

        result = await get_user_detail(db, user_id=3)

        assert result.id == 3
        assert result.username == "zhangsan"
        assert result.role == "user"
        assert result.status == "active"
        assert result.kb_count == 2
        assert result.doc_count == 15
        assert result.conversation_count == 28
        assert result.message_count == 156
        assert result.total_input_tokens == 5000
        assert result.total_output_tokens == 2000

    @pytest.mark.asyncio
    async def test_用户详情不存在抛出异常(self):
        """U15.6：查询不存在的用户抛出 UserNotFoundException (E7002)"""
        from app.core.exceptions import UserNotFoundException
        from app.services.admin_service import get_user_detail

        db = AsyncMock()
        db.get = AsyncMock(return_value=None)

        with pytest.raises(UserNotFoundException):
            await get_user_detail(db, user_id=99999)

    @pytest.mark.asyncio
    async def test_用户详情token统计为零(self):
        """无 trace 数据时 token 统计为 0，last_active_at 为 None"""
        from app.services.admin_service import get_user_detail

        db = AsyncMock()
        user = _make_user(10, "new_user")
        db.get = AsyncMock(return_value=user)

        token_execute_mock = MagicMock()
        token_execute_mock.one.return_value = (0, 0, None)

        effects = [
            _make_scalar_mock(0),                   # kb_count
            _make_scalar_mock(0),                   # doc_count
            _make_scalar_mock(0),                   # conversation_count
            _make_scalar_mock(0),                   # message_count
            token_execute_mock,                     # token_stats 全零
        ]
        db.execute = AsyncMock(side_effect=effects)

        result = await get_user_detail(db, user_id=10)

        assert result.total_input_tokens == 0
        assert result.total_output_tokens == 0
        assert result.last_active_at is None


# ==================== change_user_status 测试 ====================


class TestChangeUserStatus:
    """change_user_status — 禁用/启用用户 Service 测试

    对齐 TEST_CASES.md §6.15.1：U15.9-U15.10
    """

    @pytest.mark.asyncio
    async def test_禁用用户(self):
        """U15.9：status="disabled" 时状态更新为 disabled，并吊销 token"""
        from app.services.admin_service import change_user_status

        db = AsyncMock()
        user = _make_user(3, "target_user", status="active")
        db.get = AsyncMock(return_value=user)
        db.flush = AsyncMock()

        with patch(
            "app.services.auth_service.revoke_all_user_tokens",
            new_callable=AsyncMock,
        ) as mock_revoke:
            result = await change_user_status(
                db, user_id=3, new_status="disabled", current_user_id=2,
            )

        assert result.status == "disabled"
        assert result.id == 3
        assert result.username == "target_user"
        assert user.status == "disabled"
        db.flush.assert_called_once()
        mock_revoke.assert_called_once_with(db, 3)

    @pytest.mark.asyncio
    async def test_启用用户(self):
        """U15.10：status="active" 时状态更新为 active，不吊销 token"""
        from app.services.admin_service import change_user_status

        db = AsyncMock()
        user = _make_user(3, "target_user", status="disabled")
        db.get = AsyncMock(return_value=user)
        db.flush = AsyncMock()

        with patch(
            "app.services.auth_service.revoke_all_user_tokens",
            new_callable=AsyncMock,
        ) as mock_revoke:
            result = await change_user_status(
                db, user_id=3, new_status="active", current_user_id=2,
            )

        assert result.status == "active"
        assert user.status == "active"
        db.flush.assert_called_once()
        # 启用时不吊销 token
        mock_revoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_禁止操作自己(self):
        """admin 不能修改自己的状态，抛出 AdminSelfModifyException (E7003)"""
        from app.core.exceptions import AdminSelfModifyException
        from app.services.admin_service import change_user_status

        db = AsyncMock()

        with pytest.raises(AdminSelfModifyException):
            await change_user_status(
                db, user_id=2, new_status="disabled", current_user_id=2,
            )

    @pytest.mark.asyncio
    async def test_用户不存在(self):
        """操作不存在的用户抛出 UserNotFoundException (E7002)"""
        from app.core.exceptions import UserNotFoundException
        from app.services.admin_service import change_user_status

        db = AsyncMock()
        db.get = AsyncMock(return_value=None)

        with pytest.raises(UserNotFoundException):
            await change_user_status(
                db, user_id=99999, new_status="disabled", current_user_id=2,
            )

    @pytest.mark.asyncio
    async def test_状态相同时不更新(self):
        """用户已是目标状态时直接返回，不执行 flush"""
        from app.services.admin_service import change_user_status

        db = AsyncMock()
        user = _make_user(3, "target_user", status="active")
        db.get = AsyncMock(return_value=user)
        db.flush = AsyncMock()

        result = await change_user_status(
            db, user_id=3, new_status="active", current_user_id=2,
        )

        assert result.status == "active"
        db.flush.assert_not_called()


# ==================== reset_user_password 测试 ====================


class TestResetUserPassword:
    """reset_user_password — 重置用户密码 Service 测试

    对齐 TEST_CASES.md §6.15.1：U15.11-U15.12
    """

    @pytest.mark.asyncio
    async def test_重置密码成功(self):
        """U15.11：有效 user_id + new_password，密码哈希更新，吊销 token"""
        from app.services.admin_service import reset_user_password

        db = AsyncMock()
        user = _make_user(3, "target_user")
        user.password_hash = "$2b$12$old_hash_value"
        db.get = AsyncMock(return_value=user)
        db.flush = AsyncMock()

        with patch("app.services.admin_service.verify_password", return_value=False) as mock_verify, \
             patch("app.services.admin_service.hash_password", return_value="$2b$12$new_hash_value") as mock_hash, \
             patch("app.services.auth_service.revoke_all_user_tokens", new_callable=AsyncMock) as mock_revoke:

            result = await reset_user_password(db, user_id=3, new_password="NewPass123!")

        assert result.id == 3
        assert result.username == "target_user"
        mock_verify.assert_called_once_with("NewPass123!", "$2b$12$old_hash_value")
        mock_hash.assert_called_once_with("NewPass123!")
        assert user.password_hash == "$2b$12$new_hash_value"
        db.flush.assert_called_once()
        mock_revoke.assert_called_once_with(db, 3)

    @pytest.mark.asyncio
    async def test_重置密码用户不存在(self):
        """U15.12：无效 user_id 抛出 UserNotFoundException (E7002)"""
        from app.core.exceptions import UserNotFoundException
        from app.services.admin_service import reset_user_password

        db = AsyncMock()
        db.get = AsyncMock(return_value=None)

        with pytest.raises(UserNotFoundException):
            await reset_user_password(db, user_id=99999, new_password="NewPass123!")

    @pytest.mark.asyncio
    async def test_新密码与原密码相同(self):
        """新密码与原密码相同时抛出 PasswordSameAsCurrentException (E7004)"""
        from app.core.exceptions import PasswordSameAsCurrentException
        from app.services.admin_service import reset_user_password

        db = AsyncMock()
        user = _make_user(3, "target_user")
        user.password_hash = "$2b$12$existing_hash"
        db.get = AsyncMock(return_value=user)

        with patch("app.services.admin_service.verify_password", return_value=True):
            with pytest.raises(PasswordSameAsCurrentException):
                await reset_user_password(db, user_id=3, new_password="SamePassword!")
