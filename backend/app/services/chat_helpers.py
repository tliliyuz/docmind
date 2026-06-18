"""问答辅助函数 — 历史消息加载、会话标题生成、引用标注提取、sources 事件构建

提供 SSE 问答管线所需的纯工具函数，无状态、无 DB 连接管理，仅依赖配置和 LLM 调用。
"""

import logging
import re
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.llm import chat_completion
from app.models.message import Message
from app.rag.chunker import estimate_tokens
from app.rag.evidence_auditor import EvidenceAuditResult
from app.schemas.chat import ChatSourceChunk, PreviewRange

logger = logging.getLogger(__name__)

# LLM "未找到相关信息" 关键词：两级匹配策略
# 1. 前缀匹配（前 35 字符）：LLM 首句声明"知识库中未找到"= 真阴性
# 2. 引用标注兜底：全文含"未找到" 且 无 [来源N] 引用 = LLM 未找到可用 chunk
#    有 [来源N] 标注 = LLM 认为自己有价值引用 → sources 应保留
_NOT_FOUND_KEYWORDS = ["未找到相关信息", "知识库中未找到"]
_CITATION_PATTERN = re.compile(r'\[来源(\d+)\]')


# 标题截断长度：从用户问题前 N 个字符截取作为会话标题
TITLE_TRUNCATE_LENGTH = 12


def generate_title(question: str) -> str:
    """自动生成会话标题：截取用户问题前 N 字，去除标点。

    对齐 ARCHITECTURE.md §5.1 / ROADMAP.md Decision #24。
    """
    title = question[:TITLE_TRUNCATE_LENGTH]
    title = re.sub(r"[^\w\s一-鿿]", "", title)
    return title.strip() or "新对话"


async def generate_title_llm(question: str) -> str:
    """LLM 生成会话标题，失败时回退到前 12 字截断。

    对齐 ROADMAP.md §6.1 任务 3：替换「前 12 字截断」方案。
    此函数在 SSE 流结束后异步调用，不阻塞 finish 事件。
    """
    try:
        result = await chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": "你是一个标题生成器。根据用户的提问，生成一个简洁的中文对话标题（不超过 20 字）。只输出标题文本，不要加引号或其他格式。",
                },
                {"role": "user", "content": question},
            ],
            deep_thinking=False,
        )
        title = result.content.strip().strip('"\'""')
        if title and len(title) <= 50:
            return title[:20]
    except Exception:
        logger.warning("LLM 标题生成失败，回退到截断方案")

    # 回退：前 12 字截断（保留原逻辑）
    return generate_title(question)


async def load_history(
    db: AsyncSession,
    conversation_id: int,
    max_tokens: int = settings.HISTORY_BUDGET,
    max_messages: int = settings.HISTORY_MAX_MESSAGES,
) -> list[dict[str, str]]:
    """从 DB 加载历史消息，Token 预算截断 + [来源N] 去除。

    对齐 ARCHITECTURE.md §8.2：
    1. 查询最近 N 条消息（ORDER BY created_at DESC LIMIT 40）
    2. 反转为时间正序
    3. 从旧到新逐条累加 token，超 HISTORY_BUDGET 停止
    4. assistant 消息去除 [来源N] 标记
    5. 不注入 thinking_content

    Returns:
        [{"role": "user"/"assistant", "content": "..."}, ...]
    """
    # 查询条数 = max_messages × 2（覆盖 user+assistant 角色）+ 安全余量
    # 避免 settings.HISTORY_MAX_MESSAGES 调大后硬编码 40 不够用
    _limit = max(max_messages * 2, 40)
    q = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(_limit)
    )
    rows = (await db.execute(q)).scalars().all()

    # 反转为时间正序
    rows = list(reversed(rows))

    # Token 优先截断 + 条数硬上限
    result: list[dict[str, str]] = []
    total_tokens = 0
    for msg in rows:
        # system 消息不注入历史（系统 prompt 由 Prompt Builder 单独管理）
        if msg.role == "system":
            continue

        content = msg.content
        # assistant 消息去除 [来源N] 标记（§8.4）
        if msg.role == "assistant":
            content = re.sub(r'\[来源\d+\]', '', content).strip()
        # 不注入 thinking_content（§8.5）

        tokens = estimate_tokens(content)
        if total_tokens + tokens > max_tokens:
            # 跳过当前大消息，尝试后续（更新的）较小消息
            # 使用 continue 而非 break，避免一条大旧消息阻塞所有后续消息
            continue
        if len(result) >= max_messages:
            break

        result.append({"role": msg.role, "content": content})
        total_tokens += tokens

    return result


