"""Chat Service Trace 集成埋点测试

对齐 TEST_CASES.md §6.14.4：
- U13.10 埋点-完整 RAG 流程：KNOWLEDGE 意图 → Trace 写入，各阶段 JSON 非空
- U13.11 埋点-CASUAL 路径：CASUAL 意图 → Trace 写入，retrieve/rerank 为空
- U13.12 埋点-META 路径：META 意图 → Trace 写入，generate 为空，token_usage 全为 0
- U13.13 埋点-错误状态：LLM 失败 → Trace 写入，status=error，error_message 非空
- U13.14 埋点-retrieve 细粒度：正常检索 → retrieve JSON 含 vector/bm25/fusion/match_sentence 各 duration_ms

与已通过的 Trace 测试（§6.14.1-6.14.3，40 用例）互补：
§6.14.1-6.14.3 测 Trace 基础设施（TraceRecorder + trace_service + Trace API），
本节测 chat_service.chat() 全链路中 TraceRecorder 是否被正确调用和数据收集。

设计要点：
- 使用真实 TraceRecorder（而非 MagicMock），直接验证各 record_* 方法写入的数据
- Mock trace_service.record_trace() 阻止真实 DB 写入，但验证传入参数
- 各意图路由（KNOWLEDGE/CASUAL/META）和异常场景独立覆盖
"""

import json
from contextlib import ExitStack, contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import MetaQuestionException
from app.rag.intent import Intent, IntentResult
from app.rag.retriever import RetrievalOutput, RetrievalResult

# 测试用 UUID 常量（chat_service.chat() 要求 UUID 字符串）
_TEST_KB_UUID = "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
_TEST_CONV_UUID = "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb"


# ==================== 辅助函数 ====================


def _make_retrieval_output():
    """构造标准检索结果"""
    return RetrievalOutput(
        results=[
            RetrievalResult(
                doc_id=1, chunk_index=0,
                content="检索到的相关内容",
                score=0.95, page=1,
            ),
        ],
        total=1,
    )


def _make_llm_chunks(texts=None):
    """构造 LLM 流式 chunk 列表"""
    from app.core.llm import LLMChunk
    if texts is None:
        texts = ["这是", "LLM", "的回答"]
    chunks = []
    for text in texts:
        chunks.append(LLMChunk(content=text, reasoning_content=""))
    return chunks


async def _async_gen(items):
    """构造 async generator"""
    for item in items:
        yield item


async def _async_gen_error(msg):
    """构造抛异常的 async generator"""
    yield MagicMock(content="部分", reasoning_content="")
    raise Exception(msg)


def _mock_db_with_conversation(db, conv, kb=None, doc_count=1):
    """配置 mock DB 的通用行为"""
    if kb is None:
        kb = MagicMock()
        kb.id = 1
        kb.status = "active"
        kb.visibility = "private"
        kb.user_id = 1

    def get_side_effect(model, pk):
        if model.__name__ == "KnowledgeBase":
            return kb
        if model.__name__ == "Conversation":
            return conv
        return None

    db.get = AsyncMock(side_effect=get_side_effect)

    # doc_count 查询（scalar）
    count_result = MagicMock()
    count_result.scalar.return_value = doc_count

    # doc_names 查询（scalars().all()）
    row = MagicMock()
    row.id = 1
    row.filename = "测试文档.pdf"
    names_result = MagicMock()
    names_result.scalars.return_value.all.return_value = [row]

    # _load_history 查询（空历史）
    history_result = MagicMock()
    history_result.scalars.return_value.all.return_value = []

    # 默认空查询结果（用于未被明确覆盖的 db.execute 调用）
    empty_result = MagicMock()
    empty_result.scalar.return_value = 0
    empty_result.scalars.return_value.all.return_value = []

    db.execute = AsyncMock(side_effect=[count_result, history_result, names_result, empty_result])
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()

    return kb


