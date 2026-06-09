# TESTING — 测试策略文档

| 属性 | 值 |
|:---|:---|
| 文档版本 | v0.14 |
| 最后更新 | 2026-06-09 |
| 作者 | yuz |
| 状态 | 进行中（Phase 4 全部完成 + 第 2 轮人工评分完成，进入 Phase 5） |

---

## 1. 测试策略概述

RAG 系统的质量无法仅靠单元测试和接口测试衡量。核心挑战在于：**检索是否召回了正确的文档？生成的答案是否准确且相关？**

本项目的测试分为 6 个层次：

| 层次 | 目标 | 频率 | 方法 |
|:---|:---|:---|:---|
| **单元测试** | 验证函数/类/方法的独立逻辑正确性 | 每次提交 | pytest + vitest，Mock 外部依赖 |
| **接口测试** | 验证 API 请求/响应格式与错误码 | 每次提交 | httpx + FastAPI TestClient，真实路由链路 |
| **组件测试** | 验证前端组件的渲染与交互行为 | 每次提交 | vitest + @vue/test-utils |
| **离线检索评估** | 量化检索效果 | 每次检索代码变更 | 固定测试集 + Recall@K / MRR 指标 |
| **人工答案评分** | 评估端到端问答质量 | 每 Phase 结束时 | 1-5 分制人工评分 |
| **回归测试** | 防止已有能力退化 | 每次提交 | 固定问题集快照对比 |
| **压测** | 确保系统性能达标 | Phase 5 | 并发模拟 + P99 延迟测量 |

---

## 2. 单元测试

### 2.1 后端单元测试（pytest）

覆盖所有 services/、core/、models/、schemas/ 中的纯逻辑，**Mock 所有外部依赖（DB、Redis、外部 API）**。

**测试环境**：
- 使用 `pytest-asyncio` 支持 async/await
- 使用 `unittest.mock` Mock SQLAlchemy session、Redis 连接等
- 使用 `pytest-cov` 输出覆盖率，目标 ≥ 80%

**测试文件规范**：
- 文件名：`test_{模块名}.py`
- 测试函数：`test_{被测函数名}_{场景}`
- 每个测试函数只验证一个行为（单一断言原则）

```python
# 示例：test_security.py
def test_hash_password_returns_bcrypt_string():
    result = hash_password("test123")
    assert result.startswith("$2b$")

def test_verify_password_correct():
    hashed = hash_password("test123")
    assert verify_password("test123", hashed) is True

def test_create_access_token_contains_claims():
    token = create_access_token(1, "user", "user")
    payload = decode_access_token(token)
    assert payload["sub"] == "1"
    assert payload["username"] == "user"
```

### 2.2 前端工具函数单元测试（vitest）

覆盖 `utils/`、`api/`、`stores/` 中的纯 JavaScript 逻辑。

```javascript
// 示例：sse.test.js
import { describe, it, expect } from 'vitest'
import { parseSSEEvent } from '@/utils/sse'

describe('parseSSEEvent', () => {
  it('解析 meta 事件', () => {
    const line = 'event: meta'
    const data = '{"conversation_id": 1}'
    const result = parseSSEEvent(line, data)
    expect(result.type).toBe('meta')
  })
})
```

---

## 3. 接口测试

### 3.1 后端 API 接口测试

使用 FastAPI TestClient + httpx，**走真实路由链路**。API 接口测试使用 Mock session 隔离外部依赖；模型层测试（约束校验、关联查询）直接连接开发库 MySQL，测试数据操作后清理。

**覆盖范围**：
- 正常请求 → 正确响应码 + `{code, message, data}` 格式
- 参数校验失败 → 422 + E9003 错误码
- 业务异常 → 对应错误码（E1001/E2001/E5001 等）
- 认证缺失/过期 → 401
- 权限不足 → 403

