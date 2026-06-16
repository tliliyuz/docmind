"""问答业务逻辑 — 检索 → RRF → Rerank → Prompt → LLM SSE 流式输出

对齐 ARCHITECTURE.md §5.1 / ROADMAP.md §6.1：
- 多轮对话上下文：_load_history() 加载历史消息注入 LLM messages
- Token 预算四池子分拆：System 2000 / History 6000 / Retrieval 10000 / Question 2000
- 轻量闲谈检测：问候/致谢/告别等跳过检索，直接 LLM 回复
- 会话标题 LLM 生成：finish 先返回截断标题，SSE 流结束后异步调用 LLM 更新
- SSE 6 种事件类型 + 15s 心跳
- deep_thinking → extra_body thinking 参数映射

检索+上下文构建管线已解耦至 app.rag.knowledge_pipeline。
"""

import logging
import re
import time
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
    KnowledgeBaseNotFoundException,
    MetaQuestionException,
    QuestionEmptyException,
)
from app.core.llm import chat_completion, stream_chat_completion
from app.core.permissions import require_kb_readable
from app.core.redis_client import get_async_redis
from app.core.sse import format_sse_event, stream_with_heartbeat
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.message import Message
from app.models.user import User
from app.rag.bm25 import BM25Retriever
from app.rag.chunker import estimate_tokens
from app.rag.evidence_auditor import EvidenceAuditResult, audit_evidence
from app.rag.intent import Intent, classify_intent
from app.rag.knowledge_pipeline import (
    KnowledgePipeline,
    KnowledgePipelineResult,
    RETRIEVABLE_STATUSES,
)
from app.rag.prompt_builder import PromptBuildResult
from app.rag.retriever import RetrievalOutput
from app.rag.trace_recorder import TraceRecorder
from app.schemas.chat import ChatSourceChunk, PreviewRange, SelectableKBItem, SelectableKBResponse

logger = logging.getLogger(__name__)

# BM25 检索器懒加载单例（需要异步 Redis 客户端）
_bm25_retriever: BM25Retriever | None = None


async def _get_bm25_retriever() -> BM25Retriever:
    """获取 BM25 检索器（懒加载单例）"""
    global _bm25_retriever
    if _bm25_retriever is None:
        async_redis = await get_async_redis()
        _bm25_retriever = BM25Retriever(
            async_redis=async_redis,
            session_factory=async_session,
        )
    return _bm25_retriever


# 知识管线单例：封装检索+上下文构建全流程
_pipeline = KnowledgePipeline(bm25_retriever_factory=_get_bm25_retriever)

# LLM "未找到相关信息" 关键词：两级匹配策略
# 1. 前缀匹配（前 35 字符）：LLM 首句声明"知识库中未找到"= 真阴性
# 2. 引用标注兜底：全文含"未找到" 且 无 [来源N] 引用 = LLM 未找到可用 chunk
#    有 [来源N] 标注 = LLM 认为自己有价值引用 → sources 应保留
_NOT_FOUND_KEYWORDS = ["未找到相关信息", "知识库中未找到"]
_CITATION_PATTERN = re.compile(r'\[来源(\d+)\]')

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


def _build_sources(
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
            preview_text=preview_text,
            preview_range=preview_range,
            highlight_start=highlight_start,
            highlight_end=highlight_end,
        ))
    return sources


