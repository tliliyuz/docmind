"""问答业务逻辑 — 检索 → RRF → Rerank → Prompt → LLM SSE 流式输出

对齐 ARCHITECTURE.md §5.1 / ROADMAP.md §6.1：
- 多轮对话上下文：_load_history() 加载历史消息注入 LLM messages
- Token 预算四池子分拆：System 2000 / History 6000 / Retrieval 10000 / Question 2000
- 轻量闲谈检测：问候/致谢/告别等跳过检索，直接 LLM 回复
- 会话标题 LLM 生成：finish 先返回截断标题，SSE 流结束后异步调用 LLM 更新
- SSE 6 种事件类型 + 15s 心跳
- deep_thinking → extra_body thinking 参数映射

检索+上下文构建管线已解耦至 app.rag.knowledge_pipeline。
SSE 流生成与固定响应已解耦至 app.services.sse_stream。
辅助函数（历史加载/标题/引用/sources）已解耦至 app.services.chat_helpers。
"""

import logging
import time
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.responses import StreamingResponse
from sqlalchemy import and_, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.core.exceptions import (
    ConversationAccessDeniedException,
    ConversationNotFoundException,
    KnowledgeBaseEmptyException,
    KnowledgeBaseNotFoundException,
    MetaQuestionException,
    QuestionEmptyException,
)
from app.core.permissions import require_kb_readable
from app.core.redis_client import get_async_redis
from app.core.sse import stream_with_heartbeat
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.message import Message
from app.models.user import User
from app.rag.bm25 import BM25Retriever
from app.rag.intent import Intent, classify_intent
from app.rag.knowledge_pipeline import (
    KnowledgePipeline,
    KnowledgePipelineResult,
    RETRIEVABLE_STATUSES,
)
from app.rag.trace_recorder import TraceRecorder
from app.schemas.chat import SelectableKBItem, SelectableKBResponse
from app.services.chat_helpers import _load_history
from app.services.sse_stream import (
    _generate_meta_response,
    _generate_reject_response,
    _generate_sse_stream,
)

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


# ============================================================
# Re-exports：保持向后兼容，所有现有 from app.services.chat_service import ... 路径继续有效
# ============================================================
from app.services.chat_helpers import (  # noqa: E402, F401
    _build_sources,
    _build_sources_event_data,
    _extract_citation_indices,
    _generate_title,
    _generate_title_llm,
    _load_history,
)
