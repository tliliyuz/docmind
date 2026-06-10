"""问答业务逻辑 — 检索 → RRF → Rerank → Prompt → LLM SSE 流式输出

对齐 ARCHITECTURE.md §5.1 / ROADMAP.md §6.1：
- 多轮对话上下文：_load_history() 加载历史消息注入 LLM messages
- Token 预算四池子分拆：System 2000 / History 6000 / Retrieval 10000 / Question 2000
- 轻量闲谈检测：问候/致谢/告别等跳过检索，直接 LLM 回复
- 会话标题 LLM 生成：finish 先返回截断标题，SSE 流结束后异步调用 LLM 更新
- SSE 6 种事件类型 + 15s 心跳
- deep_thinking → extra_body thinking 参数映射
"""

import logging
import re
from datetime import datetime, timezone
from typing import AsyncIterator
from uuid import uuid4

from fastapi.responses import StreamingResponse
from sqlalchemy import and_, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import async_session
from app.core.exceptions import (
    ConversationAccessDeniedException,
    ConversationNotFoundException,
    KnowledgeBaseEmptyException,
    KnowledgeBaseNotFoundException,
    MetaQuestionException,
    PermissionDeniedException,
    QuestionEmptyException,
    RetrievalServiceException,
)
from app.core.llm import chat_completion, stream_chat_completion
from app.core.redis_client import get_redis
from app.core.sse import format_sse_event, stream_with_heartbeat
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.message import Message
from app.models.user import User
from app.rag.bm25 import BM25Retriever
from app.rag.chunker import estimate_tokens
from app.rag.fusion import rrf_fusion
from app.rag.intent import Intent, classify_intent
from app.rag.prompt_builder import build_prompt, PromptBuildResult
from app.rag.query_rewriter import _needs_rewrite, rewrite_query
from app.rag.reranker import NoopReranker
from app.rag.retriever import RetrievalOutput, VectorRetriever
from app.schemas.chat import ChatSourceChunk, PreviewRange

logger = logging.getLogger(__name__)

# 模块级单例：检索器和 Reranker（无状态，线程安全）
_vector_retriever = VectorRetriever()
_bm25_retriever = BM25Retriever(
    redis_client=get_redis(),
    session_factory=async_session,
)
_reranker = NoopReranker()

# 可检索文档状态：文档已入库、分块已写入 ChromaDB、可用于检索
RETRIEVABLE_STATUSES = ["completed", "success_with_warnings", "partial_failed"]

# 闲谈模式 System Prompt（不注入文档上下文）
CASUAL_SYSTEM_PROMPT = "你是 DocMind，一个企业知识库助手。请友好、简洁地回答用户的问题。"

# LLM "未找到相关信息" 关键词：两级匹配策略
# 1. 前缀匹配（前 35 字符）：LLM 首句声明"知识库中未找到"= 真阴性
# 2. 引用标注兜底：全文含"未找到" 且 无 [来源N] 引用 = LLM 未找到可用 chunk
#    有 [来源N] 标注 = LLM 认为自己有价值引用 → sources 应保留
_NOT_FOUND_KEYWORDS = ["未找到相关信息", "知识库中未找到"]
_CITATION_PATTERN = re.compile(r'\[来源(\d+)\]')

# 闲谈检测模式：问候/致谢/告别等无需检索的输入
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


def _is_casual_chat(question: str) -> bool:
    """轻量闲谈检测：问候/致谢/告别等无需检索的输入。

    Phase 3 不含完整意图识别模块，此处以规则覆盖高频闲谈场景。
    完整意图识别（含问题类型判别）排期 Phase 4/5。
    """
    cleaned = question.strip()
    # 极短纯标点/空白（≤1 个非空白字符）
    if len(cleaned.replace(" ", "")) <= 1:
        return True
    for pattern in _CASUAL_PATTERNS:
        if pattern.match(cleaned):
            return True
    return False


def _generate_title(question: str) -> str:
    """自动生成会话标题：截取用户问题前 12 字，去除标点。

    对齐 ARCHITECTURE.md §5.1 / ROADMAP.md Decision #24。
    """
    title = question[:12]
    title = re.sub(r"[^\w\s一-鿿]", "", title)
    return title.strip() or "新对话"


