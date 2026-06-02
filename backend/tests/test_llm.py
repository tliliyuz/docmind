"""LLM 调用模块测试

对齐 ARCHITECTURE.md §5.1.3:
- DeepSeek API (OpenAI 兼容)
- 流式 chat/completions
- extra_body 控制 thinking
- reasoning_effort 仅在 deep_thinking=true 时传递
- 解析 content + reasoning_content
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.core.llm import (
    LLMChunk,
    LLMResult,
    stream_chat_completion,
    chat_completion,
)
from app.core.exceptions import LLMCallFailedException, LLMRateLimitExceededException


@pytest.fixture
def mock_llm_client():
    """模拟 LLM 客户端"""
    with patch("app.core.llm.AsyncOpenAI") as mock:
        client = AsyncMock()
        mock.return_value = client
        yield client


@pytest.fixture
def sample_messages():
    """示例消息"""
    return [
        {"role": "system", "content": "你是一个助手"},
        {"role": "user", "content": "测试问题"},
    ]


class TestLLMChunk:
    """测试 LLMChunk 数据类"""

    def test_默认值(self):
        """默认值应为空字符串"""
        chunk = LLMChunk()
        assert chunk.content == ""
        assert chunk.reasoning_content == ""
        assert chunk.finish_reason is None

    def test_赋值(self):
        """应能正确赋值"""
        chunk = LLMChunk(
            content="回答内容",
            reasoning_content="思考过程",
            finish_reason="stop",
        )
        assert chunk.content == "回答内容"
        assert chunk.reasoning_content == "思考过程"
        assert chunk.finish_reason == "stop"


class TestLLMResult:
    """测试 LLMResult 数据类"""

    def test_默认值(self):
        """默认值应为 0"""
        result = LLMResult(
            content="",
            reasoning_content="",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
        )
        assert result.prompt_tokens == 0
        assert result.completion_tokens == 0
        assert result.total_tokens == 0


class AsyncIteratorMock:
    """模拟异步迭代器"""

    def __init__(self, items):
        self.items = items
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        return item


class TestStreamChatCompletion:
    """测试流式 LLM 调用"""

    @pytest.mark.asyncio
    async def test_正常流式输出(self, mock_llm_client, sample_messages):
        """正常流式输出应返回 chunks"""
        # 模拟流式响应
        mock_chunks = [
            MagicMock(
                choices=[MagicMock(
                    delta=MagicMock(content="你好", reasoning_content=""),
                    finish_reason=None,
                )]
            ),
            MagicMock(
                choices=[MagicMock(
                    delta=MagicMock(content="世界", reasoning_content="思考"),
                    finish_reason="stop",
                )]
            ),
            MagicMock(choices=[]),  # 空 chunk
        ]

        mock_llm_client.chat.completions.create = AsyncMock(
            return_value=AsyncIteratorMock(mock_chunks)
        )

        chunks = []
        async for chunk in stream_chat_completion(sample_messages, deep_thinking=True):
            chunks.append(chunk)

        assert len(chunks) == 2
        assert chunks[0].content == "你好"
        assert chunks[1].content == "世界"
        assert chunks[1].reasoning_content == "思考"
        assert chunks[1].finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_deep_thinking参数(self, mock_llm_client, sample_messages):
        """deep_thinking=true 应设置 thinking type=enabled"""
        mock_llm_client.chat.completions.create = AsyncMock(
            return_value=AsyncIteratorMock([])
        )

        async for _ in stream_chat_completion(sample_messages, deep_thinking=True):
            pass

        call_args = mock_llm_client.chat.completions.create.call_args
        assert call_args.kwargs["extra_body"]["thinking"]["type"] == "enabled"

    @pytest.mark.asyncio
    async def test_deep_thinking关闭(self, mock_llm_client, sample_messages):
        """deep_thinking=false 应设置 thinking type=disabled 且不传 reasoning_effort"""
        mock_llm_client.chat.completions.create = AsyncMock(
            return_value=AsyncIteratorMock([])
        )

        async for _ in stream_chat_completion(sample_messages, deep_thinking=False):
            pass

        call_args = mock_llm_client.chat.completions.create.call_args
        assert call_args.kwargs["extra_body"]["thinking"]["type"] == "disabled"
        assert "reasoning_effort" not in call_args.kwargs

    @pytest.mark.asyncio
    async def test_reasoning_effort参数(self, mock_llm_client, sample_messages):
        """deep_thinking=true 时 reasoning_effort 应传递给 API"""
        mock_llm_client.chat.completions.create = AsyncMock(
            return_value=AsyncIteratorMock([])
        )

        async for _ in stream_chat_completion(
            sample_messages,
            deep_thinking=True,
            reasoning_effort="high",
        ):
            pass

        call_args = mock_llm_client.chat.completions.create.call_args
        assert call_args.kwargs["reasoning_effort"] == "high"

    @pytest.mark.asyncio
    async def test_限流异常(self, mock_llm_client, sample_messages):
        """限流应抛出 LLMRateLimitExceededException"""
        mock_llm_client.chat.completions.create = AsyncMock(
            side_effect=Exception("Rate limit exceeded (429)")
        )

        with pytest.raises(LLMRateLimitExceededException):
            async for _ in stream_chat_completion(sample_messages):
                pass

    @pytest.mark.asyncio
    async def test_其他异常(self, mock_llm_client, sample_messages):
        """其他异常应抛出 LLMCallFailedException"""
        mock_llm_client.chat.completions.create = AsyncMock(
            side_effect=Exception("Connection error")
        )

        with pytest.raises(LLMCallFailedException):
            async for _ in stream_chat_completion(sample_messages):
                pass


class TestChatCompletion:
    """测试非流式 LLM 调用"""

    @pytest.mark.asyncio
    async def test_正常调用(self, mock_llm_client, sample_messages):
        """正常调用应返回 LLMResult"""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content="回答内容",
                    reasoning_content="思考过程",
                )
            )
        ]
        mock_response.usage = MagicMock(
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )

        mock_llm_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await chat_completion(sample_messages, deep_thinking=True)

        assert isinstance(result, LLMResult)
        assert result.content == "回答内容"
        assert result.reasoning_content == "思考过程"
        assert result.prompt_tokens == 10
        assert result.completion_tokens == 20
        assert result.total_tokens == 30

    @pytest.mark.asyncio
    async def test_空结果异常(self, mock_llm_client, sample_messages):
        """空结果应抛出 LLMCallFailedException"""
        mock_response = MagicMock()
        mock_response.choices = []

        mock_llm_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with pytest.raises(LLMCallFailedException):
            await chat_completion(sample_messages)

    @pytest.mark.asyncio
    async def test_限流异常(self, mock_llm_client, sample_messages):
        """限流应抛出 LLMRateLimitExceededException"""
        mock_llm_client.chat.completions.create = AsyncMock(
            side_effect=Exception("Rate limit (429)")
        )

        with pytest.raises(LLMRateLimitExceededException):
            await chat_completion(sample_messages)

    @pytest.mark.asyncio
    async def test_其他异常(self, mock_llm_client, sample_messages):
        """其他异常应抛出 LLMCallFailedException"""
        mock_llm_client.chat.completions.create = AsyncMock(
            side_effect=Exception("API error")
        )

        with pytest.raises(LLMCallFailedException):
            await chat_completion(sample_messages)

    @pytest.mark.asyncio
    async def test_deep_thinking参数(self, mock_llm_client, sample_messages):
        """deep_thinking 应传递给 API"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="回答", reasoning_content=""))]
        mock_response.usage = MagicMock(prompt_tokens=0, completion_tokens=0, total_tokens=0)

        mock_llm_client.chat.completions.create = AsyncMock(return_value=mock_response)

        await chat_completion(sample_messages, deep_thinking=True)

        call_args = mock_llm_client.chat.completions.create.call_args
        assert call_args.kwargs["extra_body"]["thinking"]["type"] == "enabled"
        assert call_args.kwargs["reasoning_effort"] == "high"

    @pytest.mark.asyncio
    async def test_非流式deep_thinking关闭不传reasoning_effort(self, mock_llm_client, sample_messages):
        """非流式 deep_thinking=false 不应传 reasoning_effort"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="回答", reasoning_content=""))]
        mock_response.usage = MagicMock(prompt_tokens=0, completion_tokens=0, total_tokens=0)

        mock_llm_client.chat.completions.create = AsyncMock(return_value=mock_response)

        await chat_completion(sample_messages, deep_thinking=False)

        call_args = mock_llm_client.chat.completions.create.call_args
        assert call_args.kwargs["extra_body"]["thinking"]["type"] == "disabled"
        assert "reasoning_effort" not in call_args.kwargs
