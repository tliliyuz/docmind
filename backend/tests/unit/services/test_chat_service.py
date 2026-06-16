"""Chat Service 单元测试

对齐 TEST_CASES.md §5.7：
- U7.60 正常问答流程（自动创建会话 → 检索 → RRF → Rerank → Prompt → LLM → SSE）
- U7.61 追加已有会话
- U7.62 检索失败 → SSE error 事件
- U7.63 LLM 失败 → SSE error 事件
- U7.64 KB 无文档 → 抛 KnowledgeBaseEmptyException
- U7.65 用户消息落库（user + assistant 两条）
- U7.66 标题自动生成（截取前 12 字 + 去标点）
- U7.67 message_count 递增（每轮 +2）

覆盖 app/services/chat_service.py
"""

import asyncio
import json
from contextlib import ExitStack, contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import (
    ConversationAccessDeniedException,
    ConversationNotFoundException,
    KnowledgeBaseEmptyException,
    KnowledgeBaseNotFoundException,
    MetaQuestionException,
    PermissionDeniedException,
    RetrievalServiceException,
)
from app.rag.intent import Intent, IntentResult
from app.rag.knowledge_pipeline import KnowledgePipelineResult
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


def _mock_db_with_conversation(db, conv, kb=None, doc_count=1, user_msg=None, assistant_msg=None):
    """配置 mock DB 的通用行为"""
    if kb is None:
        kb = MagicMock()
        kb.id = 1
        kb.status = "active"
        kb.visibility = "private"
        kb.user_id = 1

    if user_msg is None:
        user_msg = MagicMock()
        user_msg.id = 10
        user_msg.role = "user"
        user_msg.content = "测试问题"

    if assistant_msg is None:
        assistant_msg = MagicMock()
        assistant_msg.id = 11
        assistant_msg.role = "assistant"
        assistant_msg.content = "这是LLM的回答"

    def get_side_effect(model, pk):
        name = getattr(model, '__name__', '')
        if name == "KnowledgeBase":
            return kb
        if name == "Conversation" or not name:
            # not name → model is a MagicMock（patched class），返回 conv
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

    # _load_history 查询（scalars().all()，返回空历史）
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

    return kb, user_msg, assistant_msg


@contextmanager
def _mock_chat_pipeline(db, conv, *, retrieval_output=None, llm_chunks=None,
                         token_estimate=50, with_conversation=True, with_messages=True,
                         doc_count=1):
    """共享的 chat pipeline mock 上下文管理器。

    消除各测试方法中重复的 ~10 行 patch() 样板代码。
    返回 mocks dict，包含所有 mock 对象，测试可按需覆盖。

    mocks 字段:
        vec, bm25, rrf, reranker, prompt, llm, tokens, heartbeat — 各组件 mock
        conv — Conversation() 返回的 mock 对象
        user_msg, assistant_msg — Message() 返回的两个 mock 对象
        retrieval_output — 检索结果

    用法:
        with _mock_chat_pipeline(db, conv) as mocks:
            mocks['llm'].return_value = _async_gen_error("自定义错误")
            response = await chat(...)
    """
    if retrieval_output is None:
        retrieval_output = _make_retrieval_output()
    if llm_chunks is None:
        llm_chunks = _make_llm_chunks()

    mock_conv = MagicMock()
    mock_conv.id = conv.id
    mock_conv.uuid = _TEST_CONV_UUID
    mock_conv.user_id = conv.user_id
    mock_conv.message_count = getattr(conv, 'message_count', 0)
    mock_conv.title = getattr(conv, 'title', '新对话')

    # 使用 mock_conv 统一 db.get 和 mock_session.get 的返回值，
    # 确保 _validate_and_prepare 和 generator 对 message_count/title 的修改落在同一对象上
    _mock_db_with_conversation(db, mock_conv, doc_count=doc_count)

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
        # sse_stream.py 拆分后有自己的 async_session 导入，需同步 mock
        stack.enter_context(
            patch("app.services.sse_stream.async_session",
                  return_value=mock_ctx))
        mocks['mock_session'] = mock_session

        if with_conversation:
            mocks['conv_patch'] = stack.enter_context(
                patch("app.services.chat_service.Conversation", return_value=mock_conv))
            # sse_stream.py 拆分后有自己的 Conversation 导入，需同步 mock
            stack.enter_context(
                patch("app.services.sse_stream.Conversation", return_value=mock_conv))

        if with_messages:
            mocks['msg_patch'] = stack.enter_context(
                patch("app.services.chat_service.Message",
                      side_effect=[mock_user_msg, mock_assistant_msg]))
            # sse_stream.py 拆分后有自己的 Message 导入，仅创建 assistant 消息
            stack.enter_context(
                patch("app.services.sse_stream.Message",
                      return_value=mock_assistant_msg))

        # Mock _pipeline（KnowledgePipeline 单例，替代原来的独立检索组件 mock）
        mock_pipeline = MagicMock()
        # 构造 KnowledgePipelineResult
        _pipeline_result = KnowledgePipelineResult(
            reranked_output=retrieval_output,
            prompt_result=MagicMock(
                system_prompt="系统提示",
                user_prompt="用户提示",
                used_chunks=retrieval_output.results,
                total_context_tokens=500,
                chunks_count=len(retrieval_output.results),
                history_messages=[],
            ),
            doc_map={1: "测试文档.pdf"},
        )
        mock_pipeline.execute_knowledge = AsyncMock(return_value=_pipeline_result)
        mock_pipeline.execute_casual = AsyncMock(return_value=_pipeline_result)
        mocks['pipeline'] = stack.enter_context(
            patch("app.services.chat_service._pipeline", mock_pipeline))
        mocks['pipeline_result'] = _pipeline_result

        mocks['llm'] = stack.enter_context(patch("app.services.sse_stream.stream_chat_completion"))
        mocks['tokens'] = stack.enter_context(
            patch("app.services.sse_stream.estimate_tokens", return_value=token_estimate))
        mocks['heartbeat'] = stack.enter_context(
            patch("app.services.chat_service.stream_with_heartbeat",
                  side_effect=lambda g, **kw: g))
        mocks['intent'] = stack.enter_context(
            patch("app.services.chat_service.classify_intent", new_callable=AsyncMock))

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
        mocks['intent'].return_value = IntentResult(
            intent=Intent.KNOWLEDGE, method="llm_flash",
            metadata={"model": "deepseek-v4-flash", "confidence": None},
        )

        # LLM 默认行为配置
        mocks['llm'].return_value = _async_gen(llm_chunks)

        # Mock TraceRecorder，避免真实的 db.add 调用
        mock_recorder = MagicMock()
        mock_recorder.finish = AsyncMock()
        mock_recorder.record_intent = MagicMock()
        mock_recorder.record_rewrite = MagicMock()
        mock_recorder.record_retrieve = MagicMock()
        mock_recorder.record_rerank = MagicMock()
        mock_recorder.record_generate = MagicMock()
        mock_recorder.set_response_mode = MagicMock()
        mock_recorder.record_error = MagicMock()
        mocks['recorder'] = stack.enter_context(
            patch("app.services.chat_service.TraceRecorder", return_value=mock_recorder))

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
        # body_iterator 按 generator yield 粒度返回，每个 chunk 可能含多个行
        for line in chunk.split("\n"):
            line = line.strip()
            if line.startswith("event: "):
                current_event = line[7:]
            elif line.startswith("data: ") and current_event is not None:
                data = json.loads(line[6:])
                events.append({"event": current_event, "data": data})
    return events


