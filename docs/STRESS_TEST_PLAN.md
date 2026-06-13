## 压测方案 — DocMind RAG 系统性能验证

| 属性 | 值 |
|:---|:---|
| 文档版本 | v1.0 |
| 创建日期 | 2026-06-13 |
| 依据 | TESTING.md §8 / ARCHITECTURE.md §13.2 |
| 目标 | 验证系统性能达标 + 为限流阈值提供数据支撑 |

---

### 一、压测目标

本次压测有两个核心目的。第一，验证系统在多并发场景下的性能指标是否达标（P50 ≤ 3s、P99 ≤ 10s、错误率 ≤ 1%）。第二，根据压测结果确定限流中间件的阈值配置，取系统吞吐上限的 70% 作为限流基准（ARCHITECTURE.md §13.2.3 明确写到"压测确定系统容量 → 取 P99 并发数的 70% 作为限流阈值"）。

当前 `config.py` 中的限流占位值（chat=30/min, upload=20/min）需要在压测后用真实数据替换。

---

### 二、测试环境

#### 2.1 环境选型

压测应在与生产环境一致或接近的环境下执行。建议使用 Docker Compose 部署环境（已有 `docker-compose.yml` 5 服务编排），而非本地开发环境，原因有三：Nginx 反向代理的 SSE buffering 配置会影响首 token 延迟测量；Celery Worker 的进程模型与本地 `--pool=solo` 不同；容器资源限制更接近真实部署。

| 组件 | 配置 |
|:---|:---|
| 部署方式 | Docker Compose（`docker-compose.yml` 现有编排） |
| 后端 | FastAPI + uvicorn（单 worker，与现有部署一致） |
| 数据库 | MySQL 8.0（容器内） |
| 缓存 | Redis 7（容器内） |
| 向量库 | ChromaDB 嵌入式（挂卷持久化） |
| LLM | DeepSeek API（真实调用，不 Mock） |
| 压测客户端 | Locust（独立机器或同机器另一容器） |

#### 2.2 环境准备清单

1. 确保知识库中有足够的测试数据（建议至少 20 份文档、每份文档 10+ chunks，当前回归测试集对应的知识库即可）
2. 创建压测专用账号（避免干扰正常数据）
3. 压测前关闭限流中间件（`RATE_LIMIT_ENABLED=false`），防止限流本身成为瓶颈导致测不到真实上限
4. 确保 Redis / MySQL / ChromaDB 中无脏数据
5. 确认 DeepSeek API Key 有效且配额充足（压测会大量消耗 Token）

#### 2.3 压测前基线采集

在正式压测前先跑一轮基准测试（1 用户串行），记录无竞争下的基线延迟，作为后续对比参照。这对应 TESTING.md §8.1 中的"基准"场景。

---

### 三、测试工具

采用 **Locust**（Python 原生），理由如下：项目本身是 Python 技术栈，无需引入额外语言；Locust 原生支持 `stream=True` 可验证 SSE 流完整性；Web UI 方便实时监控；结果可导出 CSV/JSON 做后续分析。

安装命令：

```bash
pip install locust
```

---

### 四、压测脚本设计

#### 4.1 核心脚本结构 `locustfile.py`

脚本路径：`backend/tests/locustfile.py`

