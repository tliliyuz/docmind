"""会话标题 LLM 生成单元测试 — _generate_title_llm()

对齐 TEST_CASES.md §6.3：
- T1.1  LLM 正常生成标题
- T1.2  LLM 返回带引号标题 → 自动去除
- T1.3  LLM 调用失败 → 回退截断方案
- T1.4  LLM 返回空内容 → 回退截断方案
- T1.5  LLM 返回过长标题 → 截断至 20 字
"""
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.services.chat_service import _generate_title_llm, _generate_title


class TestGenerateTitleLLM:
    """LLM 标题生成"""

    @pytest.mark.asyncio
    async def test_llm_normal_title(self):
        """LLM 正常生成标题"""
        mock_result = MagicMock()
        mock_result.content = "差旅费报销流程咨询"

        with patch("app.services.chat_service.chat_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_result
            title = await _generate_title_llm("差旅费报销需要哪些材料？")

        assert title == "差旅费报销流程咨询"

    @pytest.mark.asyncio
    async def test_llm_title_with_quotes_stripped(self):
        """LLM 返回带引号的标题，自动去除"""
        mock_result = MagicMock()
        mock_result.content = '"报销流程问答"'

        with patch("app.services.chat_service.chat_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_result
            title = await _generate_title_llm("报销流程是怎样的？")

        assert title == "报销流程问答"
        assert '"' not in title
        assert '"' not in title

    @pytest.mark.asyncio
    async def test_llm_failure_fallback(self):
        """LLM 调用失败，回退到截断方案"""
        with patch("app.services.chat_service.chat_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("LLM 不可用")
            title = await _generate_title_llm("差旅费报销需要哪些材料？")

        # 应回退到 _generate_title 的截断逻辑
        assert isinstance(title, str)
        assert len(title) > 0

    @pytest.mark.asyncio
    async def test_llm_empty_content_fallback(self):
        """LLM 返回空内容，回退到截断方案"""
        mock_result = MagicMock()
        mock_result.content = "   "

        with patch("app.services.chat_service.chat_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_result
            title = await _generate_title_llm("差旅费报销需要哪些材料？")

        # 空内容视为无效，回退
        assert isinstance(title, str)
        assert len(title) > 0

    @pytest.mark.asyncio
    async def test_llm_title_too_long_truncated(self):
        """LLM 返回过长标题，截断至 20 字"""
        mock_result = MagicMock()
        mock_result.content = "这是一个非常非常长的对话标题超出了二十个字符的限制范围"

        with patch("app.services.chat_service.chat_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_result
            title = await _generate_title_llm("测试问题")

        assert len(title) <= 20

    @pytest.mark.asyncio
    async def test_fallback_matches_truncation(self):
        """回退结果与 _generate_title 一致"""
        with patch("app.services.chat_service.chat_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("LLM 不可用")
            title = await _generate_title_llm("差旅费报销需要哪些材料？")

        expected = _generate_title("差旅费报销需要哪些材料？")
        assert title == expected
