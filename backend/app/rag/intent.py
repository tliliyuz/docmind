"""意图识别模块 — LLM 3 类分类器

对齐 ARCHITECTURE.md §5.1.6：
- KNOWLEDGE: 走完整 RAG 链路（检索→RRF→Rerank→Prompt→LLM）
- CASUAL: 跳过检索，使用 CASUAL_SYSTEM_PROMPT + 历史消息 → LLM 直接回复
- META: 不调 LLM，直接返回固定模板响应（毫秒级）
- 降级：LLM 失败时回退 _is_casual_chat() 正则 stopgap

设计目标：
- 分类准确率 > 95%（相比正则 stopgap 的 ~70%）
- 分类延迟 < 300ms（轻量 Prompt + deep_thinking=False + max_tokens=10）
- LLM 分类失败时回退正则 stopgap，不影响主流程可用性
"""

import logging
from enum import Enum

from app.core.llm import chat_completion

logger = logging.getLogger(__name__)


class Intent(str, Enum):
    """意图分类枚举"""

    KNOWLEDGE = "KNOWLEDGE"  # 知识查询：走完整 RAG 链路
    CASUAL = "CASUAL"        # 闲谈：跳过检索，LLM 直接回复
    META = "META"            # 元问题：固定模板响应


# 分类 System Prompt（约 200 tokens，对齐 ARCHITECTURE.md §5.1.6）
INTENT_SYSTEM_PROMPT = """你是一个查询意图分类器。将用户问题分为以下三类之一：

- KNOWLEDGE：需要使用知识库文档来回答的问题（政策、流程、制度、技术规范等）
- CASUAL：日常闲聊、问候、致谢、与知识库无关的对话
- META：询问助手本身能力的问题（你能做什么、支持什么功能等）

仅输出类别标签，不要解释。"""

# few-shot 示例嵌入 user message（对齐 ARCHITECTURE.md §5.1.6）
INTENT_USER_TEMPLATE = """示例：
Q: 报销需要提交哪些材料？ → KNOWLEDGE
Q: 你好 → CASUAL
Q: 你能做什么？ → META
Q: 谢谢你的帮助 → CASUAL
Q: VPN 密码忘了怎么办？ → KNOWLEDGE

用户问题：{question}
分类："""

# 有效标签集合
_VALID_INTENTS = {v.value for v in Intent}


async def classify_intent(question: str) -> Intent:
    """LLM 意图分类。

    轻量分类：deep_thinking=False + max_tokens=10，预期延迟 < 300ms。

    Args:
        question: 用户问题

    Returns:
        Intent 枚举值。LLM 失败或返回无效标签时降级回退 _is_casual_chat()。
    """
    try:
        result = await chat_completion(
            messages=[
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": INTENT_USER_TEMPLATE.format(question=question)},
            ],
            deep_thinking=False,
            max_tokens=10,
        )
        label = result.content.strip().upper()

        if label in _VALID_INTENTS:
            logger.info(
                "INTENT_CLASSIFY question=%s intent=%s fallback=False",
                question[:50], label,
            )
            return Intent(label)
        else:
            logger.warning(
                "INTENT_CLASSIFY 无效标签 '%s'，降级回退正则", result.content.strip(),
            )
            return _fallback_classify(question)

    except Exception:
        logger.exception("INTENT_CLASSIFY LLM 调用失败，降级回退正则")
        return _fallback_classify(question)


def _fallback_classify(question: str) -> Intent:
    """降级分类：复用 Phase 3 正则 _is_casual_chat()。

    保守策略：正则命中 → CASUAL，否则 → KNOWLEDGE。
    「宁可查了没用，不可该查不查」——误判为知识查询多走一次检索（~1-2s），
    比误判为闲谈跳过检索导致用户得不到答案严重得多。

    Args:
        question: 用户问题

    Returns:
        Intent.CASUAL 或 Intent.KNOWLEDGE
    """
    # 局部导入：解决循环依赖（chat_service → intent → chat_service）
    # 对齐 CLAUDE.md「禁止函数内局部导入」的两种例外之一：① 解决循环导入
    from app.services.chat_service import _is_casual_chat

    if _is_casual_chat(question):
        logger.info("INTENT_FALLBACK question=%s intent=CASUAL (regex)", question[:50])
        return Intent.CASUAL
    else:
        logger.info("INTENT_FALLBACK question=%s intent=KNOWLEDGE (conservative)", question[:50])
        return Intent.KNOWLEDGE
