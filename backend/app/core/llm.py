"""LLM 调用模块 — DeepSeek API（OpenAI 兼容），流式 chat/completions

对齐 ARCHITECTURE.md §5.1.3 / ROADMAP.md §5.1:
- DeepSeek API (OpenAI 兼容接口)
- 流式 chat/completions
- extra_body 控制 thinking: deep_thinking=true -> {"thinking": {"type": "enabled"}}
- reasoning_effort 仅在 deep_thinking=true 时传递，避免 disabled + effort 冲突
- 解析 content + reasoning_content
"""

import logging
import time
from dataclasses import dataclass
from typing import AsyncIterator

from openai import AsyncOpenAI

from app.config import settings
from app.core.exceptions import LLMCallFailedException, LLMRateLimitExceededException

logger = logging.getLogger(__name__)

# 模块级单例：AsyncOpenAI 客户端（避免每次请求新建实例）
_llm_client: AsyncOpenAI | None = None


@dataclass
class LLMChunk:
    """LLM 流式输出的单个 chunk"""
    content: str = ""
    reasoning_content: str = ""
    finish_reason: str | None = None


@dataclass
class LLMResult:
    """LLM 调用结果"""
    content: str
    reasoning_content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


def _get_llm_client() -> AsyncOpenAI:
    """获取 AsyncOpenAI 客户端实例（模块级惰性单例）。

    对齐 config.py 中的 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL。
    """
    global _llm_client
    if _llm_client is None:
        _llm_client = AsyncOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
        )
    return _llm_client


async def stream_chat_completion(
    messages: list[dict[str, str]],
    deep_thinking: bool = False,
    reasoning_effort: str = "high",
) -> AsyncIterator[LLMChunk]:
    """流式调用 LLM chat/completions。

    对齐 ARCHITECTURE.md §5.1.3:
    - deep_thinking=true -> extra_body={"thinking": {"type": "enabled"}}
    - deep_thinking=false -> extra_body={"thinking": {"type": "disabled"}}
    - reasoning_effort: 仅 deep_thinking=true 时传递，固定 "high"

    Args:
        messages: OpenAI 格式的消息列表 [{"role": "system/user/assistant", "content": "..."}]
        deep_thinking: 是否启用深度思考
        reasoning_effort: 推理强度（固定 "high"）

    Yields:
        LLMChunk: 流式输出的 content 和 reasoning_content

    Raises:
        LLMCallFailedException: LLM 调用失败
        LLMRateLimitExceededException: 限流
    """
    client = _get_llm_client()

    # 构建请求参数（对齐 ARCHITECTURE.md §5.1.3）
    thinking_type = "enabled" if deep_thinking else "disabled"
    extra_body = {
        "thinking": {"type": thinking_type},
    }
    request_kwargs = {
        "model": settings.LLM_MODEL,
        "messages": messages,
        "stream": True,
        "extra_body": extra_body,
    }
    if deep_thinking:
        request_kwargs["reasoning_effort"] = reasoning_effort

    try:
        logger.info(f"调用 LLM: model={settings.LLM_MODEL}, deep_thinking={deep_thinking}")
        t0 = time.perf_counter()
        t_first = None

        stream = await client.chat.completions.create(**request_kwargs)

        async for chunk in stream:
            if not chunk.choices:
                continue

            choice = chunk.choices[0]
            delta = choice.delta

            # 解析 content 和 reasoning_content
            content = delta.content or ""
            reasoning_content = getattr(delta, "reasoning_content", "") or ""

            if t_first is None and (content or reasoning_content):
                t_first = time.perf_counter()
                logger.info("LLM_PERF(流式) 首Token=%.3fs", t_first - t0)

            yield LLMChunk(
                content=content,
                reasoning_content=reasoning_content,
                finish_reason=choice.finish_reason,
            )

    except Exception as e:
        error_msg = str(e)
        logger.error(f"LLM 调用失败: {error_msg}")

        # 区分限流和其他错误
        if "rate_limit" in error_msg.lower() or "429" in error_msg:
            raise LLMRateLimitExceededException(detail=error_msg)

        raise LLMCallFailedException(detail=error_msg)


async def chat_completion(
    messages: list[dict[str, str]],
    deep_thinking: bool = False,
    reasoning_effort: str = "high",
    max_tokens: int | None = None,
    model: str | None = None,
) -> LLMResult:
    """非流式调用 LLM chat/completions（用于标题生成、意图分类等场景）。

    Args:
        messages: OpenAI 格式的消息列表
        deep_thinking: 是否启用深度思考
        reasoning_effort: 推理强度
        max_tokens: 最大输出 token 数（None 时使用模型默认值）
        model: 模型名称（None 时使用 settings.LLM_FLASH_MODEL，适合轻量任务）

    Returns:
        LLMResult: 包含 content、reasoning_content、token 使用量

    Raises:
        LLMCallFailedException: LLM 调用失败
        LLMRateLimitExceededException: 限流
    """
    client = _get_llm_client()
    llm_model = model or settings.LLM_FLASH_MODEL

    thinking_type = "enabled" if deep_thinking else "disabled"
    extra_body = {
        "thinking": {"type": thinking_type},
    }
    request_kwargs = {
        "model": llm_model,
        "messages": messages,
        "stream": False,
        "extra_body": extra_body,
    }
    if deep_thinking:
        request_kwargs["reasoning_effort"] = reasoning_effort
    if max_tokens is not None:
        request_kwargs["max_tokens"] = max_tokens

    try:
        logger.info(f"调用 LLM (非流式): model={llm_model}")
        t0 = time.perf_counter()

        response = await client.chat.completions.create(**request_kwargs)
        t_api = time.perf_counter()

        if not response.choices:
            raise LLMCallFailedException(detail="LLM 返回空结果")

        choice = response.choices[0]
        content = choice.message.content or ""
        reasoning_content = getattr(choice.message, "reasoning_content", "") or ""

        # 提取 token 使用量
        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else 0

        logger.info(
            "LLM_PERF(非流式) api=%.3fs prompt_tok=%d completion_tok=%d",
            t_api - t0, prompt_tokens, completion_tokens,
        )

        return LLMResult(
            content=content,
            reasoning_content=reasoning_content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    except LLMCallFailedException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"LLM 调用失败: {error_msg}")

        if "rate_limit" in error_msg.lower() or "429" in error_msg:
            raise LLMRateLimitExceededException(detail=error_msg)

        raise LLMCallFailedException(detail=error_msg)