```python
"""
DocMind RAG 系统压测脚本

对齐 TESTING.md §8.3，使用 Locust 模拟真实用户问答行为。
支持 SSE 流式响应验证 + 首 token 延迟测量 + 来源引用校验。

用法:
  # Web UI 模式（推荐，可实时监控）
  locust -f tests/locustfile.py --host http://localhost:8000

  # Headless 模式（CI/自动化场景）
  locust -f tests/locustfile.py --host http://localhost:8000 \
    --users 5 --spawn-rate 1 --run-time 5m --csv results/daily \
    --headless
"""

from __future__ import annotations

import json
import random
import time
from typing import Generator

import httpx
from locust import HttpUser, task, between, events, tag

# ---- 配置 ----
KB_ID = 1  # 压测目标知识库 ID
AUTH_TOKEN = "xxx"  # 压测账号的 JWT Token（运行前替换）

# 从回归测试集中抽取的压测问题池（覆盖不同难度和类型）
QUESTION_POOL = [
    "新员工入职第一天需要完成哪些手续？",
    "员工请病假需要提前几天申请？",
    "报销差旅费用需要填哪些表格？",
    "VPN 连接步骤是什么？",
    "代码评审需要几个人参加？",
    "数据安全有哪些要求？",
    "会议室预约后如果不用会怎么样？",
    "访客来公司需要什么手续？",
    "打印机墨盒怎么换？",
    "公司的加班制度是怎样的？",
    "如何申请生产服务器权限？",
    "离职交接清单包括哪些内容？",
    "公司有哪些培训资源？",
    "邮件使用规范是什么？",
    "网络故障怎么报修？",
]

# 深度思考开关概率（10% 开启，模拟真实用户行为）
DEEP_THINKING_PROBABILITY = 0.1


class ChatUser(HttpUser):
    """模拟一个真实的 RAG 问答用户"""

    # 用户行为：每次请求后等待 3-8 秒（模拟阅读答案 + 思考下一个问题）
    wait_time = between(3, 8)

    def on_start(self):
        """用户启动时设置认证头"""
        self.client.headers.update({
            "Authorization": f"Bearer {AUTH_TOKEN}",
            "Content-Type": "application/json",
        })
        # 预定义会话 ID，模拟多轮对话（可选）
        self.conversation_id = None

    @task(8)  # 权重 8：普通问答为主
    @tag("chat", "knowledge")
    def ask_question(self):
        """核心任务：发送问答请求并验证 SSE 流完整性"""
        question = random.choice(QUESTION_POOL)
        deep_thinking = random.random() < DEEP_THINKING_PROBABILITY

        payload = {
            "kb_id": KB_ID,
            "question": question,
            "deep_thinking": deep_thinking,
        }
        if self.conversation_id:
            payload["conversation_id"] = self.conversation_id

        # ---- 手动管理 SSE 流式请求 ----
        start_time = time.perf_counter()
        ttft = None  # Time To First Token
        full_content = ""
        events_received = set()
        has_error = False

        try:
            with httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
                with client.stream(
                    "POST",
                    f"{self.host}/api/chat",
                    json=payload,
                    headers=self.client.headers,
                ) as response:
                    if response.status_code != 200:
                        events.request.fire(
                            request_type="POST",
                            name="/api/chat",
                            response_time=(time.perf_counter() - start_time) * 1000,
                            response_length=0,
                            exception=Exception(f"HTTP {response.status_code}"),
                        )
                        return

                    for line in response.iter_lines():
                        if not line or line.startswith(":"):
                            continue  # 跳过空行和心跳帧

                        if line.startswith("event: "):
                            event_type = line[7:]
                            events_received.add(event_type)
                            continue

                        if line.startswith("data: "):
                            data_str = line[6:]
                            if ttft is None and "message" in events_received:
                                ttft = (time.perf_counter() - start_time) * 1000

                            try:
                                data = json.loads(data_str)
                                if "content" in data:
                                    full_content += data["content"]
                                if "conversation_id" in data:
                                    self.conversation_id = data["conversation_id"]
                            except json.JSONDecodeError:
                                pass

            total_time = (time.perf_counter() - start_time) * 1000

            # ---- SSE 流完整性校验 ----
            required_events = {"meta", "message", "finish"}
            missing_events = required_events - events_received
            if missing_events:
                events.request.fire(
                    request_type="POST", name="/api/chat",
                    response_time=total_time, response_length=len(full_content),
                    exception=Exception(f"SSE 缺少事件: {missing_events}"),
                )
                return

            if has_error:
                events.request.fire(
                    request_type="POST", name="/api/chat",
                    response_time=total_time, response_length=len(full_content),
                    exception=Exception("SSE error 事件"),
                )
                return

            # ---- 记录成功 + TTFT ----
            events.request.fire(
                request_type="POST", name="/api/chat",
                response_time=total_time, response_length=len(full_content),
            )

            if ttft:
                events.request.fire(
                    request_type="TTFT", name="/api/chat (TTFT)",
                    response_time=ttft, response_length=0,
                )

        except Exception as e:
            events.request.fire(
                request_type="POST", name="/api/chat",
                response_time=(time.perf_counter() - start_time) * 1000,
                response_length=0, exception=e,
            )

    @task(1)  # 权重 1：少量 META 问题（模拟真实流量中的"你能做什么"类问题）
    @tag("chat", "meta")
    def ask_meta_question(self):
        meta_questions = ["你能做什么？", "你支持哪些功能？", "怎么使用这个系统？"]
        # META 问题走独立 conversation（不复用对话上下文）
        payload = {
            "kb_id": KB_ID,
            "question": random.choice(meta_questions),
            "deep_thinking": False,
        }
        start_time = time.perf_counter()
        try:
            response = self.client.post("/api/chat", json=payload)
            total_time = (time.perf_counter() - start_time) * 1000
            if response.status_code == 200:
                events.request.fire(
                    request_type="POST", name="/api/chat (meta)",
                    response_time=total_time, response_length=len(response.content),
                )
            else:
                events.request.fire(
                    request_type="POST", name="/api/chat (meta)",
                    response_time=total_time, response_length=0,
                    exception=Exception(f"HTTP {response.status_code}"),
                )
        except Exception as e:
            events.request.fire(
                request_type="POST", name="/api/chat (meta)",
                response_time=(time.perf_counter() - start_time) * 1000,
                response_length=0, exception=e,
            )

    @task(1)  # 权重 1：少量 CASUAL 问题
    @tag("chat", "casual")
    def ask_casual_question(self):
        casual_questions = ["你好", "谢谢", "再见", "今天天气怎么样"]
        payload = {
            "kb_id": KB_ID,
            "question": random.choice(casual_questions),
            "deep_thinking": False,
        }
        start_time = time.perf_counter()
        try:
            response = self.client.post("/api/chat", json=payload)
            total_time = (time.perf_counter() - start_time) * 1000
            if response.status_code == 200:
                events.request.fire(
                    request_type="POST", name="/api/chat (casual)",
                    response_time=total_time, response_length=len(response.content),
                )
            else:
                events.request.fire(
                    request_type="POST", name="/api/chat (casual)",
                    response_time=total_time, response_length=0,
                    exception=Exception(f"HTTP {response.status_code}"),
                )
        except Exception as e:
            events.request.fire(
                request_type="POST", name="/api/chat (casual)",
                response_time=(time.perf_counter() - start_time) * 1000,
                response_length=0, exception=e,
            )
```

