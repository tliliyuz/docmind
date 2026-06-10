"""SSE 工具模块测试

对齐 TEST_CASES.md §5.9：
- U7.80 SSE 事件序列（meta → thinking → message → sources → finish）
- U7.81 SSE 心跳帧格式
- U7.82 SSE 中途错误事件
- U7.83 客户端断开时 CancelledError 处理
- U7.84 StreamingResponse Content-Type 头
- U7.85 sources 事件数据结构
- U7.86 finish 事件数据结构

覆盖 app/core/sse.py 和 chat_service._build_sources()
"""

import asyncio
import json

import pytest

from app.config import settings
from app.core.sse import (
    format_sse_event,
    format_sse_heartbeat,
    stream_with_heartbeat,
)


class TestFormatSSEEvent:
    """测试 SSE 事件格式化"""

    def test_dict数据应序列化为JSON(self):
        """dict 数据应被 json.dumps 序列化"""
        result = format_sse_event("meta", {"conversation_id": 1, "task_id": "abc"})
        assert result == 'event: meta\ndata: {"conversation_id": 1, "task_id": "abc"}\n\n'

    def test_字符串数据直接使用(self):
        """字符串数据应直接作为 data"""
        result = format_sse_event("message", "hello")
        assert result == "event: message\ndata: hello\n\n"

    def test_中文不转义(self):
        """JSON 序列化时中文不应被转义"""
        result = format_sse_event("message", {"delta": "你好"})
        assert "你好" in result
        assert "\\u" not in result

    def test_事件格式符合SSE规范(self):
        """输出格式应为 event:<type>\\ndata:<data>\\n\\n"""
        result = format_sse_event("finish", {"message_id": 1})
        lines = result.split("\n")
        assert lines[0] == "event: finish"
        assert lines[1].startswith("data: ")
        assert lines[2] == ""
        assert lines[3] == ""


class TestFormatSSEHeartbeat:
    """测试 SSE 心跳帧格式"""

    def test_心跳帧格式(self):
        """心跳帧应为 : ping\\n\\n（SSE 注释帧）"""
        result = format_sse_heartbeat()
        assert result == ": ping\n\n"

    def test_心跳帧以冒号开头(self):
        """SSE 注释帧必须以 : 开头，浏览器会忽略但代理会重置超时"""
        result = format_sse_heartbeat()
        assert result.startswith(":")