# ==================== 测试类 ====================


class TestGenerateTitle:
    """测试 generate_title 标题生成（纯逻辑公开函数）"""

    def test_正常截取前12字(self):
        """截取问题前 12 字作为标题"""
        from app.services.chat_service import generate_title
        title = generate_title("这是一段超过十二个字符的用户问题内容")
        assert title == "这是一段超过十二个字符的"  # 18 字符取前 12

    def test_去除标点符号(self):
        """标题应去除标点符号"""
        from app.services.chat_service import generate_title
        title = generate_title("你好！请问这个问题怎么解决？")
        assert "！" not in title
        assert "？" not in title

    def test_全标点时返回新对话(self):
        """全标点内容去除后为空，应返回 '新对话'"""
        from app.services.chat_service import generate_title
        title = generate_title("！？。，、；：""''【】")
        assert title == "新对话"

    def test_去除首尾空格(self):
        """标题应去除首尾空格"""
        from app.services.chat_service import generate_title
        title = generate_title("  问题内容  ")
        assert title == "问题内容"


class TestChatNormalFlow:
    """U7.60 — 正常问答流程"""

    @pytest.mark.asyncio
    async def test_正常问答全流程(self):
        """自动创建会话 → 检索 → RRF → Rerank → Prompt → LLM → SSE 事件序列"""
        from app.services.chat_service import chat

        db = AsyncMock()
        conv = MagicMock()
        conv.id = 50
        conv.user_id = 1
        conv.message_count = 0
        conv.title = "新对话"

        retrieval_output = _make_retrieval_output()
        llm_chunks = _make_llm_chunks(["这是[来源1]", "LLM", "的回答"])

        with _mock_chat_pipeline(db, conv, retrieval_output=retrieval_output,
                                  llm_chunks=llm_chunks) as mocks:
            response = await chat(
                db=db, user_id=1, role="user",
                conversation_id=None, kb_id=_TEST_KB_UUID,
                question="测试问题", deep_thinking=False,
            )
            events = await _consume_sse(response)

        # 验证事件序列
        event_types = [e["event"] for e in events]
        assert event_types[0] == "meta"
        assert "message" in event_types
        assert event_types[-1] == "finish"

        # 验证 meta 事件
        meta = next(e for e in events if e["event"] == "meta")
        assert meta["data"]["conversation_id"] == _TEST_CONV_UUID

        # 验证 message 事件内容
        msg_content = "".join(
            e["data"]["delta"] for e in events if e["event"] == "message"
        )
        assert msg_content == "这是[来源1]LLM的回答"

        # 验证 sources 事件
        sources = next(e for e in events if e["event"] == "sources")
        assert len(sources["data"]["chunks"]) >= 1

        # 验证 finish 事件
        finish = next(e for e in events if e["event"] == "finish")
        assert finish["data"]["message_id"] == 11
        assert finish["data"]["title"] is not None


class TestChatAppendConversation:
    """U7.61 — 追加已有会话"""

    @pytest.mark.asyncio
    async def test_已有会话复用(self):
        """conversation_id 存在时应复用已有会话"""
        from app.services.chat_service import chat

        db = AsyncMock()
        conv = MagicMock()
        conv.id = 100
        conv.uuid = _TEST_CONV_UUID
        conv.user_id = 1
        conv.message_count = 4
        conv.title = "已有标题"

        retrieval_output = _make_retrieval_output()
        llm_chunks = _make_llm_chunks(["追加回答"])

        with _mock_chat_pipeline(db, conv, retrieval_output=retrieval_output,
                                  llm_chunks=llm_chunks, token_estimate=30,
                                  with_conversation=False, with_messages=False):
            response = await chat(
                db=db, user_id=1, role="user",
                conversation_id=_TEST_CONV_UUID, kb_id=_TEST_KB_UUID,
                question="追加问题", deep_thinking=False,
            )
            events = await _consume_sse(response)

        meta = next(e for e in events if e["event"] == "meta")
        assert meta["data"]["conversation_id"] == _TEST_CONV_UUID

        finish = next(e for e in events if e["event"] == "finish")
        assert finish["data"]["title"] is None  # 非首轮无标题


