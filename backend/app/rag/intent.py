"""意图识别模块 — 规则快速通道 + Flash 模型兜底

对齐 ARCHITECTURE.md §5.1.6 / .claude/plans/001-intent-optimization.md P0-1：
- Stage 1: 规则分类（<1ms）— META/CASUAL regex 直接命中
- Stage 2: LLM 兜底（deepseek-v4-flash，~10%流量）— 仅 UNKNOWN 进入

优化效果：
- META "你能做什么" → <1ms regex（原 ~5s pro）
- CASUAL "你好" → <1ms regex（原 ~5s pro）
- 模糊问题 → ~1-2s flash（原 ~5s pro）
"""

import logging
import re
import time
from enum import Enum

from app.config import settings
from app.core.llm import chat_completion

logger = logging.getLogger(__name__)


class Intent(str, Enum):
    """意图分类枚举"""

    KNOWLEDGE = "KNOWLEDGE"  # 知识查询：走完整 RAG 链路
    CASUAL = "CASUAL"        # 闲谈：跳过检索，LLM 直接回复
    META = "META"            # 元问题：固定模板响应


# ========== Stage 1: 规则快速通道（<1ms） ==========

# META 模式：询问助手本身能力的问题
_META_PATTERNS = [
    re.compile(r, re.IGNORECASE)
    for r in [
        r"(你能做什么|你是什么|你的功能|你的能力|介绍一下你|你是谁)",
        r"(支持什么|有哪些功能|怎么使用|如何使用|使用方法)",
        r"(你能帮|你能回答|你能处理|你能解决)",
        r"(what can you do|what are you|who are you|introduce yourself)",
        r"(what.*support|how to use|your.*feature|your.*capability)",
    ]
]

# CASUAL 模式：问候/致谢/告别等无需检索的输入
_CASUAL_PATTERNS = [
    re.compile(r, re.IGNORECASE)
    for r in [
        r"^(你好|您好|hi|hello|嗨|hey|halo)[\s！!。.,，~～-]*$",
        r"^(谢谢|感谢|多谢|thanks|thank|thx)[\s！!。.,，~～-]*$",
        r"^(在吗|在不在|有人在吗|有人吗)[\s？?！!。.,，]*$",
        r"^(早上好|下午好|晚上好|早安|午安|晚安|good\s*morning|good\s*afternoon|good\s*evening|good\s*night)[\s！!。.,，]*$",
        r"^(再见|拜拜|bye|goodbye|see\s*you|88)[\s！!。.,，]*$",
        r"^(好的|ok|okay|嗯|哦|噢|知道了|了解了|明白了)[\s！!。.,，]*$",
    ]
]


def _is_meta_question(question: str) -> bool:
    """META 检测：询问助手能力/功能的问题"""
    cleaned = question.strip()
    for pattern in _META_PATTERNS:
        if pattern.search(cleaned):
            return True
    return False


def _is_casual_chat(question: str) -> bool:
    """轻量闲谈检测：问候/致谢/告别等无需检索的输入。

    对齐 chat_service.py Phase 3 原有逻辑，迁移至 intent.py 统一管理。
    """
    cleaned = question.strip()
    # 极短纯标点/空白（≤1 个非空白字符）
    if len(cleaned.replace(" ", "")) <= 1:
        return True
    for pattern in _CASUAL_PATTERNS:
        if pattern.match(cleaned):
            return True
    return False


# ========== Stage 2: LLM 分类（仅 ~10% 流量进入） ==========

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


async def _llm_classify(question: str) -> Intent:
    """LLM 兜底分类（deepseek-v4-flash，~10% 流量）。

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
            model=settings.LLM_FLASH_MODEL,
        )
        label = result.content.strip().upper()

        if label in _VALID_INTENTS:
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
    """降级分类：正则 stopgap。

    保守策略：正则命中 → CASUAL，否则 → KNOWLEDGE。
    「宁可查了没用，不可该查不查」——误判为知识查询多走一次检索（~1-2s），
    比误判为闲谈跳过检索导致用户得不到答案严重得多。

    Args:
        question: 用户问题

    Returns:
        Intent.CASUAL 或 Intent.KNOWLEDGE
    """
    if _is_casual_chat(question):
        logger.info("INTENT_FALLBACK question=%s intent=CASUAL (regex)", question[:50])
        return Intent.CASUAL
    else:
        logger.info("INTENT_FALLBACK question=%s intent=KNOWLEDGE (conservative)", question[:50])
        return Intent.KNOWLEDGE


async def classify_intent(question: str) -> Intent:
    """意图分类入口 — 规则优先 + Flash 模型兜底。

    Stage 1: 规则分类（<1ms）
    - META regex 命中 → 直接返回
    - CASUAL regex 命中 → 直接返回
    - UNKNOWN → 进入 Stage 2

    Stage 2: LLM 兜底（deepseek-v4-flash，~10% 流量）

    Args:
        question: 用户问题

    Returns:
        Intent 枚举值
    """
    t0 = time.perf_counter()

    # Stage 1: 规则快速通道
    if _is_meta_question(question):
        logger.info(
            "INTENT_CLASSIFY question=%s intent=META rule=True cost=%.3fms",
            question[:50], (time.perf_counter() - t0) * 1000,
        )
        return Intent.META

    if _is_casual_chat(question):
        logger.info(
            "INTENT_CLASSIFY question=%s intent=CASUAL rule=True cost=%.3fms",
            question[:50], (time.perf_counter() - t0) * 1000,
        )
        return Intent.CASUAL

    # Stage 2: LLM 兜底
    intent = await _llm_classify(question)
    logger.info(
        "INTENT_CLASSIFY question=%s intent=%s rule=False cost=%.3fs",
        question[:50], intent.value, time.perf_counter() - t0,
    )
    return intent