def extract_citation_indices(text: str) -> set[str]:
    """从 LLM 回答中提取所有 [来源N] 的编号 N，去重返回。

    用于 sources 引用过滤：仅发送 LLM 实际引用的 chunk，
    过滤进入 Prompt 但未被引用的无关 chunk。

    Args:
        text: LLM 完整回答文本

    Returns:
        去重后的编号集合（字符串形式），如 {"1", "3"}。
        空字符串或无引用时返回空集合。
    """
    if not text:
        return set()
    return set(_CITATION_PATTERN.findall(text))


def build_sources(
    chunks: list,
    doc_map: dict[int, str],
) -> list[ChatSourceChunk]:
    """构建 sources 事件的 chunks 列表。

    对齐 API.md §6.1 event: sources + ARCHITECTURE.md §5.1.7 Evidence Highlight：
    - chunk_index 与 LLM 回答中的 [来源N] 编号一一对应
    - content 保留完整 chunk 内容（向前兼容）
    - preview_text：Evidence 定位（matched_sentence ±100 字符窗口）
    - highlight_start / highlight_end：证据句在 preview_text 内的偏移，前端纯渲染
    - doc_name 从 doc_map 查询
    """
    sources = []
    for i, chunk in enumerate(chunks):
        chunk_index = i + 1  # 与 LLM Prompt 中 [来源N] 编号一致
        content = chunk.content if chunk.content else ""

        # Evidence 预览：matched_sentence 由 sentence_matcher 在检索阶段填充，
        # 保证是 chunk 子串，find() 必然命中
        preview_text = None
        preview_range = None
        highlight_start = None
        highlight_end = None
        matched = getattr(chunk, 'matched_sentence', None)
        if matched and content:
            idx = content.find(matched)
            center = idx + len(matched) // 2
            start = max(0, center - 100)
            end = min(len(content), center + 100)
            preview_text = content[start:end]
            preview_range = PreviewRange(start=start, end=end)
            # 高亮区间：matched_sentence 在 preview_text 内的偏移
            hl_start = idx - start
            hl_end = hl_start + len(matched)
            # 边界裁剪（窗口未完全覆盖句子时）
            hl_start = max(0, hl_start)
            hl_end = min(len(preview_text), hl_end)
            if hl_start < hl_end:
                highlight_start = hl_start
                highlight_end = hl_end

        sources.append(ChatSourceChunk(
            chunk_index=chunk_index,
            doc_id=chunk.doc_id,
            doc_name=doc_map.get(chunk.doc_id, ""),
            content=content,
            score=round(chunk.score, 4),
            page=chunk.page,
            section_title=getattr(chunk, 'section_title', None) or None,
            section_path=getattr(chunk, 'section_path', None) or None,
            preview_text=preview_text,
            preview_range=preview_range,
            highlight_start=highlight_start,
            highlight_end=highlight_end,
        ))
    return sources


def build_sources_event_data(
    sources: list[ChatSourceChunk],
    audit_result: EvidenceAuditResult | None = None,
) -> dict:
    """构建 sources SSE 事件的 data dict，含置信度标注。

    对齐 ROADMAP.md §8.3：
    审计发现问题时通过 confidence 字段标注，前端据此展示警告提示。
    """
    data: dict = {"chunks": [s.model_dump() for s in sources]}
    if audit_result:
        data["confidence"] = audit_result.confidence_level
        if audit_result.confidence_note:
            data["confidence_note"] = audit_result.confidence_note
    return data