**测试结构**：
```python
# 示例：test_auth_api.py
@pytest.mark.asyncio
async def test_register_success(async_client):
    response = await async_client.post(
        "/api/auth/register",
        json={"username": "testuser", "password": "test123"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["username"] == "testuser"

@pytest.mark.asyncio
async def test_register_username_too_short(async_client):
    response = await async_client.post(
        "/api/auth/register",
        json={"username": "a", "password": "test123"}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "E9003"
```

### 3.2 接口测试检查清单

每个 API 端点至少覆盖：

| 场景 | 检查项 |
|:---|:---|
| 正常请求 | 状态码 2xx、响应格式 `{code:0, message, data}` |
| 参数校验 | 必填缺失、类型错误、范围越界 → 422 (E9003) |
| 业务错误 | 资源不存在 → 404、冲突 → 409、无权 → 403 |
| 认证授权 | 无 Token → 401、Token 过期 → 401 E5003、权限不足 → 403 E5005 |

---

## 4. 前端组件测试

使用 vitest + @vue/test-utils + jsdom，验证 Vue 组件的渲染与交互。

**覆盖范围**：
- 组件渲染：关键 DOM 元素存在
- 用户交互：按钮点击、表单提交触发正确事件
- 条件渲染：v-if/v-show 在不同状态下的表现
- Props/Events：父子组件通信正确

```javascript
// 示例：LoginPage.test.js
import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import LoginPage from '@/views/LoginPage.vue'

describe('LoginPage', () => {
  it('渲染用户名和密码输入框', () => {
    const wrapper = mount(LoginPage)
    expect(wrapper.find('input[type="text"]').exists()).toBe(true)
    expect(wrapper.find('input[type="password"]').exists()).toBe(true)
  })

  it('空表单提交按钮禁用', () => {
    const wrapper = mount(LoginPage)
    expect(wrapper.find('button[type="submit"]').attributes('disabled')).toBeDefined()
  })
})
```

---

## 5. 离线检索评估

### 5.1 评估指标

| 指标 | 公式 | 说明 | 目标值 |
|:---|:---|:---|:---|
| Recall@5 | （检索到的相关 chunk 数）/（知识库中所有相关 chunk 数） | top-5 召回率，衡量检索是否遗漏关键内容 | ≥ 0.85 |
| Recall@10 | 同上，取 top-10 | RRF 融合前的召回率 | ≥ 0.90 |
| MRR | `1 / N * Σ 1/rank_i`，rank_i 是第一个相关 chunk 的排名 | 平均倒数排名，衡量最相关文档是否排在前面 | ≥ 0.70 |
| Precision@5 | top-5 中相关 chunk 数 / 5 | 精确率，衡量检索结果中有效信息占比 | ≥ 0.60 |

### 5.2 评估流程

```python
# 伪代码：离线检索评估
def evaluate_retrieval(test_set, retriever):
    recall_scores = []
    mrr_scores = []
    
    for question, relevant_doc_ids in test_set:
        results = retriever.search(question, kb_id, top_k=10)
        result_doc_ids = [r.doc_id for r in results]
        
        # Recall@5
        top5 = result_doc_ids[:5]
        recall = len(set(top5) & set(relevant_doc_ids)) / len(relevant_doc_ids)
        recall_scores.append(recall)
        
        # MRR
        for i, doc_id in enumerate(result_doc_ids):
            if doc_id in relevant_doc_ids:
                mrr_scores.append(1 / (i + 1))
                break
        else:
            mrr_scores.append(0)
    
    return {
        "Recall@5": mean(recall_scores),
        "MRR": mean(mrr_scores)
    }
```

> Phase 3 实现：检索评估脚本 `backend/tests/eval_retrieval.py`，用于自动化评估向量检索、BM25、RRF 融合三者的效果差异。Phase 3 检索管线完成后执行。

---

## 6. 答案相关性人工评分

### 6.1 评分标准（1-5 分制）

| 分数 | 等级 | 定义 |
|:---|:---|:---|
| 5 | 优秀 | 答案完全正确，覆盖所有要点，引用准确，语言通顺 |
| 4 | 良好 | 答案基本正确，遗漏 1-2 个非关键点或引用存在轻微偏差 |
| 3 | 合格 | 答案部分正确，有明显遗漏或个别事实错误，但仍能回答用户核心问题 |
| 2 | 较差 | 答案大部分不相关或错误，对用户帮助有限 |
| 1 | 无效 | 答案完全错误、答非所问、或 LLM 拒答但库中确有答案 |