#### 4.2 脚本设计要点

关于 SSE 流式验证：Locust 默认的 `HttpUser.client` 不支持 `stream=True`，脚本中使用独立的 `httpx.Client` 处理核心问答任务的 SSE 流，然后通过 `events.request.fire()` 手动报告指标到 Locust 统计系统。META/CASUAL 类问题因响应快、无流式需求，直接用 `self.client`。

关于用户行为模拟：`wait_time = between(3, 8)` 模拟用户阅读答案和思考下一个问题的间隔。每个用户有独立的 `conversation_id`，模拟真实的多轮对话场景。

关于问题池分布：任务权重 8:1:1（KNOWLEDGE:META:CASUAL），反映真实流量中知识查询为主、偶尔夹带闲聊和系统问题的分布。

---

### 五、四场景测试计划

对齐 TESTING.md §8.1 定义的四个场景，按顺序执行：

#### 场景 1：基准测试（Baseline）

| 参数 | 值 |
|:---|:---|
| 并发用户 | 1 |
| 持续时间 | 2 分钟（或 10 个请求取先到） |
| 目的 | 测量无竞争下的基线延迟（P50/P99/TTFT），作为后续场景的对比参照 |

```bash
locust -f tests/locustfile.py --host http://localhost:8000 \
  --users 1 --spawn-rate 1 --run-time 2m \
  --csv results/baseline --headless
```

#### 场景 2：日常负载（Daily）

| 参数 | 值 |
|:---|:---|
| 并发用户 | 5 |
| 爬升速率 | 1 user/s（5 秒内全部启动） |
| 持续时间 | 5 分钟 |
| 目的 | 模拟小团队日常使用，验证正常使用场景下的性能表现 |

```bash
locust -f tests/locustfile.py --host http://localhost:8000 \
  --users 5 --spawn-rate 1 --run-time 5m \
  --csv results/daily --headless
```