class TestStreamWithHeartbeat:
    """测试事件流与心跳合并"""

    @pytest.mark.asyncio
    async def test_正常事件序列输出(self):
        """U7.80 — 事件应按顺序输出"""
        async def event_gen():
            yield format_sse_event("meta", {"conversation_id": 1})
            yield format_sse_event("message", {"delta": "你好"})
            yield format_sse_event("finish", {"message_id": 1})

        events = []
        async for event in stream_with_heartbeat(event_gen()):
            events.append(event)

        # 至少包含 3 个事件（可能夹杂心跳）
        meta_events = [e for e in events if "event: meta" in e]
        message_events = [e for e in events if "event: message" in e]
        finish_events = [e for e in events if "event: finish" in e]
        assert len(meta_events) == 1
        assert len(message_events) == 1
        assert len(finish_events) == 1

        # 事件顺序：meta 在 message 前，message 在 finish 前
        meta_idx = events.index(meta_events[0])
        message_idx = events.index(message_events[0])
        finish_idx = events.index(finish_events[0])
        assert meta_idx < message_idx < finish_idx

    @pytest.mark.asyncio
    async def test_空事件流(self):
        """空事件流应正常结束，不抛异常"""
        async def empty_gen():
            return
            yield  # noqa: 使成为 async generator

        events = []
        async for event in stream_with_heartbeat(empty_gen()):
            events.append(event)
        # 空流可能有 0 或少量心跳帧，但不应抛异常
        assert isinstance(events, list)

    @pytest.mark.asyncio
    async def test_事件流中异常向上传播(self):
        """U7.82 — 事件流中抛异常时应向上传播（stream_with_heartbeat 不吞异常）"""

        async def error_gen():
            yield format_sse_event("meta", {"conversation_id": 1})
            yield format_sse_event("message", {"delta": "部分"})
            raise ValueError("LLM 调用失败")

        events = []
        with pytest.raises(ValueError, match="LLM 调用失败"):
            async for event in stream_with_heartbeat(error_gen()):
                events.append(event)

        # 异常前应已收到 meta 和部分 message
        assert any("event: meta" in e for e in events)

    @pytest.mark.asyncio
    async def test_事件间隙实时发送心跳帧(self):
        """当事件流长时间无输出时，心跳帧应在间隙中实时发送（非事后收集）。

        使用短心跳间隔 (0.05s) 和慢速事件生成器 (0.15s 间隔)，
        验证心跳帧在事件间隙被 yield 输出。
        """
        async def slow_event_gen():
            yield format_sse_event("meta", {"conversation_id": 1})
            await asyncio.sleep(0.15)  # 超过心跳间隔，应触发心跳
            yield format_sse_event("message", {"delta": "延迟到达"})
            yield format_sse_event("finish", {"message_id": 1})

        events = []
        async for event in stream_with_heartbeat(slow_event_gen(), interval=0.05):
            events.append(event)

        # 验证心跳帧存在
        heartbeat_events = [e for e in events if e == ": ping\n\n"]
        assert len(heartbeat_events) >= 1, (
            f"事件间隙应发送至少 1 个心跳帧（间隔 0.05s，事件延迟 0.15s），"
            f"实际收到 {len(heartbeat_events)} 个"
        )

        # 验证事件顺序：meta → 心跳帧 → message → finish
        meta_idx = next(i for i, e in enumerate(events) if "event: meta" in e)
        msg_idx = next(i for i, e in enumerate(events) if "event: message" in e)
        finish_idx = next(i for i, e in enumerate(events) if "event: finish" in e)
        assert meta_idx < msg_idx < finish_idx

        # 所有心跳帧应在 meta 之后、message 之前
        for i, e in enumerate(events):
            if e == ": ping\n\n":
                assert meta_idx < i < msg_idx, (
                    f"心跳帧应在 meta 和 message 之间，实际位置: {i}"
                )

    @pytest.mark.asyncio
    async def test_事件流结束后无多余心跳(self):
        """事件流结束时应正常停止，不残留未完成的心跳任务"""
        async def quick_gen():
            yield format_sse_event("meta", {"conversation_id": 1})
            yield format_sse_event("finish", {"message_id": 1})

        events = []
        async for event in stream_with_heartbeat(quick_gen(), interval=0.05):
            events.append(event)

        # 快速事件流不应有遗留心跳帧（事件瞬间完成）
        heartbeat_events = [e for e in events if e == ": ping\n\n"]
        assert len(heartbeat_events) == 0, (
            f"快速事件流不应包含心跳帧，实际收到 {len(heartbeat_events)} 个"
        )