### 6.2 评分维度

每次打分需从以下 4 个维度独立评估：

| 维度 | 权重 | 说明 | 检查问题 |
|:---|:---|:---|:---|
| **准确性** | 40% | 答案中的事实是否与源文档一致 | "答案中的每条陈述都能在源文档中找到依据吗？" |
| **完整性** | 30% | 是否涵盖了文档中相关的核心内容 | "用户读完这个答案还需要额外查询吗？" |
| **溯源正确性** | 20% | 引用的来源文档是否真实、页码是否正确 | "引用的文档确实包含这段信息吗？" |
| **表达质量** | 10% | 语言是否通顺、结构是否清晰 | "答案易读吗？格式规范吗？" |

**综合分计算**：`总分 = 准确性×0.4 + 完整性×0.3 + 溯源正确性×0.2 + 表达质量×0.1`

**目标**：平均综合分 ≥ 4.0/5.0，且无 1 分评分。

### 6.3 评分流程

1. 从回归测试集中随机抽取 10 个问题
2. 运行系统获取完整答案（含引用来源）
3. 人工对照源文档逐维度打分
4. 记录评分表，每次 Phase 结束时执行一次

> 人工评分记录模板：`backend/tests/human_eval_template.md`——10 题 × 4 维度评分表，含评分标准、逐题记录区、汇总表、问题记录区。

### 6.4 多轮对话评分补充（Phase 4 第 2 轮人工评分）

第 2 轮人工评分与第 1 轮有本质区别：第 1 轮评估的是**单轮独立问答**质量，第 2 轮评估的是**多轮对话**质量。

#### 评估对象差异

| 差异点 | 第 1 轮（单轮） | 第 2 轮（多轮） |
|:---|:---|:---|
| 评估对象 | 独立问题 × 10 | Session × 5（每 Session 含 3-10 轮） |
| 评分层级 | 仅问题级（4 维度） | **轮次级（4 维度）+ Session 级（3 跨轮维度）** |
| 核心关注 | 答案准确性 + 来源引用 | 单轮质量 + **上下文理解** + **RAG 不退化** |

#### 跨轮维度（Session 级，第 2 轮新增）

| 维度 | 权重 | 检查问题 | 说明 |
|:---|:---|:---|:---|
| **上下文连贯性** | 25% | 后续轮次是否正确理解了前面轮次的上下文？代词指代是否消解正确？ | 多轮对话的核心体验指标 |
| **RAG 保活性** | 20% | 第 2 轮及之后是否仍在检索知识库并引用来源？（而非退化为纯聊天） | Phase 4 关键验证点——防止 RAG 静默退化 |
| **历史记忆准确性** | 10% | 系统是否记住了前面轮次的关键信息？有没有遗忘或混淆？ | 辅助指标 |

#### 综合分计算

```
Session 综合分 = (Σ 各轮轮次分 / 轮数) × 0.45
               + 上下文连贯性 × 0.25
               + RAG 保活性 × 0.20
               + 历史记忆准确性 × 0.10
```

**权重设计理念**：轮次均分占 45%（单轮质量是基础），上下文连贯性 25%（多轮核心价值），RAG 保活性 20%（Phase 4 关键验证点），历史记忆准确性 10%（辅助指标）。

#### 对比方式

- **同口径对比**：第 2 轮的「轮次均分」与第 1 轮的 4.38/5.0 直接对比，验证多轮场景下单轮质量是否下降
- **增量评估**：第 2 轮独有的 Session 综合分衡量多轮对话整体体验
- **目标**：轮次均分 ≥ 4.0（不建议低于第 1 轮），Session 综合分平均 ≥ 4.0