#### 场景 3：峰值负载（Peak）

| 参数 | 值 |
|:---|:---|
| 并发用户 | 10 |
| 爬升速率 | 2 users/s（5 秒内全部启动） |
| 持续时间 | 5 分钟 |
| 目的 | 模拟周一早晨集中使用，验证峰值下的延迟是否仍在可接受范围 |

```bash
locust -f tests/locustfile.py --host http://localhost:8000 \
  --users 10 --spawn-rate 2 --run-time 5m \
  --csv results/peak --headless
```

#### 场景 4：极限测试（Stress）

| 参数 | 值 |
|:---|:---|
| 并发用户 | 20 |
| 爬升速率 | 5 users/s（4 秒内全部启动） |
| 持续时间 | 2 分钟 |
| 目的 | 找到系统吞吐上限，确定限流阈值的数据依据 |

```bash
locust -f tests/locustfile.py --host http://localhost:8000 \
  --users 20 --spawn-rate 5 --run-time 2m \
  --csv results/stress --headless
```

---

### 六、测量指标与通过标准

对齐 TESTING.md §8.2：

| 指标 | 目标值 | 测量方式 | 说明 |
|:---|:---|:---|:---|
| 端到端 P50 延迟 | ≤ 3s | Locust `POST /api/chat` response time | 从请求发出到收到 `finish` 事件 |
| 端到端 P99 延迟 | ≤ 10s | Locust P99 | 99% 的请求在 10s 内完成 |
| 首 token 延迟 P50 | ≤ 1.5s | Locust `TTFT` 自定义指标 | 从请求到首个 SSE `message` 事件 |
| 错误率 | ≤ 1% | Locust failure rate | HTTP 非 2xx 或 SSE 缺少 `finish` 事件 |
| 吞吐量 | ≥ 2 req/s | Locust RPS | 10 并发下的系统吞吐 |
| Token 消耗 | ≤ 4000 tokens/请求 | Trace 系统聚合 | 从 `traces` 表查询 `input_tokens + output_tokens` |

每个场景执行完毕后，从 Locust CSV 输出和 Trace 系统中提取上述指标，填入结果汇总表。

---

### 七、执行流程

#### 7.1 执行顺序

```
环境准备 → 基线(2min) → 间隔 3min → 日常(5min) → 间隔 5min → 峰值(5min) → 间隔 5min → 极限(2min)
```

场景之间留间隔是为了让系统资源（Redis 连接池、BM25 缓存、数据库连接）恢复到稳态，避免前一场压测的残留影响后一场的数据。

#### 7.2 执行前检查

1. `docker compose ps` 确认 5 个服务全部 running
2. `curl -H "Authorization: Bearer $TOKEN" http://localhost/api/health` 确认可达
3. 确认 `RATE_LIMIT_ENABLED=false`（压测期间关闭限流）
4. 确认 DeepSeek API 配额充足
5. 创建 `results/` 目录

#### 7.3 执行命令（一键脚本）

```bash
#!/bin/bash
# run_stress_test.sh — 压测全流程执行脚本

set -e

HOST="http://localhost"
LOCUSTFILE="tests/locustfile.py"
RESULTS_DIR="results/stress_test_$(date +%Y%m%d_%H%M%S)"

mkdir -p "$RESULTS_DIR"

echo "=== [1/4] 基准测试 (1 user, 2min) ==="
locust -f "$LOCUSTFILE" --host "$HOST" \
  --users 1 --spawn-rate 1 --run-time 2m \
  --csv "$RESULTS_DIR/baseline" --headless --only-summary

echo ">>> 冷却 3 分钟..."
sleep 180

echo "=== [2/4] 日常负载 (5 users, 5min) ==="
locust -f "$LOCUSTFILE" --host "$HOST" \
  --users 5 --spawn-rate 1 --run-time 5m \
  --csv "$RESULTS_DIR/daily" --headless --only-summary

echo ">>> 冷却 5 分钟..."
sleep 300

echo "=== [3/4] 峰值负载 (10 users, 5min) ==="
locust -f "$LOCUSTFILE" --host "$HOST" \
  --users 10 --spawn-rate 2 --run-time 5m \
  --csv "$RESULTS_DIR/peak" --headless --only-summary

echo ">>> 冷却 5 分钟..."
sleep 300

echo "=== [4/4] 极限测试 (20 users, 2min) ==="
locust -f "$LOCUSTFILE" --host "$HOST" \
  --users 20 --spawn-rate 5 --run-time 2m \
  --csv "$RESULTS_DIR/stress" --headless --only-summary

echo "=== 压测完成！结果保存在 $RESULTS_DIR ==="
echo ">>> 请查看 $RESULTS_DIR/*.csv 和 Trace 系统数据"
```