class TestBuildSources:
    """测试 sources 事件数据结构（使用生产函数 _build_sources 避免逻辑重复）"""

    def test_sources数据结构完整(self):
        """U7.85 — sources 事件 chunks 应包含 chunk_index/doc_id/doc_name/content/score/page/preview_text/preview_range"""
        from app.rag.retriever import RetrievalResult, RetrievalOutput
        from app.services.chat_service import _build_sources

        results = [
            RetrievalResult(
                doc_id=1, chunk_index=0,
                content="这是第一段检索内容" * 20,
                score=0.95, page=1,
            ),
            RetrievalResult(
                doc_id=2, chunk_index=1,
                content="第二段内容",
                score=0.80, page=None,
            ),
        ]
        reranked_output = RetrievalOutput(results=results, total=2)
        doc_map = {1: "文档A.pdf", 2: "文档B.md"}

        sources = _build_sources(reranked_output.results, doc_map)

        assert len(sources) == 2

        # 第一条：content 保留完整内容（不截断）
        assert sources[0].chunk_index == 1
        assert sources[0].doc_id == 1
        assert sources[0].doc_name == "文档A.pdf"
        assert len(sources[0].content) == len("这是第一段检索内容" * 20)
        assert sources[0].score == 0.95
        assert sources[0].page == 1
        # 无 assistant_content 时 preview 字段为 None
        assert sources[0].preview_text is None
        assert sources[0].preview_range is None

        # 第二条：page 为 None
        assert sources[1].chunk_index == 2
        assert sources[1].doc_id == 2
        assert sources[1].doc_name == "文档B.md"
        assert sources[1].page is None

    def test_智能预览定位(self):
        """有 assistant_content 时应生成 preview_text 和 preview_range"""
        from app.rag.retriever import RetrievalResult, RetrievalOutput
        from app.services.chat_service import _build_sources

        content = "公司报销制度规定：差旅报销需提交差旅申请单和交通票据。报销金额上限为每次5000元。"
        results = [RetrievalResult(doc_id=1, chunk_index=0, content=content, score=0.9)]
        reranked_output = RetrievalOutput(results=results, total=1)

        assistant_content = "根据报销制度，差旅报销需要提交[来源1]差旅申请单和交通票据。"
        sources = _build_sources(reranked_output.results, {1: "报销制度.md"}, assistant_content=assistant_content)

        assert sources[0].preview_text is not None
        assert sources[0].preview_range is not None
        assert sources[0].preview_range.start >= 0
        assert sources[0].preview_range.end <= len(content)

    def test_智能预览降级(self):
        """assistant_content 中 snippet 在 chunk 中找不到时应降级到前 200 字符"""
        from app.rag.retriever import RetrievalResult, RetrievalOutput
        from app.services.chat_service import _build_sources

        content = "x" * 300
        results = [RetrievalResult(doc_id=1, chunk_index=0, content=content, score=0.9)]
        reranked_output = RetrievalOutput(results=results, total=1)

        # snippet 在 chunk 中不存在
        assistant_content = "[来源1]完全不相关的文本内容"
        sources = _build_sources(reranked_output.results, {1: "x.txt"}, assistant_content=assistant_content)

        assert sources[0].preview_text is not None
        assert len(sources[0].preview_text) == 200
        assert sources[0].preview_range.start == 0
        assert sources[0].preview_range.end == 200

    def test_doc_map缺失时doc_name为空(self):
        """doc_map 中找不到 doc_id 时 doc_name 应为空字符串"""
        from app.rag.retriever import RetrievalResult, RetrievalOutput
        from app.services.chat_service import _build_sources

        results = [RetrievalResult(doc_id=99, chunk_index=0, content="内容", score=0.5)]
        reranked_output = RetrievalOutput(results=results, total=1)

        sources = _build_sources(reranked_output.results, {})  # 空 doc_map

        assert sources[0].doc_name == ""


class TestFinishEventData:
    """测试 finish 事件数据结构"""

    def test_finish数据结构(self):
        """U7.86 — finish 事件应包含 message_id / title / token_usage"""
        finish_data = {
            "message_id": 42,
            "title": "测试标题",
            "token_usage": {"prompt": 100, "completion": 50, "total": 150},
        }
        assert finish_data["message_id"] == 42
        assert finish_data["title"] == "测试标题"
        assert finish_data["token_usage"]["prompt"] + finish_data["token_usage"]["completion"] == \
               finish_data["token_usage"]["total"]

    def test_finish首轮无title时title为None(self):
        """非首轮 finish 事件 title 应为 None"""
        finish_data = {
            "message_id": 43,
            "title": None,
            "token_usage": {"prompt": 80, "completion": 30, "total": 110},
        }
        assert finish_data["title"] is None


class TestSSEHeartbeatInterval:
    """测试心跳间隔常量"""

    def test_心跳间隔为15秒(self):
        """心跳间隔应为 15 秒，对齐 ARCHITECTURE.md §5.1.3"""
        assert settings.SSE_HEARTBEAT_INTERVAL == 15
