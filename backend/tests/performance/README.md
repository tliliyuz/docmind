# 压测操作手册

> 压测策略、目标、通过标准、风险预案详见 [TESTING.md §8](../../../docs/tests/TESTING.md#8-压测phase-5)。

## 环境准备

| 步骤 | 说明 |
|:---|:---|
| 数据准备 | 知识库中 ≥ 20 份文档，每份 ≥ 10 chunks（回归测试集对应知识库即可） |
| 压测账号 | 创建专用账号，避免干扰正常数据 |
| 关闭限流 | `RATE_LIMIT_ENABLED=false`，防止限流成为瓶颈 |
| API 配额 | 确认 DeepSeek API Key 有效且配额充足 |
| 基线采集 | 正式压测前先跑 1 用户串行，记录无竞争基线延迟 |

> 压测应在 Docker Compose 生产级环境执行（Nginx SSE buffering 影响 TTFT 测量、Celery prefork vs solo 行为不同），**不 Mock LLM**（真实调用 DeepSeek API）。

## 测试场景

按顺序执行，场景之间间隔 3-5 分钟让系统恢复稳态：

| 场景 | 并发 | 爬升 | 持续时间 | 目的 |
|:---|:---|:---|:---|:---|
| 基准 | 1 | 1/s | 2 min | 无竞争基线（P50/P99/TTFT） |
| 日常负载 | 5 | 1/s | 5 min | 模拟小团队日常使用 |
| 峰值负载 | 10 | 2/s | 5 min | 模拟周一早晨集中使用 |
| 极限 | 20 | 5/s | 2 min | 找到系统吞吐上限 |

```bash
# 一键执行（按顺序跑 4 个场景）
locust -f locustfile.py --host http://localhost \
  --users 1 --spawn-rate 1 --run-time 2m --csv results/baseline --headless
# ...间隔 3-5min...
locust -f locustfile.py --host http://localhost \
  --users 5 --spawn-rate 1 --run-time 5m --csv results/daily --headless
locust -f locustfile.py --host http://localhost \
  --users 10 --spawn-rate 2 --run-time 5m --csv results/peak --headless
locust -f locustfile.py --host http://localhost \
  --users 20 --spawn-rate 5 --run-time 2m --csv results/stress --headless
```

## 压测脚本

脚本路径：`locustfile.py`

**设计要点**：
- 使用独立 `httpx.Client` 处理 SSE 流（Locust 默认 client 不支持 `stream=True`），通过 `events.request.fire()` 手动报告到 Locust 统计
- 任务权重 8:1:1（KNOWLEDGE : META : CASUAL），模拟真实流量分布
- `wait_time = between(3, 8)` 模拟用户阅读+思考间隔
- 每用户独立 `conversation_id`，模拟多轮对话
- 深度思考开关概率 10%
- `TTFT` 自定义指标：从请求发出到首个 `message` 事件的毫秒延迟
- SSE 完整性校验：必须收到 `meta` → `message` → `finish` 事件序列

## 执行流程

```
环境准备 → 基线(2min) → 冷却3min → 日常(5min) → 冷却5min → 峰值(5min) → 冷却5min → 极限(2min)
```

执行前检查：
1. `docker compose ps` 确认 5 个服务 running
2. `curl` 确认 `/api/health` 可达
3. 确认 `RATE_LIMIT_ENABLED=false`
4. 确认 DeepSeek API 配额充足