@contextmanager
def _mock_chat_pipeline_for_trace(db, conv, *, retrieval_output=None, llm_chunks=None,
                                   intent_result=None, use_real_recorder=True):
    """Trace 集成测试专用 mock 上下文管理器。

    与 _mock_chat_pipeline 不同：
    1. 使用真实 TraceRecorder（而非 MagicMock），直接验证各阶段数据收集
    2. Mock trace_service.record_trace() 阻止真实 DB 写入，但验证传入参数
    3. 返回 recorder 实例，测试可直接检查 _intent_data/_retrieve_data 等内部属性

    参数:
        use_real_recorder: True → 使用真实 TraceRecorder，mock record_trace 阻止 DB 写入
                          False → MagicMock recorder（用于 META 等需要手动控制路径）
    """
    if retrieval_output is None:
        retrieval_output = _make_retrieval_output()
    if llm_chunks is None:
        llm_chunks = _make_llm_chunks()
    if intent_result is None:
        intent_result = IntentResult(
            intent=Intent.KNOWLEDGE, method="llm_flash",
            metadata={"model": "deepseek-v4-flash", "confidence": None},
        )

    _mock_db_with_conversation(db, conv)

    mock_conv = MagicMock()
    mock_conv.id = conv.id
    mock_conv.uuid = _TEST_CONV_UUID
    mock_conv.user_id = conv.user_id
    mock_conv.message_count = getattr(conv, 'message_count', 0)
    mock_conv.title = getattr(conv, 'title', '新对话')

    mock_user_msg = MagicMock(id=10, role="user", content="测试问题")
    mock_assistant_msg = MagicMock(
        id=11, role="assistant", content="这是LLM的回答",
        thinking_content=None, token_count=50,
    )

    with ExitStack() as stack:
        mocks = {}

        # Mock async_session：generator 内部自管短 session（ADR-017）
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_conv)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mocks['async_session'] = stack.enter_context(
            patch("app.services.chat_service.async_session",
                  return_value=mock_ctx))
        mocks['mock_session'] = mock_session

        mocks['conv_patch'] = stack.enter_context(
            patch("app.services.chat_service.Conversation", return_value=mock_conv))
        mocks['msg_patch'] = stack.enter_context(
            patch("app.services.chat_service.Message",
                  side_effect=[mock_user_msg, mock_assistant_msg]))

        mocks['vec'] = stack.enter_context(patch("app.services.chat_service._vector_retriever"))
        mocks['bm25'] = stack.enter_context(patch("app.services.chat_service._bm25_retriever"))
        mocks['rrf'] = stack.enter_context(
            patch("app.services.chat_service.rrf_fusion", return_value=retrieval_output))
        mocks['reranker'] = stack.enter_context(patch("app.services.chat_service._reranker"))
        mocks['prompt'] = stack.enter_context(patch("app.services.chat_service.build_prompt"))
        mocks['llm'] = stack.enter_context(patch("app.services.chat_service.stream_chat_completion"))
        mocks['tokens'] = stack.enter_context(
            patch("app.services.chat_service.estimate_tokens", return_value=50))
        mocks['heartbeat'] = stack.enter_context(
            patch("app.services.chat_service.stream_with_heartbeat",
                  side_effect=lambda g, **kw: g))
        mocks['intent'] = stack.enter_context(
            patch("app.services.chat_service.classify_intent", new_callable=AsyncMock))
        mocks['intent'].return_value = intent_result

        # Mock resolve_uuid_to_id：将 UUID 字符串转回整数 ID
        _conv_id = conv.id
        async def _mock_resolve(db, model, uuid_str):
            if uuid_str == _TEST_KB_UUID:
                return 1
            if uuid_str == _TEST_CONV_UUID:
                return _conv_id
            return None
        mocks['resolve_uuid'] = stack.enter_context(
            patch("app.core.uuid_helpers.resolve_uuid_to_id",
                  new_callable=AsyncMock, side_effect=_mock_resolve))

        # Mock record_trace 阻止真实 DB 写入，但记录调用参数
        record_trace_mock = AsyncMock()
        mocks['record_trace'] = stack.enter_context(
            patch("app.rag.trace_recorder.record_trace", new=record_trace_mock))

        # Recorder: 使用真实 TraceRecorder（验证数据收集正确性）
        # 或 MagicMock（用于需要手动控制的路径）
        if use_real_recorder:
            from app.rag.trace_recorder import TraceRecorder
            # 使用真实 TraceRecorder，但 finish 中调用的 record_trace 已被 mock
            recorder_instance = TraceRecorder(
                trace_id="test-trace-integration",
                user_id=1,
                conversation_id=None,
                kb_id=1,
                question="测试问题",
            )
            mocks['TraceRecorder'] = stack.enter_context(
                patch("app.services.chat_service.TraceRecorder", return_value=recorder_instance))
            mocks['recorder'] = recorder_instance
        else:
            mock_recorder = MagicMock()
            mock_recorder.finish = AsyncMock()
            mock_recorder.record_intent = MagicMock()
            mock_recorder.record_rewrite = MagicMock()
            mock_recorder.record_retrieve = MagicMock()
            mock_recorder.record_rerank = MagicMock()
            mock_recorder.record_generate = MagicMock()
            mock_recorder.set_response_mode = MagicMock()
            mock_recorder.record_error = MagicMock()
            mocks['TraceRecorder'] = stack.enter_context(
                patch("app.services.chat_service.TraceRecorder", return_value=mock_recorder))
            mocks['recorder'] = mock_recorder

        # 默认行为配置
        mocks['vec'].search = AsyncMock(return_value=retrieval_output)
        mocks['bm25'].search = AsyncMock(return_value=retrieval_output)
        mocks['reranker'].rerank = AsyncMock(return_value=retrieval_output)
        mocks['prompt'].return_value = MagicMock(
            system_prompt="系统提示",
            user_prompt="用户提示",
            used_chunks=retrieval_output.results,
            total_context_tokens=500,
            chunks_count=len(retrieval_output.results),
            history_messages=[],
        )
        mocks['llm'].return_value = _async_gen(llm_chunks)

        # 便捷访问别名
        mocks['conv'] = mock_conv
        mocks['user_msg'] = mock_user_msg
        mocks['assistant_msg'] = mock_assistant_msg
        mocks['retrieval_output'] = retrieval_output

        yield mocks


