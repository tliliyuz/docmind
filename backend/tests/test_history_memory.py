"""历史记忆单元测试 — _load_history() Token 截断 + [来源N] 去除 + 条数硬上限
+ Retrieval 超限截断 + 双池子独立截断

对齐 TEST_CASES.md §6.2：
- H1.1  空历史 → []
- H1.2  少量消息全部注入
- H1.3  Token 超限截断（从旧到新移除）
- H1.4  条数硬上限（max_messages=20）
- H1.5  assistant 消息 [来源N] 去除
- H1.6  thinking_content 不注入
- H1.7  system 消息不注入
- U8.2  Retrieval 超限截断（从低分 chunk 丢弃）
- U8.3  History + Retrieval 双池子独立截断
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import settings
from app.rag.chunker import estimate_tokens
from app.rag.prompt_builder import build_prompt
from app.rag.retriever import RetrievalOutput, RetrievalResult
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


# ============================================================
# U8.2: Retrieval 超限截断 — 从低分 chunk 开始丢弃
# 对齐 ARCHITECTURE.md §8.1 + TEST_CASES.md §6.2 U8.2
# ============================================================


class TestRetrievalBudgetTruncation:
    """U8.2: 检索结果 token > RETRIEVAL_BUDGET(10000) → 从低分 chunk 开始丢弃

    对齐 ARCHITECTURE.md §8.1：
    - Retrieval Chunks ≤ 10000 tokens
    - 超限策略：从低分 chunk 开始丢弃直到预算内
    - build_prompt() 保持 RRF 相关性排序，高分优先填充
    """

    def test_超预算从低分chunk丢弃(self):
        """当检索结果总 token 超过 RETRIEVAL_BUDGET 时，低分 chunk 被优先丢弃"""
        # 构造 12 个中文 chunk，每个约 1200 tokens，总计约 14400 tokens > 10000
        chunks = []
        for i in range(12):
            content = "检索结果内容" * 300  # ~1800 中文字 ≈ 1200 tokens
            chunks.append(RetrievalResult(
                doc_id=1, chunk_index=i,
                content=content,
                score=round(0.95 - i * 0.04, 2),
            ))
        output = RetrievalOutput(results=chunks)

        # 使用 RETRIEVAL_BUDGET + 足够大的 max_chunks（覆盖默认 PROMPT_MAX_CHUNKS=5）
        result = build_prompt("测试问题", output, max_chunks=20)

        # 验证：并非所有 chunk 都被保留
        assert result.chunks_count < 12
        # 验证：最高分的 chunk 被保留
        assert result.used_chunks[0].score == 0.95
        # 验证：保留的 chunks 按 score 降序（相关性优先）
        used_scores = [c.score for c in result.used_chunks]
        assert used_scores == sorted(used_scores, reverse=True)
        # 验证：总 token 不超过 RETRIEVAL_BUDGET
        assert result.total_context_tokens <= settings.RETRIEVAL_BUDGET
        # 验证：最低分的 chunk 被丢弃（不是随机丢弃，而是从低分开始丢弃）
        assert chunks[-1].score not in used_scores

    def test_软上限跳过超大chunk保留更小低分chunk(self):
        """软上限策略：超大 chunk 被跳过后，更小的低分 chunk 仍可加入

        对齐 ARCHITECTURE.md §8.1 + prompt_builder 软上限逻辑：
        超预算时 continue（而非 break），尝试后续较小 chunk
        """
        medium = "中等长度的检索内容" * 30  # ~180 中文字 ≈ 120 tokens
        large = "超大长度的检索内容" * 200  # ~1200 中文字 ≈ 800 tokens
        small = "短"

        chunks = [
            RetrievalResult(doc_id=1, chunk_index=0, content=medium, score=0.9),
            RetrievalResult(doc_id=1, chunk_index=1, content=medium, score=0.8),
            RetrievalResult(doc_id=1, chunk_index=2, content=large, score=0.7),
            RetrievalResult(doc_id=2, chunk_index=0, content=small, score=0.6),
        ]
        output = RetrievalOutput(results=chunks)

        # 预算：够 chunk1 + chunk2 + chunk4，但不够 + chunk3
        medium_tokens = estimate_tokens(medium)
        small_tokens = estimate_tokens(small)
        budget = medium_tokens * 2 + small_tokens + 5  # 留 5 tokens 余量

        result = build_prompt("问题", output, max_context_tokens=budget)

        used_scores = [c.score for c in result.used_chunks]
        # chunk1、chunk2（高分+中等大小）一定在
        assert 0.9 in used_scores
        assert 0.8 in used_scores
        # chunk3（超大，score=0.7）应被跳过
        assert 0.7 not in used_scores
        # chunk4（小，score=0.6）应能塞入（软上限 continue 策略）
        assert 0.6 in used_scores

    def test_保留chunk的score严格降序_低分先丢弃(self):
        """保留的 chunks 按 score 严格降序排列，验证「从低分开始丢弃」策略

        当 budget 不够所有 chunk 时，丢弃的总是 score 最低的尾部 chunk
        """
        # 5 个 chunk，score 递减，大小相似
        chunks = [
            RetrievalResult(doc_id=i, chunk_index=0,
                            content="内容" * 200,  # ~400 中文字 ≈ 267 tokens
                            score=round(0.95 - i * 0.1, 2))
            for i in range(5)
        ]
        output = RetrievalOutput(results=chunks)

        # 每个 chunk 约 267 tokens，设置 budget=800 → 只能保留前 3 个
        result = build_prompt("问题", output, max_context_tokens=800, max_chunks=20)

        used_scores = [c.score for c in result.used_chunks]
        # 保留的 score 应为前 N 个（最高的），而非随机选择
        assert used_scores == sorted(used_scores, reverse=True)
        # score 最低的一定不在
        assert 0.55 not in used_scores
        # score 最高的 2 个一定在
        assert 0.95 in used_scores
        assert 0.85 in used_scores


# ============================================================
# U8.3: History + Retrieval 同时超限 → 各自独立截断，互不侵蚀
# 对齐 ARCHITECTURE.md §8.1 + TEST_CASES.md §6.2 U8.3
# ============================================================


class TestHistoryRetrievalDualBudget:
    """U8.3: History + Retrieval 同时超限 → 各自独立截断，互不侵蚀

    对齐 ARCHITECTURE.md §8.1：各池子独立控制预算，互不侵蚀。
    P0 Bug 防御：避免历史挤掉检索 → RAG 退化。
    """

    @pytest.mark.asyncio
    async def test_双池子独立截断(self):
        """History 和 Retrieval 各自独立截断，互不侵蚀"""
        # 1. 构造超过 HISTORY_BUDGET 的历史消息
        db = AsyncMock()
        long_content = "这是一段较长的历史消息内容" * 100  # ~1200 中文字 ≈ 800 tokens
        messages = [
            _make_message(msg_id=i, role="user" if i % 2 == 1 else "assistant",
                          content=long_content)
            for i in range(1, 11)  # 10 条 × ~800 tokens = ~8000 > 6000
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = list(reversed(messages))
        db.execute.return_value = mock_result

        # 加载历史（应截断到 ≤ HISTORY_BUDGET=6000）
        history = await _load_history(db, conversation_id=1)
        history_tokens = sum(estimate_tokens(m["content"]) for m in history)
        assert history_tokens <= settings.HISTORY_BUDGET
        assert len(history) < 10  # 部分消息被截断

        # 2. 构造超过 RETRIEVAL_BUDGET 的检索结果
        retrieval_chunks = [
            RetrievalResult(
                doc_id=1, chunk_index=i,
                content="检索结果内容" * 200,  # ~1200 中文字 ≈ 800 tokens
                score=round(0.95 - i * 0.04, 2),
            )
            for i in range(15)  # 15 × ~800 = ~12000 > 10000
        ]
        retrieval_output = RetrievalOutput(results=retrieval_chunks)

        # 3. 调用 build_prompt，传入截断后的历史
        prompt_result = build_prompt("测试问题", retrieval_output,
                                     history_messages=history, max_chunks=20)

        # 验证：检索结果被独立截断（不受历史影响）
        assert prompt_result.total_context_tokens <= settings.RETRIEVAL_BUDGET
        assert prompt_result.chunks_count < 15

        # 验证：历史消息被原样传递（未被 build_prompt 进一步截断）
        assert prompt_result.history_messages == history
        assert len(prompt_result.history_messages) == len(history)

        # P0 Bug 防御：总 token = history + retrieval 不超过各自预算之和
        total_tokens = history_tokens + prompt_result.total_context_tokens
        assert total_tokens <= settings.HISTORY_BUDGET + settings.RETRIEVAL_BUDGET

    @pytest.mark.asyncio
    async def test_历史不侵蚀检索预算(self):
        """历史消息占满 HISTORY_BUDGET 不影响 RETRIEVAL_BUDGET

        P0 Bug 防御：如果历史和检索共享预算，
        检索只能用 RETRIEVAL_BUDGET - HISTORY_BUDGET = 4000 tokens，
        这会导致 RAG 退化（检索结果不够）。
        """
        # 构造占满 HISTORY_BUDGET 的历史
        db = AsyncMock()
        messages = [
            _make_message(msg_id=i, role="user" if i % 2 == 1 else "assistant",
                          content="历史消息" * 250)  # ~1000 中文字 ≈ 667 tokens
            for i in range(1, 12)  # 11 条 × ~667 tokens ≈ 7337 > 6000
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = list(reversed(messages))
        db.execute.return_value = mock_result

        history = await _load_history(db, conversation_id=1)
        history_tokens = sum(estimate_tokens(m["content"]) for m in history)
        assert history_tokens > 0  # 历史非空
        assert history_tokens <= settings.HISTORY_BUDGET

        # 构造大量检索结果
        retrieval_chunks = [
            RetrievalResult(
                doc_id=1, chunk_index=i,
                content="检索内容" * 300,  # ~900 中文字 ≈ 600 tokens
                score=round(0.95 - i * 0.03, 2),
            )
            for i in range(20)  # 20 × ~600 = ~12000 > 10000
        ]
        retrieval_output = RetrievalOutput(results=retrieval_chunks)

        prompt_result = build_prompt("问题", retrieval_output,
                                     history_messages=history, max_chunks=20)

        # 关键断言：检索预算仍为 RETRIEVAL_BUDGET，不受历史占用影响
        assert prompt_result.total_context_tokens <= settings.RETRIEVAL_BUDGET
        # 检索应该能用到接近 RETRIEVAL_BUDGET 的 token
        # 如果历史侵蚀了检索预算，retrieval tokens 会远小于 RETRIEVAL_BUDGET
        # （例如共享预算时只剩余 10000 - 6000 = 4000 tokens）
        assert prompt_result.total_context_tokens > settings.RETRIEVAL_BUDGET * 0.5

    @pytest.mark.asyncio
    async def test_检索不侵蚀历史预算(self):
        """检索结果占满 RETRIEVAL_BUDGET 不影响 HISTORY_BUDGET"""
        # 构造超出 HISTORY_BUDGET 的历史
        db = AsyncMock()
        messages = [
            _make_message(msg_id=i, role="user" if i % 2 == 1 else "assistant",
                          content="历史消息" * 200)  # ~800 中文字 ≈ 533 tokens
            for i in range(1, 15)  # 14 条 × ~533 tokens = ~7462 > 6000
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = list(reversed(messages))
        db.execute.return_value = mock_result

        history = await _load_history(db, conversation_id=1)
        original_history_len = len(history)
        history_tokens = sum(estimate_tokens(m["content"]) for m in history)

        # 构造占满 RETRIEVAL_BUDGET 的检索结果
        retrieval_chunks = [
            RetrievalResult(
                doc_id=1, chunk_index=0,
                content="检索结果" * 3000,  # ~9000 tokens
                score=0.9,
            ),
        ]
        retrieval_output = RetrievalOutput(results=retrieval_chunks)

        prompt_result = build_prompt("问题", retrieval_output,
                                     history_messages=history)

        # 关键断言：历史消息不受检索影响
        assert len(prompt_result.history_messages) == original_history_len
        assert prompt_result.history_messages == history
        # 历史非空（如果检索侵蚀了历史，历史可能为空或减少）
        assert len(prompt_result.history_messages) > 0
        # 历史仍在 HISTORY_BUDGET 内
        assert history_tokens <= settings.HISTORY_BUDGET
