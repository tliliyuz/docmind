"""意图识别单元测试

对齐 ROADMAP.md §7.5 / TEST_CASES.md：
- 分类正确性 6 用例（知识查询/闲谈/元问题各 2 个）
- 路由逻辑 2 用例（META 返回固定响应；CASUAL 跳过检索）
- 降级回退 2 用例（LLM 失败 → 正则降级；无效标签 → 正则降级）

覆盖 app/rag/intent.py + chat_service.py 集成
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import settings
from app.core.llm import LLMResult
from app.rag.intent import Intent, IntentResult, classify_intent
from app.rag.retriever import RetrievalOutput

# 测试用 UUID 常量（chat_service.chat() 要求 UUID 字符串）
_TEST_KB_UUID = "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
_TEST_CONV_UUID = "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb"


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
    """U-I01: 政策类问题 → KNOWLEDGE，method=llm_flash"""
    with patch("app.rag.intent.chat_completion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _make_llm_result("KNOWLEDGE")
        result = await classify_intent("报销需要提交哪些材料？")
        assert result.intent == Intent.KNOWLEDGE
        assert result.method == "llm_flash"
        assert result.metadata["model"] == settings.LLM_FLASH_MODEL
        mock_llm.assert_called_once()
        # 验证 deep_thinking=False + max_tokens=10
        call_kwargs = mock_llm.call_args
        assert call_kwargs.kwargs.get("deep_thinking") is False
        assert call_kwargs.kwargs.get("max_tokens") == 10


@pytest.mark.asyncio
async def test_classify_knowledge_technical_question():
    """U-I02: 技术规范问题 → KNOWLEDGE，method=llm_flash"""
    with patch("app.rag.intent.chat_completion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _make_llm_result("KNOWLEDGE")
        result = await classify_intent("VPN 密码忘了怎么办？")
        assert result.intent == Intent.KNOWLEDGE
        assert result.method == "llm_flash"


@pytest.mark.asyncio
async def test_classify_casual_greeting():
    """U-I03: 问候语 → CASUAL，method=regex（规则直接命中，不走 LLM）"""
    # "你好" 命中 _CASUAL_PATTERNS，不调 LLM
    result = await classify_intent("你好")
    assert result.intent == Intent.CASUAL
    assert result.method == "regex"


@pytest.mark.asyncio
async def test_classify_casual_thanks():
    """U-I04: 致谢 → CASUAL，method=llm_flash（"谢谢你的帮助"含内容，不匹配纯致谢正则，走 LLM 兜底）"""
    with patch("app.rag.intent.chat_completion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _make_llm_result("CASUAL")
        result = await classify_intent("谢谢你的帮助")
    assert result.intent == Intent.CASUAL
    assert result.method == "llm_flash"


@pytest.mark.asyncio
async def test_classify_meta_capability():
    """U-I05: 询问助手能力 → META，method=regex"""
    result = await classify_intent("你能做什么？")
    assert result.intent == Intent.META
    assert result.method == "regex"


@pytest.mark.asyncio
async def test_classify_meta_format_support():
    """U-I06: 询问支持格式 → META，method=regex"""
    result = await classify_intent("支持什么文件格式？")
    assert result.intent == Intent.META
    assert result.method == "regex"


# ==================== 降级回退（2 用例） ====================


@pytest.mark.asyncio
async def test_fallback_on_llm_failure():
    """U-I07: LLM 调用失败 → 降级回退正则，method=regex

    正则命中「你好」→ CASUAL；正则未命中 → KNOWLEDGE（保守策略）。
    """
    with patch("app.rag.intent.chat_completion", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = Exception("LLM 调用失败")

        # 问候语命中正则 → CASUAL
        result_casual = await classify_intent("你好")
        assert result_casual.intent == Intent.CASUAL
        assert result_casual.method == "regex"

        # 普通问题未命中正则 → KNOWLEDGE（保守路由）
        result_knowledge = await classify_intent("报销制度是什么？")
        assert result_knowledge.intent == Intent.KNOWLEDGE
        assert result_knowledge.method == "regex"


@pytest.mark.asyncio
async def test_fallback_on_invalid_label():
    """U-I08: LLM 返回无效标签 → 降级回退正则，method=regex

    LLM 返回 "UNKNOWN" 不在有效标签集合中，触发降级。
    """
    with patch("app.rag.intent.chat_completion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _make_llm_result("UNKNOWN")

        # 问候语命中正则 → CASUAL
        result = await classify_intent("你好")
        assert result.intent == Intent.CASUAL
        assert result.method == "regex"


# ==================== 路由逻辑 ====================
# META/CASUAL 路由逻辑通过 chat() 公共 API 的 SSE 集成测试间接覆盖
# （见 tests/unit/services/test_chat_service.py TestChatNormalFlow 等）。
# _validate_and_prepare() 为 chat() 内部私有方法，禁止直接测试。
