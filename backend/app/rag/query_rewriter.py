"""Query Rewrite — 多轮对话问题重写模块

对齐 ARCHITECTURE.md §5.1.5：
- needs_rewrite(): 轻量歧义检测，仅在含代词/指示词等歧义信号时触发
- rewrite_query(): LLM 上下文补全改写，失败时降级返回原始 question
- 仅取最近 2 轮（4 条消息）作为改写上下文
- 改写结果不持久化，仅用于检索阶段

触发策略说明：
- 仅检查明确的歧义信号词（代词/指示词/上下文引用），不使用短问题阈值
- 中文问题天然短（「VPN 密码忘了怎么办」11 字，「病假需要提供医院证明吗」14 字），
  短问题阈值会导致大量语义完整的独立问题被强制改写，引入噪声
"""

import logging
from dataclasses import dataclass

from app.config import settings
from app.core.llm import chat_completion

logger = logging.getLogger(__name__)

# 歧义信号词列表：代词/指示词/上下文引用
# 仅当 question 包含其中任一信号词时才触发 rewrite，不使用短问题阈值
AMBIGUOUS_SIGNALS = [
    "它", "这个", "那个", "该", "此", "呢", "那",
    "他们", "这些", "那些",
    "上面", "前面说的", "刚才",
]

REWRITE_SYSTEM_PROMPT = """你是一个查询改写助手。根据对话历史，将用户的最新问题改写为一个完整、独立、可直接用于检索的问题。

规则：
- 将代词（它、这个、那个、该、此）替换为对话历史中对应的实体
- 补全省略的主语或宾语
- 保持原问题的核心意图不变
- 只输出改写后的问题，不要解释，不要其他内容"""

REWRITE_USER_TEMPLATE = """对话历史：
{history}

用户问题：{question}
改写后的问题："""


@dataclass
class RewriteResult:
    """问题重写结果 — 携带改写后的文本和 LLM 调用元数据。

    对齐 ARCHITECTURE.md §5.1.8：
    - metadata.model: 使用的 LLM 模型名（未触发重写时为 None）
    - metadata.input_tokens / output_tokens: Token 消耗（未触发重写时为 0）
    """
    rewritten: str
    metadata: dict

# 引号字符集（用于剥离 LLM 可能输出的引号包裹，含 ASCII 引号 + 中文双/单引号）
_QUOTE_CHARS = "\"'“”‘’"


def needs_rewrite(question: str, history: list[dict[str, str]] | None) -> bool:
    """判断是否需要 Query Rewrite。

    纯函数，零外部依赖。仅当同时满足以下条件时返回 True：
    1. 存在历史对话（有可参考的上下文）
    2. 当前问题含明确的歧义信号词（代词/指示词/上下文引用）

    不使用短问题阈值：中文问题天然短，14 字以下的独立完整问题
    （如「病假需要提供医院证明吗」）被强制改写反而引入噪声。

    Args:
        question: 用户原始问题
        history: 历史消息（已由 _load_history() 处理，不含 [来源N]）

    Returns:
        bool: True 表示需要改写
    """
    if not history:
        return False

    # 检查是否含明确歧义信号词（代词/指示词/上下文引用）
    return any(s in question for s in AMBIGUOUS_SIGNALS)



async def rewrite_query(
    question: str,
    history: list[dict[str, str]],
) -> RewriteResult:
    """对歧义问题进行上下文补全改写。

    Args:
        question: 用户原始问题
        history: 历史消息（已由 _load_history() 处理，不含 [来源N]）

    Returns:
        RewriteResult。LLM 调用失败时降级返回原始 question。
    """
    # 仅取最近 2 轮（4 条消息）作为改写上下文
    max_history = settings.REWRITE_HISTORY_MESSAGES
    recent = history[-max_history:] if len(history) > max_history else history

    # 格式化历史为纯文本
    history_text = "\n".join(
        f"{'用户' if m['role'] == 'user' else '助手'}: {m['content']}"
        for m in recent
    )

    try:
        result = await chat_completion(
            messages=[
                {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
                {"role": "user", "content": REWRITE_USER_TEMPLATE.format(
                    history=history_text,
                    question=question,
                )},
            ],
            deep_thinking=False,  # 改写不需要深度思考
        )
        rewritten = result.content.strip().strip(_QUOTE_CHARS)
        if rewritten and len(rewritten) >= settings.REWRITE_MIN_LENGTH:
            logger.info("Query Rewrite 成功: %s → %s", question[:50], rewritten[:80])
        else:
            logger.warning("Query Rewrite 输出异常（空或过短），降级使用原始 query")
            rewritten = question
        return RewriteResult(
            rewritten=rewritten,
            metadata={
                "model": settings.LLM_FLASH_MODEL,
                "input_tokens": result.prompt_tokens,
                "output_tokens": result.completion_tokens,
            },
        )
    except Exception:
        logger.exception("Query Rewrite LLM 调用失败，降级使用原始 query")
        return RewriteResult(
            rewritten=question,
            metadata={"model": None, "input_tokens": 0, "output_tokens": 0},
        )
