"""问答业务逻辑 — 检索 → RRF → Rerank → Prompt → LLM SSE 流式输出

对齐 ARCHITECTURE.md §5.1 / ROADMAP.md §5.2：
- 单轮问答核心链路（Phase 3 不含完整意图识别和问题重写）
- 轻量闲谈检测：问候/致谢/告别等跳过检索，直接 LLM 回复
- conversation_id=null 时自动创建会话，不注入历史（history=[]）
- 标题自动生成：截取用户问题前 12 字
- SSE 6 种事件类型 + 15s 心跳
- deep_thinking → extra_body thinking 参数映射
"""

import logging
import re
from typing import AsyncIterator

from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.core.exceptions import (
    ConversationAccessDeniedException,
    ConversationNotFoundException,
    KnowledgeBaseEmptyException,
    KnowledgeBaseNotFoundException,
    PermissionDeniedException,
    QuestionEmptyException,
    RetrievalServiceException,
)
from app.core.llm import stream_chat_completion
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
from app.rag.prompt_builder import build_prompt, PromptBuildResult
from app.rag.reranker import NoopReranker
from app.rag.retriever import RetrievalOutput, VectorRetriever

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

# LLM "未找到相关信息" 关键词：匹配后跳过 sources 事件发送
# 对齐 API.md §6.1：LLM 判定文档不相关时应抑制引用来源
_NOT_FOUND_KEYWORDS = ["未找到相关信息", "知识库中未找到"]

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


def _build_sources(reranked_output: RetrievalOutput, doc_map: dict[int, str]) -> list[dict]:
    """构建 sources 事件的 chunks 列表。

    对齐 API.md §6.1 event: sources：
    - content 截断至 200 字符
    - doc_name 从 doc_map 查询
    """
    sources = []
    for chunk in reranked_output.results:
        sources.append({
            "doc_id": chunk.doc_id,
            "doc_name": doc_map.get(chunk.doc_id, ""),
            "content": chunk.content[:200] if chunk.content else "",
            "score": round(chunk.score, 4),
            "page": chunk.page,
        })
    return sources


async def _generate_sse_stream(
    db: AsyncSession,
    conv: Conversation,
    task_id: str,
    question: str,
    deep_thinking: bool,
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
        # 构建 OpenAI 格式消息列表
        messages = [
            {"role": "system", "content": prompt_result.system_prompt},
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
        if reranked_output.results:
            sources = _build_sources(reranked_output, doc_map)
            yield format_sse_event("sources", {"chunks": sources})

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

    # 发送 sources 事件（有检索结果 且 LLM 未声明"未找到相关信息"时发送）
    # 对齐 API.md §6.1：LLM 判定文档不相关时抑制引用来源，避免展示无关片段
    _not_found = any(kw in assistant_content for kw in _NOT_FOUND_KEYWORDS)
    if reranked_output.results and not _not_found:
        sources = _build_sources(reranked_output, doc_map)
        yield format_sse_event("sources", {"chunks": sources})

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
        await db.flush()
        await db.refresh(assistant_msg)

        # 标题自动生成（仅首轮，对齐 ROADMAP.md Decision #24）
        title = None
        if conv.message_count == 2:  # user(1) + assistant(1) = 首轮
            title = _generate_title(question)
            conv.title = title

        await db.commit()

        # 发送 finish 事件
        yield format_sse_event("finish", {
            "message_id": assistant_msg.id,
            "title": title,
            "token_usage": token_usage,
        })
    except Exception:
        logger.exception("保存助手消息失败")
        await db.rollback()
        yield format_sse_event("error", {
            "code": "E9001",
            "message": "保存消息失败",
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
        (conv, reranked_output, prompt_result, doc_map)
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

    # 会话自动创建（Phase 3 不注入历史）
    if conversation_id:
        conv = await db.get(Conversation, conversation_id)
        if conv is None:
            raise ConversationNotFoundException(conversation_id)
        if conv.user_id != user_id:
            raise ConversationAccessDeniedException()
    else:
        conv = Conversation(user_id=user_id, kb_id=kb_id)
        db.add(conv)
        await db.flush()

    # 保存用户消息
    user_msg = Message(
        conversation_id=conv.id,
        role="user",
        content=question,
    )
    db.add(user_msg)
    conv.message_count += 1
    await db.commit()

    # 闲谈检测：跳过检索，直接使用无上下文 Prompt
    if _is_casual_chat(question):
        logger.info("检测到闲谈输入，跳过检索: %s", question[:30])
        reranked_output = RetrievalOutput()
        prompt_result = PromptBuildResult(
            system_prompt=CASUAL_SYSTEM_PROMPT,
            user_prompt=question,
            used_chunks=[],
            total_context_tokens=0,
            chunks_count=0,
        )
    else:
        # 多路检索（失败包装为 E4003）
        try:
            vector_output = await _vector_retriever.search(question, kb_id)
            bm25_output = await _bm25_retriever.search(question, kb_id)
            fused_output = rrf_fusion(vector_output, bm25_output)
            reranked_output = await _reranker.rerank(question, fused_output)
            prompt_result = build_prompt(question, reranked_output)
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

    return conv, reranked_output, prompt_result, doc_map


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
    from uuid import uuid4

    conv, reranked_output, prompt_result, doc_map = await _validate_and_prepare(
        db=db, user_id=user_id, role=role,
        conversation_id=conversation_id, kb_id=kb_id, question=question,
    )

    task_id = str(uuid4())

    return StreamingResponse(
        stream_with_heartbeat(_generate_sse_stream(
            db=db,
            conv=conv,
            task_id=task_id,
            question=question,
            deep_thinking=deep_thinking,
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
    from sqlalchemy import and_, exists

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