class TestChatRetrievalFailure:
    """U7.62 — 检索失败"""

    @pytest.mark.asyncio
    async def test_检索失败包装为E4003(self):
        """检索服务异常时应包装为 RetrievalServiceException(E4003)"""
        from app.services.chat_service import chat

        db = AsyncMock()
        conv = MagicMock()
        conv.id = 50
        conv.user_id = 1
        conv.message_count = 0

        with _mock_chat_pipeline(db, conv) as mocks:
            mocks['pipeline'].execute_knowledge = AsyncMock(
                side_effect=RetrievalServiceException(detail="检索链路异常")
            )

            with pytest.raises(RetrievalServiceException) as exc_info:
                await chat(
                    db=db, user_id=1, role="user",
                    conversation_id=None, kb_id=_TEST_KB_UUID,
                    question="测试问题", deep_thinking=False,
                )
            assert exc_info.value.error_code == "E4003"
            assert "检索链路异常" in str(exc_info.value.error_detail)


class TestChatLLMFailure:
    """U7.63 — LLM 调用失败"""

    @pytest.mark.asyncio
    async def test_LLM失败发送error事件(self):
        """LLM 失败时应发送 sources → error 事件序列"""
        from app.services.chat_service import chat

        db = AsyncMock()
        conv = MagicMock()
        conv.id = 50
        conv.user_id = 1
        conv.message_count = 0

        retrieval_output = _make_retrieval_output()

        with _mock_chat_pipeline(db, conv, retrieval_output=retrieval_output) as mocks:
            mocks['llm'].return_value = _async_gen_error("API 超时")

            response = await chat(
                db=db, user_id=1, role="user",
                conversation_id=None, kb_id=_TEST_KB_UUID,
                question="测试问题", deep_thinking=False,
            )
            events = await _consume_sse(response)

        event_types = [e["event"] for e in events]
        assert event_types[0] == "meta"

        # error 之前应有 sources
        error_idx = event_types.index("error")
        assert "sources" in event_types[:error_idx]

        error = next(e for e in events if e["event"] == "error")
        assert error["data"]["code"] == "E4002"


class TestChatKBEmpty:
    """U7.64 — KB 无文档"""

    @pytest.mark.asyncio
    async def test_KB无文档抛异常(self):
        """KB 下无已完成文档时应抛 KnowledgeBaseEmptyException"""
        from app.services.chat_service import chat

        db = AsyncMock()
        conv = MagicMock()
        conv.id = 50
        conv.user_id = 1
        conv.message_count = 0

        with _mock_chat_pipeline(db, conv, doc_count=0) as mocks:
            # 覆盖 execute_knowledge：KB 空检查在 _validate_and_prepare 中已触发，
            # 此处作为兜底确保 pipeline 层也会正确抛出
            mocks['pipeline'].execute_knowledge = AsyncMock(
                side_effect=KnowledgeBaseEmptyException(1)
            )
            with pytest.raises(KnowledgeBaseEmptyException):
                await chat(
                    db=db, user_id=1, role="user",
                    conversation_id=None, kb_id=_TEST_KB_UUID,
                    question="测试问题", deep_thinking=False,
                )


class TestChatMessageSaved:
    """U7.65 — 用户消息落库"""

    @pytest.mark.asyncio
    async def test_保存user和assistant消息(self):
        """正常问答应写入 role=user + role=assistant 两条消息"""
        from app.services.chat_service import chat

        db = AsyncMock()
        conv = MagicMock()
        conv.id = 50
        conv.user_id = 1
        conv.message_count = 0
        conv.title = "新对话"

        retrieval_output = _make_retrieval_output()

        with _mock_chat_pipeline(db, conv, retrieval_output=retrieval_output,
                                  llm_chunks=_make_llm_chunks(["回答"])) as mocks:
            response = await chat(
                db=db, user_id=1, role="user",
                conversation_id=None, kb_id=_TEST_KB_UUID,
                question="测试问题", deep_thinking=False,
            )
            await _consume_sse(response)

        # 验证消息落库（ADR-017：generator 内短 session）
        # db.add：Conversation + Message(user) — 在 _validate_and_prepare 中
        db_add_calls = db.add.call_args_list
        assert len(db_add_calls) == 2

        # 第二次调用是 user message
        user_msg_arg = db_add_calls[1][0][0]
        assert user_msg_arg.role == "user"
        assert user_msg_arg.content == "测试问题"

        # mock_session.add：Message(assistant) — 在 generator 短 session 中
        session_add_calls = mocks['mock_session'].add.call_args_list
        assert len(session_add_calls) == 1
        assistant_msg_arg = session_add_calls[0][0][0]
        assert assistant_msg_arg.role == "assistant"
        assert assistant_msg_arg.thinking_content is None


class TestChatMessageCount:
    """U7.67 — message_count 递增"""

    @pytest.mark.asyncio
    async def test_每轮message_count加2(self):
        """每轮问答后 conversation.message_count 应增加 2"""
        from app.services.chat_service import chat

        db = AsyncMock()
        conv = MagicMock()
        conv.id = 50
        conv.uuid = _TEST_CONV_UUID
        conv.user_id = 1
        conv.message_count = 10
        conv.title = "已有标题"

        retrieval_output = _make_retrieval_output()

        with _mock_chat_pipeline(db, conv, retrieval_output=retrieval_output,
                                  llm_chunks=_make_llm_chunks(["回答"]),
                                  token_estimate=30,
                                  with_conversation=False, with_messages=False) as mocks:
            response = await chat(
                db=db, user_id=1, role="user",
                conversation_id=_TEST_CONV_UUID, kb_id=_TEST_KB_UUID,
                question="测试问题", deep_thinking=False,
            )
            await _consume_sse(response)

        # message_count: 初始 10 → +1(user) → +1(assistant) = 12
        # ADR-017: _validate_and_prepare 和 generator 通过 _mock_db_with_conversation(db, mock_conv)
        # 统一修改 mocks['conv']，确保两个阶段落在同一对象上
        assert mocks['conv'].message_count == 12