> 完整评分表模板见 `backend/tests/human_eval_template.md`「第 2 轮：多轮对话人工评分」章节。
>
> **评估结果（2026-06-09）**：
> - Session 综合分平均：**4.76/5.0** ✅ 远超 ≥ 4.0 目标
> - 轮次均分：4.62/5.0（vs 第 1 轮 4.38，↑ +0.24）
> - RAG 保活性：5.0/5.0 满分（23 轮均有 sources，未退化）
> - 上下文连贯性：4.8/5.0（平均）
> - 无上下文断裂、无指代消解失败、无 RAG 退化
> - 发现的问题：无关文档混入（3次）、编造细节（S5-T10）、回答立场软化（S5-T9）

---

## 7. 回归测试集

### 7.1 设计原则

- 固定 20-30 个问题，覆盖知识库中的所有文档
- 每个问题必须标注：**期望引用的源文档文件名**（至少 1 个）
- 问题类型多样化：精确查询、模糊语义查询、跨文档查询、多轮对话
- 测试集不随功能迭代而修改，仅当知识库内容发生结构性变化时更新
- 每次代码提交后运行全量回归

### 7.2 测试集结构

```json
[
  {
    "id": 1,
    "question": "入职需要开通哪些账号？",
    "type": "单文档精确查询",
    "kb_id": 1,
    "expected_docs": ["入职指南.md"],
    "min_relevant_chunks": 1
  },
  {
    "id": 2,
    "question": "报销差旅费要填什么表？",
    "type": "单文档模糊查询",
    "kb_id": 1,
    "expected_docs": ["报销制度.md"],
    "min_relevant_chunks": 1
  },
  {
    "id": 3,
    "question": "打印机墨盒怎么换？",
    "type": "语义匹配（同义词）",
    "kb_id": 1,
    "expected_docs": ["打印机使用说明.md"],
    "min_relevant_chunks": 1
  },
  {
    "id": 4,
    "question": "请假需要提前几天申请？",
    "type": "单文档精确查询",
    "kb_id": 1,
    "expected_docs": ["请假与考勤制度.md"],
    "min_relevant_chunks": 1
  },
  {
    "id": 5,
    "question": "生产数据库密码和生产服务器权限分别怎么申请？",
    "type": "跨文档查询",
    "kb_id": 1,
    "expected_docs": ["系统权限申请流程.md"],
    "min_relevant_chunks": 2
  },
  {
    "id": 6,
    "question": "数据安全有哪些要求？既包括用户数据处理的，也包括日常办公安全的",
    "type": "跨文档查询",
    "kb_id": 1,
    "expected_docs": ["数据安全规范.md", "信息安全规范.md"],
    "min_relevant_chunks": 2
  },
  {
    "id": 7,
    "question": "VPN怎么连？",
    "type": "简称匹配",
    "kb_id": 1,
    "expected_docs": ["VPN配置指南.md"],
    "min_relevant_chunks": 1
  },
  {
    "id": 8,
    "question": "代码评审需要几个人参加？",
    "type": "单文档精确查询",
    "kb_id": 1,
    "expected_docs": ["代码评审标准.md"],
    "min_relevant_chunks": 1
  },
  {
    "id": 9,
    "question": "会议室预约后如果不用会怎么样？",
    "type": "蕴含推理",
    "kb_id": 1,
    "expected_docs": ["会议室预约规则.md"],
    "min_relevant_chunks": 1
  },
  {
    "id": 10,
    "question": "访客来公司需要什么手续？",
    "type": "单文档模糊查询",
    "kb_id": 1,
    "expected_docs": ["访客登记流程.md"],
    "min_relevant_chunks": 1
  }
]
```

> 以上为单轮查询 10 题示例，完整测试集需扩充至 25-30 题。Phase 4 新增多轮会话测试集（见 §7.4）。

### 7.3 回归检查项

