"""历史记忆单元测试 — _load_history() Token 截断 + [来源N] 去除 + 条数硬上限

对齐 TEST_CASES.md §6.2：
- H1.1  空历史 → []
- H1.2  少量消息全部注入
- H1.3  Token 超限截断（从旧到新移除）
- H1.4  条数硬上限（max_messages=20）
- H1.5  assistant 消息 [来源N] 去除
- H1.6  thinking_content 不注入
- H1.7  system 消息不注入
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import settings
from app.services.chat_service import _load_history


def _make_message(msg_id=1, role="user", content="测试内容",
                  thinking_content=None, created_at=None):
    """构造 Message ORM Mock 对象"""
    msg = MagicMock()
    msg.id = msg_id
    msg.role = role
    msg.content = content
    msg.thinking_content = thinking_content
    msg.created_at = created_at or datetime.now(timezone.utc)
    return msg


class TestLoadHistoryEmpty:
    """空历史 → 返回空列表"""

    @pytest.mark.asyncio
    async def test_empty_conversation(self):
        db = AsyncMock()
        # 模拟查询返回空列表
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result

        result = await _load_history(db, conversation_id=1)
        assert result == []


class TestLoadHistoryBasicInjection:
    """少量消息全部注入"""

    @pytest.mark.asyncio
    async def test_few_messages_all_injected(self):
        db = AsyncMock()
        messages = [
            _make_message(msg_id=1, role="user", content="第一个问题"),
            _make_message(msg_id=2, role="assistant", content="第一个回答"),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = list(reversed(messages))
        db.execute.return_value = mock_result

        result = await _load_history(db, conversation_id=1)
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "第一个问题"
        assert result[1]["role"] == "assistant"
        assert result[1]["content"] == "第一个回答"


class TestLoadHistoryTokenTruncation:
    """Token 超限时从旧到新移除"""

    @pytest.mark.asyncio
    async def test_token_budget_truncation(self):
        """最新消息优先保留，超大旧消息被跳过"""
        db = AsyncMock()
        # msg1 极长（会被 continue 跳过），msg2-4 较短（应保留）
        long_msg = "非常长的消息内容占据大量空间" * 100  # ~1200 中文字符 → ~800 tokens
        messages = [
            _make_message(msg_id=1, role="user", content=long_msg),           # 旧：~800 tokens → 超 budget
            _make_message(msg_id=2, role="assistant", content="中等长度回答" * 20),  # ~120 中文字符 → ~80 tokens
            _make_message(msg_id=3, role="user", content="短问题"),                 # 最新：很短
            _make_message(msg_id=4, role="assistant", content="短回答"),            # 最新：很短
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = list(reversed(messages))
        db.execute.return_value = mock_result

        # 小预算：msg1 被 continue 跳过，msg2-4 在预算内
        result = await _load_history(db, conversation_id=1, max_tokens=500)

        # msg1 被跳过，msg2 + msg3 + msg4 共 3 条
        assert len(result) == 3
        # 结果按时间正序排列
        assert result[0]["role"] == "assistant"  # msg2（中等）
        assert result[1]["role"] == "user"       # msg3（短问题）
        assert result[2]["role"] == "assistant"  # msg4（短回答）
        # 最旧的大消息 msg1 被跳过
        assert all(long_msg not in m["content"] for m in result)


class TestLoadHistoryMaxMessages:
    """条数硬上限"""

    @pytest.mark.asyncio
    async def test_max_messages_limit(self):
        db = AsyncMock()
        # 创建 30 条短消息（不超过 token 预算）
        messages = [
            _make_message(msg_id=i, role="user" if i % 2 == 1 else "assistant", content=f"消息{i}")
            for i in range(1, 31)
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = list(reversed(messages))
        db.execute.return_value = mock_result

        result = await _load_history(db, conversation_id=1, max_tokens=100000, max_messages=20)
        assert len(result) <= 20


class TestLoadHistorySourceMarkerRemoval:
    """assistant 消息 [来源N] 去除"""

    @pytest.mark.asyncio
    async def test_source_markers_removed(self):
        db = AsyncMock()
        messages = [
            _make_message(msg_id=1, role="user", content="问题"),
            _make_message(msg_id=2, role="assistant", content="根据[来源1]和[来源3]，报销需要发票[来源2]"),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = list(reversed(messages))
        db.execute.return_value = mock_result

        result = await _load_history(db, conversation_id=1)
        # assistant 消息中不应包含 [来源N]
        assistant_msg = [m for m in result if m["role"] == "assistant"][0]
        assert "[来源" not in assistant_msg["content"]
        assert "根据和，报销需要发票" in assistant_msg["content"] or "报销需要发票" in assistant_msg["content"]

    @pytest.mark.asyncio
    async def test_user_content_unchanged(self):
        """user 消息中即使包含 [来源N] 也不去除"""
        db = AsyncMock()
        messages = [
            _make_message(msg_id=1, role="user", content="请展开[来源1]"),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = list(reversed(messages))
        db.execute.return_value = mock_result

        result = await _load_history(db, conversation_id=1)
        assert result[0]["content"] == "请展开[来源1]"


class TestLoadHistoryThinkingContentExcluded:
    """thinking_content 不注入"""

    @pytest.mark.asyncio
    async def test_thinking_not_injected(self):
        db = AsyncMock()
        messages = [
            _make_message(msg_id=1, role="user", content="问题"),
            _make_message(msg_id=2, role="assistant", content="回答",
                          thinking_content="深度思考过程" * 100),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = list(reversed(messages))
        db.execute.return_value = mock_result

        result = await _load_history(db, conversation_id=1)
        # 结果只包含 role 和 content 字段
        assert len(result) == 2
        assert "thinking_content" not in result[1]


class TestLoadHistorySystemMessageExcluded:
    """system 消息不注入历史"""

    @pytest.mark.asyncio
    async def test_system_messages_filtered_out(self):
        """_load_history 过滤 role=system 的消息"""
        db = AsyncMock()
        messages = [
            _make_message(msg_id=1, role="system", content="你是一个有帮助的助手"),
            _make_message(msg_id=2, role="user", content="问题"),
            _make_message(msg_id=3, role="assistant", content="回答"),
            _make_message(msg_id=4, role="system", content="中间注入的系统消息"),
            _make_message(msg_id=5, role="user", content="追问"),
            _make_message(msg_id=6, role="assistant", content="回答追问"),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = list(reversed(messages))
        db.execute.return_value = mock_result

        result = await _load_history(db, conversation_id=1)

        # system 消息被过滤，只保留 user + assistant
        assert len(result) == 4
        assert all(m["role"] in ("user", "assistant") for m in result)
        # 验证 user 消息内容正确（没有被 system 挤掉位置）
        user_roles = [m["role"] for m in result]
        assert user_roles == ["user", "assistant", "user", "assistant"]