class TestChatTitleGeneration:
    """U7.66 — 标题自动生成（通过 chat 流程）"""

    @pytest.mark.asyncio
    async def test_首轮生成标题(self):
        """首轮问答（message_count == 2）应自动生成标题"""
        from app.services.chat_service import chat

        db = AsyncMock()
        conv = MagicMock()
        conv.id = 50
        conv.user_id = 1
        conv.message_count = 0
        conv.title = "新对话"

        retrieval_output = _make_retrieval_output()

        with _mock_chat_pipeline(db, conv, retrieval_output=retrieval_output,
                                  llm_chunks=_make_llm_chunks(["回答"])) as mocks:
            # Mock LLM 标题生成，避免真实调用
            with patch("app.services.sse_stream.generate_title_llm",
                       new_callable=AsyncMock, return_value="测试问题标题生成") as mock_title_llm:
                response = await chat(
                    db=db, user_id=1, role="user",
                    conversation_id=None, kb_id=_TEST_KB_UUID,
                    question="这是一个测试问题内容很长", deep_thinking=False,
                )
                events = await _consume_sse(response)

                finish = next(e for e in events if e["event"] == "finish")
                # finish 事件返回截断标题（不等待 LLM 后台任务）
                assert finish["data"]["title"] is not None
                # 标题生成已改为 asyncio.create_task 异步执行，需让出事件循环让其完成
                # 必须在 mock 作用域内 sleep，否则 patch 回收后后台任务调用真实 API
                await asyncio.sleep(0)
                # conv.title 由后台任务异步更新
                assert mocks['conv'].title == "测试问题标题生成"

    @pytest.mark.asyncio
    async def test_非首轮不更新标题(self):
        """非首轮（message_count > 2）finish 事件 title 应为 None"""
        from app.services.chat_service import chat

        db = AsyncMock()
        conv = MagicMock()
        conv.id = 100
        conv.uuid = _TEST_CONV_UUID
        conv.user_id = 1
        conv.message_count = 10
        conv.title = "旧标题"

        retrieval_output = _make_retrieval_output()

        with _mock_chat_pipeline(db, conv, retrieval_output=retrieval_output,
                                  llm_chunks=_make_llm_chunks(["追加回答"]),
                                  token_estimate=30,
                                  with_conversation=False, with_messages=False):
            response = await chat(
                db=db, user_id=1, role="user",
                conversation_id=_TEST_CONV_UUID, kb_id=_TEST_KB_UUID,
                question="追加问题", deep_thinking=False,
            )
            events = await _consume_sse(response)

        finish = next(e for e in events if e["event"] == "finish")
        assert finish["data"]["title"] is None
        assert conv.title == "旧标题"


class TestChatTokenUsage:
    """finish 事件 token_usage 数据"""

    @pytest.mark.asyncio
    async def test_token_usage字段完整(self):
        """finish 事件应包含 prompt/completion/total 三个字段"""
        from app.services.chat_service import chat

        db = AsyncMock()
        conv = MagicMock()
        conv.id = 50
        conv.user_id = 1
        conv.message_count = 0
        conv.title = "新对话"

        retrieval_output = _make_retrieval_output()

        with _mock_chat_pipeline(db, conv, retrieval_output=retrieval_output,
                                  llm_chunks=_make_llm_chunks(["回答内容"])):
            response = await chat(
                db=db, user_id=1, role="user",
                conversation_id=None, kb_id=_TEST_KB_UUID,
                question="测试问题", deep_thinking=False,
            )
            events = await _consume_sse(response)

        finish = next(e for e in events if e["event"] == "finish")
        usage = finish["data"]["token_usage"]
        assert "prompt" in usage
        assert "completion" in usage
        assert "total" in usage
        assert usage["prompt"] + usage["completion"] == usage["total"]


class TestChatKBNotFound:
    """KB 不存在 / 无权限"""

    @pytest.mark.asyncio
    async def test_KB不存在抛异常(self):
        """kb_id 对应的 KB 不存在时应抛 KnowledgeBaseNotFoundException"""
        from app.services.chat_service import chat

        db = AsyncMock()
        db.get = AsyncMock(return_value=None)  # KB 不存在

        with patch("app.core.uuid_helpers.resolve_uuid_to_id", new_callable=AsyncMock,
                    return_value=999):
            with pytest.raises(KnowledgeBaseNotFoundException):
                await chat(
                    db=db, user_id=1, role="user",
                    conversation_id=None, kb_id="ffffffff-ffff-4fff-ffff-ffffffffffff",
                    question="测试问题", deep_thinking=False,
                )

    @pytest.mark.asyncio
    async def test_非owner访问private_KB被拒(self):
        """非 owner 用户访问 private KB 应抛 PermissionDeniedException"""
        from app.services.chat_service import chat

        db = AsyncMock()
        kb = MagicMock()
        kb.id = 1
        kb.status = "active"
        kb.visibility = "private"
        kb.user_id = 1  # owner 是 user 1

        db.get = AsyncMock(return_value=kb)

        with patch("app.core.uuid_helpers.resolve_uuid_to_id", new_callable=AsyncMock,
                    return_value=1):
            with pytest.raises(PermissionDeniedException):
                await chat(
                    db=db, user_id=3, role="user",  # user 3 非 owner
                    conversation_id=None, kb_id=_TEST_KB_UUID,
                    question="测试问题", deep_thinking=False,
                )

    @pytest.mark.asyncio
    async def test_admin可访问private_KB(self):
        """admin 角色应可访问 private KB"""
        from app.services.chat_service import chat

        db = AsyncMock()
        conv = MagicMock()
        conv.id = 50
        conv.user_id = 1
        conv.message_count = 0
        conv.title = "新对话"

        with _mock_chat_pipeline(db, conv,
                                  llm_chunks=_make_llm_chunks(["回答"])) as mocks:
            # admin（user_id=2）访问 user 1 的 private KB
            response = await chat(
                db=db, user_id=2, role="admin",
                conversation_id=None, kb_id=_TEST_KB_UUID,
                question="测试问题", deep_thinking=False,
            )
            events = await _consume_sse(response)

        assert any(e["event"] == "meta" for e in events)