| 检查项 | 方法 | 通过标准 |
|:---|:---|:---|
| 检索召回 | 脚本自动计算 | Recall@5 ≥ 0.85，且不低于上一版本 |
| 答案非空 | 接口返回检查 | 所有问题均返回非空答案 |
| 引用来源有效 | 脚本校验 | `sources` 事件中的 doc_id 均在 MySQL 中存在 |
| SSE 格式正确 | 脚本校验 | 所有问题均收到 `meta` → `message` → `sources` → `finish` 事件序列 |
| 错误率 | 脚本统计 | 无 E9xxx / E4xxx 系统级错误 |

> Phase 3 实现：回归测试脚本 `backend/tests/regression_test.py`，遍历测试集、调用 `/api/chat`、自动检查上述项并输出报告。Phase 3 问答 API 完成后执行。

### 7.4 多轮 RAG 回归测试（Phase 4 新增）

多轮对话场景下，历史消息注入可能引入以下退化：
- 历史消息挤占检索结果 → RAG 退化为纯聊天
- 旧轮次 `[来源N]` 编号与当前轮次检索结果冲突
- assistant 消息注入导致 LLM 混淆角色边界

#### 测试集设计

```json
[
  {
    "session_id": "multi-turn-001",
    "name": "报销制度三连问",
    "kb_id": 1,
    "turns": [
      {
        "turn": 1,
        "question": "介绍一下公司的报销制度",
        "expected": {
          "has_answer": true,
          "has_sources": true,
          "min_chunks": 1,
          "expected_docs": ["报销制度.md"]
        }
      },
      {
        "turn": 2,
        "question": "审批流程需要多长时间？",
        "expected": {
          "has_answer": true,
          "has_sources": true,
          "min_chunks": 1,
          "expected_docs": ["报销制度.md"],
          "context_dependent": true
        }
      },
      {
        "turn": 3,
        "question": "金额限制具体是多少？",
        "expected": {
          "has_answer": true,
          "has_sources": true,
          "min_chunks": 1,
          "expected_docs": ["报销制度.md"],
          "context_dependent": true
        }
      }
    ]
  }
]
```

#### 回归检查项（多轮）

| 检查项 | 方法 | 通过标准 |
|:---|:---|:---|
| 每轮检索召回 | 脚本自动计算 | 全部 turn Recall@5 ≥ 0.85 |
| 每轮答案非空 | 接口返回检查 | 全部 turn 返回非空答案 |
| 每轮引用来源有效 | 脚本校验 | 全部 turn `sources` 中的 doc_id 均在 MySQL 中存在 |
| 上下文连贯 | 人工/LLM 评估 | Turn 2/3 的答案与 Turn 1 主题一致，未出现主题漂移 |
| RAG 不退化 | 脚本校验 | Turn 2/3 仍返回 `sources` 事件（未被历史挤掉检索结果） |
| 历史截断不报错 | 脚本校验 | 20+ 轮后仍正常返回答案和来源 |

> **重要**：单轮测试全部通过 ≠ 多轮没问题。这是 Phase 4 最容易出 Bug 的地方——历史注入逻辑错误会导致 RAG 静默退化为普通聊天，而单轮测试无法发现。

#### 脚本与测试集

| 文件 | 用途 |
|:---|:---|
| `backend/tests/eval_multi_turn_test_set.py` | 多轮测试集：5 个 Session（报销三连问 / 主题切换 / 跨文档追问 / 指代消解 / 长对话保活），共 23 轮 |
| `backend/tests/regression_multi_turn_test.py` | 多轮回归脚本：复用 `conversation_id` 实现真正的多轮对话，含 RAG 退化检测 + 上下文断裂检测 + Session×Turn 结果矩阵 |

```bash
# 运行多轮回归测试
python tests/regression_multi_turn_test.py --kb-id 1 --token "xxx"
python tests/regression_multi_turn_test.py --kb-id 1 --base-url http://localhost:8000 --token "xxx"
```

---

## 8. 压测指标

### 8.1 测试场景

| 场景 | 并发用户数 | 持续时间 | 说明 |
|:---|:---|:---|:---|
| 基准 | 1 | - | 单用户串行，测量无竞争下的基线延迟 |
| 日常负载 | 5 | 5 min | 模拟小团队日常使用 |
| 峰值负载 | 10 | 5 min | 模拟周一早晨集中使用 |
| 极限 | 20 | 2 min | 找到系统吞吐上限 |