async def _consume_sse(response):
    """消费 StreamingResponse，返回解析后的事件列表"""
    events = []
    current_event = None
    async for chunk in response.body_iterator:
        for line in chunk.split("\n"):
            line = line.strip()
            if line.startswith("event: "):
                current_event = line[7:]
            elif line.startswith("data: ") and current_event is not None:
                data = json.loads(line[6:])
                events.append({"event": current_event, "data": data})
    return events


# ==================== 测试类 ====================


class TestTraceKnowledgeRAGFlow:
    """U13.10 — 埋点-完整 RAG 流程（KNOWLEDGE 意图）

    验证 KNOWLEDGE 意图问答全流程中，TraceRecorder 各阶段数据被正确收集：
    - intent: intent_type=KNOWLEDGE, method=llm_flash
    - rewrite: original_question + rewritten_question（或跳过标记）
    - retrieve: vector/bm25/fusion/match_sentence 各 duration_ms
    - rerank: input_count/output_count/duration_ms
    - generate: model/ttft_ms/total_ms/input_tokens/output_tokens
    """

    @pytest.mark.asyncio
    async def test_完整RAG流程_Trace各阶段JSON非空(self):
        """KNOWLEDGE 意图 → Trace 写入，intent/rewrite/retrieve/rerank/generate 各阶段 JSON 非空"""
        from app.services.chat_service import chat

        db = AsyncMock()
        conv = MagicMock()
        conv.id = 50
        conv.user_id = 1
        conv.message_count = 0
        conv.title = "新对话"

        retrieval_output = _make_retrieval_output()
        llm_chunks = _make_llm_chunks(["这是[来源1]", "LLM", "的回答"])

        with _mock_chat_pipeline_for_trace(
            db, conv,
            retrieval_output=retrieval_output,
            llm_chunks=llm_chunks,
            use_real_recorder=True,
        ) as mocks:
            response = await chat(
                db=db, user_id=1, role="user",
                conversation_id=None, kb_id=_TEST_KB_UUID,
                question="测试问题", deep_thinking=False,
            )
            events = await _consume_sse(response)

        recorder = mocks['recorder']

        # 验证 SSE 流正常完成
        event_types = [e["event"] for e in events]
        assert "finish" in event_types

        # 验证 intent 阶段
        assert recorder._intent_data is not None
        assert recorder._intent_type == "KNOWLEDGE"
        assert recorder._intent_method == "llm_flash"
        assert recorder._intent_data["intent_type"] == "KNOWLEDGE"
        assert recorder._intent_data["method"] == "llm_flash"
        assert recorder._intent_data["duration_ms"] >= 0

        # 验证 rewrite 阶段（KNOWLEDGE 首轮可能不触发重写，但应记录跳过）
        assert recorder._rewrite_data is not None
        assert recorder._rewrite_data["span_name"] == "rewrite"
        assert recorder._rewrite_data["original_question"] == "测试问题"

        # 验证 retrieve 阶段
        assert recorder._retrieve_data is not None
        assert recorder._retrieve_data["span_name"] == "retrieve"
        assert recorder._retrieve_data["duration_ms"] >= 0  # Mock 环境下 perf_counter 无真实延迟，允许 0
        assert "vector" in recorder._retrieve_data
        assert "bm25" in recorder._retrieve_data
        assert "fusion" in recorder._retrieve_data

        # 验证 rerank 阶段
        assert recorder._rerank_data is not None
        assert recorder._rerank_data["span_name"] == "rerank"
        assert recorder._rerank_data["input_count"] > 0
        assert recorder._rerank_data["output_count"] > 0

        # 验证 generate 阶段
        # record_generate 参数 total_ms → 写入为 duration_ms=int(total_ms)
        assert recorder._generate_data is not None
        assert recorder._generate_data["span_name"] == "generate"
        assert recorder._generate_data["model"] is not None
        assert recorder._generate_data["ttft_ms"] >= 0
        assert recorder._generate_data["duration_ms"] >= 0  # Mock 环境下 perf_counter 无真实延迟，允许 0
        # token 估算值被更新（非初始 0）
        assert recorder._generate_data["input_tokens"] > 0
        assert recorder._generate_data["output_tokens"] > 0

        # 验证 record_trace 被调用（finish 写入 DB）
        assert mocks['record_trace'].called

        # 验证顶层字段
        assert recorder._response_mode == "RAG"
        assert recorder._status == "success"
        assert recorder._error_message is None