class TestChatConversationNotFound:
    """会话不存在 / 无权访问"""

    @pytest.mark.asyncio
    async def test_会话不存在(self):
        """conversation_id 对应的会话不存在时应抛异常"""
        from app.services.chat_service import chat

        db = AsyncMock()
        kb = MagicMock()
        kb.id = 1
        kb.status = "active"
        kb.visibility = "private"
        kb.user_id = 1

        def get_side_effect(model, pk):
            if model.__name__ == "KnowledgeBase":
                return kb
            if model.__name__ == "Conversation":
                return None  # 会话不存在
            return None

        db.get = AsyncMock(side_effect=get_side_effect)
        count_result = MagicMock()
        count_result.scalar.return_value = 1
        db.execute = AsyncMock(return_value=count_result)

        async def _mock_resolve(db, model, uuid_str):
            if uuid_str == _TEST_KB_UUID:
                return 1
            return 999  # conversation UUID → 999，db.get 返回 None

        with patch("app.core.uuid_helpers.resolve_uuid_to_id", new_callable=AsyncMock,
                    side_effect=_mock_resolve):
            with pytest.raises(ConversationNotFoundException):
                await chat(
                    db=db, user_id=1, role="user",
                    conversation_id="cccccccc-cccc-4ccc-cccc-cccccccccccc", kb_id=_TEST_KB_UUID,
                    question="测试问题", deep_thinking=False,
                )

    @pytest.mark.asyncio
    async def test_非owner访问他人会话(self):
        """非 owner 访问他人会话应抛 ConversationAccessDeniedException(E3002)"""
        from app.services.chat_service import chat

        db = AsyncMock()
        kb = MagicMock()
        kb.id = 1
        kb.status = "active"
        kb.visibility = "public"  # public KB，所有人可检索
        kb.user_id = 2

        conv = MagicMock()
        conv.id = 100
        conv.user_id = 2  # 会话属于 user 2

        def get_side_effect(model, pk):
            if model.__name__ == "KnowledgeBase":
                return kb
            if model.__name__ == "Conversation":
                return conv
            return None

        db.get = AsyncMock(side_effect=get_side_effect)
        count_result = MagicMock()
        count_result.scalar.return_value = 1
        db.execute = AsyncMock(return_value=count_result)

        async def _mock_resolve(db, model, uuid_str):
            if uuid_str == _TEST_KB_UUID:
                return 1
            if uuid_str == _TEST_CONV_UUID:
                return 100
            return None

        with patch("app.core.uuid_helpers.resolve_uuid_to_id", new_callable=AsyncMock,
                    side_effect=_mock_resolve):
            with pytest.raises(ConversationAccessDeniedException) as exc_info:
                await chat(
                    db=db, user_id=3, role="user",  # user 3 非 owner
                    conversation_id=_TEST_CONV_UUID, kb_id=_TEST_KB_UUID,
                    question="测试问题", deep_thinking=False,
                )
            assert exc_info.value.error_code == "E3002"


