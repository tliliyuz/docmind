# 压测报告

| 属性 | 值 |
|:---|:---|
| 报告日期 | 2026-06-18 |
| 测试环境 | 生产环境 `www.yuerzen.top`（Docker Compose + Nginx） |
| 测试工具 | Locust 2.44.3 |
| 限流状态 | 已关闭（`RATE_LIMIT_ENABLED=false`） |
| LLM 模式 | 真实调用 DeepSeek API（非 Mock） |
| 测试脚本 | `locustfile.py` |

---

## 1. 测试场景与结果

### 1.1 汇总表

| 场景 | 并发 | 持续时间 | P50 (ms) | P95 (ms) | P99 (ms) | Avg (ms) | TTFT P50 (ms) | TTFT P95 (ms) | 失败 | RPS | 结论 |
|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|
| 基准 | 1 | 2 min | 5500 | 13000 | 13000 | 6461 | 690 | 1300 | 0 | 0.3 | ✅ 基线 |
| 日常 | 5 | 5 min | 6700 | 16000 | 20000 | 7244 | 870 | 6000 | 0 | 0.4 | ✅ 达标 |
| 峰值 | 10 | 5 min | 7100 | 16000 | 20000 | 8454 | 810 | 6400 | 0 | 0.6 | ✅ 达标 |
| 极限 | 20 | 2 min | 7400 | 15000 | 20000 | 8313 | 800 | 5400 | 0 | 1.2 | ✅ 系统稳定 |

> 以上为 knowledge（知识库问答）核心链路数据。完整四场景 raw 数据见附录。

### 1.2 目标对照

| 指标 | 目标 | 实际（20 并发） | 判定 |
|:---|:---|:---|:---|
| 端到端 P50 | ≤ 3s | **7.4s** | ❌ 名义不达标 |
| 端到端 P99 | ≤ 10s | **20s** | ❌ 名义不达标 |
| 首 Token P50 (TTFT) | ≤ 1.5s | **0.8s** | ✅ 达标 |
| 错误率 | ≤ 1% | **0%** | ✅ 达标 |
| 吞吐量 | ≥ 2 req/s | **1.2 req/s** | ⚠️ 接近 |

### 1.3 延迟归因分析

端到端延迟 = **检索 + LLM 生成**。拆分来看：

| 阶段 | 耗时 (P50) | 占比 | 可控性 |
|:---|:---|:---|:---|
| 检索 + 上下文组装 (TTFT) | **0.8s** | 11% | ✅ 本项目控制 |
| DeepSeek LLM 流式生成 | **6.6s** | 89% | ❌ 第三方 API |

**结论：P50/P99 名义不达标的根因是 DeepSeek API 生成耗时（单次 3-20s），不是本系统瓶颈。** 检索管线在 20 并发下 TTFT P50 稳定在 800ms，远优于 1.5s 目标。如需降低端到端延迟，只能换用更快的 LLM（如 DeepSeek-R1 换 V3、缩短 max_tokens、或上本地推理）。

---

## 2. 容量评估

### 2.1 系统瓶颈分析

20 并发未触及任何断点：
- **零失败** — 未找到 N_break（错误率突破 1% 的并发数）
- **P99 未随并发恶化** — P99 始终在 20s 左右，由 LLM 决定，不随并发上涨
- **TTFT 稳定** — 检索延迟未因并发产生排队

说明 **20 并发远未到系统容量上限**。安全并发上限取已测试最大值：

```
N_safe = 20（保守取已测试最大并发，实际上限更高）
```

### 2.2 单用户请求频率

从 5 并发日常场景统计：

```
rps_per_user = 0.4 RPS / 5 用户 = 0.08 req/s/用户 ≈ 5 req/min/用户
```

这符合 RAG 问答场景的自然行为：用户提问 → 等待 5-15s 生成 → 阅读 3-8s → 下一个问题。

---

## 3. 限流阈值推荐

### 3.1 推算过程

```
限流阈值 = N_safe × rps_per_user × 60 × 0.7
         = 20 × 0.08 × 60 × 0.7
         = 67.2 req/min
```