class TestTraceCasualFlow:
    """U13.11 — 埋点-CASUAL 跳过检索

    验证 CASUAL 意图问答中，TraceRecorder 数据收集：
    - intent: intent_type=CASUAL, method=regex（规则快速通道）
    - rewrite: 记录跳过标记
    - retrieve: None（CASUAL 跳过检索，不调 record_retrieve）
    - rerank: None（同上）
    - generate: 正常记录（CASUAL 仍调 LLM，使用 CASUAL_SYSTEM_PROMPT）
    """

    @pytest.mark.asyncio
    async def test_CASUAL跳过检索_retrieve_rerank为空(self):
        """CASUAL 意图 → Trace 写入，retrieve/rerank 为 None"""
        from app.services.chat_service import chat

        db = AsyncMock()
        conv = MagicMock()
        conv.id = 50
        conv.user_id = 1
        conv.message_count = 0
        conv.title = "新对话"

        llm_chunks = _make_llm_chunks(["你好！很高兴为你服务。"])

        with _mock_chat_pipeline_for_trace(
            db, conv,
            retrieval_output=_make_retrieval_output(),
            llm_chunks=llm_chunks,
            intent_result=IntentResult(
                intent=Intent.CASUAL, method="regex",
                metadata={"rule": "CASUAL_PATTERNS"},
            ),
            use_real_recorder=True,
        ) as mocks:
            response = await chat(
                db=db, user_id=1, role="user",
                conversation_id=None, kb_id=_TEST_KB_UUID,
                question="你好", deep_thinking=False,
            )
            events = await _consume_sse(response)

        recorder = mocks['recorder']

        # 验证 SSE 流正常完成
        event_types = [e["event"] for e in events]
        assert "finish" in event_types

        # 验证 intent 阶段
        assert recorder._intent_type == "CASUAL"
        assert recorder._intent_method == "regex"
        assert recorder._intent_data is not None
        assert recorder._intent_data["intent_type"] == "CASUAL"

        # 验证 CASUAL 跳过检索：retrieve/rerank 为 None
        assert recorder._retrieve_data is None
        assert recorder._rerank_data is None

        # 验证 generate 阶段（CASUAL 仍调 LLM）
        # record_generate 参数 total_ms → 写入为 duration_ms=int(total_ms)
        assert recorder._generate_data is not None
        assert recorder._generate_data["model"] is not None
        assert recorder._generate_data["duration_ms"] >= 0  # Mock 环境下 perf_counter 无真实延迟，允许 0

        # 验证顶层字段
        assert recorder._response_mode == "CASUAL"
        assert recorder._status == "success"


