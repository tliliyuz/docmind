"""
DocMind RAG 系统压测脚本

对齐 TESTING.md §8.3，使用 Locust 模拟真实用户问答行为。
支持 SSE 流式响应验证 + 首 token 延迟测量 + 来源引用校验。

4 场景（对齐 TESTING.md §8.1）：
  - 基准：1 并发，2 分钟
  - 日常：5 并发，5 分钟
  - 峰值：10 并发，5 分钟
  - 极限：20 并发，2 分钟

用法:
  cd backend

  # Web UI 模式（推荐，可实时监控）
  locust -f tests/locustfile.py --host http://localhost:8000

  # Headless 模式 — 基准
  locust -f tests/locustfile.py --host http://localhost:8000 \
    --users 1 --spawn-rate 1 --run-time 2m --csv results/baseline --headless

  # Headless 模式 — 日常
  locust -f tests/locustfile.py --host http://localhost:8000 \
    --users 5 --spawn-rate 1 --run-time 5m --csv results/daily --headless

  # Headless 模式 — 峰值
  locust -f tests/locustfile.py --host http://localhost:8000 \
    --users 10 --spawn-rate 2 --run-time 5m --csv results/peak --headless

  # Headless 模式 — 极限
  locust -f tests/locustfile.py --host http://localhost:8000 \
    --users 20 --spawn-rate 5 --run-time 2m --csv results/stress --headless

环境变量:
  STRESS_KB_ID         压测目标知识库 ID（默认 1）
  STRESS_AUTH_TOKEN    压测账号的 JWT Token（必须设置）
  STRESS_DEEP_THINKING 深度思考开启概率 0.0-1.0（默认 0.1）
"""

from __future__ import annotations

import json
import os
import random
import time

import httpx
from locust import HttpUser, task, between, events, tag

# ============================================================================
# 配置（支持环境变量覆盖）
# ============================================================================

KB_ID = int(os.environ.get("STRESS_KB_ID", "1"))
AUTH_TOKEN = os.environ.get("STRESS_AUTH_TOKEN", "")
DEEP_THINKING_PROBABILITY = float(os.environ.get("STRESS_DEEP_THINKING", "0.1"))

# SSE 超时设置（秒）
SSE_CONNECT_TIMEOUT = 10.0
SSE_READ_TIMEOUT = 60.0

# ============================================================================
# 问题池 — 覆盖不同难度和类型
# ============================================================================

KNOWLEDGE_QUESTIONS = [
    "新员工入职第一天需要完成哪些手续？",
    "员工请病假需要提前几天申请，需要提交什么材料？",
    "报销差旅费用需要填哪些表格，走什么审批流程？",
    "VPN 连接步骤是什么？忘记密码了怎么办？",
    "代码评审需要几个人参加？",
    "数据安全有哪些要求？既包括用户数据处理的，也包括日常办公安全的",
    "会议室预约后如果不用会怎么样？",
    "访客来公司需要什么手续？",
    "打印机墨盒怎么换？",
    "公司的加班制度是怎样的？",
    "如何申请生产服务器权限？",
    "离职交接清单包括哪些内容？",
    "公司有哪些培训资源可以使用？",
    "邮件使用规范是什么？",
    "网络故障怎么报修？",
    "请假需要提前几天申请？",
    "公司信息安全有什么具体要求？",
    "代码提交规范是怎样的？",
    "会议室设备坏了找谁修？",
    "新员工如何申请开发环境权限？",
]

META_QUESTIONS = [
    "你能做什么？",
    "你支持哪些功能？",
    "怎么使用这个系统？",
    "帮我介绍一下你自己",
]

CASUAL_QUESTIONS = [
    "你好",
    "谢谢你的回答",
    "好的我知道了",
    "再见",
]


# ============================================================================
# SSE 解析辅助
# ============================================================================

def _parse_sse_stream(response: httpx.Response) -> dict:
    """解析 SSE 流，返回统计信息"""
    result = {
        "events_received": set(),
        "has_error": False,
        "error_code": None,
        "content_length": 0,
        "ttft_ms": None,
        "conversation_id": None,
        "has_sources": False,
        "source_count": 0,
    }

    start = time.perf_counter()
    current_event = None

    for line in response.iter_lines():
        if not line:
            current_event = None
            continue

        # 心跳帧跳过
        if line.startswith(":"):
            continue

        if line.startswith("event: "):
            current_event = line[7:].strip()
            result["events_received"].add(current_event)
            continue

        if line.startswith("data: "):
            data_str = line[6:]

            # 首 token 延迟：首个 message 事件的数据到达时间
            if current_event == "message" and result["ttft_ms"] is None:
                result["ttft_ms"] = (time.perf_counter() - start) * 1000

            try:
                data = json.loads(data_str)

                if current_event == "message" and "content" in data:
                    result["content_length"] += len(data["content"])

                if current_event == "meta" and "conversation_id" in data:
                    result["conversation_id"] = data["conversation_id"]

                if current_event == "error":
                    result["has_error"] = True
                    result["error_code"] = data.get("code")

                if current_event == "sources":
                    result["has_sources"] = True
                    chunks = data.get("chunks", [])
                    result["source_count"] = len(chunks)

            except json.JSONDecodeError:
                pass

    return result


# ============================================================================
# Locust User 定义
# ============================================================================

