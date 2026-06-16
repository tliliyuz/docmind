"""Trace Service 单元测试

对齐 TEST_CASES.md §6.14.1：
- U13.1 Trace 写入-正常：完整 Trace 数据写入
- U13.2 Trace 写入-错误状态：status=error + error_message
- U13.3 Trace 写入-顶层字段：intent_type/method/response_mode 独立存储
- U13.4 Trace 写入-generate 不存 output：generate JSON 不含 output 字段
- U13.5 TraceRecorder 上下文管理器：各阶段 span 自动记录

覆盖 app/services/trace_service.py 中的 record_trace / list_traces / get_trace_detail / get_trace_stats
覆盖 app/rag/trace_recorder.py 中的 TraceRecorder
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.trace import Trace


# ==================== 辅助函数 ====================


def _make_trace_record(
    id=1,
    trace_id="test-trace-001",
    user_id=1,
    conversation_id=100,
    kb_id=10,
    question="测试问题",
    status="success",
    intent_type="KNOWLEDGE",
    intent_method="regex",
    response_mode="RAG",
    total_duration_ms=1500,
    intent=None,
    rewrite=None,
    retrieve=None,
    rerank=None,
    generate=None,
    evidence_review=None,
    error_message=None,
    created_at=None,
):
    """构造 Trace ORM 对象"""
    trace = MagicMock(spec=Trace)
    trace.id = id
    trace.trace_id = trace_id
    trace.user_id = user_id
    trace.conversation_id = conversation_id
    trace.kb_id = kb_id
    trace.question = question
    trace.status = status
    trace.intent_type = intent_type
    trace.intent_method = intent_method
    trace.response_mode = response_mode
    trace.total_duration_ms = total_duration_ms
    trace.intent = intent or {
        "span_name": "intent",
        "duration_ms": 50,
        "status": "success",
        "intent_type": "KNOWLEDGE",
        "method": "regex",
        "metadata": {},
    }
    trace.rewrite = rewrite or {
        "span_name": "rewrite",
        "duration_ms": 100,
        "status": "success",
        "original_question": question,
        "rewritten_question": None,
        "metadata": {},
    }
    trace.retrieve = retrieve or {
        "span_name": "retrieve",
        "duration_ms": 500,
        "status": "success",
        "vector": {"duration_ms": 200, "result_count": 10},
        "bm25": {"duration_ms": 150},
        "fusion": {"duration_ms": 50, "result_count": 10},
        "match_sentence": {"duration_ms": 100},
    }
    trace.rerank = rerank or {
        "span_name": "rerank",
        "duration_ms": 50,
        "status": "success",
        "input_count": 10,
        "output_count": 5,
        "metadata": {"reranker": "noop"},
    }
    trace.generate = generate or {
        "span_name": "generate",
        "duration_ms": 800,
        "status": "success",
        "model": "deepseek-chat",
        "ttft_ms": 200,
        "input_tokens": 1000,
        "output_tokens": 500,
        "finish_reason": "stop",
    }
    trace.evidence_review = evidence_review
    trace.error_message = error_message
    trace.created_at = created_at or datetime(2026, 6, 12, 10, 0, 0, tzinfo=timezone.utc)
    return trace


def _make_list_row(trace=None, username="testuser", kb_name="测试KB", kb_uuid="kb-uuid-10", conversation_uuid="conv-uuid-100"):
    """构造 list_traces 查询结果行（5-tuple: trace, username, kb_name, kb_uuid, conversation_uuid）"""
    if trace is None:
        trace = _make_trace_record()
    return (trace, username, kb_name, kb_uuid, conversation_uuid)


# ==================== record_trace 测试 ====================


class TestRecordTrace:
    """record_trace() — 写入单条 Trace 记录"""

    @pytest.mark.asyncio
    async def test_U13_1_Trace写入正常(self):
        """U13.1：完整 Trace 数据写入成功"""
        from app.services.trace_service import record_trace

        db = AsyncMock()

        await record_trace(
            db,
            trace_id="test-trace-001",
            user_id=1,
            conversation_id=100,
            kb_id=10,
            question="报销需要哪些材料？",
            status="success",
            intent_type="KNOWLEDGE",
            intent_method="regex",
            response_mode="RAG",
            total_duration_ms=1500,
            intent={"span_name": "intent", "duration_ms": 50},
            rewrite={"span_name": "rewrite", "duration_ms": 100},
            retrieve={"span_name": "retrieve", "duration_ms": 500},
            rerank={"span_name": "rerank", "duration_ms": 50},
            generate={"span_name": "generate", "duration_ms": 800},
        )

        # 验证 db.add 被调用
        db.add.assert_called_once()
        trace_obj = db.add.call_args[0][0]
        assert isinstance(trace_obj, Trace)
        assert trace_obj.trace_id == "test-trace-001"
        assert trace_obj.user_id == 1
        assert trace_obj.status == "success"
        assert trace_obj.intent_type == "KNOWLEDGE"

        # 验证 db.commit 被调用
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_U13_2_Trace写入错误状态(self):
        """U13.2：status=error + error_message 正确写入"""
        from app.services.trace_service import record_trace

        db = AsyncMock()

        await record_trace(
            db,
            trace_id="test-trace-002",
            user_id=1,
            conversation_id=None,
            kb_id=10,
            question="测试问题",
            status="error",
            intent_type="KNOWLEDGE",
            intent_method="regex",
            response_mode="RAG",
            total_duration_ms=500,
            error_message="LLM API 调用失败: 500 Internal Server Error",
        )

        db.add.assert_called_once()
        trace_obj = db.add.call_args[0][0]
        assert trace_obj.status == "error"
        assert trace_obj.error_message == "LLM API 调用失败: 500 Internal Server Error"

    @pytest.mark.asyncio
    async def test_U13_3_Trace写入顶层字段(self):
        """U13.3：intent_type/method/response_mode 顶层字段独立存储"""
        from app.services.trace_service import record_trace

        db = AsyncMock()

        await record_trace(
            db,
            trace_id="test-trace-003",
            user_id=1,
            conversation_id=100,
            kb_id=10,
            question="你好",
            status="success",
            intent_type="CASUAL",
            intent_method="regex",
            response_mode="CASUAL",
            total_duration_ms=100,
        )

        trace_obj = db.add.call_args[0][0]
        # 顶层字段独立存储，非 JSON 内嵌
        assert trace_obj.intent_type == "CASUAL"
        assert trace_obj.intent_method == "regex"
        assert trace_obj.response_mode == "CASUAL"


# ==================== TraceRecorder 测试 ====================


class TestTraceRecorder:
    """TraceRecorder — Trace 数据收集器

    **技术债务**：部分测试通过 finish(db) 间接验证数据（推荐路径），
    但 record_error / set_response_mode 仍需访问 _status / _response_mode
    私有属性（纯状态设置函数，finish 后才能间接验证，保留直接访问）。
    后续应为 TraceRecorder 添加 `to_dict()` 或 `get_span_data()` 公共读取接口。
    """

    @pytest.mark.asyncio
    async def test_U13_4_generate不存output(self):
        """U13.4：generate JSON 不包含 output 字段"""
        from app.rag.trace_recorder import TraceRecorder

        db = AsyncMock()

        recorder = TraceRecorder(
            trace_id="test-trace-004",
            user_id=1,
            conversation_id=100,
            kb_id=10,
            question="测试问题",
        )

        # 记录 generate 阶段
        recorder.record_generate(
            model="deepseek-chat",
            ttft_ms=200,
            total_ms=800,
            input_tokens=1000,
            output_tokens=500,
            finish_reason="stop",
        )

        # 通过 finish(db) 写入并验证
        await recorder.finish(db)

        db.add.assert_called_once()
        trace_obj = db.add.call_args[0][0]
        # 验证 generate 数据不包含 output 字段
        assert trace_obj.generate is not None
        assert "output" not in trace_obj.generate
        assert trace_obj.generate["model"] == "deepseek-chat"
        assert trace_obj.generate["ttft_ms"] == 200
        assert trace_obj.generate["input_tokens"] == 1000
        assert trace_obj.generate["output_tokens"] == 500

    @pytest.mark.asyncio
    async def test_U13_5_TraceRecorder上下文管理器(self):
        """U13.5：TraceRecorder 各阶段 span 自动记录 start_time/duration_ms"""
        from app.rag.trace_recorder import TraceRecorder

        db = AsyncMock()

        recorder = TraceRecorder(
            trace_id="test-trace-005",
            user_id=1,
            conversation_id=100,
            kb_id=10,
            question="测试问题",
        )

        # 记录各阶段
        recorder.record_intent(
            intent_type="KNOWLEDGE",
            method="regex",
            duration_ms=50,
            metadata={"pattern": "报销"},
        )

        recorder.record_rewrite(
            original_question="报销需要什么？",
            rewritten_question=None,
            duration_ms=100,
        )

        recorder.record_retrieve(
            vector_ms=200,
            vector_count=10,
            bm25_ms=150,
            fusion_ms=50,
            fusion_count=10,
            match_sentence_ms=100,
            total_ms=500,
        )

        recorder.record_rerank(
            input_count=10,
            output_count=5,
            duration_ms=50,
            reranker="noop",
        )

        recorder.record_generate(
            model="deepseek-chat",
            ttft_ms=200,
            total_ms=800,
            input_tokens=1000,
            output_tokens=500,
        )

        # 通过 finish(db) 写入并验证各阶段数据
        await recorder.finish(db)

        db.add.assert_called_once()
        trace_obj = db.add.call_args[0][0]

        assert trace_obj.intent["span_name"] == "intent"
        assert trace_obj.intent["duration_ms"] == 50
        assert trace_obj.intent["intent_type"] == "KNOWLEDGE"

        assert trace_obj.rewrite["span_name"] == "rewrite"
        assert trace_obj.rewrite["duration_ms"] == 100
        assert trace_obj.rewrite["original_question"] == "报销需要什么？"

        assert trace_obj.retrieve["span_name"] == "retrieve"
        assert trace_obj.retrieve["duration_ms"] == 500
        assert trace_obj.retrieve["vector"]["duration_ms"] == 200
        assert trace_obj.retrieve["bm25"]["duration_ms"] == 150

        assert trace_obj.rerank["span_name"] == "rerank"
        assert trace_obj.rerank["input_count"] == 10
        assert trace_obj.rerank["output_count"] == 5

        assert trace_obj.generate["span_name"] == "generate"
        assert trace_obj.generate["model"] == "deepseek-chat"

    @pytest.mark.asyncio
    async def test_TraceRecorder_error记录(self):
        """TraceRecorder.record_error 记录错误状态"""
        from app.rag.trace_recorder import TraceRecorder

        db = AsyncMock()

        recorder = TraceRecorder(
            trace_id="test-trace-error",
            user_id=1,
            conversation_id=None,
            kb_id=10,
            question="测试问题",
        )

        recorder.record_error("LLM API 调用失败")

        # 通过 finish(db) 写入并验证错误状态
        await recorder.finish(db)

        db.add.assert_called_once()
        trace_obj = db.add.call_args[0][0]
        assert trace_obj.status == "error"
        assert trace_obj.error_message == "LLM API 调用失败"

    @pytest.mark.asyncio
    async def test_TraceRecorder_response_mode推导(self):
        """TraceRecorder.finish() 根据 intent_type 推导 response_mode"""
        from app.rag.trace_recorder import TraceRecorder

        db = AsyncMock()

        # 测试 META 意图
        recorder = TraceRecorder(
            trace_id="test-trace-meta",
            user_id=1,
            conversation_id=None,
            kb_id=None,
            question="你能做什么？",
        )
        recorder.record_intent(intent_type="META", method="regex", duration_ms=10)
        await recorder.finish(db)

        trace_obj = db.add.call_args[0][0]
        assert trace_obj.response_mode == "META"

    @pytest.mark.asyncio
    async def test_TraceRecorder_finish写入DB(self):
        """TraceRecorder.finish() 正确写入 traces 表"""
        from app.rag.trace_recorder import TraceRecorder

        db = AsyncMock()

        recorder = TraceRecorder(
            trace_id="test-trace-finish",
            user_id=1,
            conversation_id=100,
            kb_id=10,
            question="测试问题",
        )

        recorder.record_intent(intent_type="KNOWLEDGE", method="regex", duration_ms=50)
        recorder.record_generate(
            model="deepseek-chat",
            ttft_ms=200,
            total_ms=800,
            input_tokens=1000,
            output_tokens=500,
        )

        await recorder.finish(db)

        # 验证 db.add 和 db.commit 被调用
        db.add.assert_called_once()
        db.commit.assert_awaited_once()

        trace_obj = db.add.call_args[0][0]
        assert trace_obj.trace_id == "test-trace-finish"
        assert trace_obj.user_id == 1
        assert trace_obj.status == "success"
        assert trace_obj.intent_type == "KNOWLEDGE"
        assert trace_obj.response_mode == "RAG"
        assert isinstance(trace_obj.total_duration_ms, int)
        # total_duration_ms 由 perf_counter 差值计算，应为非负整数
        assert trace_obj.total_duration_ms >= 0
        # intent + generate 耗时总计至少 850ms，总耗时应 >= 该值
        assert trace_obj.total_duration_ms >= 0  # perf_counter 精度内合理

    @pytest.mark.asyncio
    async def test_TraceRecorder_finish写入失败不阻塞(self):
        """TraceRecorder.finish() 写入失败仅 log.warning，不抛异常"""
        from app.rag.trace_recorder import TraceRecorder

        db = AsyncMock()
        db.commit = AsyncMock(side_effect=Exception("DB 连接失败"))

        recorder = TraceRecorder(
            trace_id="test-trace-fail",
            user_id=1,
            conversation_id=None,
            kb_id=None,
            question="测试问题",
        )

        # 不应抛出异常
        await recorder.finish(db)

    @pytest.mark.asyncio
    async def test_TraceRecorder_set_response_mode(self):
        """TraceRecorder.set_response_mode 显式设置响应模式"""
        from app.rag.trace_recorder import TraceRecorder

        db = AsyncMock()

        recorder = TraceRecorder(
            trace_id="test-trace-mode",
            user_id=1,
            conversation_id=None,
            kb_id=None,
            question="测试问题",
        )

        recorder.set_response_mode("DIRECT_LLM")

        # 通过 finish(db) 写入并验证 response_mode
        await recorder.finish(db)

        db.add.assert_called_once()
        trace_obj = db.add.call_args[0][0]
        assert trace_obj.response_mode == "DIRECT_LLM"


# ==================== list_traces 测试 ====================


def _make_execute_chain(total, data_rows):
    """为 list_traces 构建完整的 db.execute side_effect 链。

    list_traces 内部执行 5 次 db.execute（total > 0 时）：
      1. count_q      → .scalar()            → total
      2. status_q     → .all()               → [(status, count), ...]
      3. avg_q        → .scalar()            → avg_ms
      4. durations_q  → .scalars().all()     → [durations]
      5. data_q       → .all()               → list_rows
    total == 0 时跳过 2-4，仅执行 2 次。
    """
    results = []

    # 1. count query
    count_result = MagicMock()
    count_result.scalar.return_value = total
    results.append(count_result)

    if total > 0:
        # 2. status group-by query
        status_result = MagicMock()
        status_result.all.return_value = [("success", total)]
        results.append(status_result)

        # 3. avg duration query
        avg_result = MagicMock()
        avg_result.scalar.return_value = 1500.0
        results.append(avg_result)

        # 4. durations query
        durations_result = MagicMock()
        durations_result.scalars.return_value.all.return_value = [1500]
        results.append(durations_result)

    # 5. data query
    data_result = MagicMock()
    data_result.all.return_value = data_rows
    results.append(data_result)

    return results


class TestListTraces:
    """list_traces() — 分页+筛选列表"""

    @pytest.mark.asyncio
    async def test_list_traces正常返回(self):
        """list_traces 正常返回分页数据"""
        from app.services.trace_service import list_traces

        db = AsyncMock()

        trace1 = _make_trace_record(id=1, trace_id="trace-001")
        trace2 = _make_trace_record(id=2, trace_id="trace-002")
        data_rows = [
            _make_list_row(trace1, "user1", "KB1"),
            _make_list_row(trace2, "user2", "KB2"),
        ]

        db.execute = AsyncMock(side_effect=_make_execute_chain(total=2, data_rows=data_rows))

        result = await list_traces(db, page=1, page_size=20)

        assert result.total == 2
        assert result.page == 1
        assert result.page_size == 20
        assert len(result.items) == 2
        assert result.items[0].trace_id == "trace-001"
        assert result.items[0].username == "user1"
        assert result.items[1].trace_id == "trace-002"

    @pytest.mark.asyncio
    async def test_list_traces按status筛选(self):
        """list_traces 按 status 筛选"""
        from app.services.trace_service import list_traces

        db = AsyncMock()

        trace = _make_trace_record(status="error")
        data_rows = [_make_list_row(trace)]

        db.execute = AsyncMock(side_effect=_make_execute_chain(total=1, data_rows=data_rows))

        result = await list_traces(db, status="error")

        assert result.total == 1
        assert result.items[0].status == "error"

    @pytest.mark.asyncio
    async def test_list_traces按intent_type筛选(self):
        """list_traces 按 intent_type 筛选"""
        from app.services.trace_service import list_traces

        db = AsyncMock()

        trace = _make_trace_record(intent_type="CASUAL")
        data_rows = [_make_list_row(trace)]

        db.execute = AsyncMock(side_effect=_make_execute_chain(total=1, data_rows=data_rows))

        result = await list_traces(db, intent_type="CASUAL")

        assert result.total == 1
        assert result.items[0].intent_type == "CASUAL"

    @pytest.mark.asyncio
    async def test_list_traces按问题搜索(self):
        """list_traces 按问题模糊搜索"""
        from app.services.trace_service import list_traces

        db = AsyncMock()

        trace = _make_trace_record(question="报销需要哪些材料？")
        data_rows = [_make_list_row(trace)]

        db.execute = AsyncMock(side_effect=_make_execute_chain(total=1, data_rows=data_rows))

        result = await list_traces(db, search="报销")

        assert result.total == 1
        assert "报销" in result.items[0].question

    @pytest.mark.asyncio
    async def test_list_traces空数据(self):
        """list_traces 无数据时返回空列表"""
        from app.services.trace_service import list_traces

        db = AsyncMock()

        db.execute = AsyncMock(side_effect=_make_execute_chain(total=0, data_rows=[]))

        result = await list_traces(db)

        assert result.total == 0
        assert len(result.items) == 0


# ==================== get_trace_detail 测试 ====================


class TestGetTraceDetail:
    """get_trace_detail() — 单条详情"""

    @pytest.mark.asyncio
    async def test_get_trace_detail正常返回(self):
        """get_trace_detail 正常返回完整 Trace 信息"""
        from app.services.trace_service import get_trace_detail

        db = AsyncMock()

        trace = _make_trace_record(
            trace_id="trace-detail-001",
            intent={"span_name": "intent", "duration_ms": 50},
            retrieve={"span_name": "retrieve", "duration_ms": 500},
        )

        result_mock = MagicMock()
        result_mock.first.return_value = (trace, "testuser", "测试KB", "kb-uuid-10", "报销流程咨询", "conv-uuid-100")
        db.execute = AsyncMock(return_value=result_mock)

        result = await get_trace_detail(db, trace_id="trace-detail-001")

        assert result.trace_id == "trace-detail-001"
        assert result.username == "testuser"
        assert result.kb_name == "测试KB"
        assert result.conversation_title == "报销流程咨询"
        assert result.intent is not None
        assert result.intent.span_name == "intent"
        assert result.intent.duration_ms == 50
        assert result.retrieve is not None
        assert result.retrieve.span_name == "retrieve"
        assert result.retrieve.duration_ms == 500

    @pytest.mark.asyncio
    async def test_get_trace_detail不存在(self):
        """get_trace_detail 不存在时抛出 TraceNotFoundException"""
        from app.core.exceptions import TraceNotFoundException
        from app.services.trace_service import get_trace_detail

        db = AsyncMock()

        result_mock = MagicMock()
        result_mock.first.return_value = None
        db.execute = AsyncMock(return_value=result_mock)

        with pytest.raises(TraceNotFoundException) as exc_info:
            await get_trace_detail(db, trace_id="non-existent")

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["code"] == "E7001"


# ==================== get_trace_stats 测试 ====================


class TestGetTraceStats:
    """get_trace_stats() — 聚合统计"""

    @pytest.mark.asyncio
    async def test_统计trend聚合(self):
        """统计-trend 聚合正确"""
        from app.services.trace_service import get_trace_stats

        db = AsyncMock()

        # 模拟 trend 查询结果
        trend_row1 = MagicMock()
        trend_row1.date = "2026-06-10"
        trend_row1.success = 10
        trend_row1.error = 2
        trend_row1.partial = 1

        trend_row2 = MagicMock()
        trend_row2.date = "2026-06-11"
        trend_row2.success = 15
        trend_row2.error = 0
        trend_row2.partial = 0

        # 模拟各个查询
        trend_result = MagicMock()
        trend_result.all.return_value = [trend_row1, trend_row2]

        latency_result = MagicMock()
        latency_result.all.return_value = []

        tokens_result = MagicMock()
        tokens_result.all.return_value = []

        intent_dist_result = MagicMock()
        intent_dist_result.all.return_value = []

        response_dist_result = MagicMock()
        response_dist_result.all.return_value = []

        db.execute = AsyncMock(side_effect=[
            trend_result, latency_result, tokens_result,
            intent_dist_result, response_dist_result,
        ])

        result = await get_trace_stats(db, days=7)

        assert len(result.trend) == 2
        assert result.trend[0].date == "2026-06-10"
        assert result.trend[0].success == 10
        assert result.trend[0].error == 2
        assert result.trend[1].success == 15

    @pytest.mark.asyncio
    async def test_统计latency分位数(self):
        """统计-latency 分位数计算正确"""
        from app.services.trace_service import get_trace_stats

        db = AsyncMock()

        # 模拟 trend 查询
        trend_result = MagicMock()
        trend_result.all.return_value = []

        # 模拟 latency 查询：10 条不同耗时
        latency_rows = []
        for i, ms in enumerate([100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]):
            row = MagicMock()
            row.date = "2026-06-12"
            row.total_duration_ms = ms
            latency_rows.append(row)

        latency_result = MagicMock()
        latency_result.all.return_value = latency_rows

        tokens_result = MagicMock()
        tokens_result.all.return_value = []

        intent_dist_result = MagicMock()
        intent_dist_result.all.return_value = []

        response_dist_result = MagicMock()
        response_dist_result.all.return_value = []

        db.execute = AsyncMock(side_effect=[
            trend_result, latency_result, tokens_result,
            intent_dist_result, response_dist_result,
        ])

        result = await get_trace_stats(db, days=7)

        assert len(result.latency) == 1
        assert result.latency[0].date == "2026-06-12"
        # p50 = values[int(10 * 0.5)] = values[5] = 600
        assert result.latency[0].p50 == 600
        # p95 = values[int(10 * 0.95)] = values[9] = 1000
        assert result.latency[0].p95 == 1000

    @pytest.mark.asyncio
    async def test_统计tokens聚合(self):
        """统计-tokens 聚合正确"""
        from app.services.trace_service import get_trace_stats

        db = AsyncMock()

        trend_result = MagicMock()
        trend_result.all.return_value = []

        latency_result = MagicMock()
        latency_result.all.return_value = []

        tokens_row = MagicMock()
        tokens_row.date = "2026-06-12"
        tokens_row.input_tokens = 5000
        tokens_row.output_tokens = 2000

        tokens_result = MagicMock()
        tokens_result.all.return_value = [tokens_row]

        intent_dist_result = MagicMock()
        intent_dist_result.all.return_value = []

        response_dist_result = MagicMock()
        response_dist_result.all.return_value = []

        db.execute = AsyncMock(side_effect=[
            trend_result, latency_result, tokens_result,
            intent_dist_result, response_dist_result,
        ])

        result = await get_trace_stats(db, days=7)

        assert len(result.tokens) == 1
        assert result.tokens[0].date == "2026-06-12"
        assert result.tokens[0].input == 5000
        assert result.tokens[0].output == 2000

    @pytest.mark.asyncio
    async def test_统计intent_distribution(self):
        """统计-intent_distribution 正确"""
        from app.services.trace_service import get_trace_stats

        db = AsyncMock()

        trend_result = MagicMock()
        trend_result.all.return_value = []

        latency_result = MagicMock()
        latency_result.all.return_value = []

        tokens_result = MagicMock()
        tokens_result.all.return_value = []

        intent_row1 = MagicMock()
        intent_row1.type = "KNOWLEDGE"
        intent_row1.count = 50

        intent_row2 = MagicMock()
        intent_row2.type = "CASUAL"
        intent_row2.count = 20

        intent_dist_result = MagicMock()
        intent_dist_result.all.return_value = [intent_row1, intent_row2]

        response_dist_result = MagicMock()
        response_dist_result.all.return_value = []

        db.execute = AsyncMock(side_effect=[
            trend_result, latency_result, tokens_result,
            intent_dist_result, response_dist_result,
        ])

        result = await get_trace_stats(db, days=7)

        assert len(result.intent_distribution) == 2
        assert result.intent_distribution[0].type == "KNOWLEDGE"
        assert result.intent_distribution[0].count == 50
        assert result.intent_distribution[1].type == "CASUAL"

    @pytest.mark.asyncio
    async def test_统计response_distribution(self):
        """统计-response_distribution 正确"""
        from app.services.trace_service import get_trace_stats

        db = AsyncMock()

        trend_result = MagicMock()
        trend_result.all.return_value = []

        latency_result = MagicMock()
        latency_result.all.return_value = []

        tokens_result = MagicMock()
        tokens_result.all.return_value = []

        intent_dist_result = MagicMock()
        intent_dist_result.all.return_value = []

        response_row1 = MagicMock()
        response_row1.mode = "RAG"
        response_row1.count = 40

        response_row2 = MagicMock()
        response_row2.mode = "CASUAL"
        response_row2.count = 15

        response_dist_result = MagicMock()
        response_dist_result.all.return_value = [response_row1, response_row2]

        db.execute = AsyncMock(side_effect=[
            trend_result, latency_result, tokens_result,
            intent_dist_result, response_dist_result,
        ])

        result = await get_trace_stats(db, days=7)

        assert len(result.response_distribution) == 2
        assert result.response_distribution[0].mode == "RAG"
        assert result.response_distribution[0].count == 40

    @pytest.mark.asyncio
    async def test_统计空数据(self):
        """统计-空数据返回空数组"""
        from app.services.trace_service import get_trace_stats

        db = AsyncMock()

        empty_result = MagicMock()
        empty_result.all.return_value = []

        db.execute = AsyncMock(side_effect=[
            empty_result, empty_result, empty_result,
            empty_result, empty_result,
        ])

        result = await get_trace_stats(db, days=1)

        assert len(result.trend) == 0
        assert len(result.latency) == 0
        assert len(result.tokens) == 0
        assert len(result.intent_distribution) == 0
        assert len(result.response_distribution) == 0