class TestChatSourcesSuppression:
    """U7.63b — LLM 声明"未找到相关信息"时抑制 sources 事件"""

    @pytest.mark.asyncio
    async def test_LLM输出未找到时sources不发送(self):
        """当 LLM 回答以"未找到相关信息"开头时，不发送 event: sources"""
        from app.services.chat_service import chat

        db = AsyncMock()
        conv = MagicMock()
        conv.id = 50
        conv.user_id = 1
        conv.message_count = 0

        retrieval_output = _make_retrieval_output()
        # LLM 回答以"知识库中未找到相关信息"开头（真阴性）
        llm_chunks = _make_llm_chunks([
            "知识库中未找到相关信息。",
            "当前文档库覆盖了企业知识库系统的技术架构",
        ])

        with _mock_chat_pipeline(db, conv, retrieval_output=retrieval_output,
                                  llm_chunks=llm_chunks):
            response = await chat(
                db=db, user_id=1, role="user",
                conversation_id=None, kb_id=_TEST_KB_UUID,
                question="广告投放主要在哪个平台", deep_thinking=False,
            )
            events = await _consume_sse(response)

        # 验证事件序列中不存在 sources 事件
        event_types = [e["event"] for e in events]
        assert "sources" not in event_types, (
            f"LLM 回答以'未找到相关信息'开头时应抑制 sources，但实际事件序列含 sources: {event_types}"
        )
        # 验证仍有 meta / message / finish
        assert "meta" in event_types
        assert "message" in event_types
        assert "finish" in event_types

    @pytest.mark.asyncio
    async def test_LLM部分回答后文提及未找到时sources仍发送(self):
        """当 LLM 给出有价值回答、仅后文提及'未找到'时，sources 应正常发送（防假阳性）"""
        from app.services.chat_service import chat

        db = AsyncMock()
        conv = MagicMock()
        conv.id = 50
        conv.user_id = 1
        conv.message_count = 0

        retrieval_output = _make_retrieval_output()
        # LLM 先给出有价值回答 + [来源] 引用，仅后文提及子问题未找到（假阳性场景）
        llm_chunks = _make_llm_chunks([
            "根据文档内容，员工请假需要提供医院证明[来源1]。",
            "但是，关于提前几天申请，文档中未找到相关信息。",
        ])

        with _mock_chat_pipeline(db, conv, retrieval_output=retrieval_output,
                                  llm_chunks=llm_chunks):
            response = await chat(
                db=db, user_id=1, role="user",
                conversation_id=None, kb_id=_TEST_KB_UUID,
                question="员工请病假需要提前几天申请", deep_thinking=False,
            )
            events = await _consume_sse(response)

        # 验证事件序列中存在 sources 事件（前缀匹配不应命中后文的"未找到"）
        event_types = [e["event"] for e in events]
        assert "sources" in event_types, (
            f"LLM 仅后文提及'未找到'时 sources 应保留，但实际事件序列不含 sources: {event_types}"
        )
        sources = next(e for e in events if e["event"] == "sources")
        assert len(sources["data"]["chunks"]) >= 1

    @pytest.mark.asyncio
    async def test_LLM全文含未找到且无引用标注时sources不发送(self):
        """当 LLM 回答含"未找到"且无任何 [来源N] 引用时，视为真阴性，抑制 sources（引用兜底）"""
        from app.services.chat_service import chat

        db = AsyncMock()
        conv = MagicMock()
        conv.id = 50
        conv.user_id = 1
        conv.message_count = 0

        retrieval_output = _make_retrieval_output()
        # LLM 先解释了一圈，最后才说"未找到"，且无 [来源N] 引用（Q29 风格但无引用）
        llm_chunks = _make_llm_chunks([
            "根据提供的文档内容，其中没有包含公司Wi-Fi密码的信息。",
            "所有文档均未提及相关密码配置。知识库中未找到相关信息。",
        ])

        with _mock_chat_pipeline(db, conv, retrieval_output=retrieval_output,
                                  llm_chunks=llm_chunks):
            response = await chat(
                db=db, user_id=1, role="user",
                conversation_id=None, kb_id=_TEST_KB_UUID,
                question="Wi-Fi密码是多少", deep_thinking=False,
            )
            events = await _consume_sse(response)

        # 无引用标注 + 全文含"未找到" → 引用兜底抑制 sources
        event_types = [e["event"] for e in events]
        assert "sources" not in event_types, (
            f"LLM 全文含'未找到'且无 [来源N] 引用时应抑制 sources，但实际含 sources: {event_types}"
        )

    @pytest.mark.asyncio
    async def test_LLM正常回答时sources正常发送(self):
        """当 LLM 正常回答且不含'未找到'关键词时，sources 应正常发送"""
        from app.services.chat_service import chat

        db = AsyncMock()
        conv = MagicMock()
        conv.id = 50
        conv.user_id = 1
        conv.message_count = 0

        retrieval_output = _make_retrieval_output()
        llm_chunks = _make_llm_chunks([
            "广告投放的主要平台是抖音[来源1]。",
            "抖音日活7亿，18-45岁用户占比七成。",
        ])

        with _mock_chat_pipeline(db, conv, retrieval_output=retrieval_output,
                                  llm_chunks=llm_chunks):
            response = await chat(
                db=db, user_id=1, role="user",
                conversation_id=None, kb_id=_TEST_KB_UUID,
                question="广告投放主要在哪个平台", deep_thinking=False,
            )
            events = await _consume_sse(response)

        # 验证事件序列中存在 sources 事件
        event_types = [e["event"] for e in events]
        assert "sources" in event_types, (
            f"LLM 正常回答时应发送 sources，但实际事件序列不含 sources: {event_types}"
        )
        sources = next(e for e in events if e["event"] == "sources")
        assert len(sources["data"]["chunks"]) >= 1

    @pytest.mark.asyncio
    async def test_LLM前缀含未找到但有引用标注时sources仍发送(self):
        """回归 VPN case：LLM 以"知识库中未找到"开头但给出 [来源N] 引用时，
        应视为部分答案而非真阴性，sources 必须保留。

        历史Bug：条件1（前缀匹配）不检查 _has_citation，导致
        "知识库中未找到关于VPN忘记密码的直接处理流程……通过OA系统重置密码[来源1]"
        被误判为真阴性，sources 事件被抑制。
        修复：两级匹配均须尊重 _has_citation，有引用 → 不抑制。
        """
        from app.services.chat_service import chat

        db = AsyncMock()
        conv = MagicMock()
        conv.id = 50
        conv.user_id = 1
        conv.message_count = 0

        retrieval_output = _make_retrieval_output()
        # LLM 以"未找到"开头，但后文给出有效引用（VPN case 典型模式）
        llm_chunks = _make_llm_chunks([
            "知识库中未找到关于VPN忘记密码的直接处理流程。",
            "但根据文档，可以通过OA系统重置密码[来源1]。",
        ])

        with _mock_chat_pipeline(db, conv, retrieval_output=retrieval_output,
                                  llm_chunks=llm_chunks):
            response = await chat(
                db=db, user_id=1, role="user",
                conversation_id=None, kb_id=_TEST_KB_UUID,
                question="VPN忘记密码怎么办", deep_thinking=False,
            )
            events = await _consume_sse(response)

        # 关键断言：有 [来源N] 引用时，即使前缀含"未找到"，sources 也必须发送
        event_types = [e["event"] for e in events]
        assert "sources" in event_types, (
            f"LLM 以'未找到'开头但有 [来源N] 引用时 sources 应保留，"
            f"但实际事件序列不含 sources: {event_types}"
        )
        sources = next(e for e in events if e["event"] == "sources")
        assert len(sources["data"]["chunks"]) >= 1