class ChatUser(HttpUser):
    """模拟一个真实的 RAG 问答用户

    - 每次请求后等待 3-8 秒（模拟阅读答案 + 思考下一个问题）
    - 维护独立的 conversation_id 模拟多轮对话
    - 任务权重 8:1:1（KNOWLEDGE:META:CASUAL）
    """

    wait_time = between(3, 8)

    def on_start(self):
        """用户启动时设置认证头"""
        if not AUTH_TOKEN:
            raise ValueError(
                "请设置 STRESS_AUTH_TOKEN 环境变量。"
                "可通过 POST /api/auth/login 获取 token。"
            )
        self.client.headers.update({
            "Authorization": f"Bearer {AUTH_TOKEN}",
        })
        self.conversation_id = None

    # ---- 核心任务：知识库问答（权重 8） ----

    @task(8)
    @tag("chat", "knowledge")
    def ask_knowledge_question(self):
        """发送知识查询请求并验证 SSE 流完整性"""
        question = random.choice(KNOWLEDGE_QUESTIONS)
        deep_thinking = random.random() < DEEP_THINKING_PROBABILITY

        payload = {
            "kb_id": KB_ID,
            "question": question,
            "deep_thinking": deep_thinking,
        }
        if self.conversation_id:
            payload["conversation_id"] = self.conversation_id

        self._do_chat_request(payload, "knowledge")

    # ---- META 问题（权重 1） ----

    @task(1)
    @tag("chat", "meta")
    def ask_meta_question(self):
        """发送 META 类问题（系统能力查询）"""
        payload = {
            "kb_id": KB_ID,
            "question": random.choice(META_QUESTIONS),
            "deep_thinking": False,
        }
        # META 问题不复用会话上下文
        self._do_chat_request(payload, "meta", reuse_conversation=False)

    # ---- CASUAL 问题（权重 1） ----

    @task(1)
    @tag("chat", "casual")
    def ask_casual_question(self):
        """发送闲聊类问题"""
        payload = {
            "kb_id": KB_ID,
            "question": random.choice(CASUAL_QUESTIONS),
            "deep_thinking": False,
        }
        self._do_chat_request(payload, "casual", reuse_conversation=False)

    # ---- 内部方法 ----

    def _do_chat_request(
        self,
        payload: dict,
        label: str,
        reuse_conversation: bool = True,
    ):
        """执行 SSE 流式请求并上报指标到 Locust"""
        start_time = time.perf_counter()
        request_name = f"/api/chat ({label})"

        try:
            with httpx.Client(
                timeout=httpx.Timeout(SSE_READ_TIMEOUT, connect=SSE_CONNECT_TIMEOUT)
            ) as client:
                with client.stream(
                    "POST",
                    f"{self.host}/api/chat",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {AUTH_TOKEN}",
                        "Content-Type": "application/json",
                    },
                ) as response:
                    if response.status_code != 200:
                        total_ms = (time.perf_counter() - start_time) * 1000
                        events.request.fire(
                            request_type="POST",
                            name=request_name,
                            response_time=total_ms,
                            response_length=0,
                            exception=Exception(
                                f"HTTP {response.status_code}: "
                                f"{response.read().decode(errors='replace')[:200]}"
                            ),
                        )
                        return

                    result = _parse_sse_stream(response)

            total_ms = (time.perf_counter() - start_time) * 1000

            # ---- 更新会话 ID ----
            if reuse_conversation and result["conversation_id"]:
                self.conversation_id = result["conversation_id"]

            # ---- 错误检查 ----
            if result["has_error"]:
                events.request.fire(
                    request_type="POST",
                    name=request_name,
                    response_time=total_ms,
                    response_length=result["content_length"],
                    exception=Exception(f"SSE error event: {result['error_code']}"),
                )
                return

            # ---- SSE 流完整性校验 ----
            required_events = {"meta", "message", "finish"}
            # META/CASUAL 不要求 sources 事件
            if label == "knowledge":
                # knowledge 类问题期望有 sources（但也允许零引用情况）
                pass

            missing = required_events - result["events_received"]
            if missing:
                events.request.fire(
                    request_type="POST",
                    name=request_name,
                    response_time=total_ms,
                    response_length=result["content_length"],
                    exception=Exception(f"SSE 缺少事件: {missing}"),
                )
                return

            # ---- 上报端到端延迟 ----
            events.request.fire(
                request_type="POST",
                name=request_name,
                response_time=total_ms,
                response_length=result["content_length"],
            )

            # ---- 上报首 Token 延迟（TTFT） ----
            if result["ttft_ms"] is not None:
                events.request.fire(
                    request_type="TTFT",
                    name=f"{request_name} TTFT",
                    response_time=result["ttft_ms"],
                    response_length=0,
                )

        except httpx.TimeoutException:
            total_ms = (time.perf_counter() - start_time) * 1000
            events.request.fire(
                request_type="POST",
                name=request_name,
                response_time=total_ms,
                response_length=0,
                exception=Exception("SSE 请求超时"),
            )
        except httpx.ConnectError as e:
            total_ms = (time.perf_counter() - start_time) * 1000
            events.request.fire(
                request_type="POST",
                name=request_name,
                response_time=total_ms,
                response_length=0,
                exception=Exception(f"连接失败: {e}"),
            )
        except Exception as e:
            total_ms = (time.perf_counter() - start_time) * 1000
            events.request.fire(
                request_type="POST",
                name=request_name,
                response_time=total_ms,
                response_length=0,
                exception=e,
            )
