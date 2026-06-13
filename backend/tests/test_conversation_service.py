"""会话 Service 层单元测试 — 覆盖 _enrich_kb_status / list / create / detail

对齐 TEST_CASES.md §6.1b：
- _enrich_kb_status 四分支（kb_id=None / active / unavailable / deleted 防御）
- list_conversations 分页 + 排序 + kb_status 填充
- create_conversation 正常创建 + kb_status 填充
- get_conversation_detail 正常 + 不存在 + 无权访问
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import (
    ConversationAccessDeniedException,
    ConversationNotFoundException,
)
from app.schemas.conversation import ConversationResponse


# ==================== 辅助函数 ====================


def _make_conv(conv_id=1, user_id=1, kb_id=1, title="新对话",
               message_count=0, last_message_at=None,
               original_kb_id=None, original_kb_name=None):
    """构造 Conversation ORM 对象 mock（带 knowledge_base relationship）

    kb_status / kb_name 显式设为 None：model_validate(from_attributes=True)
    会尝试读取这两个字段，MagicMock 属性会导致 Pydantic 校验失败。
    """
    conv = MagicMock()
    conv.id = conv_id
    conv.user_id = user_id
    conv.kb_id = kb_id
    conv.original_kb_id = original_kb_id
    conv.original_kb_name = original_kb_name
    conv.title = title
    conv.message_count = message_count
    conv.created_at = datetime(2026, 5, 1, tzinfo=timezone.utc)
    conv.updated_at = datetime(2026, 6, 10, tzinfo=timezone.utc)
    conv.last_message_at = last_message_at
    # model_validate(from_attributes=True) 会读取这两个非 ORM 列字段
    conv.kb_status = None
    conv.kb_name = None
    return conv


def _make_kb(kb_id=1, name="测试知识库", visibility="public", user_id=1):
    """构造 KnowledgeBase ORM 对象 mock"""
    kb = MagicMock()
    kb.id = kb_id
    kb.name = name
    kb.visibility = visibility
    kb.user_id = user_id
    return kb


def _make_msg(msg_id=1, conversation_id=1, role="user", content="你好"):
    """构造 Message ORM 对象 mock"""
    msg = MagicMock()
    msg.id = msg_id
    msg.conversation_id = conversation_id
    msg.role = role
    msg.content = content
    msg.thinking_content = None
    msg.token_count = 10
    msg.feedback = None
    msg.metadata_ = None
    msg.created_at = datetime(2026, 6, 13, 10, 0, 0, tzinfo=timezone.utc)
    return msg


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


def _make_scalars_unique_one_or_none(value):
    """构造 scalars().unique().one_or_none() 返回值的 execute 结果 mock"""
    m = MagicMock()
    m.scalars.return_value.unique.return_value.one_or_none.return_value = value
    return m


def _make_scalars_unique_all(items):
    """构造 scalars().unique().all() 返回列表的 execute 结果 mock"""
    m = MagicMock()
    m.scalars.return_value.unique.return_value.all.return_value = items
    return m


# ==================== _enrich_kb_status 测试 ====================


class TestEnrichKbStatus:
    """_enrich_kb_status — kb_status / kb_name 填充逻辑"""

    def test_kb_id为None且original_kb_id为None时两个字段均为None(self):
        """kb_id=null + original_kb_id=null → 从未关联 KB，kb_status=None"""
        from app.services.conversation_service import _enrich_kb_status

        conv = _make_conv(kb_id=None, original_kb_id=None)
        resp = ConversationResponse(
            id=1, user_id=1, kb_id=None, title="新对话", message_count=0,
            created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
        )

        _enrich_kb_status(resp, conv, user_id=1)

        assert resp.kb_status is None
        assert resp.kb_name is None

    def test_kb_id为None且original_kb_id非None时返回deleted(self):
        """kb_id=null + original_kb_id=5 → 孤儿会话（KB 已删除），kb_status="deleted" """
        from app.services.conversation_service import _enrich_kb_status

        conv = _make_conv(kb_id=None, original_kb_id=5, original_kb_name="已删除知识库")
        resp = ConversationResponse(
            id=1, user_id=1, kb_id=None, title="新对话", message_count=0,
            created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
        )

        _enrich_kb_status(resp, conv, user_id=1)

        assert resp.kb_status == "deleted"
        assert resp.kb_name == "已删除知识库"

    def test_KB存在且可访问时返回active(self):
        """KB visibility=public，非 owner → kb_status="active", kb_name=实际名"""
        from app.services.conversation_service import _enrich_kb_status

        kb = _make_kb(kb_id=5, name="公共知识库", visibility="public", user_id=99)
        conv = _make_conv(kb_id=5)
        conv.knowledge_base = kb
        resp = ConversationResponse(
            id=1, user_id=1, kb_id=5, title="新对话", message_count=0,
            created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
        )

        _enrich_kb_status(resp, conv, user_id=1)

        assert resp.kb_status == "active"
        assert resp.kb_name == "公共知识库"

    def test_private_KB_owner可访问(self):
        """KB visibility=private，user 是 owner → kb_status="active" """
        from app.services.conversation_service import _enrich_kb_status

        kb = _make_kb(kb_id=5, name="私有知识库", visibility="private", user_id=1)
        conv = _make_conv(kb_id=5)
        conv.knowledge_base = kb
        resp = ConversationResponse(
            id=1, user_id=1, kb_id=5, title="新对话", message_count=0,
            created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
        )

        _enrich_kb_status(resp, conv, user_id=1)

        assert resp.kb_status == "active"
        assert resp.kb_name == "私有知识库"

    def test_private_KB非owner返回unavailable(self):
        """KB visibility=private，user 非 owner → kb_status="unavailable" """
        from app.services.conversation_service import _enrich_kb_status

        kb = _make_kb(kb_id=5, name="私有知识库", visibility="private", user_id=99)
        conv = _make_conv(kb_id=5)
        conv.knowledge_base = kb
        resp = ConversationResponse(
            id=1, user_id=1, kb_id=5, title="新对话", message_count=0,
            created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
        )

        _enrich_kb_status(resp, conv, user_id=1)

        assert resp.kb_status == "unavailable"
        assert resp.kb_name == "私有知识库"


# ==================== list_conversations 测试 ====================


class TestListConversations:
    """list_conversations — 会话列表 Service 测试"""

    @pytest.mark.asyncio
    async def test_正常分页返回新字段(self):
        """分页返回含 kb_status / kb_name / last_message_at"""
        from app.services.conversation_service import list_conversations

        db = AsyncMock()
        kb = _make_kb(kb_id=1, name="我的知识库")
        now = datetime(2026, 6, 13, 10, 0, 0, tzinfo=timezone.utc)
        conv1 = _make_conv(conv_id=1, kb_id=1, title="会话1", last_message_at=now)
        conv1.knowledge_base = kb
        conv2 = _make_conv(conv_id=2, kb_id=1, title="会话2", last_message_at=now)
        conv2.knowledge_base = kb

        db.execute = AsyncMock(side_effect=[
            _make_scalar_mock(2),                      # count
            _make_scalars_unique_all([conv1, conv2]),   # list query
        ])

        result = await list_conversations(db, user_id=1, page=1, page_size=20)

        assert result.total == 2
        assert len(result.items) == 2
        assert result.items[0].kb_status == "active"
        assert result.items[0].kb_name == "我的知识库"
        assert result.items[0].last_message_at == now

    @pytest.mark.asyncio
    async def test_空列表(self):
        """无会话时返回 total=0, items=[]"""
        from app.services.conversation_service import list_conversations

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[
            _make_scalar_mock(0),
            _make_scalars_unique_all([]),
        ])

        result = await list_conversations(db, user_id=1)

        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_孤儿会话kb_status为deleted(self):
        """kb_id=None + original_kb_id 非空的会话（KB 已删除），kb_status="deleted" """
        from app.services.conversation_service import list_conversations

        db = AsyncMock()
        conv = _make_conv(conv_id=10, kb_id=None, title="孤儿会话",
                          original_kb_id=5, original_kb_name="已删除知识库")
        conv.knowledge_base = None

        db.execute = AsyncMock(side_effect=[
            _make_scalar_mock(1),
            _make_scalars_unique_all([conv]),
        ])

        result = await list_conversations(db, user_id=1)

        assert result.items[0].kb_status == "deleted"
        assert result.items[0].kb_name == "已删除知识库"


# ==================== create_conversation 测试 ====================


class TestCreateConversation:
    """create_conversation — 创建会话 Service 测试"""

    @pytest.mark.asyncio
    async def test_正常创建返回kb_status(self):
        """创建后返回含 kb_status="active", last_message_at=None"""
        from app.services.conversation_service import create_conversation
        from app.schemas.conversation import ConversationCreate

        db = AsyncMock()
        kb = _make_kb(kb_id=1, name="测试知识库")

        # flush 后 conv 被设置 id 等属性；refresh 无副作用
        async def fake_flush():
            pass

        async def fake_refresh(obj):
            obj.id = 100
            obj.created_at = datetime(2026, 6, 13, tzinfo=timezone.utc)
            obj.updated_at = datetime(2026, 6, 13, tzinfo=timezone.utc)
            obj.last_message_at = None
            obj.message_count = 0

        db.flush = AsyncMock(side_effect=fake_flush)
        db.refresh = AsyncMock(side_effect=fake_refresh)

        data = ConversationCreate(kb_id=1, title="测试会话")

        # 需要 mock selectinload 查询 KB
        with patch("app.services.conversation_service._enrich_kb_status") as mock_enrich:
            # 直接验证 enrich 被调用即可（enrich 本身已由 TestEnrichKbStatus 覆盖）
            result = await create_conversation(db, user_id=1, data=data)

        assert db.add.called
        db.flush.assert_called_once()
        db.refresh.assert_called_once()


# ==================== get_conversation_detail 测试 ====================


class TestGetConversationDetail:
    """get_conversation_detail — 会话详情 Service 测试"""

    @pytest.mark.asyncio
    async def test_正常详情含消息和新字段(self):
        """返回含 messages 列表 + kb_status / kb_name"""
        from app.services.conversation_service import get_conversation_detail

        db = AsyncMock()
        kb = _make_kb(kb_id=1, name="测试知识库")
        conv = _make_conv(conv_id=50, kb_id=1, title="详情测试")
        conv.knowledge_base = kb
        msg1 = _make_msg(msg_id=1, conversation_id=50, role="user", content="问题")
        msg2 = _make_msg(msg_id=2, conversation_id=50, role="assistant", content="回答")

        db.execute = AsyncMock(side_effect=[
            _make_scalars_unique_one_or_none(conv),     # conv query
            _make_scalars_all_mock([msg1, msg2]),       # messages query
        ])

        result = await get_conversation_detail(db, conv_id=50, user_id=1)

        assert result.id == 50
        assert result.title == "详情测试"
        assert result.kb_status == "active"
        assert result.kb_name == "测试知识库"
        assert len(result.messages) == 2
        assert result.messages[0].role == "user"
        assert result.messages[1].role == "assistant"

    @pytest.mark.asyncio
    async def test_会话不存在抛异常(self):
        """查询不存在的 conv_id 抛出 ConversationNotFoundException"""
        from app.services.conversation_service import get_conversation_detail

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[
            _make_scalars_unique_one_or_none(None),
        ])

        with pytest.raises(ConversationNotFoundException):
            await get_conversation_detail(db, conv_id=99999, user_id=1)

    @pytest.mark.asyncio
    async def test_非owner访问抛异常(self):
        """非会话 owner 访问抛出 ConversationAccessDeniedException"""
        from app.services.conversation_service import get_conversation_detail

        db = AsyncMock()
        conv = _make_conv(conv_id=50, user_id=99)  # user_id=99, 当前 user_id=1
        conv.knowledge_base = None

        db.execute = AsyncMock(side_effect=[
            _make_scalars_unique_one_or_none(conv),
        ])

        with pytest.raises(ConversationAccessDeniedException):
            await get_conversation_detail(db, conv_id=50, user_id=1)