### 8.2 测量指标

| 指标 | 目标值 | 说明 |
|:---|:---|:---|
| 端到端 P50 延迟 | ≤ 3s | 50% 的问答在 3 秒内完成 |
| 端到端 P99 延迟 | ≤ 10s | 99% 的问答在 10 秒内完成 |
| 首 token 延迟 P50 | ≤ 1.5s | 从请求到首个 SSE message 事件的时间 |
| 错误率 | ≤ 1% | HTTP 非 2xx 或 SSE error 事件 |
| 吞吐量 | ≥ 2 req/s | 10 并发下的系统吞吐 |
| Token 消耗上限 | ≤ 4000 tokens/请求 | 单次问答 prompt+completion 总和 |

### 8.3 压测工具

推荐使用 **Locust**（Python 原生，支持 SSE 流式响应验证）：

```python
# 压测脚本示例
from locust import HttpUser, task

class ChatUser(HttpUser):
    @task
    def ask_question(self):
        with self.client.post(
            "/api/chat",
            json={"kb_id": 1, "question": "入职需要开通哪些账号？"},
            headers={"Authorization": f"Bearer {token}"},
            stream=True,
            catch_response=True
        ) as response:
            # 验证 SSE 流完整性
            events = parse_sse(response)
            if not has_event(events, "finish"):
                response.failure("未收到 finish 事件")
```

> TODO: [待实现] Locust 压测脚本 `backend/tests/locustfile.py`，模拟真实用户的问答行为（含等待间隔）。Phase 5 时执行。

---

## 9. 测试执行计划

