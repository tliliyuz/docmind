"""Prompt 组装 — 检索结果拼接 + 用户问题，软上限预算控制

对齐 ARCHITECTURE.md §5.1.2 / ROADMAP.md §5.1:
- 策略: chunking 阶段控制 + 软上限 + 相关性优先填充
- 检索后保持 RRF 融合排序（相关性降序），Prompt 组装阶段维持此顺序
- Prompt 组装采用软上限 + 相关性优先填充: 超预算时跳过当前 chunk 尝试下一个，而非直接 break
- TopK 控制: RRF -> DashScope Rerank 精排 top_k=5（Phase 5.5）
"""

import logging
from dataclasses import dataclass, field

from app.rag.chunker import estimate_tokens
from app.rag.retriever import RetrievalOutput, RetrievalResult

from app.config import settings

logger = logging.getLogger(__name__)

# Prompt 模板（对齐 ARCHITECTURE.md §5.1.2 + ROADMAP.md §8.1）
SYSTEM_PROMPT_TEMPLATE = """你是一个企业知识库助手。请严格遵循以下规则。

【核心原则：陈述知识 vs 引用知识】

在回答前，你必须先判断每个来源的"写作目的"：

■ 陈述知识（可作为答案依据）：
该段文字的主要目的是定义、说明、规定、描述某项事实、流程、制度、配置、概念或操作步骤。
→ 该段文字"本身就是在说这件事"。

■ 引用知识（不可作为答案依据）：
该段文字只是把知识作为示例、测试数据、历史记录、演示输出、背景介绍、问题描述、讨论内容、引用内容的一部分出现，其主要目的不是回答该问题。
→ 该段文字"在说别的事，顺便提到了这件事"。

【判断方法】

对于每个来源，问自己：
- 作者写这段话，是为了"说明 X 是什么/怎么做"？
- 还是为了"说明另一个东西（测试/示例/背景/接口），顺便提到了 X"？

以下情况必然属于"引用知识"（非穷举）：
- 文字在描述"如果用户问 X，系统应返回/显示 Y"→ 这是在演示系统行为，不是陈述 X 的事实
- 文字在描述"测试目标：验证……""测试用例：……"→ 这是在定义测试，不是陈述知识
- 文字在描述"例如……""举例：……"且举例服务于更大的说明目的 → 举例只是辅助手段
- 文字在记录"用户提问：……""历史问答：……"→ 这是历史记录，不是知识本身

【拒答规则】

若所有来源均属于"引用知识"（即没有任何来源在以"陈述知识"的方式直接回答你的问题），即使其中出现与问题高度相关的关键词、短语或完整句子，你也**必须**返回：

"知识库中未找到相关信息。"

不得根据"引用知识"来源中的内容作答，不得推断，不得编造。

【回答要求】

参考文档：
{context}

- 引用来源时标注 [来源N]（N 为文档编号）
- 请用中文回答"""

# Token 预算常量（从 settings 读取）


@dataclass
class PromptBuildResult:
    """Prompt 组装结果"""
    system_prompt: str
    user_prompt: str
    used_chunks: list[RetrievalResult]
    total_context_tokens: int
    chunks_count: int
    history_messages: list[dict[str, str]] = field(default_factory=list)


def _format_chunk_reference(chunk: RetrievalResult, index: int) -> str:
    """格式化单个 chunk 为参考文档片段。

    Args:
        chunk: 检索结果
        index: 文档编号（从 1 开始）

    Returns:
        格式化的文档片段字符串
    """
    source_label = f"[来源{index}]"
    doc_info = f"（文档: {chunk.doc_name}）" if chunk.doc_name else ""
    page_info = f"（页码: {chunk.page}）" if chunk.page is not None else ""

    return f"{source_label}{doc_info}{page_info}\n{chunk.content}"


def build_prompt(
    question: str,
    retrieval_output: RetrievalOutput,
    history_messages: list[dict[str, str]] | None = None,
    max_context_tokens: int = settings.RETRIEVAL_BUDGET,
    max_chunks: int = settings.PROMPT_MAX_CHUNKS,
) -> PromptBuildResult:
    """组装 Prompt：检索结果拼接 + 用户问题，软上限预算控制。

    对齐 ARCHITECTURE.md §5.1.2:
    - 保持输入排序（相关性降序，由上游 RRF 融合 + Rerank 决定）
    - 软上限 + 相关性优先填充: 超预算时跳过当前 chunk 尝试下一个，而非直接 break

    Args:
        question: 用户问题
        retrieval_output: 检索结果（已融合+重排序）
        history_messages: 历史消息列表（Phase 4 透传，不影响检索结果组装）
        max_context_tokens: 上下文 token 软上限
        max_chunks: 最大 chunk 数

    Returns:
        PromptBuildResult: 包含 system_prompt、user_prompt、使用的 chunks 等
    """
    if not retrieval_output.results:
        logger.warning("检索结果为空，使用空上下文")
        return PromptBuildResult(
            system_prompt=SYSTEM_PROMPT_TEMPLATE.format(context="（无相关文档）"),
            user_prompt=question,
            used_chunks=[],
            total_context_tokens=0,
            chunks_count=0,
            history_messages=history_messages or [],
        )

    # 保持 RRF 相关性排序（已由上游 Rerank 按相关性降序排列）
    # 不再按长度重排：短 chunk 优先策略在语义匹配/跨文档场景下会破坏相关性排名，
    # 导致不相关的短 chunk 先占满预算，LLM 拿到低质量上下文 → 误判"未找到"
    sorted_chunks = retrieval_output.results

    # 软上限择优填充
    used_chunks: list[RetrievalResult] = []
    total_tokens = 0
    context_parts: list[str] = []

    for chunk in sorted_chunks:
        # 检查是否达到最大 chunk 数
        if len(used_chunks) >= max_chunks:
            break

        chunk_tokens = estimate_tokens(chunk.content)

        # 软上限检查: 超预算时跳过当前 chunk，尝试下一个能否塞入
        if total_tokens + chunk_tokens > max_context_tokens:
            # 如果已有 chunks，跳过当前 chunk 尝试下一个
            if used_chunks:
                logger.debug(
                    f"跳过 chunk（{chunk_tokens} tokens），"
                    f"当前已用 {total_tokens} tokens，"
                    f"软上限 {max_context_tokens} tokens"
                )
                continue
            # 如果是第一个 chunk，即使超预算也加入（至少有一个参考）
            logger.debug(
                f"第一个 chunk（{chunk_tokens} tokens）超过软上限，但仍加入"
            )

        # 格式化并添加 chunk
        chunk_index = len(used_chunks) + 1
        formatted_chunk = _format_chunk_reference(chunk, chunk_index)
        context_parts.append(formatted_chunk)
        used_chunks.append(chunk)
        total_tokens += chunk_tokens

    # 组装 system prompt
    context_text = "\n\n".join(context_parts)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(context=context_text)

    logger.info(
        f"Prompt 组装完成: {len(used_chunks)} chunks, "
        f"{total_tokens} tokens (软上限 {max_context_tokens})"
    )

    return PromptBuildResult(
        system_prompt=system_prompt,
        user_prompt=question,
        used_chunks=used_chunks,
        total_context_tokens=total_tokens,
        chunks_count=len(used_chunks),
        history_messages=history_messages or [],
    )