class TestTraceMetaFlow:
    """U13.12 — 埋点-META 不调 LLM

    验证 META 意图问答中，TraceRecorder 数据收集：
    - intent: intent_type=META, method=regex（规则快速通道）
    - generate: None（META 不调 LLM，返回固定模板）
    - token_usage: 全为 0（无 LLM 调用）

    注意：META 路径在 _validate_and_prepare 中抛 MetaQuestionException，
    由 chat() 外层捕获后走 _generate_meta_response。TraceRecorder 在此路径中：
    - record_intent 已在 _validate_and_prepare 中完成
    - record_rewrite 被调用（记录跳过标记，duration_ms=0）
    - retrieve/rerank/generate 不会被调用（META 不走检索和 LLM）
    - finish() 在 _generate_meta_response 中调用
    """

    @pytest.mark.asyncio
    async def test_META不调LLM_generate为空_token为零(self):
        """META 意图 → Trace 写入，generate 为 None，token 全为 0"""
        from app.services.chat_service import chat

        db = AsyncMock()
        conv = MagicMock()
        conv.id = 50
        conv.user_id = 1
        conv.message_count = 0
        conv.title = "新对话"

        kb = MagicMock()
        kb.id = 1
        kb.status = "active"
        kb.visibility = "public"
        kb.user_id = 2  # 非 owner，public KB

        _mock_db_with_conversation(db, conv, kb=kb)

        # 使用真实 TraceRecorder
        from app.rag.trace_recorder import TraceRecorder
        recorder_instance = TraceRecorder(
            trace_id="test-trace-meta",
            user_id=1,
            conversation_id=None,
            kb_id=1,
            question="你能做什么？",
        )

        # Mock record_trace 阻止真实 DB 写入
        record_trace_mock = AsyncMock()

        # META 路径：_validate_and_prepare 内抛 MetaQuestionException
        # conv 对象在 Exception 中携带
        mock_conv_for_meta = MagicMock()
        mock_conv_for_meta.id = 50
        mock_conv_for_meta.uuid = _TEST_CONV_UUID
        mock_conv_for_meta.user_id = 1
        mock_conv_for_meta.message_count = 0
        mock_conv_for_meta.title = "新对话"

        # 用户消息需要先保存（_validate_and_prepare 中 db.add user_msg + commit）
        mock_user_msg = MagicMock(id=10, role="user", content="你能做什么？")

        with ExitStack() as stack:
            stack.enter_context(
                patch("app.services.chat_service.Conversation", return_value=mock_conv_for_meta))
            stack.enter_context(
                patch("app.services.chat_service.Message",
                      side_effect=[mock_user_msg, MagicMock(id=11, role="assistant")]))

            # Mock async_session：_generate_meta_response 内部自管短 session（ADR-017）
            mock_session = AsyncMock()
            mock_session.get = AsyncMock(return_value=mock_conv_for_meta)
            mock_session.add = MagicMock()
            mock_session.flush = AsyncMock()
            mock_session.refresh = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_session.rollback = AsyncMock()
            mock_ctx = MagicMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            stack.enter_context(
                patch("app.services.chat_service.async_session",
                      return_value=mock_ctx))

            stack.enter_context(
                patch("app.services.chat_service.classify_intent", new_callable=AsyncMock,
                      return_value=IntentResult(
                          intent=Intent.META, method="regex",
                          metadata={"rule": "META_PATTERNS"},
                      )))
            stack.enter_context(
                patch("app.rag.trace_recorder.record_trace", new=record_trace_mock))
            stack.enter_context(
                patch("app.services.chat_service.TraceRecorder", return_value=recorder_instance))
            stack.enter_context(
                patch("app.services.chat_service.stream_with_heartbeat",
                      side_effect=lambda g, **kw: g))
            stack.enter_context(
                patch("app.core.uuid_helpers.resolve_uuid_to_id",
                      new_callable=AsyncMock, return_value=1))

            response = await chat(
                db=db, user_id=1, role="user",
                conversation_id=None, kb_id=_TEST_KB_UUID,
                question="你能做什么？", deep_thinking=False,
            )
            events = await _consume_sse(response)

        # 验证 SSE 流正常完成
        event_types = [e["event"] for e in events]
        assert "finish" in event_types

        # 验证 intent 阶段
        assert recorder_instance._intent_type == "META"
        assert recorder_instance._intent_method == "regex"
        assert recorder_instance._intent_data is not None
        assert recorder_instance._intent_data["intent_type"] == "META"

        # 验证 META 不调 LLM：generate 为 None
        assert recorder_instance._generate_data is None

        # 验证 retrieve/rerank 也为 None（META 跳过检索）
        assert recorder_instance._retrieve_data is None
        assert recorder_instance._rerank_data is None

        # 验证顶层字段
        assert recorder_instance._response_mode == "META"
        assert recorder_instance._status == "success"

        # 验证 finish 事件 token_usage 全为 0
        finish = next(e for e in events if e["event"] == "finish")
        usage = finish["data"]["token_usage"]
        assert usage["prompt"] == 0
        assert usage["completion"] == 0
        assert usage["total"] == 0

        # 验证 record_trace 被调用（finish 写入 DB）
        assert record_trace_mock.called


