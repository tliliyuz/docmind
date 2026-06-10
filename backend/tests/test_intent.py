"""意图识别单元测试

对齐 ROADMAP.md §7.5 / TEST_CASES.md：
- 分类正确性 6 用例（知识查询/闲谈/元问题各 2 个）
- 路由逻辑 2 用例（META 返回固定响应；CASUAL 跳过检索）
- 降级回退 2 用例（LLM 失败 → 正则降级；无效标签 → 正则降级）

覆盖 app/rag/intent.py + chat_service.py 集成
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.llm import LLMResult
from app.rag.intent import Intent, classify_intent


# ==================== 辅助函数 ====================


def _make_llm_result(content: str) -> LLMResult:
    """构造 LLM 非流式调用结果"""
    return LLMResult(
        content=content,
        reasoning_content="",
        prompt_tokens=10,
        completion_tokens=1,
        total_tokens=11,
    )


# ==================== 分类正确性（6 用例） ====================


@pytest.mark.asyncio
async def test_classify_knowledge_policy_question():
    """U-I01: 政策类问题 → KNOWLEDGE"""
    with patch("app.rag.intent.chat_completion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _make_llm_result("KNOWLEDGE")
        result = await classify_intent("报销需要提交哪些材料？")
        assert result == Intent.KNOWLEDGE
        mock_llm.assert_called_once()
        # 验证 deep_thinking=False + max_tokens=10
        call_kwargs = mock_llm.call_args
        assert call_kwargs.kwargs.get("deep_thinking") is False
        assert call_kwargs.kwargs.get("max_tokens") == 10


@pytest.mark.asyncio
async def test_classify_knowledge_technical_question():
    """U-I02: 技术规范问题 → KNOWLEDGE"""
    with patch("app.rag.intent.chat_completion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _make_llm_result("KNOWLEDGE")
        result = await classify_intent("VPN 密码忘了怎么办？")
        assert result == Intent.KNOWLEDGE


@pytest.mark.asyncio
async def test_classify_casual_greeting():
    """U-I03: 问候语 → CASUAL"""
    with patch("app.rag.intent.chat_completion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _make_llm_result("CASUAL")
        result = await classify_intent("你好")
        assert result == Intent.CASUAL


@pytest.mark.asyncio
async def test_classify_casual_thanks():
    """U-I04: 致谢 → CASUAL"""
    with patch("app.rag.intent.chat_completion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _make_llm_result("CASUAL")
        result = await classify_intent("谢谢你的帮助")
        assert result == Intent.CASUAL


@pytest.mark.asyncio
async def test_classify_meta_capability():
    """U-I05: 询问助手能力 → META"""
    with patch("app.rag.intent.chat_completion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _make_llm_result("META")
        result = await classify_intent("你能做什么？")
        assert result == Intent.META


@pytest.mark.asyncio
async def test_classify_meta_format_support():
    """U-I06: 询问支持格式 → META"""
    with patch("app.rag.intent.chat_completion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _make_llm_result("META")
        result = await classify_intent("支持什么文件格式？")
        assert result == Intent.META


# ==================== 降级回退（2 用例） ====================


@pytest.mark.asyncio
async def test_fallback_on_llm_failure():
    """U-I07: LLM 调用失败 → 降级回退正则

    正则命中「你好」→ CASUAL；正则未命中 → KNOWLEDGE（保守策略）。
    """
    with patch("app.rag.intent.chat_completion", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = Exception("LLM 调用失败")

        # 问候语命中正则 → CASUAL
        result_casual = await classify_intent("你好")
        assert result_casual == Intent.CASUAL

        # 普通问题未命中正则 → KNOWLEDGE（保守路由）
        result_knowledge = await classify_intent("报销制度是什么？")
        assert result_knowledge == Intent.KNOWLEDGE


@pytest.mark.asyncio
async def test_fallback_on_invalid_label():
    """U-I08: LLM 返回无效标签 → 降级回退正则

    LLM 返回 "UNKNOWN" 不在有效标签集合中，触发降级。
    """
    with patch("app.rag.intent.chat_completion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _make_llm_result("UNKNOWN")

        # 问候语命中正则 → CASUAL
        result = await classify_intent("你好")
        assert result == Intent.CASUAL


# ==================== 路由逻辑（2 用例，集成测试） ====================


@pytest.mark.asyncio
async def test_meta_routing_returns_fixed_response():
    """U-I09: META 意图 → chat() 返回固定 SSE 响应（不调 LLM）

    验证 MetaQuestionException 被捕获后，返回 StreamingResponse。
    """
    from app.core.exceptions import MetaQuestionException
    from app.services.chat_service import chat

    mock_conv = MagicMock()
    mock_conv.id = 1
    mock_conv.message_count = 0
    mock_conv.user_id = 1

    mock_kb = MagicMock()
    mock_kb.id = 1
    mock_kb.status = "active"
    mock_kb.visibility = "private"
    mock_kb.user_id = 1

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=mock_kb)

    mock_user_msg = MagicMock(id=10, role="user", content="你能做什么？")

    with patch("app.services.chat_service.classify_intent", new_callable=AsyncMock) as mock_classify, \
         patch("app.services.chat_service.Conversation", return_value=mock_conv), \
         patch("app.services.chat_service.Message", return_value=mock_user_msg):
        mock_classify.return_value = Intent.META

        # _validate_and_prepare 应抛出 MetaQuestionException
        with pytest.raises(MetaQuestionException) as exc_info:
            from app.services.chat_service import _validate_and_prepare
            await _validate_and_prepare(
                db=mock_db, user_id=1, role="user",
                conversation_id=None, kb_id=1, question="你能做什么？",
            )

        # 验证异常携带 conv 信息
        assert exc_info.value.conv == mock_conv
        assert exc_info.value.is_first_turn is True


@pytest.mark.asyncio
async def test_casual_routing_skips_retrieval():
    """U-I10: CASUAL 意图 → 跳过检索，使用 CASUAL_SYSTEM_PROMPT

    验证 CASUAL 路径下不调用向量检索和 BM25 检索。
    """
    from app.services.chat_service import _validate_and_prepare, CASUAL_SYSTEM_PROMPT

    mock_conv = MagicMock()
    mock_conv.id = 1
    mock_conv.user_id = 1
    mock_conv.message_count = 0
    mock_conv.title = "新对话"

    mock_kb = MagicMock()
    mock_kb.id = 1
    mock_kb.status = "active"
    mock_kb.visibility = "private"
    mock_kb.user_id = 1

    mock_db = AsyncMock()

    def get_side_effect(model, pk):
        if model.__name__ == "KnowledgeBase":
            return mock_kb
        if model.__name__ == "Conversation":
            return mock_conv
        return None

    mock_db.get = AsyncMock(side_effect=get_side_effect)

    # 历史查询返回空
    history_result = MagicMock()
    history_result.scalars.return_value.all.return_value = []
    # 文档名查询返回空
    doc_name_result = MagicMock()
    doc_name_result.scalars.return_value.all.return_value = []

    mock_db.execute = AsyncMock(side_effect=[history_result, doc_name_result])

    with patch("app.services.chat_service.classify_intent", new_callable=AsyncMock) as mock_classify, \
         patch("app.services.chat_service.Conversation", return_value=mock_conv), \
         patch("app.services.chat_service.Message") as MockMessage, \
         patch("app.services.chat_service._vector_retriever") as mock_vec, \
         patch("app.services.chat_service._bm25_retriever") as mock_bm25:

        mock_classify.return_value = Intent.CASUAL
        MockMessage.return_value = MagicMock(id=10, role="user", content="你好")

        conv, is_first_turn, reranked_output, prompt_result, doc_map = await _validate_and_prepare(
            db=mock_db, user_id=1, role="user",
            conversation_id=None, kb_id=1, question="你好",
        )

        # CASUAL 路径：prompt 使用 CASUAL_SYSTEM_PROMPT
        assert prompt_result.system_prompt == CASUAL_SYSTEM_PROMPT
        assert prompt_result.used_chunks == []
        assert prompt_result.chunks_count == 0

        # 检索器不应被调用
        mock_vec.search.assert_not_called()
        mock_bm25.search.assert_not_called()


# ==================== 辅助导入（用于集成测试） ====================

from unittest.mock import MagicMock
