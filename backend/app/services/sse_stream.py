"""SSE 事件流生成器 — LLM 流式调用 + 固定响应 + 消息持久化

从 chat_service.py 提取，封装所有 SSE 生成逻辑：
- _generate_sse_stream：LLM 流式 → sources → 持久化 → finish
- _generate_meta_response / _generate_reject_response：固定模板响应
- _persist_fixed_response：固定响应共享持久化
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import AsyncIterator
from uuid import uuid4

from app.config import settings
from app.core.database import async_session
from app.core.exceptions import ConversationNotFoundException
from app.core.llm import stream_chat_completion
from app.core.sse import format_sse_event
from app.models.conversation import Conversation
from app.models.message import Message
from app.rag.chunker import estimate_tokens
from app.rag.evidence_auditor import EvidenceAuditResult, audit_evidence
from app.rag.prompt_builder import PromptBuildResult
from app.rag.retriever import RetrievalOutput
from app.rag.trace_recorder import TraceRecorder
from app.services.chat_helpers import (
    _NOT_FOUND_KEYWORDS,
    _CITATION_PATTERN,
    _build_sources,
    _build_sources_event_data,
    _extract_citation_indices,
    _generate_title,
    _generate_title_llm,
)

logger = logging.getLogger(__name__)

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
        if recorder:
            recorder.set_token_usage(prompt_tokens, completion_tokens)

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
    # 两级匹配均须尊重引用标注：LLM 写了 [来源N] 意味着它认为自己有价值引用，
    # 即使以"未找到"开头也是部分答案而非真阴性（如"未找到X的直接流程，但Y[来源1]"）
    # _answer_head 是 _answer_stripped 的前缀，仅需检查全文即可覆盖两级匹配
    _not_found = (
        not _has_citation
        and any(kw in _answer_stripped for kw in _NOT_FOUND_KEYWORDS)
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

    # SSE 流结束后，异步调用 LLM 生成更好标题（真正异步，不阻塞生成器关闭）
    # 使用 asyncio.create_task 替代 await，避免 LLM 标题生成超时导致
    # 客户端虽已收到 finish 事件但生成器未关闭的问题
    if is_first_turn:

        async def _update_title_async():
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

        asyncio.create_task(_update_title_async())


async def _persist_fixed_response(
    conv: Conversation,
    is_first_turn: bool,
    question: str,
    content: str,
    log_label: str,
    recorder: TraceRecorder | None = None,
) -> tuple[int | None, str | None]:
    """固定响应公共持久化：创建 Message → 更新 Conversation → 写入 Trace。

    供 _generate_reject_response / _generate_meta_response 复用，
    消除 ~50 行重复代码。

    Args:
        conv: 会话对象（跨 session 引用，内部重新查询）
        is_first_turn: 是否首轮，用于生成标题
        question: 用户问题，用于生成标题
        content: assistant 消息文本
        log_label: 日志标识（"REJECT" / "META"）
        recorder: Trace 收集器

    Returns:
        (message_id, title)：成功时 message_id > 0；异常时返回 (0, None)
    """
    message_id = 0
    title = None
    async with async_session() as s:
        try:
            conv_in = await s.get(Conversation, conv.id)
            if conv_in is None:
                logger.error("会话 %d 在 %s 持久化时已不存在", conv.id, log_label)
                raise ConversationNotFoundException(conv.id)

            assistant_msg = Message(
                conversation_id=conv_in.id,
                role="assistant",
                content=content,
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

            if recorder:
                await recorder.finish(s, commit=False)

            await s.commit()

        except Exception:
            logger.exception("%s 响应保存失败", log_label)
            await s.rollback()
            return None, None

    return message_id, title


async def _generate_reject_response(
    conv: Conversation,
    is_first_turn: bool,
    question: str,
    recorder: TraceRecorder | None = None,
) -> AsyncIterator[str]:
    """证据审查 REJECT 时的固定 SSE 响应：不调 LLM，直接返回兜底消息。

    SSE 事件序列（对齐 ADR-021 §7b）：
    meta → message("未找到相关信息") → sources(空) → finish
    """
    yield format_sse_event("meta", {"conversation_id": conv.uuid, "task_id": str(uuid4())})
    yield format_sse_event("message", {"delta": _REJECT_RESPONSE})

    message_id, title = await _persist_fixed_response(
        conv, is_first_turn, question, _REJECT_RESPONSE, "REJECT", recorder,
    )
    if message_id is None:
        yield format_sse_event("sources", {"chunks": []})
        yield format_sse_event("finish", {
            "message_id": 0, "title": None,
            "token_usage": {"prompt": 0, "completion": 0, "total": 0},
        })
        return

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
    """META 意图的固定 SSE 响应：不调 LLM，直接返回模板。"""
    yield format_sse_event("meta", {"conversation_id": conv.uuid, "task_id": str(uuid4())})
    yield format_sse_event("message", {"delta": _META_RESPONSE})

    message_id, title = await _persist_fixed_response(
        conv, is_first_turn, question, _META_RESPONSE, "META", recorder,
    )

    yield format_sse_event("sources", {"chunks": []})
    yield format_sse_event("finish", {
        "message_id": message_id or 0,
        "title": title,
        "token_usage": {"prompt": 0, "completion": 0, "total": 0},
    })