class TestTraceErrorFlow:
    """U13.13 — 埋点-错误状态

    验证 LLM 调用失败时，TraceRecorder 数据收集：
    - intent/rewrite/retrieve/rerank 正常记录（失败发生在 LLM 阶段之后）
    - generate: None（LLM 失败，record_generate 未被调用）
    - status: error
    - error_message: 非空
    """

    @pytest.mark.asyncio
    async def test_LLM失败_Trace错误状态_error_message非空(self):
        """LLM 调用失败 → Trace 写入，status=error，error_message 非空"""
        from app.services.chat_service import chat

        db = AsyncMock()
        conv = MagicMock()
        conv.id = 50
        conv.user_id = 1
        conv.message_count = 0
        conv.title = "新对话"

        retrieval_output = _make_retrieval_output()

        with _mock_chat_pipeline_for_trace(
            db, conv,
            retrieval_output=retrieval_output,
            use_real_recorder=True,
        ) as mocks:
            mocks['llm'].return_value = _async_gen_error("API 超时")

            response = await chat(
                db=db, user_id=1, role="user",
                conversation_id=None, kb_id=_TEST_KB_UUID,
                question="测试问题", deep_thinking=False,
            )
            events = await _consume_sse(response)

        recorder = mocks['recorder']

        # 验证 SSE 流包含 error 事件
        event_types = [e["event"] for e in events]
        assert "error" in event_types

        # 验证 intent 阶段（意图识别在 LLM 之前，正常完成）
        assert recorder._intent_data is not None
        assert recorder._intent_type == "KNOWLEDGE"

        # 验证 rewrite 阶段（在 LLM 之前，正常完成）
        assert recorder._rewrite_data is not None

        # 验证 retrieve 阶段（在 LLM 之前，正常完成）
        assert recorder._retrieve_data is not None
        assert recorder._retrieve_data["span_name"] == "retrieve"

        # 验证 rerank 阶段（在 LLM 之前，正常完成）
        assert recorder._rerank_data is not None

        # 验证 generate 为 None（LLM 失败，record_generate 未被调用）
        assert recorder._generate_data is None

        # 验证错误状态
        assert recorder._status == "error"
        assert recorder._error_message is not None
        assert len(recorder._error_message) > 0

        # 验证 record_trace 被调用（finish 在 error 处理中写入）
        assert mocks['record_trace'].called