class TestExtractCitationIndices:
    """U7.63d — extract_citation_indices 单元测试（纯逻辑公开函数）"""

    def test_单个引用编号提取(self):
        from app.services.chat_service import extract_citation_indices
        result = extract_citation_indices("根据文档[来源1]，报销需要提交申请单。")
        assert result == {"1"}

    def test_多个引用编号提取(self):
        from app.services.chat_service import extract_citation_indices
        result = extract_citation_indices(
            "入职需要提交材料[来源1]，并参加培训[来源3]。"
            "系统权限由IT部门开通[来源1]。"
        )
        assert result == {"1", "3"}

    def test_无引用返回空集合(self):
        from app.services.chat_service import extract_citation_indices
        result = extract_citation_indices("根据文档内容，员工请假需要提前三天申请。")
        assert result == set()

    def test_空字符串返回空集合(self):
        from app.services.chat_service import extract_citation_indices
        result = extract_citation_indices("")
        assert result == set()

    def test_包含未找到关键词但有引用(self):
        """回归：后文含'未找到'但有 [来源N] 引用时，仍能提取引用编号"""
        from app.services.chat_service import extract_citation_indices
        result = extract_citation_indices(
            "根据文档，请假需要医院证明[来源1]。"
            "但是关于提前几天，文档中未找到相关信息。"
        )
        assert result == {"1"}