async def _generate_title_llm(question: str) -> str:
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
    return _generate_title(question)


async def _load_history(
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
    # 查询（取 40 条，足够覆盖 max_messages=20 × 2 角色）
    q = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(40)
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


def _extract_citation_indices(text: str) -> set[str]:
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


def _fallback_preview(content: str) -> tuple[str, PreviewRange]:
    """降级预览：返回 chunk 前 200 字符（当前行为）。"""
    end = min(len(content), 200)
    return content[:end], PreviewRange(start=0, end=end)


def _locate_preview(
    chunk_content: str, assistant_content: str, chunk_index: int
) -> tuple[str, PreviewRange]:
    """在 chunk 内定位 LLM 引用段落，返回预览文本和位置范围。

    对齐 ARCHITECTURE.md §5.1.7 定位算法：
    1. 从 assistant_content 中提取 [来源N] 后 50 字符作为 snippet
    2. 在 chunk_content 中做不区分大小写子串匹配
    3. 匹配成功：窗口中心 ±100 字符
    4. 匹配失败：降级到 chunk 前 200 字符
    """
    try:
        # 1. 提取 [来源N] 后紧跟的文本片段（最多 50 字符）
        pattern = re.compile(rf'\[来源{chunk_index}\](.{{1,50}})', re.DOTALL)
        match = pattern.search(assistant_content)
        if not match:
            return _fallback_preview(chunk_content)

        snippet = match.group(1).strip()
        # 去除可能混入的其他 [来源M] 标记
        snippet = re.sub(r'\[来源\d+\]', '', snippet).strip()
        if len(snippet) < 4:
            return _fallback_preview(chunk_content)

        # 2. 规范化空格后在 chunk 中查找（不区分大小写）
        norm_content = re.sub(r'\s+', ' ', chunk_content)
        norm_snippet = re.sub(r'\s+', ' ', snippet)
        idx = norm_content.lower().find(norm_snippet.lower())

        if idx < 0:
            return _fallback_preview(chunk_content)

        # 3. 计算 ±100 字符窗口（在原始 content 上操作）
        center = idx + len(norm_snippet) // 2
        start = max(0, center - 100)
        end = min(len(chunk_content), center + 100)
        preview_text = chunk_content[start:end]
        return preview_text, PreviewRange(start=start, end=end)

    except Exception:
        logger.debug("sources 预览定位异常，降级到 chunk 前 200 字符", exc_info=True)
        return _fallback_preview(chunk_content)


def _build_sources(
    chunks: list,
    doc_map: dict[int, str],
    assistant_content: str | None = None,
) -> list[ChatSourceChunk]:
    """构建 sources 事件的 chunks 列表。

    对齐 API.md §6.1 event: sources + ARCHITECTURE.md §5.1.7 sources 智能预览：
    - chunk_index 与 LLM 回答中的 [来源N] 编号一一对应
    - content 保留完整 chunk 内容（向前兼容）
    - preview_text / preview_range：精确定位 LLM 引用段落（可选）
    - doc_name 从 doc_map 查询
    """
    sources = []
    for i, chunk in enumerate(chunks):
        chunk_index = i + 1  # 与 LLM Prompt 中 [来源N] 编号一致
        content = chunk.content if chunk.content else ""

        # 智能预览：仅在有 assistant_content 时执行定位
        preview_text = None
        preview_range = None
        if assistant_content and content:
            preview_text, preview_range = _locate_preview(
                content, assistant_content, chunk_index
            )

        sources.append(ChatSourceChunk(
            chunk_index=chunk_index,
            doc_id=chunk.doc_id,
            doc_name=doc_map.get(chunk.doc_id, ""),
            content=content,
            score=round(chunk.score, 4),
            page=chunk.page,
            preview_text=preview_text,
            preview_range=preview_range,
        ))
    return sources


async def _generate_sse_stream(
    db: AsyncSession,
    conv: Conversation,
    task_id: str,
    question: str,
    deep_thinking: bool,
    is_first_turn: bool,
    prompt_result: PromptBuildResult,
    reranked_output: RetrievalOutput,
    doc_map: dict[int, str],
) -> AsyncIterator[str]:
    """SSE 事件流生成器 — LLM 流式调用 + 消息持久化。

    事件序列对齐 API.md §6.1：
    meta → thinking(可选) → message → sources → finish
    异常时：sources → error
    """
    assistant_content = ""
    token_usage: dict = {}

    # 发送 meta 事件
    yield format_sse_event("meta", {
        "conversation_id": conv.id,
        "task_id": task_id,
    })

    try:
        # 构建 OpenAI 格式消息列表（含历史消息注入，对齐 ARCHITECTURE.md §8.2）
        messages = [
            {"role": "system", "content": prompt_result.system_prompt},
            *prompt_result.history_messages,  # Phase 4：历史消息
            {"role": "user", "content": prompt_result.user_prompt},
        ]

        # 流式调用 LLM
        async for chunk in stream_chat_completion(
            messages=messages,
            deep_thinking=deep_thinking,
        ):
            if chunk.reasoning_content and deep_thinking:
                yield format_sse_event("thinking", {
                    "delta": chunk.reasoning_content,
                })
            if chunk.content:
                assistant_content += chunk.content
                yield format_sse_event("message", {
                    "delta": chunk.content,
                })

        # DeepSeek 流式 API 不返回 usage，使用 chunker 估算
        prompt_tokens = (
            estimate_tokens(prompt_result.system_prompt)
            + estimate_tokens(prompt_result.user_prompt)
        )
        completion_tokens = estimate_tokens(assistant_content)
        token_usage = {
            "prompt": prompt_tokens,
            "completion": completion_tokens,
            "total": prompt_tokens + completion_tokens,
        }

    except Exception as e:
        logger.exception("LLM 流式调用异常")
        # 即使 LLM 失败，也发送 sources（对齐 API.md §6 错误流程）
        # 优先使用 prompt_result.used_chunks（与 [来源N] 编号一致），为空时回退
        _error_chunks = prompt_result.used_chunks or reranked_output.results
        if _error_chunks:
            # LLM 失败时无 assistant_content，preview 降级为 None
            sources = _build_sources(_error_chunks, doc_map, assistant_content=None)
            yield format_sse_event("sources", {"chunks": [s.model_dump() for s in sources]})

        error_code = "E4002"
        error_msg = "LLM 调用失败"
        if hasattr(e, "error_code"):
            error_code = e.error_code
            error_msg = e.error_message
        yield format_sse_event("error", {
            "code": error_code,
            "message": error_msg,
            "detail": str(e),
        })
        return

    # 发送 sources 事件
    # 对齐 API.md §6.1：
    #   1. "未找到相关信息"抑制（两级匹配）
    #   2. 引用过滤：LLM 写了 [来源N] 时仅发送被引用的 chunk（保留引用过滤优化）
    #   3. 回退：LLM 未引用 [来源N] 但有检索结果时，发送全部 used_chunks
    #      防止因 LLM 格式问题（DeepSeek/Qwen 常忘记写 [来源N]）导致 sources 消失
    _answer_stripped = assistant_content.strip()
    _answer_head = _answer_stripped[:35]
    _has_citation = bool(_CITATION_PATTERN.search(_answer_stripped))
    _not_found = (
        any(kw in _answer_head for kw in _NOT_FOUND_KEYWORDS)
        or (any(kw in _answer_stripped for kw in _NOT_FOUND_KEYWORDS) and not _has_citation)
    )
    logger.info(
        "SOURCES_DIAG used_chunks=%d cited=%s answer_head=%s",
        len(prompt_result.used_chunks) if prompt_result.used_chunks else 0,
        _extract_citation_indices(_answer_stripped) if _answer_stripped else set(),
        _answer_stripped[:200] if _answer_stripped else "(empty)",
    )

    if reranked_output.results and not _not_found:
        _send_chunks = prompt_result.used_chunks or reranked_output.results
        _cited_indices = _extract_citation_indices(_answer_stripped)
        if _cited_indices:
            _cited_with_orig_index = [
                (i + 1, c) for i, c in enumerate(_send_chunks)
                if str(i + 1) in _cited_indices
            ]
            if _cited_with_orig_index:
                sources = _build_sources(
                    [c for _, c in _cited_with_orig_index],
                    doc_map,
                    assistant_content=assistant_content,
                )
                for j, (orig_idx, _) in enumerate(_cited_with_orig_index):
                    sources[j].chunk_index = orig_idx
                yield format_sse_event("sources", {"chunks": [s.model_dump() for s in sources]})
        else:
            # 回退：LLM 未引用 [来源N] 但检索有结果 → 发送全部 used_chunks
            # 防止因 LLM 格式问题导致 sources 事件消失（RAG 退化误判）
            logger.info(
                "SOURCES_FALLBACK: LLM 未引用 [来源N]，回退发送全部 used_chunks (%d 个)",
                len(_send_chunks),
            )
            sources = _build_sources(_send_chunks, doc_map, assistant_content=assistant_content)
            yield format_sse_event("sources", {"chunks": [s.model_dump() for s in sources]})

    # 保存助手消息（仅 LLM 正常完成后落库，对齐 API.md §6）
    try:
        assistant_msg = Message(
            conversation_id=conv.id,
            role="assistant",
            content=assistant_content,
            thinking_content=None,  # Phase 3 不落库
            token_count=token_usage.get("total", 0),
        )
        db.add(assistant_msg)
        conv.message_count += 1
        # 手动同步 updated_at（对齐 ARCHITECTURE.md §8.6）
        conv.updated_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(assistant_msg)

        # 标题生成（首轮：截断标题立即返回，LLM 标题异步更新）
        title = None
        if is_first_turn:
            title = _generate_title(question)
            conv.title = title

        await db.commit()

        # 发送 finish 事件（含截断标题，保证不延迟）
        yield format_sse_event("finish", {
            "message_id": assistant_msg.id,
            "title": title,
            "token_usage": token_usage,
        })

        # SSE 流结束后，异步调用 LLM 生成更好标题
        if is_first_turn:
            try:
                llm_title = await _generate_title_llm(question)
                conv.title = llm_title
                await db.commit()
                logger.info("LLM 标题生成成功: %s", llm_title)
            except Exception:
                logger.warning("LLM 标题生成失败，保留截断标题")

    except Exception:
        logger.exception("保存助手消息失败")
        await db.rollback()
        yield format_sse_event("error", {
            "code": "E9001",
            "message": "保存消息失败",
        })


# META 固定回复模板（对齐 ARCHITECTURE.md §5.1.6）
_META_RESPONSE = (
    "我是 DocMind，一个企业知识库智能问答助手。\n\n"
    "我可以帮你：\n"
    "1. 查询知识库中的文档信息\n"
    "2. 回答关于公司制度、流程、规范等问题\n"
    "3. 检索相关文档并提供引用来源\n\n"
    "请直接向我提问，或选择一个知识库开始问答。"
)


async def _generate_meta_response(
    db: AsyncSession,
    conv: Conversation,
    is_first_turn: bool,
    question: str,
) -> AsyncIterator[str]:
    """META 意图的固定 SSE 响应：不调 LLM，直接返回模板。

    与 _generate_sse_stream 一致：保存 assistant 消息到数据库，
    保证对话历史完整性（用户消息已在 _validate_and_prepare 中保存）。
    """
    yield format_sse_event("meta", {"conversation_id": conv.id, "task_id": str(uuid4())})
    yield format_sse_event("message", {"delta": _META_RESPONSE})

    # 保存 assistant 消息（对齐主流程，保持消息成对）
    try:
        assistant_msg = Message(
            conversation_id=conv.id,
            role="assistant",
            content=_META_RESPONSE,
            thinking_content=None,
            token_count=0,
        )
        db.add(assistant_msg)
        conv.message_count += 1
        conv.updated_at = datetime.now(timezone.utc)

        title = None
        if is_first_turn:
            title = _generate_title(question)
            conv.title = title

        await db.commit()
        await db.refresh(assistant_msg)

        yield format_sse_event("sources", {"chunks": []})
        yield format_sse_event("finish", {
            "message_id": assistant_msg.id,
            "title": title,
            "token_usage": {"prompt": 0, "completion": 0, "total": 0},
        })
    except Exception:
        logger.exception("META 响应保存失败")
        await db.rollback()
        yield format_sse_event("sources", {"chunks": []})
        yield format_sse_event("finish", {
            "message_id": 0,
            "title": None,
            "token_usage": {"prompt": 0, "completion": 0, "total": 0},
        })


async def _validate_and_prepare(
    db: AsyncSession,
    user_id: int,
    role: str,
    conversation_id: int | None,
    kb_id: int,
    question: str,
) -> tuple[Conversation, RetrievalOutput, PromptBuildResult, dict[int, str]]:
    """权限校验 + 会话准备 + 检索 + 文档名查询。

    所有校验在 SSE 连接建立前执行，失败直接抛 HTTP 异常。

    Returns:
        (conv, is_first_turn, reranked_output, prompt_result, doc_map)
    """
    # 基础校验
    if not question or not question.strip():
        raise QuestionEmptyException()

    # 权限检查（visibility 优先于 ownership，对齐 PRD §5.4）
    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None or kb.status != "active":
        raise KnowledgeBaseNotFoundException(kb_id)
    if kb.visibility == "private" and kb.user_id != user_id and role != "admin":
        raise PermissionDeniedException()

    # 检查 KB 是否有可检索文档（含 partial_failed：部分分块可用）

    # 会话处理 + 历史消息加载
    if conversation_id:
        conv = await db.get(Conversation, conversation_id)
        if conv is None:
            raise ConversationNotFoundException(conversation_id)
        if conv.user_id != user_id:
            raise ConversationAccessDeniedException()
        is_first_turn = (conv.message_count == 0)  # 在插入用户消息前判定
        # 加载历史消息（在保存用户消息之前！避免当前消息被重复注入）
        history_messages = await _load_history(db, conv.id)
    else:
        conv = Conversation(user_id=user_id, kb_id=kb_id)
        db.add(conv)
        await db.flush()
        is_first_turn = True
        history_messages = []  # 新会话无历史

    # 保存用户消息
    user_msg = Message(
        conversation_id=conv.id,
        role="user",
        content=question,
    )
    db.add(user_msg)
    conv.message_count += 1
    # 手动同步 updated_at（对齐 ARCHITECTURE.md §8.6）
    conv.updated_at = datetime.now(timezone.utc)
    await db.commit()

    # 意图识别（Phase 5，对齐 ARCHITECTURE.md §5.1.6）
    intent = await classify_intent(question)
    logger.info("INTENT question=%s intent=%s", question[:50], intent.value)

    if intent == Intent.META:
        raise MetaQuestionException(question, conv, is_first_turn)

    skip_retrieval = (intent == Intent.CASUAL)

    # 问题重写：仅 KNOWLEDGE 路径触发（对齐 ARCHITECTURE.md §5.1.5）
    _original_question = question
    if not skip_retrieval and _needs_rewrite(question, history_messages):
        question = await rewrite_query(question, history_messages)
        logger.info(
            "QUERY_REWRITE original=%s rewritten=%s triggered=True",
            _original_question[:100], question[:100],
        )
    else:
        logger.info(
            "QUERY_REWRITE original=%s rewritten=(skipped) triggered=False",
            _original_question[:100],
        )

    if skip_retrieval:
        # CASUAL 路径：跳过检索，直接使用无上下文 Prompt（仍注入历史，对齐设计决策）
        logger.info("检测到闲谈意图，跳过检索: %s", question[:30])
        reranked_output = RetrievalOutput()
        prompt_result = PromptBuildResult(
            system_prompt=CASUAL_SYSTEM_PROMPT,
            user_prompt=question,
            used_chunks=[],
            total_context_tokens=0,
            chunks_count=0,
            history_messages=history_messages,
        )
    else:
        # KNOWLEDGE 路径：检查 KB 是否有可检索文档
        doc_count_q = (
            select(func.count())
            .select_from(Document)
            .where(
                Document.kb_id == kb_id,
                Document.status.in_(RETRIEVABLE_STATUSES),
            )
        )
        doc_count = (await db.execute(doc_count_q)).scalar()
        if doc_count == 0:
            raise KnowledgeBaseEmptyException(kb_id)

        # 多路检索（失败包装为 E4003）
        try:
            vector_output = await _vector_retriever.search(question, kb_id)
            bm25_output = await _bm25_retriever.search(question, kb_id)
            fused_output = rrf_fusion(vector_output, bm25_output)
            reranked_output = await _reranker.rerank(question, fused_output)
            prompt_result = build_prompt(question, reranked_output, history_messages=history_messages)
        except Exception as e:
            logger.exception("检索链路异常")
            raise RetrievalServiceException(detail=str(e))

    # 查询涉及的文档名（用于 sources 事件）
    doc_ids = list({c.doc_id for c in reranked_output.results})
    doc_map: dict[int, str] = {}
    if doc_ids:
        doc_rows = await db.execute(
            select(Document.id, Document.filename).where(Document.id.in_(doc_ids))
        )
        doc_map = {row.id: row.filename for row in doc_rows.all()}

    return conv, is_first_turn, reranked_output, prompt_result, doc_map


async def chat(
    db: AsyncSession,
    user_id: int,
    role: str,
    conversation_id: int | None,
    kb_id: int,
    question: str,
    deep_thinking: bool,
) -> StreamingResponse:
    """问答核心流程：检索 → RRF → Rerank → Prompt → LLM SSE 流式。

    对齐 ARCHITECTURE.md §5.1 / API.md §6：
    - 参数校验 / 权限检查在 SSE 之外（直接抛 HTTP 异常）
    - 检索也在 SSE 之外执行（检索失败包装为 E4003）
    - LLM 流式输出通过 SSE 事件推送
    - LLM 失败时先发 sources 再发 error
    """
    try:
        conv, is_first_turn, reranked_output, prompt_result, doc_map = await _validate_and_prepare(
            db=db, user_id=user_id, role=role,
            conversation_id=conversation_id, kb_id=kb_id, question=question,
        )
    except MetaQuestionException as e:
        # 元问题：不调 LLM，直接返回固定模板 SSE 响应
        # 用户消息已保存，_generate_meta_response 会保存 assistant 消息保持成对
        return StreamingResponse(
            stream_with_heartbeat(_generate_meta_response(
                db=db, conv=e.conv, is_first_turn=e.is_first_turn, question=question,
            )),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    task_id = str(uuid4())

    return StreamingResponse(
        stream_with_heartbeat(_generate_sse_stream(
            db=db,
            conv=conv,
            task_id=task_id,
            question=question,
            deep_thinking=deep_thinking,
            is_first_turn=is_first_turn,
            prompt_result=prompt_result,
            reranked_output=reranked_output,
            doc_map=doc_map,
        )),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


async def get_selectable_kbs(
    db: AsyncSession, user_id: int
) -> dict:
    """获取当前用户可用于问答的知识库列表，按所有权分组。

    对齐 API.md §3 GET /api/knowledge-bases/selectable：
    - mine: 当前用户所有 active 且有可检索文档的 KB
    - public: 其他用户 public + active 且有可检索文档的 KB

    仅返回至少有一篇可检索文档（completed / success_with_warnings / partial_failed）的 KB，
    避免前端展示空 KB 导致用户选中后收到 E4001。

    Returns:
        {"mine": [...], "public": [...]}
    """
    # 子查询：KB 下是否有可检索文档
    has_retrievable = exists().where(
        and_(
            Document.kb_id == KnowledgeBase.id,
            Document.status.in_(RETRIEVABLE_STATUSES),
        )
    )

    # 我的知识库（active + 有可检索文档）
    mine_q = (
        select(KnowledgeBase)
        .where(
            KnowledgeBase.user_id == user_id,
            KnowledgeBase.status == "active",
            has_retrievable,
        )
        .order_by(KnowledgeBase.created_at.desc())
    )
    mine_rows = (await db.execute(mine_q)).scalars().all()

    # 公共知识库（其他用户的 public + active + 有可检索文档）
    public_q = (
        select(KnowledgeBase, User.username)
        .join(User, KnowledgeBase.user_id == User.id)
        .where(
            KnowledgeBase.visibility == "public",
            KnowledgeBase.status == "active",
            KnowledgeBase.user_id != user_id,
            has_retrievable,
        )
        .order_by(KnowledgeBase.created_at.desc())
    )
    public_rows = (await db.execute(public_q)).all()

    return {
        "mine": [
            {
                "id": kb.id,
                "name": kb.name,
                "visibility": kb.visibility,
                "doc_count": kb.doc_count,
            }
            for kb in mine_rows
        ],
        "public": [
            {
                "id": kb.id,
                "name": kb.name,
                "visibility": kb.visibility,
                "doc_count": kb.doc_count,
                "username": username,
            }
            for kb, username in public_rows
        ],
    }