def _build_sources_event_data(
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


async def _generate_sse_stream(
    conv: Conversation,
    task_id: str,
    question: str,
    deep_thinking: bool,
    is_first_turn: bool,
    prompt_result: PromptBuildResult,
    reranked_output: RetrievalOutput,
    doc_map: dict[int, str],
    recorder: TraceRecorder | None = None,
) -> AsyncIterator[str]:
    """SSE 事件流生成器 — LLM 流式调用 + 消息持久化。

    事件序列对齐 API.md §6.1：
    meta → thinking(可选) → message → sources → finish
    异常时：sources → error

    DB 会话管理（ADR-017）：LLM 流式阶段不持有 DB 连接；
    消息持久化阶段创建独立短生命周期 session，消息 + Trace 单事务提交。
    """
    assistant_content = ""
    token_usage: dict = {}
    t0 = time.perf_counter()  # 总起点
    t_first_token = None
    t_stream_end = None
    t_sources_end = None

    # 发送 meta 事件（conversation_id 使用 UUID，对齐 API.md §6.1）
    yield format_sse_event("meta", {
        "conversation_id": conv.uuid,
        "task_id": task_id,
    })

    try:
        # 构建 OpenAI 格式消息列表（含历史消息注入，对齐 ARCHITECTURE.md §8.2）
        messages = [
            {"role": "system", "content": prompt_result.system_prompt},
            *prompt_result.history_messages,  # Phase 4：历史消息
            {"role": "user", "content": prompt_result.user_prompt},
        ]

        # 流式调用 LLM（此阶段不持有 DB 连接，对齐 ADR-017）
        llm_finish_reason: str | None = None
        async for chunk in stream_chat_completion(
            messages=messages,
            deep_thinking=deep_thinking,
        ):
            if chunk.finish_reason:
                llm_finish_reason = chunk.finish_reason
            if chunk.reasoning_content and deep_thinking:
                if t_first_token is None:
                    t_first_token = time.perf_counter()
                yield format_sse_event("thinking", {
                    "delta": chunk.reasoning_content,
                })
            if chunk.content:
                if t_first_token is None:
                    t_first_token = time.perf_counter()
                assistant_content += chunk.content
                yield format_sse_event("message", {
                    "delta": chunk.content,
                })

        t_stream_end = time.perf_counter()  # LLM 流结束

        # Trace: 记录 LLM 生成阶段（纯内存操作，不涉及 IO）
        if recorder:
            _ttft_val = (t_first_token - t0) * 1000 if t_first_token else 0
            _total_val = (t_stream_end - t0) * 1000
            recorder.record_generate(
                model=settings.LLM_MODEL,
                ttft_ms=_ttft_val,
                total_ms=_total_val,
                input_tokens=0,  # 流式 API 不返回 usage，下面估算后更新
                output_tokens=0,
                finish_reason=llm_finish_reason or "stop",
                t_span_start=t0,
            )

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

        # Trace: 更新 token 估算值（纯内存操作）
        if recorder and recorder._generate_data:
            recorder._generate_data["input_tokens"] = prompt_tokens
            recorder._generate_data["output_tokens"] = completion_tokens

        # 三层证据审计（ROADMAP.md §8.3）
        # LLM 流完成后执行，检查答案的证据链是否可追溯
        _audit_result: EvidenceAuditResult | None = None
        if assistant_content and prompt_result.used_chunks:
            try:
                _audit_result = audit_evidence(assistant_content, prompt_result.used_chunks)
                # 补填 post_audit 到 evidence_review Trace（ADR-021）
                if recorder and _audit_result:
                    recorder.set_post_audit({
                        "has_citation": _audit_result.has_citation,
                        "citations_detected": _audit_result.cited_indices,
                        "consistency_status": _audit_result.consistency_status,
                        "evidence_status": _audit_result.evidence_status,
                        "confidence_level": _audit_result.confidence_level,
                        "confidence_note": _audit_result.confidence_note,
                        "raw_answer_preview": assistant_content[:200],
                    })
            except Exception:
                logger.warning("证据审计执行失败，跳过", exc_info=True)

    except Exception as e:
        t_error = time.perf_counter()
        logger.exception("LLM 流式调用异常")
        _ttft = (t_first_token - t0) if t_first_token else None
        logger.info(
            "PERF(异常) 首Token=%.3fs LLM已耗时=%.3fs",
            _ttft if _ttft else -1,
            t_error - t0,
        )
        # 即使 LLM 失败，也发送 sources（对齐 API.md §6 错误流程）
        # 优先使用 prompt_result.used_chunks（与 [来源N] 编号一致），为空时回退
        _error_chunks = prompt_result.used_chunks or reranked_output.results
        if _error_chunks:
            # LLM 失败时无 assistant_content，preview 降级为 None
            sources = _build_sources(_error_chunks, doc_map)
            yield format_sse_event("sources", {"chunks": [s.model_dump() for s in sources]})

        error_code = "E4002"
        error_msg = "LLM 调用失败"
        if hasattr(e, "error_code"):
            error_code = e.error_code
            error_msg = e.error_message
        # Trace 记录 LLM 错误（独立短 session，对齐 ADR-017）
        if recorder:
            recorder.record_error(error_msg)
            async with async_session() as s:
                try:
                    await recorder.finish(s)
                    await s.commit()
                except Exception:
                    await s.rollback()
        yield format_sse_event("error", {
            "code": error_code,
            "message": error_msg,
            "detail": str(e),
        })
        return

    # 发送 sources 事件
    # 对齐 API.md §6.1：
    #   1. "未找到相关信息"抑制：两级匹配均须尊重引用标注
    #      - 前缀含"未找到" + 无 [来源N] → 真阴性，抑制 sources
    #      - 前缀含"未找到" + 有 [来源N] → LLM 给出了部分引用答案，保留 sources
    #      - 全文含"未找到" + 无 [来源N] → 真阴性，抑制 sources
    #   2. 引用过滤：LLM 写了 [来源N] 时仅发送被引用的 chunk（保留引用过滤优化）
    #   3. 回退：LLM 未引用 [来源N] 但有检索结果时，发送全部 used_chunks
    #      防止因 LLM 格式问题（DeepSeek/Qwen 常忘记写 [来源N]）导致 sources 消失
    _answer_stripped = assistant_content.strip()
    _answer_head = _answer_stripped[:35]
    _has_citation = bool(_CITATION_PATTERN.search(_answer_stripped))
    # 两级匹配均须尊重引用：LLM 写了 [来源N] 意味着它认为自己有有价值引用，
    # 即使以"未找到"开头也是部分答案而非真阴性（如"未找到X的直接流程，但Y[来源1]"）
    _not_found = (
        (any(kw in _answer_head for kw in _NOT_FOUND_KEYWORDS) and not _has_citation)
        or (any(kw in _answer_stripped for kw in _NOT_FOUND_KEYWORDS) and not _has_citation)
    )
    logger.info(
        "SOURCES_DIAG used_chunks=%d cited=%s has_citation=%s not_found=%s answer_head=%s",
        len(prompt_result.used_chunks) if prompt_result.used_chunks else 0,
        _extract_citation_indices(_answer_stripped) if _answer_stripped else set(),
        _has_citation,
        _not_found,
        _answer_head,
    )

    if _not_found:
        logger.info(
            "SOURCES_SUPPRESSED: LLM 判定未找到（not_found=True），抑制 sources 发送",
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
                )
                for j, (orig_idx, _) in enumerate(_cited_with_orig_index):
                    sources[j].chunk_index = orig_idx
                yield format_sse_event(
                    "sources",
                    _build_sources_event_data(sources, _audit_result),
                )
        else:
            # 回退：LLM 未引用 [来源N] 但检索有结果 → 发送全部 used_chunks
            # 防止因 LLM 格式问题导致 sources 事件消失（RAG 退化误判）
            logger.info(
                "SOURCES_FALLBACK: LLM 未引用 [来源N]，回退发送全部 used_chunks (%d 个)",
                len(_send_chunks),
            )
            sources = _build_sources(_send_chunks, doc_map)
            yield format_sse_event(
                "sources",
                _build_sources_event_data(sources, _audit_result),
            )

    t_sources_end = time.perf_counter()  # 引用构建结束

    # 持久化阶段：独立短生命周期 session，消息 + Trace 单事务提交（ADR-017）
    # LLM 流式期间不持有 DB 连接，session 仅在最后持久化阶段短暂占用
    title = None
    message_id = 0  # 异常回退时的默认值
    async with async_session() as s:
        try:
            # 跨 session 重新查询 conv，确保绑定到当前 session
            conv_in = await s.get(Conversation, conv.id)
            if conv_in is None:
                logger.error("会话 %d 在持久化时已不存在", conv.id)
                raise ConversationNotFoundException(conv.id)

            # 保存助手消息
            assistant_msg = Message(
                conversation_id=conv_in.id,
                role="assistant",
                content=assistant_content,
                thinking_content=None,  # Phase 3 不落库
                token_count=token_usage.get("total", 0),
            )
            s.add(assistant_msg)
            conv_in.message_count += 1
            # 手动同步 updated_at + last_message_at（对齐 ARCHITECTURE.md §8.6）
            _now = datetime.now(timezone.utc)
            conv_in.updated_at = _now
            conv_in.last_message_at = _now
            await s.flush()
            await s.refresh(assistant_msg)
            message_id = assistant_msg.id

            # 标题生成（首轮：截断标题立即返回，LLM 标题异步更新）
            if is_first_turn:
                title = _generate_title(question)
                conv_in.title = title

            # Trace 写入（commit=False，由外层统一提交，确保与消息在同一事务）
            if recorder:
                await recorder.finish(s, commit=False)

            await s.commit()

        except Exception:
            logger.exception("保存助手消息失败")
            await s.rollback()
            yield format_sse_event("error", {
                "code": "E9001",
                "message": "保存消息失败",
            })
            return

    # session 已释放，安全发送 finish 事件（message_id 来自已提交的记录）
    yield format_sse_event("finish", {
        "message_id": message_id,
        "title": title,
        "token_usage": token_usage,
    })

    t_finish = time.perf_counter()
    _ttft = (t_first_token - t0) if t_first_token else -1
    logger.info(
        "PERF 首Token=%.3fs 生成=%.3fs 引用构建=%.3fs 收尾=%.3fs 总计=%.3fs",
        _ttft,
        (t_stream_end - t_first_token) if (t_first_token and t_stream_end) else -1,
        (t_sources_end - t_stream_end) if (t_stream_end and t_sources_end) else -1,
        (t_finish - t_sources_end) if t_sources_end else -1,
        t_finish - t0,
    )

    # SSE 流结束后，异步调用 LLM 生成更好标题（独立短 session，对齐 ADR-017）
    if is_first_turn:
        try:
            llm_title = await _generate_title_llm(question)
            async with async_session() as s2:
                try:
                    conv_in = await s2.get(Conversation, conv.id)
                    if conv_in is not None:
                        conv_in.title = llm_title
                        await s2.commit()
                        logger.info("LLM 标题生成成功: %s", llm_title)
                except Exception:
                    await s2.rollback()
                    raise
        except Exception:
            logger.warning("LLM 标题生成失败，保留截断标题")


# META 固定回复模板（对齐 ARCHITECTURE.md §5.1.6）
_META_RESPONSE = (
    "我是 DocMind，一个企业知识库智能问答助手。\n\n"
    "我可以帮你：\n"
    "1. 查询知识库中的文档信息\n"
    "2. 回答关于公司制度、流程、规范等问题\n"
    "3. 检索相关文档并提供引用来源\n\n"
    "请直接向我提问，或选择一个知识库开始问答。"
)

# REJECT 固定回复模板（对齐 ADR-021：证据审查门控拒绝时返回）
_REJECT_RESPONSE = "未找到相关信息"


async def _generate_reject_response(
    conv: Conversation,
    is_first_turn: bool,
    question: str,
    recorder: TraceRecorder | None = None,
) -> AsyncIterator[str]:
    """证据审查 REJECT 时的固定 SSE 响应：不调 LLM，直接返回兜底消息。

    与 _generate_meta_response 同样的持久化模式：
    保存 assistant 消息到数据库，保证对话成对。

    SSE 事件序列（对齐 ADR-021 §7b）：
    meta → message("未找到相关信息") → sources(空) → finish
    """
    yield format_sse_event("meta", {"conversation_id": conv.uuid, "task_id": str(uuid4())})
    yield format_sse_event("message", {"delta": _REJECT_RESPONSE})

    # 持久化阶段：独立短生命周期 session，消息 + Trace 单事务提交（ADR-017）
    title = None
    message_id = 0
    async with async_session() as s:
        try:
            conv_in = await s.get(Conversation, conv.id)
            if conv_in is None:
                logger.error("会话 %d 在 REJECT 持久化时已不存在", conv.id)
                raise ConversationNotFoundException(conv.id)

            assistant_msg = Message(
                conversation_id=conv_in.id,
                role="assistant",
                content=_REJECT_RESPONSE,
                thinking_content=None,
                token_count=0,
            )
            s.add(assistant_msg)
            conv_in.message_count += 1
            _now = datetime.now(timezone.utc)
            conv_in.updated_at = _now
            conv_in.last_message_at = _now
            await s.flush()
            await s.refresh(assistant_msg)
            message_id = assistant_msg.id

            if is_first_turn:
                title = _generate_title(question)
                conv_in.title = title

            # Trace 写入（commit=False，由外层统一提交，确保与消息在同一事务）
            if recorder:
                await recorder.finish(s, commit=False)

            await s.commit()

        except Exception:
            logger.exception("REJECT 响应保存失败")
            await s.rollback()
            yield format_sse_event("sources", {"chunks": []})
            yield format_sse_event("finish", {
                "message_id": 0,
                "title": None,
                "token_usage": {"prompt": 0, "completion": 0, "total": 0},
            })
            return

    # session 已释放，安全发送事件
    yield format_sse_event("sources", {"chunks": []})
    yield format_sse_event("finish", {
        "message_id": message_id,
        "title": title,
        "token_usage": {"prompt": 0, "completion": 0, "total": 0},
    })


async def _generate_meta_response(
    conv: Conversation,
    is_first_turn: bool,
    question: str,
    recorder: TraceRecorder | None = None,
) -> AsyncIterator[str]:
    """META 意图的固定 SSE 响应：不调 LLM，直接返回模板。

    与 _generate_sse_stream 一致：保存 assistant 消息到数据库，
    保证对话历史完整性（用户消息已在 _validate_and_prepare 中保存）。

    DB 会话管理（ADR-017）：使用独立短生命周期 session，消息 + Trace 单事务提交。
    """
    yield format_sse_event("meta", {"conversation_id": conv.uuid, "task_id": str(uuid4())})
    yield format_sse_event("message", {"delta": _META_RESPONSE})

    # 持久化阶段：独立短生命周期 session，消息 + Trace 单事务提交（ADR-017）
    title = None
    message_id = 0  # 异常回退时的默认值
    async with async_session() as s:
        try:
            # 跨 session 重新查询 conv，确保绑定到当前 session
            conv_in = await s.get(Conversation, conv.id)
            if conv_in is None:
                logger.error("会话 %d 在 META 持久化时已不存在", conv.id)
                raise ConversationNotFoundException(conv.id)

            assistant_msg = Message(
                conversation_id=conv_in.id,
                role="assistant",
                content=_META_RESPONSE,
                thinking_content=None,
                token_count=0,
            )
            s.add(assistant_msg)
            conv_in.message_count += 1
            _now = datetime.now(timezone.utc)
            conv_in.updated_at = _now
            conv_in.last_message_at = _now
            await s.flush()
            await s.refresh(assistant_msg)
            message_id = assistant_msg.id

            if is_first_turn:
                title = _generate_title(question)
                conv_in.title = title

            # Trace 写入（commit=False，由外层统一提交，确保与消息在同一事务）
            if recorder:
                await recorder.finish(s, commit=False)

            await s.commit()

        except Exception:
            logger.exception("META 响应保存失败")
            await s.rollback()
            yield format_sse_event("sources", {"chunks": []})
            yield format_sse_event("finish", {
                "message_id": 0,
                "title": None,
                "token_usage": {"prompt": 0, "completion": 0, "total": 0},
            })
            return

    # session 已释放，安全发送事件
    yield format_sse_event("sources", {"chunks": []})
    yield format_sse_event("finish", {
        "message_id": message_id,
        "title": title,
        "token_usage": {"prompt": 0, "completion": 0, "total": 0},
    })


async def _validate_and_prepare(
    db: AsyncSession,
    user_id: int,
    role: str,
    conversation_id: str | None,
    kb_id: str,
    question: str,
    recorder: TraceRecorder | None = None,
) -> tuple[Conversation, bool, KnowledgePipelineResult]:
    """权限校验 + 会话准备 + 检索 + 文档名查询。

    所有校验在 SSE 连接建立前执行，失败直接抛 HTTP 异常。

    Args:
        conversation_id: 会话 UUID 字符串或 None
        kb_id: 知识库 UUID 字符串

    Returns:
        (conv, is_first_turn, pipeline_result: KnowledgePipelineResult)
    """
    from app.core.uuid_helpers import resolve_uuid_to_id

    t_prep = time.perf_counter()

    # UUID → integer ID（API 边界转换）
    real_kb_id = await resolve_uuid_to_id(db, KnowledgeBase, kb_id)
    real_conv_id = None
    if conversation_id:
        real_conv_id = await resolve_uuid_to_id(db, Conversation, conversation_id)

    # 基础校验
    if not question or not question.strip():
        raise QuestionEmptyException()

    # 权限检查（visibility 优先于 ownership，对齐 PRD §5.4）
    kb = await db.get(KnowledgeBase, real_kb_id)
    if kb is None or kb.status != "active":
        raise KnowledgeBaseNotFoundException(real_kb_id)
    require_kb_readable(kb, user_id, role)

    # 检查 KB 是否有可检索文档（含 partial_failed：部分分块可用）
    # 提前到意图分支之前，避免 CASUAL 意图绕过检查导致 LLM 无上下文生成
    doc_count_q = (
        select(func.count())
        .select_from(Document)
        .where(
            Document.kb_id == real_kb_id,
            Document.status.in_(RETRIEVABLE_STATUSES),
        )
    )
    retrievable_count = (await db.execute(doc_count_q)).scalar() or 0
    if retrievable_count == 0:
        from app.core.exceptions import KnowledgeBaseEmptyException
        raise KnowledgeBaseEmptyException(real_kb_id)

    # 会话处理 + 历史消息加载
    if real_conv_id:
        conv = await db.get(Conversation, real_conv_id)
        if conv is None:
            raise ConversationNotFoundException(real_conv_id)
        if conv.user_id != user_id:
            raise ConversationAccessDeniedException()
        is_first_turn = (conv.message_count == 0)  # 在插入用户消息前判定
        # 加载历史消息（在保存用户消息之前！避免当前消息被重复注入）
        history_messages = await _load_history(db, conv.id)
    else:
        conv = Conversation(uuid=str(uuid4()), user_id=user_id, kb_id=real_kb_id)
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
    # 手动同步 updated_at + last_message_at（对齐 ARCHITECTURE.md §8.6）
    _now = datetime.now(timezone.utc)
    conv.updated_at = _now
    conv.last_message_at = _now
    await db.commit()
    # commit 后 expire_on_commit 使 ORM 属性过期，SSE 流式生成器中访问会触发
    # MissingGreenlet（已脱离原始 greenlet 上下文）。提前 refresh 确保属性在当前
    # async 上下文中完成加载。
    await db.refresh(conv)
    t_db_done = time.perf_counter()

    # 意图识别（Phase 5，对齐 ARCHITECTURE.md §5.1.6）
    t_intent_start = time.perf_counter()
    intent_result = await classify_intent(question)
    intent = intent_result.intent
    t_intent = time.perf_counter()
    logger.info("INTENT question=%s intent=%s method=%s", question[:50], intent.value, intent_result.method)

    # Trace: 记录意图识别阶段
    if recorder:
        recorder.record_intent(
            intent_type=intent.value,
            method=intent_result.method,
            duration_ms=(t_intent - t_intent_start) * 1000,
            metadata=intent_result.metadata,
        )

    if intent == Intent.META:
        raise MetaQuestionException(question, conv, is_first_turn)

    skip_retrieval = (intent == Intent.CASUAL)

    # 检索+上下文构建管线（已解耦至 KnowledgePipeline）
    if skip_retrieval:
        pipeline_result = await _pipeline.execute_casual(
            question=question,
            history_messages=history_messages,
            recorder=recorder,
        )
    else:
        pipeline_result = await _pipeline.execute_knowledge(
            db=db,
            question=question,
            kb_id=real_kb_id,
            history_messages=history_messages,
            recorder=recorder,
        )

    t_prep_end = time.perf_counter()
    prep_phase = "CASUAL" if skip_retrieval else "KNOWLEDGE"
    logger.info(
        "PREP_PERF 权限+会话=%.3fs 意图=%.3fs 管线=%s 总计=%.3fs",
        t_db_done - t_prep,
        t_intent - t_db_done,
        prep_phase,
        t_prep_end - t_prep,
    )

    return conv, is_first_turn, pipeline_result


async def chat(
    db: AsyncSession,
    user_id: int,
    role: str,
    conversation_id: str | None,
    kb_id: str,
    question: str,
    deep_thinking: bool,
) -> StreamingResponse:
    """问答核心流程：检索 → RRF → Rerank → Prompt → LLM SSE 流式。

    对齐 ARCHITECTURE.md §5.1 / API.md §6：
    - 参数校验 / 权限检查在 SSE 之外（直接抛 HTTP 异常）
    - 检索也在 SSE 之外执行（检索失败包装为 E4003）
    - LLM 流式输出通过 SSE 事件推送
    - LLM 失败时先发 sources 再发 error

    Args:
        conversation_id: 会话 UUID 字符串或 None
        kb_id: 知识库 UUID 字符串
    """
    trace_id = str(uuid4())

    # Trace: 提前创建 recorder，传入 _validate_and_prepare 记录各阶段数据
    # conversation_id / kb_id 此时为 UUID 字符串，_validate_and_prepare 内部转换为 integer
    recorder = TraceRecorder(
        trace_id=trace_id, user_id=user_id,
        conversation_id=None, kb_id=None, question=question,
    )

    try:
        conv, is_first_turn, pipeline_result = await _validate_and_prepare(
            db=db, user_id=user_id, role=role,
            conversation_id=conversation_id, kb_id=kb_id, question=question,
            recorder=recorder,
        )
    except MetaQuestionException as e:
        # 元问题：不调 LLM，直接返回固定模板 SSE 响应
        # 用户消息已保存，_generate_meta_response 会保存 assistant 消息保持成对
        # Trace: META 路径，recorder 已在 _validate_and_prepare 中记录 intent
        recorder.conversation_id = e.conv.id
        recorder.kb_id = e.conv.kb_id
        return StreamingResponse(
            stream_with_heartbeat(_generate_meta_response(
                conv=e.conv, is_first_turn=e.is_first_turn, question=question,
                recorder=recorder,
            )),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    # 证据审查 REJECT 门控（ADR-021）：无陈述性证据时跳过 LLM，直接返回固定拒绝响应
    if pipeline_result.evidence_review and pipeline_result.evidence_review.decision == "REJECT":
        recorder.conversation_id = conv.id
        recorder.kb_id = conv.kb_id
        return StreamingResponse(
            stream_with_heartbeat(_generate_reject_response(
                conv=conv, is_first_turn=is_first_turn, question=question,
                recorder=recorder,
            )),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    # Trace: 新会话时 conversation_id 为 None，用 conv.id 回写
    recorder.conversation_id = conv.id
    recorder.kb_id = conv.kb_id

    task_id = str(uuid4())

    return StreamingResponse(
        stream_with_heartbeat(_generate_sse_stream(
            conv=conv,
            task_id=task_id,
            question=question,
            deep_thinking=deep_thinking,
            is_first_turn=is_first_turn,
            prompt_result=pipeline_result.prompt_result,
            reranked_output=pipeline_result.reranked_output,
            doc_map=pipeline_result.doc_map,
            recorder=recorder,
        )),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


async def get_selectable_kbs(
    db: AsyncSession, user_id: int
) -> SelectableKBResponse:
    """获取当前用户可用于问答的知识库列表，按所有权分组。

    对齐 API.md §3 GET /api/knowledge-bases/selectable：
    - mine: 当前用户所有 active 且有可检索文档的 KB
    - public: 其他用户 public + active 且有可检索文档的 KB

    仅返回至少有一篇可检索文档（completed / success_with_warnings / partial_failed）的 KB，
    避免前端展示空 KB 导致用户选中后收到 E4001。
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

    return SelectableKBResponse(
        mine=[
            SelectableKBItem(
                uuid=kb.uuid,
                name=kb.name,
                visibility=kb.visibility,
                doc_count=kb.doc_count,
            )
            for kb in mine_rows
        ],
        public=[
            SelectableKBItem(
                uuid=kb.uuid,
                name=kb.name,
                visibility=kb.visibility,
                doc_count=kb.doc_count,
                username=username,
            )
            for kb, username in public_rows
        ],
    )