class TestChatCitationFiltering:
    """U7.63d — sources 引用过滤集成测试"""

    @pytest.mark.asyncio
    async def test_LLM仅引用部分chunk时sources仅含被引用chunk(self):
        """LLM 回答中仅引用 [来源1] 和 [来源3]，sources 应只含这 2 个 chunk"""
        from app.services.chat_service import chat

        db = AsyncMock()
        conv = MagicMock()
        conv.id = 50
        conv.user_id = 1
        conv.message_count = 0

        # 构造 4 个 chunk 的检索结果
        retrieval_output = RetrievalOutput(
            results=[
                RetrievalResult(doc_id=1, chunk_index=0,
                                content="入职需要提交身份证和学历证书", score=0.95, page=1),
                RetrievalResult(doc_id=2, chunk_index=0,
                                content="离职交接需要部门签字确认", score=0.82, page=3),
                RetrievalResult(doc_id=3, chunk_index=0,
                                content="系统权限由IT部门在入职当日开通", score=0.78, page=1),
                RetrievalResult(doc_id=4, chunk_index=0,
                                content="病假需提供二级甲等以上医院证明", score=0.71, page=5),
            ],
            total=4,
        )
        # LLM 只引用 [来源1] 和 [来源3]
        llm_chunks = _make_llm_chunks([
            "入职需要提交身份证和学历证书[来源1]。",
            "此外，系统权限由IT部门在入职当日开通[来源3]。",
        ])

        with _mock_chat_pipeline(db, conv, retrieval_output=retrieval_output,
                                  llm_chunks=llm_chunks):
            response = await chat(
                db=db, user_id=1, role="user",
                conversation_id=None, kb_id=_TEST_KB_UUID,
                question="入职第一天需要完成哪些手续", deep_thinking=False,
            )
            events = await _consume_sse(response)

        sources_events = [e for e in events if e["event"] == "sources"]
        assert len(sources_events) == 1, (
            f"应有 1 个 sources 事件，实际: {len(sources_events)}"
        )
        chunks = sources_events[0]["data"]["chunks"]
        assert len(chunks) == 2, (
            f"仅引用 2 个 chunk，sources 应含 2 个，实际: {len(chunks)}"
        )
        cited_indices = {c["chunk_index"] for c in chunks}
        assert cited_indices == {1, 3}, (
            f"sources chunk_index 应为 {{1, 3}}，实际: {cited_indices}"
        )

    @pytest.mark.asyncio
    async def test_LLM引用全部chunk时sources全量发送(self):
        """LLM 引用了全部 chunk，sources 应包含全部"""
        from app.services.chat_service import chat

        db = AsyncMock()
        conv = MagicMock()
        conv.id = 50
        conv.user_id = 1
        conv.message_count = 0

        retrieval_output = RetrievalOutput(
            results=[
                RetrievalResult(doc_id=1, chunk_index=0,
                                content="入职需要提交身份证", score=0.95, page=1),
                RetrievalResult(doc_id=2, chunk_index=0,
                                content="入职当天参加培训", score=0.88, page=2),
            ],
            total=2,
        )
        llm_chunks = _make_llm_chunks([
            "入职需要提交身份证[来源1]，",
            "并在当天参加培训[来源2]。",
        ])

        with _mock_chat_pipeline(db, conv, retrieval_output=retrieval_output,
                                  llm_chunks=llm_chunks):
            response = await chat(
                db=db, user_id=1, role="user",
                conversation_id=None, kb_id=_TEST_KB_UUID,
                question="入职第一天做什么", deep_thinking=False,
            )
            events = await _consume_sse(response)

        sources_events = [e for e in events if e["event"] == "sources"]
        assert len(sources_events) == 1
        chunks = sources_events[0]["data"]["chunks"]
        assert len(chunks) == 2, (
            f"LLM 引用了全部 2 个 chunk，sources 应含 2 个，实际: {len(chunks)}"
        )

    @pytest.mark.asyncio
    async def test_LLM零引用时sources仍发送_回退全量(self):
        """LLM 未引用 [来源N] 但有检索结果 → sources 回退发送全部 used_chunks。

        原行为（BUG）：LLM 没写 [来源N] → sources 不发送 → RAG 退化误判。
        修复后：LLM 没写 [来源N] 时回退发送全部 used_chunks，
        防止因 LLM 格式问题（DeepSeek/Qwen 常忘记写 [来源N]）导致 sources 消失。
        """
        from app.services.chat_service import chat

        db = AsyncMock()
        conv = MagicMock()
        conv.id = 50
        conv.user_id = 1
        conv.message_count = 0

        retrieval_output = RetrievalOutput(
            results=[
                RetrievalResult(doc_id=1, chunk_index=0,
                                content="检索到的相关内容", score=0.95, page=1),
            ],
            total=1,
        )
        # LLM 回答没有 [来源N] 引用，也未说"未找到"
        llm_chunks = _make_llm_chunks([
            "入职手续通常包括报到签约、领取物品、系统开通等步骤。",
        ])

        with _mock_chat_pipeline(db, conv, retrieval_output=retrieval_output,
                                  llm_chunks=llm_chunks):
            response = await chat(
                db=db, user_id=1, role="user",
                conversation_id=None, kb_id=_TEST_KB_UUID,
                question="入职第一天需要完成哪些手续", deep_thinking=False,
            )
            events = await _consume_sse(response)

        event_types = [e["event"] for e in events]
        assert "sources" in event_types, (
            f"LLM 未引用 [来源N] 时仍应发送 sources（回退到全部 used_chunks），"
            f"防止 LLM 格式问题导致 RAG 退化误判，实际: {event_types}"
        )
        sources = next(e for e in events if e["event"] == "sources")
        assert len(sources["data"]["chunks"]) == 1, (
            f"回退模式应发送全部 used_chunks (1 个)，实际: {len(sources['data']['chunks'])}"
        )

    @pytest.mark.asyncio
    async def test_LLM正确回答但未写来源N时sources仍发送_回退全量(self):
        """LLM 正确使用了检索内容但未写 [来源N] → sources 回退发送全部 used_chunks。

        验证脆弱耦合修复：sources 来自 used_chunks，而非 LLM 是否写 [来源N]。
        场景模拟 multi-005 T3/T5/T7：LLM 基于 chunk 给出了正确答案但忘记标注来源。
        """
        from app.services.chat_service import chat

        db = AsyncMock()
        conv = MagicMock()
        conv.id = 50
        conv.user_id = 1
        conv.message_count = 0

        # 模拟 multi-005 T5 场景：检索到病假证明相关内容
        retrieval_output = RetrievalOutput(
            results=[
                RetrievalResult(doc_id=1, chunk_index=0,
                                content="员工请病假需提供二级甲等以上医院出具的病假证明。",
                                score=0.95, page=5),
            ],
            total=1,
        )
        # LLM 正确回答了（体现了 retrieval 内容），但没写 [来源N]
        # 这在 DeepSeek/Qwen/Kimi 等模型非常常见
        llm_chunks = _make_llm_chunks([
            "根据公司病假制度，员工需要提供二级甲等以上医院证明。",
        ])

        with _mock_chat_pipeline(db, conv, retrieval_output=retrieval_output,
                                  llm_chunks=llm_chunks):
            response = await chat(
                db=db, user_id=1, role="user",
                conversation_id=None, kb_id=_TEST_KB_UUID,
                question="病假需要提供医院证明吗？", deep_thinking=False,
            )
            events = await _consume_sse(response)

        event_types = [e["event"] for e in events]
        assert "sources" in event_types, (
            f"LLM 未写 [来源N] 但检索有结果时，sources 仍应发送（回退到全部 used_chunks），"
            f"实际: {event_types}"
        )
        sources = next(e for e in events if e["event"] == "sources")
        assert len(sources["data"]["chunks"]) == 1, (
            f"回退模式应发送全部 used_chunks (1 个)，实际: {len(sources['data']['chunks'])}"
        )

    @pytest.mark.asyncio
    async def test_LLM失败时sources回退全量发送(self):
        """LLM 流式调用失败时，无 assistant_content，sources 回退到全量 chunk"""
        from app.services.chat_service import chat

        db = AsyncMock()
        conv = MagicMock()
        conv.id = 50
        conv.user_id = 1
        conv.message_count = 0

        retrieval_output = RetrievalOutput(
            results=[
                RetrievalResult(doc_id=1, chunk_index=0,
                                content="检索内容A", score=0.95, page=1),
                RetrievalResult(doc_id=2, chunk_index=0,
                                content="检索内容B", score=0.82, page=3),
            ],
            total=2,
        )

        with _mock_chat_pipeline(db, conv, retrieval_output=retrieval_output) as mocks:
            # 让 LLM 抛出异常
            mocks['llm'].return_value = _async_gen_error("LLM API 500 错误")
            response = await chat(
                db=db, user_id=1, role="user",
                conversation_id=None, kb_id=_TEST_KB_UUID,
                question="测试问题", deep_thinking=False,
            )
            events = await _consume_sse(response)

        # LLM 失败时仍应发送 sources（含全部 chunk）
        sources_events = [e for e in events if e["event"] == "sources"]
        assert len(sources_events) == 1, (
            f"LLM 失败后应回退发送全量 sources，实际 sources 事件数: {len(sources_events)}"
        )
        chunks = sources_events[0]["data"]["chunks"]
        assert len(chunks) == 2, (
            f"LLM 失败回退应发送全部 2 个 chunk，实际: {len(chunks)}"
        )


# ==================== 辅助 async generator ====================


async def _async_gen(items):
    """构造 async generator"""
    for item in items:
        yield item


async def _async_gen_error(msg):
    """构造抛异常的 async generator"""
    yield MagicMock(content="部分", reasoning_content="")
    raise Exception(msg)
