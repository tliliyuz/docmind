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

import json
from contextlib import ExitStack, contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import (
    ConversationAccessDeniedException,
    ConversationNotFoundException,
    KnowledgeBaseEmptyException,
    KnowledgeBaseNotFoundException,
    PermissionDeniedException,
    RetrievalServiceException,
)
from app.rag.retriever import RetrievalOutput, RetrievalResult


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

    db.execute = AsyncMock(side_effect=[count_result, names_result])
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()

    return kb, user_msg, assistant_msg


@contextmanager
def _mock_chat_pipeline(db, conv, *, retrieval_output=None, llm_chunks=None,
                         token_estimate=50, with_conversation=True, with_messages=True):
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

    _mock_db_with_conversation(db, conv)

    mock_conv = MagicMock()
    mock_conv.id = conv.id
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

        if with_conversation:
            mocks['conv_patch'] = stack.enter_context(
                patch("app.services.chat_service.Conversation", return_value=mock_conv))

        if with_messages:
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
            patch("app.services.chat_service.estimate_tokens", return_value=token_estimate))
        mocks['heartbeat'] = stack.enter_context(
            patch("app.services.chat_service.stream_with_heartbeat",
                  side_effect=lambda g, **kw: g))

        # 默认行为配置
        mocks['vec'].search = AsyncMock(return_value=retrieval_output)
        mocks['bm25'].search = AsyncMock(return_value=retrieval_output)
        mocks['reranker'].rerank = AsyncMock(return_value=retrieval_output)
        mocks['prompt'].return_value = MagicMock(
            system_prompt="系统提示", user_prompt="用户提示")
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
    """测试 _generate_title 标题生成"""

    def test_正常截取前12字(self):
        """截取问题前 12 字作为标题"""
        from app.services.chat_service import _generate_title
        title = _generate_title("这是一段超过十二个字符的用户问题内容")
        assert title == "这是一段超过十二个字符的"  # 18 字符取前 12

    def test_去除标点符号(self):
        """标题应去除标点符号"""
        from app.services.chat_service import _generate_title
        title = _generate_title("你好！请问这个问题怎么解决？")
        assert "！" not in title
        assert "？" not in title

    def test_全标点时返回新对话(self):
        """全标点内容去除后为空，应返回 '新对话'"""
        from app.services.chat_service import _generate_title
        title = _generate_title("！？。，、；：""''【】")
        assert title == "新对话"

    def test_去除首尾空格(self):
        """标题应去除首尾空格"""
        from app.services.chat_service import _generate_title
        title = _generate_title("  问题内容  ")
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
        llm_chunks = _make_llm_chunks(["这是", "LLM", "的回答"])

        with _mock_chat_pipeline(db, conv, retrieval_output=retrieval_output,
                                  llm_chunks=llm_chunks) as mocks:
            response = await chat(
                db=db, user_id=1, role="user",
                conversation_id=None, kb_id=1,
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
        assert meta["data"]["conversation_id"] == 50

        # 验证 message 事件内容
        msg_content = "".join(
            e["data"]["delta"] for e in events if e["event"] == "message"
        )
        assert msg_content == "这是LLM的回答"

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
                conversation_id=100, kb_id=1,
                question="追加问题", deep_thinking=False,
            )
            events = await _consume_sse(response)

        meta = next(e for e in events if e["event"] == "meta")
        assert meta["data"]["conversation_id"] == 100

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
            mocks['vec'].search = AsyncMock(
                side_effect=Exception("ChromaDB 连接失败")
            )

            with pytest.raises(RetrievalServiceException) as exc_info:
                await chat(
                    db=db, user_id=1, role="user",
                    conversation_id=None, kb_id=1,
                    question="测试问题", deep_thinking=False,
                )
            assert exc_info.value.error_code == "E4003"
            assert "ChromaDB" in str(exc_info.value.error_detail)


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
                conversation_id=None, kb_id=1,
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

        kb, _, _ = _mock_db_with_conversation(db, conv, doc_count=0)

        with patch("app.services.chat_service.stream_with_heartbeat", side_effect=lambda g, **kw: g):
            with pytest.raises(KnowledgeBaseEmptyException):
                await chat(
                    db=db, user_id=1, role="user",
                    conversation_id=None, kb_id=1,
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
                conversation_id=None, kb_id=1,
                question="测试问题", deep_thinking=False,
            )
            await _consume_sse(response)

        # 验证 db.add 被调用 3 次：Conversation + Message(user) + Message(assistant)
        add_calls = db.add.call_args_list
        assert len(add_calls) == 3

        # 第二次调用是 user message
        user_msg_arg = add_calls[1][0][0]
        assert user_msg_arg.role == "user"
        assert user_msg_arg.content == "测试问题"

        # 第三次调用是 assistant message
        assistant_msg_arg = add_calls[2][0][0]
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
        conv.user_id = 1
        conv.message_count = 10
        conv.title = "已有标题"

        retrieval_output = _make_retrieval_output()

        with _mock_chat_pipeline(db, conv, retrieval_output=retrieval_output,
                                  llm_chunks=_make_llm_chunks(["回答"]),
                                  token_estimate=30,
                                  with_conversation=False, with_messages=False):
            response = await chat(
                db=db, user_id=1, role="user",
                conversation_id=50, kb_id=1,
                question="测试问题", deep_thinking=False,
            )
            await _consume_sse(response)

        # message_count: 初始 10 → +1(user) → +1(assistant) = 12
        assert conv.message_count == 12


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
            response = await chat(
                db=db, user_id=1, role="user",
                conversation_id=None, kb_id=1,
                question="这是一个测试问题内容很长", deep_thinking=False,
            )
            events = await _consume_sse(response)

        finish = next(e for e in events if e["event"] == "finish")
        assert finish["data"]["title"] == "这是一个测试问题内容很长"[:12]
        assert mocks['conv'].title == finish["data"]["title"]

    @pytest.mark.asyncio
    async def test_非首轮不更新标题(self):
        """非首轮（message_count > 2）finish 事件 title 应为 None"""
        from app.services.chat_service import chat

        db = AsyncMock()
        conv = MagicMock()
        conv.id = 100
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
                conversation_id=100, kb_id=1,
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
                conversation_id=None, kb_id=1,
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

        with pytest.raises(KnowledgeBaseNotFoundException):
            await chat(
                db=db, user_id=1, role="user",
                conversation_id=None, kb_id=999,
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

        with pytest.raises(PermissionDeniedException):
            await chat(
                db=db, user_id=3, role="user",  # user 3 非 owner
                conversation_id=None, kb_id=1,
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
                conversation_id=None, kb_id=1,
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

        with pytest.raises(ConversationNotFoundException):
            await chat(
                db=db, user_id=1, role="user",
                conversation_id=999, kb_id=1,
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

        with pytest.raises(ConversationAccessDeniedException) as exc_info:
            await chat(
                db=db, user_id=3, role="user",  # user 3 非 owner
                conversation_id=100, kb_id=1,
                question="测试问题", deep_thinking=False,
            )
        assert exc_info.value.error_code == "E3002"


# ==================== 辅助 async generator ====================


async def _async_gen(items):
    """构造 async generator"""
    for item in items:
        yield item


async def _async_gen_error(msg):
    """构造抛异常的 async generator"""
    yield MagicMock(content="部分", reasoning_content="")
    raise Exception(msg)