class TestTraceRetrieveGranularity:
    """U13.14 — 埋点-retrieve 细粒度

    验证正常检索流程中，retrieve JSON 含 vector/bm25/fusion/match_sentence 各 duration_ms。
    对齐 ARCHITECTURE.md §5.1.8 retrieve 细粒度拆分。
    """

    @pytest.mark.asyncio
    async def test_retrieve细粒度_含vector_bm25_fusion_match_sentence各duration_ms(self):
        """正常检索 → retrieve JSON 含 vector/bm25/fusion/match_sentence 各 duration_ms"""
        from app.services.chat_service import chat

        db = AsyncMock()
        conv = MagicMock()
        conv.id = 50
        conv.user_id = 1
        conv.message_count = 0
        conv.title = "新对话"

        retrieval_output = _make_retrieval_output()
        llm_chunks = _make_llm_chunks(["这是[来源1]的回答"])

        with _mock_chat_pipeline_for_trace(
            db, conv,
            retrieval_output=retrieval_output,
            llm_chunks=llm_chunks,
            use_real_recorder=True,
        ) as mocks:
            # BM25 返回含 stats 的检索结果（模拟真实 BM25 细粒度数据）
            bm25_output = RetrievalOutput(
                results=[
                    RetrievalResult(
                        doc_id=1, chunk_index=0,
                        content="BM25检索结果",
                        score=0.88, page=1,
                    ),
                ],
                total=1,
                stats={
                    "redis_cache": True,
                    "tokenize_ms": 15,
                    "score_ms": 8,
                    "candidate_count": 100,
                    "result_count": 1,
                },
            )
            mocks['bm25'].search = AsyncMock(return_value=bm25_output)

            response = await chat(
                db=db, user_id=1, role="user",
                conversation_id=None, kb_id=_TEST_KB_UUID,
                question="测试问题", deep_thinking=False,
            )
            events = await _consume_sse(response)

        recorder = mocks['recorder']

        # 验证 SSE 流正常完成
        event_types = [e["event"] for e in events]
        assert "finish" in event_types

        # 验证 retrieve 阶段存在
        assert recorder._retrieve_data is not None
        retrieve_json = recorder._retrieve_data

        # 验证 retrieve 细粒度字段
        assert retrieve_json["span_name"] == "retrieve"
        # duration_ms 在 mock 环境下 perf_counter 精度有限，允许为 0
        assert retrieve_json["duration_ms"] >= 0

        # 验证 vector 子字段
        assert "vector" in retrieve_json
        vector_data = retrieve_json["vector"]
        assert "duration_ms" in vector_data
        assert vector_data["duration_ms"] >= 0
        assert "result_count" in vector_data

        # 验证 bm25 子字段
        assert "bm25" in retrieve_json
        bm25_data = retrieve_json["bm25"]
        assert "duration_ms" in bm25_data
        assert bm25_data["duration_ms"] >= 0
        # BM25 stats 字段应被透传
        assert bm25_data.get("redis_cache") is True or bm25_data.get("redis_cache") is not None

        # 验证 fusion 子字段
        assert "fusion" in retrieve_json
        fusion_data = retrieve_json["fusion"]
        assert "duration_ms" in fusion_data
        assert fusion_data["duration_ms"] >= 0
        assert "method" in fusion_data
        assert "result_count" in fusion_data

        # 验证 match_sentence 子字段
        assert "match_sentence" in retrieve_json
        match_data = retrieve_json["match_sentence"]
        assert "duration_ms" in match_data
        assert match_data["duration_ms"] >= 0

        # 验证总耗时 ≥ 各子阶段之和（允许微小浮点误差）
        total_retrieve_ms = retrieve_json["duration_ms"]
        sub_total = (
            vector_data["duration_ms"]
            + bm25_data["duration_ms"]
            + fusion_data["duration_ms"]
            + match_data["duration_ms"]
        )
        # 总耗时至少等于各子阶段之和（可能有 match_sentence 在 rerank 之后的耗时差异）
        assert total_retrieve_ms >= sub_total - 50  # 允许 50ms 误差（perf_counter Mock 精度）
