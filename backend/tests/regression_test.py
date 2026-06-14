"""回归测试脚本 — 端到端问答质量验证

对齐 TESTING.md §7：
- 遍历 30 题测试集，调用 /api/chat SSE 接口
- 检查：答案非空 / 引用来源有效 / SSE 格式正确 / 无系统错误
- 每次提交前运行，防止已有能力退化

用法:
  cd backend
  # 需要先启动服务: uvicorn app.main:app --port 8000
  python tests/regression_test.py --kb-uuid 550e8400-e29b-41d4-a716-446655440000 --base-url http://localhost:8000 --token "xxx"
  python tests/regression_test.py --kb-uuid 550e8400-e29b-41d4-a716-446655440000 --token "xxx"   # 默认 localhost:8000
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
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tests.eval_test_set import EVAL_TEST_SET

logger = logging.getLogger(__name__)

# ============================================================================
# 数据结构
# ============================================================================


@dataclass
class SSECheckResult:
    """单个问题的回归检查结果"""
    question_id: int
    question: str
    difficulty: str
    question_type: str
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
    answer_contains_not_found: bool = False
    answer_text: str = ""  # LLM 完整回答（用于诊断）
    # 来源
    source_count: int = 0
    source_doc_ids: list[int] = field(default_factory=list)
    # 元信息
    conversation_id: str | None = None
    title: str | None = None
    # 综合
    passed: bool = False
    failure_reasons: list[str] = field(default_factory=list)


@dataclass
class RegressionSummary:
    """回归测试汇总"""
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0  # 连接/网络错误
    results: list[SSECheckResult] = field(default_factory=list)
    # 分类统计
    answer_empty_count: int = 0
    sources_missing_count: int = 0  # 应有 sources 但无
    sources_unexpected_count: int = 0  # 不应有 sources 但有（out-of-scope）
    answer_not_found_count: int = 0  # LLM 回答含"未找到相关信息"
    sse_sequence_broken_count: int = 0
    system_error_count: int = 0


# ============================================================================
# SSE 解析器
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
    """解析 SSE 响应流，返回事件列表。

    Args:
        response: httpx Response（已确认 status=200）

    Returns:
        解析后的事件列表
    """
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

    # 流结束后处理最后一条事件（无结尾空行的情况）
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
# 回归检查引擎
# ============================================================================


class RegressionRunner:
    """回归测试执行器

    对单个知识库逐一发送 30 题，校验 SSE 响应。
    """

    def __init__(self, kb_uuid: str, base_url: str, token: str, timeout: int = 60):
        self.kb_uuid = kb_uuid
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._chat_url = f"{self.base_url}/api/chat"

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def _send_question(self, item: dict[str, Any]) -> tuple[list[SSEEvent], str | None]:
        """发送单个问题，返回 SSE 事件列表。

        Returns:
            (events, error_string): 成功时 error_string 为 None
        """
        payload = {
            "kb_id": self.kb_uuid,
            "question": item["question"],
            "deep_thinking": False,
        }

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
                        # 连接建立前的错误（JSON 响应）
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

    def _check_question(self, item: dict[str, Any], events: list[SSEEvent],
                        error: str | None) -> SSECheckResult:
        """对单题结果执行全部检查项。

        对齐 TESTING.md §7.3 回归检查项：
        1. 答案非空
        2. 引用来源有效
        3. SSE 格式正确
        4. 错误率
        """
        qid = item["id"]
        result = SSECheckResult(
            question_id=qid,
            question=item["question"],
            difficulty=item["difficulty"],
            question_type=item["type"],
        )

        # --- 连接/网络错误（致命） ---
        if error:
            result.failure_reasons.append(f"连接错误: {error}")
            return result  # passed=False

        # --- 事件类型收集 ---
        event_types = set()
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
        result.answer_contains_not_found = (
            "未找到相关信息" in full_answer or "知识库中未找到" in full_answer
        )
        result.answer_text = full_answer

        # ================================================================
        # 检查项 1: 答案非空（TESTING.md §7.3 第 2 项）
        # ================================================================
        if not result.answer_non_empty:
            result.failure_reasons.append("答案为空白（无 message 事件或内容为空）")
        elif result.answer_length < 10:
            result.failure_reasons.append(f"答案过短（{result.answer_length} 字符）")

        # ================================================================
        # 检查项 2: 引用来源有效（TESTING.md §7.3 第 3 项）
        # ================================================================
        is_out_of_scope = item["difficulty"] == "out-of-scope"
        has_expected_docs = len(item.get("expected_docs", [])) > 0

        if has_expected_docs and not result.has_sources:
            # 应有 sources 但没有
            result.failure_reasons.append("缺失 sources 事件（期望有引用来源）")
        elif has_expected_docs and result.has_sources and result.source_count == 0:
            result.failure_reasons.append("sources 事件中 chunks 为空")
        elif is_out_of_scope and result.has_sources and result.source_count > 0:
            # out-of-scope 不应有 sources
            result.failure_reasons.append(
                f"超出知识库范围但返回了 {result.source_count} 个引用来源"
            )
        elif is_out_of_scope and not result.answer_contains_not_found:
            # out-of-scope 应提示"未找到"
            result.failure_reasons.append(
                "超出知识库范围但答案未包含'未找到相关信息'"
            )

        # ================================================================
        # 检查项 3: SSE 格式正确（TESTING.md §7.3 第 4 项）
        # ================================================================
        required_events = {"meta", "finish"}
        missing = required_events - event_types
        if missing:
            result.failure_reasons.append(f"SSE 事件缺失: {missing}")

        # ================================================================
        # 检查项 4: 错误率（TESTING.md §7.3 第 5 项）
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

    async def run(self) -> RegressionSummary:
        """运行全部 30 题的回归测试。

        Returns:
            RegressionSummary: 汇总结果
        """
        summary = RegressionSummary(total=len(EVAL_TEST_SET))

        print(f"\n{'='*70}")
        print(f"  回归测试 — kb_uuid={self.kb_uuid}")
        print(f"  服务地址: {self.base_url}")
        print(f"  测试集: {len(EVAL_TEST_SET)} 题")
        print(f"{'='*70}\n")

        for i, item in enumerate(EVAL_TEST_SET, 1):
            qid = item["id"]
            question = item["question"]
            print(f"[{i:2d}/{len(EVAL_TEST_SET)}] Q{qid}: {question[:55]}...", end=" ", flush=True)

            events, error = await self._send_question(item)

            if error:
                # 连接/网络级错误
                result = SSECheckResult(
                    question_id=qid,
                    question=question,
                    difficulty=item["difficulty"],
                    question_type=item["type"],
                )
                result.failure_reasons.append(f"连接错误: {error}")
                summary.errors += 1
                summary.failed += 1
                print(f"❌ {error}")
            else:
                result = self._check_question(item, events, None)
                if result.passed:
                    summary.passed += 1
                    print(f"✅ ({result.answer_length} 字符)")
                else:
                    summary.failed += 1
                    reasons = "; ".join(result.failure_reasons)
                    print(f"❌ {reasons}")

            summary.results.append(result)

            # 分类统计
            if not result.answer_non_empty:
                summary.answer_empty_count += 1
            if result.has_error:
                summary.system_error_count += 1
            if result.answer_contains_not_found:
                summary.answer_not_found_count += 1

            # 请求间隔（避免打爆服务）
            if i < len(EVAL_TEST_SET):
                await asyncio.sleep(0.5)

        return summary


# ============================================================================
# 报告输出
# ============================================================================


def print_regression_report(summary: RegressionSummary) -> None:
    """打印回归测试报告"""
    print(f"\n{'='*70}")
    print("  回归测试报告")
    print(f"{'='*70}\n")

    total = summary.total
    pass_rate = summary.passed / total * 100 if total > 0 else 0

    print(f"  总计: {total} 题")
    print(f"  通过: {summary.passed} ✅")
    print(f"  失败: {summary.failed} ❌")
    print(f"  连接错误: {summary.errors} 🔌")
    print(f"  通过率: {pass_rate:.1f}%")
    print()

    # 分类明细
    print(f"  答案为空/过短: {summary.answer_empty_count}")
    print(f"  LLM 含'未找到相关信息': {summary.answer_not_found_count}")
    print(f"  系统错误 (SSE error): {summary.system_error_count}")
    print()

    # 逐题详情
    failed_results = [r for r in summary.results if not r.passed]
    if failed_results:
        print(f"  失败详情 ({len(failed_results)} 题):")
        print(f"  {'-'*66}")
        for r in failed_results:
            print(f"  Q{r.question_id} [{r.difficulty}] {r.question[:50]}...")
            for reason in r.failure_reasons:
                print(f"    → {reason}")
            if r.answer_text:
                # 显示 LLM 回答片段用于诊断
                snippet = r.answer_text[:120].replace('\n', ' ')
                nf_mark = " [含'未找到']" if r.answer_contains_not_found else ""
                print(f"    💬 回答{nf_mark}: {snippet}...")
        print()

    # 按难度分组统计
    print(f"  按难度分组:")
    for diff in ["easy", "medium", "hard", "out-of-scope"]:
        group = [r for r in summary.results if r.difficulty == diff]
        if not group:
            continue
        group_pass = sum(1 for r in group if r.passed)
        print(f"    {diff:<12}: {group_pass}/{len(group)} 通过")

    print()

    if summary.passed == total:
        print("🎉 全部回归测试通过！")
    else:
        print(f"⚠️  {summary.failed} 题未通过，请检查上方失败详情。")

    print()


# ============================================================================
# CLI 入口
# ============================================================================


async def main_async(kb_uuid: str, base_url: str, token: str, timeout: int) -> None:
    """异步主流程"""
    runner = RegressionRunner(
        kb_uuid=kb_uuid,
        base_url=base_url,
        token=token,
        timeout=timeout,
    )
    summary = await runner.run()
    print_regression_report(summary)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DocMind 回归测试 — 端到端问答质量验证",
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
        "--timeout", type=int, default=60,
        help="单题超时秒数（默认 60）",
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