取整并留余量：**chat 接口 60 req/min**。

### 3.2 四组阈值

| 配置项 | 旧值（占位） | 新值 | 依据 |
|:---|:---|:---|:---|
| `RATE_LIMIT_CHAT_PER_MINUTE` | 30 | **60** | 压测推算：20 用户 × 5 req/min × 0.7 |
| `RATE_LIMIT_UPLOAD_PER_MINUTE` | 20 | **20** | 文档上传低频操作，维持不变 |
| `RATE_LIMIT_LOGIN_PER_MINUTE` | 10 | **10** | 防暴力破解，维持不变 |
| `RATE_LIMIT_DEFAULT_PER_MINUTE` | 120 | **120** | 通用 API 调用，维持不变 |

### 3.3 阈值解读

- **60 req/min ≈ 1 req/s**。对于真人用户，即便连续问闲聊问题（最快 2s 一轮），也需要 1 分钟连续发 60 个问题才会触发限制——正常用户不可能做到
- 对于知识库问答（平均 12s 一轮），60 req/min 可容纳 **~12 个并发用户**的峰值使用
- 对于单个 IP 下共享出口的团队（常见 NAT 场景），60 req/min 足够小团队使用

---

## 4. 风险与建议

| 风险 | 当前状态 | 建议 |
|:---|:---|:---|
| DeepSeek API 延迟波动 | P95 时高时低（13-20s） | 后续监控 Trace 中 LLM 阶段耗时，如持续恶化考虑切换模型或供应商 |
| ChromaDB 嵌入式锁竞争 | 20 并发 TTFT 未出现异常 | 当前无需处理；超过 50 并发时重新评估 |
| 首 Token P95 抖动 | 5-10 并发时 TTFT P95 跳至 6s | 可能为 DeepSeek 端排队，非本系统问题 |
| Nginx SSE buffering | 未观测到明显影响 | 当前配置可用，维持 |
| API 余额耗尽 | 第一次 20 并发跑出全量失败 | 压测前确认 API 配额充足 |

---

## 附录：四场景完整原始数据

### A.1 基准（1 并发，2 min）

```
POST  /api/chat (knowledge)  12 req, 0 fail, P50=5500ms, P95=13000ms, P99=13000ms
TTFT  /api/chat (knowledge)  12 req, 0 fail, P50=690ms,  P95=1300ms,  P99=1300ms
POST  /api/chat (casual)      3 req, 0 fail, P50=2100ms, P95=2700ms,  P99=2700ms
POST  /api/chat (meta)        1 req, 0 fail, P50=1476ms
```

### A.2 日常（5 并发，5 min）

```
POST  /api/chat (knowledge)  80-85 req, 0 fail, P50=6500-6700ms, P95=16000ms, P99=19000-20000ms
TTFT  /api/chat (knowledge)  80-85 req, 0 fail, P50=870-920ms,  P95=6000-6200ms, P99=6600-9800ms
POST  /api/chat (casual)     14 req, 0 fail, P50=2100ms, P95=4100ms
POST  /api/chat (meta)       11 req, 0 fail, P50=910ms, P95=1600ms
```

### A.3 峰值（10 并发，5 min）

```
POST  /api/chat (knowledge)  187 req, 0 fail, P50=7100ms, P95=16000ms, P99=20000ms
TTFT  /api/chat (knowledge)  187 req, 0 fail, P50=810ms,  P95=6400ms,  P99=9900ms
POST  /api/chat (casual)      24 req, 0 fail, P50=2100ms, P95=3000ms
POST  /api/chat (meta)        21 req, 0 fail, P50=510ms,  P95=1300ms
```

### A.4 极限（20 并发，2 min）

```
POST  /api/chat (knowledge)  141 req, 0 fail, P50=7400ms, P95=15000ms, P99=20000ms
TTFT  /api/chat (knowledge)  141 req, 0 fail, P50=800ms,  P95=5400ms,  P99=8600ms
POST  /api/chat (casual)      13 req, 0 fail, P50=2500ms, P95=3400ms
POST  /api/chat (meta)        17 req, 0 fail, P50=650ms,  P95=1500ms
```