| Phase | 测试活动 | 测试类型 | 产出 | 准入条件 |
|:---|:---|:---|:---|:---|
| Phase 1 | 认证模块单元测试 | 单元测试 | JWT / 密码哈希 / Service 逻辑 | Phase 2 准入 |
| Phase 1 | 认证 API 接口测试 | 接口测试 | 注册/登录 正常 + 异常用例 | Phase 2 准入 |
| Phase 1 | Schema 校验测试 | 单元测试 | RegisterRequest / LoginRequest 边界值 | Phase 2 准入 |
| Phase 1 | 前端组件测试 | 组件测试 | LoginPage / AppLayout / 路由守卫 | Phase 2 准入 |
| Phase 2 | 知识库 CRUD + 文档管理 API 测试 | 接口测试 | 正常 + 错误码覆盖 | Phase 3 准入 |
| Phase 2 | Celery 流水线测试 | 单元测试 | 幂等锁 / 解析容错 / 分块 / checkpoint | Phase 3 准入 |
| Phase 2 | 前端 KB/Doc 页面组件测试 | 组件测试 | 网格/表格渲染、交互、状态轮询 | Phase 3 准入 |
| Phase 2.5 | visibility Schema 校验测试 | 单元测试 | KnowledgeBaseCreate/Update visibility 字段校验 + 默认值 | ✅ |
| Phase 2.5 | KB 权限矩阵接口测试 | 接口测试 | public KB 非 owner 可读/不可写；private KB 非 owner 拒绝；admin 全局可读 + 管理写 | ✅ |
| Phase 2.5 | 公共 KB 列表接口测试 | 接口测试 | GET /public 分页 + 仅返回 public+active + 含 username | ✅ |
| Phase 2.5 | 文档接口权限矩阵测试 | 接口测试 | 上传/reprocess 仅 owner；查看/分块/删除 owner + admin；18 用例全覆盖 | ✅ |
| Phase 2.5 | 前端公共 KB 页组件测试 | 组件测试 | PublicKnowledgeList 渲染 + 无编辑/删除/新建按钮 | ✅ |
| Phase 3 | 检索器 + RRF 测试 | 单元测试 | 检索正确性 + RRF 排序验证 | Phase 4 准入 |
| Phase 3 | 问答 SSE API 测试 | 接口测试 | SSE 事件序列 + 错误码 | Phase 4 准入 |
| Phase 3 | 前端 ChatPage + SSE 解析测试 | 组件+单元测试 | 消息发送/流式渲染/停止/来源引用 | Phase 4 准入 |
| Phase 3 完成 | 离线检索评估 | 检索评估 | BM25 vs 向量 vs RRF 的 Recall@5/MRR 对比报告 | Phase 4 准入 |
| Phase 3 完成 | 回归测试集初版建立 | 回归测试 | 25-30 个固定问题 + 期望文档标注 | Phase 4 准入 |
| Phase 3 完成 | 人工答案评分（第 1 轮） | 人工评估 | 10 题 × 4 维度评分表 | Phase 4 准入 | ✅ 已完成（2026-06-04，4.38/5.0） |
| Phase 4 | 会话 CRUD API 接口测试 | 接口测试 | 会话 CRUD 正常流程 + 错误码 + 权限拒绝 | Phase 5 准入 |
| Phase 4 | 滑动窗口记忆测试 | 单元测试 | 各池子独立截断不互侵（History 超限/Retrieval 超限/同时超限） | Phase 5 准入 |
| Phase 4 | 多轮 RAG 回归测试 | 接口测试 | 5 Session × 23 轮全部通过：每轮检索召回 + 答案非空 + 引用有效 + RAG 未退化（详见 TEST_CASES.md §6.3） | ✅ 已完成（2026-06-09） |
| Phase 4 | 前端会话列表组件测试 | 组件测试 | Sidebar 会话 CRUD 交互 | Phase 5 准入 |
| Phase 4 | 错误处理测试 | 单元测试 | 异常→HTTP 状态码映射 / 生产环境堆栈屏蔽 / 未知异常兜底（3 用例） | Phase 5 准入 |
| Phase 4 | Refresh Token 测试 | 接口测试 | Token 刷新 / Rotation（旧 token 失效）/ 主动吊销（6 用例） | Phase 5 准入 |
| Phase 4 | 结构化日志测试 | 单元测试 | 请求入口/检索耗时/LLM 调用日志格式校验（3 用例） | Phase 5 准入 |
| Phase 4 完成 | 人工答案评分（第 2 轮） | 人工评估 | 5 Session 修正后平均综合分 **4.76/5.0** ✅ 远超 ≥ 4.0 目标。轮次均分 4.62/5.0（vs 第 1 轮 4.38 ↑ +0.24），RAG 保活性 5.0/5.0 满分 | ✅ 已完成（2026-06-09） |
| Phase 5 | 全量回归测试 | 回归测试 | 遍历完整测试集，检查召回/非空/来源/SSE/错误率 | 上线准入 |
| Phase 5 | 压测 | 性能测试 | Locust 4 场景，P50≤3s / P99≤10s。**压测完成后据此设定限流阈值** | 上线准入 |
| Phase 5 | Admin 接口测试 | 接口测试 | Admin 端点权限校验 + 数据聚合正确性（4 用例） | 上线准入 |
| Phase 5 | 限流测试 | 接口测试 | IP/用户级频率限制生效验证（阈值来自压测结果，3 用例） | 上线准入 |
| Phase 5 | 最终人工评分 | 人工评估 | 最终 10 题 × 4 维度评分，平均综合分 ≥ 4.0 | 上线准入 |
| Phase 6 | 高级功能测试 | 按需 | DashScope Rerank / 结构感知分块 / LLM 摘要压缩等 9 项（详见 TEST_CASES.md §7.4） | 不设时限 |

---

## 10. 相关文档

- [测试用例跟踪](TEST_CASES.md) — 各 Phase 测试用例清单与执行状态
- [产品需求文档](PRD.md) — 验收标准章节
- [架构设计文档](ARCHITECTURE.md) — 检索/问答流程细节
- [接口文档](../backend/docs/API.md) — `/api/chat` SSE 事件格式
- [开发指南](DEVELOPMENT.md)
- [开发排期](ROADMAP.md)
- [UI 设计规范](../frontend/docs/UIDESIGN.md)