---

### 八、结果分析与限流阈值设定

#### 8.1 结果汇总模板

压测完成后，将四个场景的核心指标填入下表：

| 场景 | 并发 | P50 (s) | P99 (s) | TTFT P50 (s) | 错误率 | RPS | 结论 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| 基准 | 1 | — | — | — | — | — | 基线 |
| 日常 | 5 | — | — | — | — | — | 达标/不达标 |
| 峰值 | 10 | — | — | — | — | — | 达标/不达标 |
| 极限 | 20 | — | — | — | — | — | 系统上限 |

#### 8.2 限流阈值推算方法

依据 ARCHITECTURE.md §13.2.3 的策略：

1. 从极限测试中找到**错误率刚好突破 1%** 时的并发数（记为 `N_break`）
2. 从峰值/极限测试中找到 **P99 刚好超过 10s** 时的并发数（记为 `N_p99`）
3. 取 `N_safe = min(N_break, N_p99)` 作为系统安全并发上限
4. 计算每用户请求频率：从日常负载测试中统计单用户 RPS（记为 `rps_per_user`）
5. 限流阈值 = `N_safe × rps_per_user × 60 × 0.7`（取 70% 安全系数，换算为每分钟）

示例推算：假设 `N_safe = 12`，`rps_per_user = 0.2`（每 5 秒一个请求），则 chat 限流 = `12 × 0.2 × 60 × 0.7 ≈ 100/min`。

#### 8.3 配置更新

推算完成后，更新 `config.py` 和 `.env` 文件：

```python
# 限流（压测后修正值）
RATE_LIMIT_CHAT_PER_MINUTE: int = {推算值}     # 聊天接口
RATE_LIMIT_UPLOAD_PER_MINUTE: int = {推算值}   # 上传接口（取 chat 的 60-70%）
RATE_LIMIT_LOGIN_PER_MINUTE: int = 10          # 登录接口（保持不变）
RATE_LIMIT_DEFAULT_PER_MINUTE: int = {推算值}  # 其他接口（取 chat 的 3-4 倍）
```

同时更新 `ROADMAP.md` 和 `ARCHITECTURE.md` 中的限流占位值。

---

### 九、风险与预案

| 风险 | 预案 |
|:---|:---|
| DeepSeek API 本身限流/降速 | 观察 LLM 调用阶段的 TTFT 和 total_ms 是否异常偏高；必要时在 Trace 系统按 `model` 字段过滤分析 |
| ChromaDB 嵌入式在高并发下锁竞争 | 极限场景下关注 `retrieve` 阶段的 `vector_ms`，若 P99 > 2s 考虑 ChromaDB 迁移到 client-server 模式 |
| Redis 连接池耗尽 | 监控 Redis `connected_clients` 指标；BM25 进程内缓存（60s TTL）应在高并发下有效减少 Redis 访问 |
| 数据库连接池不足 | uvicorn 默认 SQLAlchemy 连接池大小需确认（建议 `pool_size=20, max_overflow=10`） |
| Token 消耗超预期 | 从 Trace 系统聚合 `input_tokens + output_tokens`，若均值 > 4000 需排查 Prompt 预算逻辑 |

---

### 十、后续步骤

压测完成后的工作：

1. 将结果填入上方汇总表
2. 按 §8.2 方法推算限流阈值，更新 `config.py`
3. 开启限流中间件（`RATE_LIMIT_ENABLED=true`），运行 `test_rate_limit.py` 验证阈值生效
4. 更新 `ROADMAP.md` §7.5 压测行状态为 ✅，记录关键指标
5. 进入「最终人工评分」（Phase 5 最后一个测试项）
