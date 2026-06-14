"""多轮 RAG 回归测试脚本 — 端到端多轮问答质量验证

对齐 TESTING.md §7.4：
  - 遍历多轮测试集，逐 session 逐 turn 调用 /api/chat SSE 接口
  - 同一 session 内复用 conversation_id 实现真正的多轮对话
  - 检查项在单轮基础上新增：
    ① RAG 退化检测（Turn ≥2 时 sources 消失）
    ② 上下文断裂检测（context_dependent 轮次无答案）
    ③ 历史截断不报错（长对话最后几轮仍正常）

用法:
  cd backend
  # 需要先启动服务: uvicorn app.main:app --port 8000
  python tests/regression/regression_multi_turn_test.py --kb-uuid 550e8400-e29b-41d4-a716-446655440000 --base-url http://localhost:8000 --token "xxx"
  python tests/regression/regression_multi_turn_test.py --kb-uuid 550e8400-e29b-41d4-a716-446655440000 --token "xxx"   # 默认 localhost:8000
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

# 确保 backend 目录在 sys.path 中
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tests.eval.eval_multi_turn_test_set import MULTI_TURN_TEST_SET

logger = logging.getLogger(__name__)

# ============================================================================
# 数据结构
# ============================================================================


@dataclass
class TurnResult:
    """单轮回归检查结果"""
    turn: int
    question: str
    # 事件序列
    has_meta: bool = False
    has_message: bool = False
    has_sources: bool = False
    has_finish: bool = False
    has_error: bool = False
    error_code: str | None = None
    error_message: str | None = None
    # 内容质量
    answer_non_empty: bool = False
    answer_length: int = 0
    answer_text: str = ""
    # 来源
    source_count: int = 0
    source_doc_ids: list[int] = field(default_factory=list)
    source_doc_names: list[str] = field(default_factory=list)
    # 元信息
    conversation_id: str | None = None
    title: str | None = None
    # 综合
    passed: bool = False
    failure_reasons: list[str] = field(default_factory=list)
    # 多轮特有标记
    rag_degraded: bool = False     # 应有 sources 但无（Turn ≥2）
    context_dependent: bool = False  # 该轮是否依赖前轮上下文
    in_truncation_zone: bool = False  # 该轮是否在历史截断观察区内


@dataclass
class SessionResult:
    """单个多轮 session 的汇总结果"""
    session_id: str
    session_name: str
    turns: list[TurnResult] = field(default_factory=list)
    # Session 级汇总
    total_turns: int = 0
    passed_turns: int = 0
    failed_turns: int = 0
    error_turns: int = 0
    # 多轮特有退化检测
    rag_degraded_count: int = 0    # 出现 RAG 退化的轮次数
    context_dependent_total: int = 0  # context_dependent=True 的轮次总数
    context_dependent_pass: int = 0   # 其中通过的轮次数
    # 截断区域统计
    truncation_zone_total: int = 0    # 截断观察区内的轮次数
    truncation_zone_pass: int = 0     # 其中通过的轮次数
    truncation_zone_rag_degraded: int = 0  # 截断区内 RAG 退化轮次
    # 综合
    passed: bool = False           # 全部 turn 通过


@dataclass
class MultiTurnSummary:
    """多轮回归测试汇总"""
    total_sessions: int = 0
    passed_sessions: int = 0
    failed_sessions: int = 0
    total_turns: int = 0
    passed_turns: int = 0
    failed_turns: int = 0
    # 退化统计
    rag_degraded_total: int = 0
    context_dependent_total: int = 0
    context_dependent_pass: int = 0
    # 截断区域统计
    truncation_zone_total: int = 0
    truncation_zone_pass: int = 0
    truncation_zone_rag_degraded: int = 0
    # 详细结果
    sessions: list[SessionResult] = field(default_factory=list)


# ============================================================================
# SSE 解析器（复用 regression_test.py 的解析逻辑）
# ============================================================================


class SSEEvent:
    """单条 SSE 事件"""
    __slots__ = ("event", "data")
    event: str
    data: dict[str, Any] | None

    def __init__(self, event: str, data: dict[str, Any] | None = None):
        self.event = event
        self.data = data


async def parse_sse_stream(response: httpx.Response) -> list[SSEEvent]:
    """解析 SSE 响应流，返回事件列表。"""
    events: list[SSEEvent] = []
    current_event: str | None = None
    current_data_lines: list[str] = []

    async for line in response.aiter_lines():
        # 心跳帧（注释行）
        if line.startswith(":"):
            continue

        # 空行 = 事件结束
        if line == "":
            if current_event is not None:
                data_str = "\n".join(current_data_lines)
                data: dict[str, Any] | None = None
                if data_str.strip():
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        data = {"raw": data_str}
                events.append(SSEEvent(event=current_event, data=data))

            current_event = None
            current_data_lines = []
            continue

        # event: 行
        if line.startswith("event:"):
            current_event = line[6:].strip()
            continue

        # data: 行
        if line.startswith("data:"):
            current_data_lines.append(line[5:].strip())
            continue

    # 流结束后处理最后一条事件
    if current_event is not None:
        data_str = "\n".join(current_data_lines)
        data = None
        if data_str.strip():
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                data = {"raw": data_str}
        events.append(SSEEvent(event=current_event, data=data))

    return events


# ============================================================================
# 多轮回归执行器
# ============================================================================


class MultiTurnRegressionRunner:
    """多轮回归测试执行器

    对每个多轮 session，逐 turn 发送请求，复用 conversation_id。
    """

    def __init__(self, kb_uuid: str, base_url: str, token: str, timeout: int = 60):
        self.kb_uuid = kb_uuid
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._chat_url = f"{self.base_url}/api/chat"

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def _send_turn(
        self,
        question: str,
        conversation_id: str | None,
        deep_thinking: bool = False,
    ) -> tuple[list[SSEEvent], str | None]:
        """发送单轮问题，返回 SSE 事件列表。

        Args:
            question: 用户问题
            conversation_id: 会话 ID（None 表示新建会话）
            deep_thinking: 是否启用深度思考

        Returns:
            (events, error_string): 成功时 error_string 为 None
        """
        payload: dict[str, Any] = {
            "kb_id": self.kb_uuid,
            "question": question,
            "deep_thinking": deep_thinking,
        }
        if conversation_id is not None:
            payload["conversation_id"] = conversation_id

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    self._chat_url,
                    json=payload,
                    headers={
                        **self._auth_headers(),
                        "Content-Type": "application/json",
                        "Accept": "text/event-stream",
                    },
                ) as response:
                    if response.status_code != 200:
                        body = ""
                        async for chunk in response.aiter_text():
                            body += chunk
                        try:
                            err_data = json.loads(body)
                            err_msg = err_data.get("detail", {}).get("message", body)
                        except json.JSONDecodeError:
                            err_msg = body[:200]
                        return [], f"HTTP {response.status_code}: {err_msg}"

                    events = await parse_sse_stream(response)
                    return events, None

        except httpx.TimeoutException:
            return [], "请求超时"
        except httpx.ConnectError as e:
            return [], f"连接失败: {e}"
        except Exception as e:
            return [], f"未知错误: {e}"

    def _check_turn(
        self,
        turn_spec: dict[str, Any],
        events: list[SSEEvent],
        error: str | None,
    ) -> TurnResult:
        """对单轮结果执行全部检查项。

        在单轮检查基础上，新增多轮特有检查：
        - RAG 退化检测
        - context_dependent 标记追踪
        """
        turn_num = turn_spec["turn"]
        expected = turn_spec["expected"]
        is_context_dependent = expected.get("context_dependent", False)

        result = TurnResult(
            turn=turn_num,
            question=turn_spec["question"],
            context_dependent=is_context_dependent,
        )

        # --- 连接/网络错误（致命） ---
        if error:
            result.failure_reasons.append(f"连接错误: {error}")
            return result  # passed=False

        # --- 事件类型收集 ---
        event_types: set[str] = set()
        answer_parts: list[str] = []
        has_error_event = False

        for evt in events:
            event_types.add(evt.event)

            if evt.event == "meta" and evt.data:
                result.conversation_id = evt.data.get("conversation_id")
                result.has_meta = True

            elif evt.event == "message" and evt.data:
                delta = evt.data.get("delta", "")
                answer_parts.append(delta)
                result.has_message = True

            elif evt.event == "sources" and evt.data:
                result.has_sources = True
                chunks = evt.data.get("chunks", [])
                result.source_count = len(chunks)
                result.source_doc_ids = [c.get("doc_id", 0) for c in chunks]
                result.source_doc_names = [c.get("doc_name", "?") for c in chunks]

            elif evt.event == "finish" and evt.data:
                result.has_finish = True
                result.title = evt.data.get("title")

            elif evt.event == "error" and evt.data:
                result.has_error = True
                result.error_code = evt.data.get("code", "?")
                result.error_message = evt.data.get("message", "")
                has_error_event = True

        # --- 组装完整答案 ---
        full_answer = "".join(answer_parts)
        result.answer_length = len(full_answer)
        result.answer_non_empty = len(full_answer.strip()) > 0
        result.answer_text = full_answer

        # ================================================================
        # 检查项 1: 答案非空
        # ================================================================
        if not result.answer_non_empty:
            result.failure_reasons.append("答案为空白（无 message 事件或内容为空）")
        elif result.answer_length < 10:
            result.failure_reasons.append(f"答案过短（{result.answer_length} 字符）")

        # ================================================================
        # 检查项 2: 引用来源有效 + RAG 退化检测
        # ================================================================
        expects_sources = expected.get("has_sources", True)
        if expects_sources and not result.has_sources:
            reason = "缺失 sources 事件（期望有引用来源）"
            # 区分：Turn 1 无 sources vs Turn ≥2 无 sources（RAG 退化）
            if turn_num >= 2:
                reason += " ← RAG 退化警告"
                result.rag_degraded = True
            result.failure_reasons.append(reason)
        elif expects_sources and result.has_sources and result.source_count == 0:
            result.failure_reasons.append("sources 事件中 chunks 为空")
            if turn_num >= 2:
                result.rag_degraded = True

        # --- 期望文档匹配（检查项 2b） ---
        expected_docs = expected.get("expected_docs", [])
        if expected_docs and result.has_sources and result.source_count > 0:
            actual_names = set(result.source_doc_names)
            matched = [d for d in expected_docs if d in actual_names]
            if not matched:
                result.failure_reasons.append(
                    f"文档不匹配: 期望包含 {expected_docs}，实际 {sorted(actual_names)}"
                )
                # 文档不匹配也视为 RAG 退化（检索到了错误的文档）
                if turn_num >= 2:
                    result.rag_degraded = True

        # ================================================================
        # 检查项 3: SSE 格式正确
        # ================================================================
        required_events = {"meta", "finish"}
        missing = required_events - event_types
        if missing:
            result.failure_reasons.append(f"SSE 事件缺失: {missing}")

        # ================================================================
        # 检查项 4: 系统错误
        # ================================================================
        if has_error_event:
            result.failure_reasons.append(
                f"SSE error 事件: code={result.error_code}, msg={result.error_message}"
            )

        # ================================================================
        # 综合判断
        # ================================================================
        result.passed = len(result.failure_reasons) == 0

        return result

    async def run_session(self, session: dict[str, Any]) -> SessionResult:
        """运行一个多轮 session 的全部 turn。

        关键：同一 session 内复用 conversation_id。
        """
        session_id = session["session_id"]
        session_name = session["name"]
        turns_spec = session["turns"]

        session_result = SessionResult(
            session_id=session_id,
            session_name=session_name,
            total_turns=len(turns_spec),
        )

        truncation_zone_start = session.get("truncation_zone_start")
        conversation_id: str | None = None

        for i, turn_spec in enumerate(turns_spec):
            turn_num = turn_spec["turn"]
            question = turn_spec["question"]
            in_trunc_zone = (
                truncation_zone_start is not None and turn_num >= truncation_zone_start
            )

            display_q = question[:50] + ("..." if len(question) > 50 else "")
            ctx_tag = " [依赖上下文]" if turn_spec["expected"].get("context_dependent") else ""
            trunc_tag = " [截断区]" if in_trunc_zone else ""
            print(
                f"    T{turn_num}: {display_q}{ctx_tag}{trunc_tag}",
                end=" ",
                flush=True,
            )

            # 发送请求（Turn 1 不传 conversation_id，后续 turn 传入）
            events, error = await self._send_turn(
                question=question,
                conversation_id=conversation_id,
            )

            if error:
                # 连接/网络级错误
                turn_result = TurnResult(
                    turn=turn_num,
                    question=question,
                    context_dependent=turn_spec["expected"].get("context_dependent", False),
                    in_truncation_zone=in_trunc_zone,
                )
                turn_result.failure_reasons.append(f"连接错误: {error}")
                session_result.error_turns += 1
                session_result.failed_turns += 1
                print(f"❌ {error}")
            else:
                turn_result = self._check_turn(turn_spec, events, None)
                turn_result.in_truncation_zone = in_trunc_zone

                # 更新 conversation_id（从 meta 事件中获取，用于下一轮）
                if turn_result.conversation_id is not None:
                    conversation_id = turn_result.conversation_id

                if turn_result.passed:
                    session_result.passed_turns += 1
                    src_info = f"({turn_result.source_count} 来源)" if turn_result.has_sources else "(无来源)"
                    print(f"✅ {turn_result.answer_length} 字符 {src_info}")
                else:
                    session_result.failed_turns += 1
                    reasons = "; ".join(turn_result.failure_reasons)
                    print(f"❌ {reasons}")

            # 统计多轮特有指标
            if turn_result.rag_degraded:
                session_result.rag_degraded_count += 1
            if turn_result.context_dependent:
                session_result.context_dependent_total += 1
                if turn_result.passed:
                    session_result.context_dependent_pass += 1
            if turn_result.in_truncation_zone:
                session_result.truncation_zone_total += 1
                if turn_result.passed:
                    session_result.truncation_zone_pass += 1
                if turn_result.rag_degraded:
                    session_result.truncation_zone_rag_degraded += 1

            session_result.turns.append(turn_result)

            # 请求间隔（≥1.0s，确保后端异步落库完成）
            if i < len(turns_spec) - 1:
                await asyncio.sleep(1.0)

        # Session 级判断：全部 turn 通过才算通过
        session_result.passed = session_result.failed_turns == 0 and session_result.error_turns == 0

        return session_result

    async def run(self) -> MultiTurnSummary:
        """运行全部多轮 session 的回归测试。"""
        summary = MultiTurnSummary(total_sessions=len(MULTI_TURN_TEST_SET))

        # 计算总轮数
        total_turns = sum(len(s["turns"]) for s in MULTI_TURN_TEST_SET)

        print(f"\n{'='*70}")
        print(f"  多轮 RAG 回归测试 — kb_uuid={self.kb_uuid}")
        print(f"  服务地址: {self.base_url}")
        print(f"  测试集: {len(MULTI_TURN_TEST_SET)} 个 Session，共 {total_turns} 轮")
        print(f"{'='*70}\n")

        for session_idx, session in enumerate(MULTI_TURN_TEST_SET, 1):
            session_name = session["name"]
            session_id = session["session_id"]

            print(f"[{session_idx}/{len(MULTI_TURN_TEST_SET)}] {session_name} ({session_id})")

            session_result = await self.run_session(session)

            # 汇总统计
            summary.total_turns += session_result.total_turns
            summary.passed_turns += session_result.passed_turns
            summary.failed_turns += session_result.failed_turns
            summary.rag_degraded_total += session_result.rag_degraded_count
            summary.context_dependent_total += session_result.context_dependent_total
            summary.context_dependent_pass += session_result.context_dependent_pass
            summary.truncation_zone_total += session_result.truncation_zone_total
            summary.truncation_zone_pass += session_result.truncation_zone_pass
            summary.truncation_zone_rag_degraded += session_result.truncation_zone_rag_degraded

            if session_result.passed:
                summary.passed_sessions += 1
                print(f"  ✅ Session 通过 ({session_result.passed_turns}/{session_result.total_turns} 轮)")
            else:
                summary.failed_sessions += 1
                print(f"  ❌ Session 失败 ({session_result.failed_turns}/{session_result.total_turns} 轮失败)")

            summary.sessions.append(session_result)

            # Session 间暂停（避免打爆服务 + 让前一个 session 的消息落库）
            if session_idx < len(MULTI_TURN_TEST_SET):
                await asyncio.sleep(1.0)

        return summary


# ============================================================================
# 报告输出
# ============================================================================


def print_multi_turn_report(summary: MultiTurnSummary) -> None:
    """打印多轮回归测试报告"""
    print(f"\n{'='*70}")
    print("  多轮 RAG 回归测试报告")
    print(f"{'='*70}\n")

    # 总览
    total_sessions = summary.total_sessions
    session_pass_rate = (
        summary.passed_sessions / total_sessions * 100 if total_sessions > 0 else 0
    )
    turn_pass_rate = (
        summary.passed_turns / summary.total_turns * 100 if summary.total_turns > 0 else 0
    )

    print(f"  Session 总计: {total_sessions}")
    print(f"  Session 通过: {summary.passed_sessions} ✅")
    print(f"  Session 失败: {summary.failed_sessions} ❌")
    print(f"  Session 通过率: {session_pass_rate:.1f}%")
    print()
    print(f"  Turn 总计: {summary.total_turns}")
    print(f"  Turn 通过: {summary.passed_turns} ✅")
    print(f"  Turn 失败: {summary.failed_turns} ❌")
    print(f"  Turn 通过率: {turn_pass_rate:.1f}%")
    print()

    # 多轮特有指标
    print(f"  ── 多轮特有指标 ──")
    print(f"  RAG 退化轮次: {summary.rag_degraded_total}")
    print(f"  上下文依赖轮次: {summary.context_dependent_total}")
    print(f"  上下文依赖-可用性检查通过: {summary.context_dependent_pass}")
    if summary.context_dependent_total > 0:
        cd_pass_rate = summary.context_dependent_pass / summary.context_dependent_total * 100
        print(f"  上下文依赖-可用性通过率: {cd_pass_rate:.1f}%")
    print(f"  ℹ️  「可用性检查」= 有回答 + 有来源 + SSE 正常（必要条件，非充分条件）")
    print(f"     上下文是否真正被理解，需通过 LLM-as-judge 或人工评估确认。")
    print()
    if summary.truncation_zone_total > 0:
        print(f"  ── 截断区域指标 ──")
        print(f"  截断区内轮次: {summary.truncation_zone_total}")
        print(f"  截断区内通过: {summary.truncation_zone_pass}")
        print(f"  截断区内 RAG 退化: {summary.truncation_zone_rag_degraded}")
        tz_pass_rate = summary.truncation_zone_pass / summary.truncation_zone_total * 100
        print(f"  截断区通过率: {tz_pass_rate:.1f}%")
        if summary.truncation_zone_rag_degraded > 0:
            print(f"  ⚠️  截断区内出现 RAG 退化！历史截断可能侵蚀了检索预算。")
        else:
            print(f"  ✅ 截断区内无 RAG 退化，历史截断未影响检索。")
        print(f"  ℹ️  截断区起点基于 token 预算估算（History Budget=6000），实际截断位置依赖具体消息长度。")
    print()

    # 逐 Session 详情
    for session_result in summary.sessions:
        status = "✅" if session_result.passed else "❌"
        print(f"  {status} {session_result.session_name} ({session_result.session_id})")
        print(f"     Turns: {session_result.passed_turns}/{session_result.total_turns} 通过")

        if session_result.rag_degraded_count > 0:
            print(f"     ⚠️ RAG 退化: {session_result.rag_degraded_count} 轮")

        if session_result.truncation_zone_total > 0:
            tz_info = (
                f"✅ 截断区: {session_result.truncation_zone_pass}/{session_result.truncation_zone_total}"
                if session_result.truncation_zone_rag_degraded == 0
                else f"⚠️ 截断区 RAG 退化: {session_result.truncation_zone_rag_degraded}/{session_result.truncation_zone_total}"
            )
            print(f"     {tz_info}")

        if session_result.context_dependent_total > 0:
            cd_status = (
                "✅" if session_result.context_dependent_pass == session_result.context_dependent_total
                else "❌"
            )
            print(
                f"     {cd_status} 上下文依赖可用性: "
                f"{session_result.context_dependent_pass}/{session_result.context_dependent_total}"
            )

        # 逐 Turn 详情（仅失败时展开）
        failed_turns = [t for t in session_result.turns if not t.passed]
        if failed_turns:
            for t in failed_turns:
                print(f"     T{t.turn} ❌ {t.question[:50]}...")
                for reason in t.failure_reasons:
                    print(f"        → {reason}")
                if t.answer_text:
                    snippet = t.answer_text[:120].replace("\n", " ")
                    print(f"        💬 回答: {snippet}...")
        print()

    # Session 级矩阵一览
    print(f"  ── Session × Turn 结果矩阵 ──")
    header = "  Session".ljust(20)
    max_turns = max(len(s.turns) for s in summary.sessions)
    for i in range(1, max_turns + 1):
        header += f" T{i} "
    print(header)
    print("  " + "-" * (20 + 4 * max_turns))

    for session_result in summary.sessions:
        row = f"  {session_result.session_name[:18]}".ljust(20)
        for t in session_result.turns:
            if t.rag_degraded:
                row += " 🔻 "  # RAG 退化
            elif not t.passed:
                row += " ❌ "
            elif t.in_truncation_zone:
                row += " 🟐 "  # 截断区通过
            elif t.passed:
                row += " ✅ "
            else:
                row += " ⬜ "
        print(row)

    print()
    print(f"  图例: ✅ 通过  ❌ 失败  🔻 RAG退化  🟐 截断区通过")
    print()

    # 最终结论
    if summary.passed_sessions == total_sessions:
        print("🎉 全部多轮 Session 通过！RAG 未退化，多轮对话正常。")
    else:
        print(f"⚠️  {summary.failed_sessions}/{total_sessions} Session 未通过，请检查上方详情。")
        if summary.rag_degraded_total > 0:
            print(f"⚠️  检测到 {summary.rag_degraded_total} 轮 RAG 退化（Turn ≥2 时 sources 消失）")
            print("    → 检查项：历史消息是否挤占了检索结果的 Prompt 预算")
            print("    → 检查项：_load_history() 是否错误过滤了本轮检索结果")

    print()


# ============================================================================
# CLI 入口
# ============================================================================


async def main_async(kb_uuid: str, base_url: str, token: str, timeout: int) -> None:
    """异步主流程"""
    runner = MultiTurnRegressionRunner(
        kb_uuid=kb_uuid,
        base_url=base_url,
        token=token,
        timeout=timeout,
    )
    summary = await runner.run()
    print_multi_turn_report(summary)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DocMind 多轮 RAG 回归测试 — 端到端多轮问答质量验证",
    )
    parser.add_argument(
        "--kb-uuid", type=str, required=True,
        help="目标知识库 UUID",
    )
    parser.add_argument(
        "--base-url", type=str, default="http://localhost:8000",
        help="服务地址（默认 http://localhost:8000）",
    )
    parser.add_argument(
        "--token", type=str, required=True,
        help="JWT access_token（可通过 /api/auth/login 获取）",
    )
    parser.add_argument(
        "--timeout", type=int, default=90,
        help="单轮超时秒数（默认 90，多轮场景 LLM 生成时间可能较长）",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    asyncio.run(main_async(
        kb_uuid=args.kb_uuid,
        base_url=args.base_url,
        token=args.token,
        timeout=args.timeout,
    ))


if __name__ == "__main__":
    main()
