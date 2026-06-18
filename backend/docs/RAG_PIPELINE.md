# RAG Pipeline — 问答管线详细设计

| 属性 | 值          |
|:---|:-----------|
| 文档版本 | v1.0       |
| 最后更新 | 2026-06-16 |

本文档描述 DocMind 问答管线（RAG Pipeline）的完整设计，涵盖多路检索、Prompt 组装、问题重写、意图识别、句级修辞过滤、Evidence Review 门控、Evidence Highlight、三层证据审计、Trace 链路追踪、SSE 事件流等核心模块。

---

## 1. 问答管线总览

> Phase 3 实现单轮问答核心链路。Phase 4 加入多轮对话（会话记忆 + 问题重写），Phase 5 加入意图识别。

### 1.1 目标架构

```
用户提问
	    ↓
[Intent] 意图识别 → 判断类型（查知识库 / 闲聊 / 元问题）       ← [Designed: Phase 5]
	    ↓ （如果是查知识库）
[Rewrite] 问题重写 → 结合对话历史补全上下文              ← [Implemented]
	    ↓
[Retrieval] 多路检索 → 向量检索 + BM25 关键词检索       ← [Implemented]
	    ↓
[Fusion] RRF 融合排序 → 合并两路结果                     ← [Implemented]
	    ↓
[Rerank] 重排序 → DashScope Rerank API 精排              ← [Phase 5.5 ✅]
	    ↓
[修辞过滤] 句级修辞角色过滤 → 过滤引用性句子 + 返回 FilterStats 统计  ← [Phase 5.5 ADR-019]
	    ↓
[Evidence] 句级 BM25 定位 → 选出最佳证据句                        ← [Implemented]
	    ↓
[证据审查] Evidence Review → chunk 角色分类 + 门控决策                 ← [Phase 5.5 ADR-021]
	  ├─ ALLOW → 继续
	  └─ REJECT → 跳过 LLM，直接返回「未找到相关信息」
	    ↓
[Prompt] 组装 Prompt → 陈述/引用知识判断框架 + 检索结果            ← [Phase 5.5 升级]
	    ↓
[LLM] 调用 LLM → SSE 流式返回答案                        ← [Implemented]
	    ↓
[证据审计] 三层程序级审计 → 置信度标注                    ← [Phase 5.5 ADR-020]
```

## 2. 多路检索

### 2.1 向量检索

- 调用已有 `embedder.embed_chunks()` 将问题向量化（1024 维）
- `collection.query(query_embeddings=[vec], n_results=10, where={"kb_id": kb_id})`
- metadata 值为数值类型（int），入库和查询两端统一使用 int，无需类型转换

### 2.2 BM25 关键词检索

| 技术 | rank-bm25 (BM25Okapi) + jieba 分词 |
|:---|:---|

#### 索引生命周期（三级缓存）

```
文档终态（completed/success_with_warnings）
    ↓ Celery ingest task 末尾触发
DEL Redis key: bm25_tokens:{kb_id}  +  清除进程内缓存
    ↓ 下次查询时
get_bm25_index(kb_id):
  ├── L1: 进程内缓存（dict，TTL=60s）
  │   ├── 命中 → 直接返回 BM25Okapi 实例（不含 chunk 原文）（<1ms）
  │   ├── 大 KB 保护：chunk 数 > BM25_LOCAL_CACHE_MAX_CHUNKS 时跳过 L1
  │   └── 未命中 → 进入 L2
  ├── L2: Redis 缓存（async Redis，TTL=300s）
  │   ├── 命中 → json.loads → BM25Okapi(tokens) 实例化（~50ms～数秒）
  │   │   回填 L1（不超过阈值时）
  │   └── 未命中 → 进入 L3
  └── L3: 懒加载重建（MySQL → jieba → Redis → L1）
       1. SELECT content FROM chunks WHERE kb_id=? ORDER BY id
       2. [jieba.lcut(c.content) for c in chunks]  ← 最昂贵步骤
       3. SETEX bm25_tokens:{kb_id} 300 {"doc_ids":[...], "tokens":[[...],...], "section_info":[...]}
          ↳ 注意：不缓存 chunk 原文（contents），避免大 KB OOM
       4. BM25Okapi(tokens)
       5. 回填 L1（不超过阈值时）
  └── BM25 评分 → get_scores(jieba.lcut(question)) → top_k
  └── 按需取原文：SELECT content FROM chunks WHERE (doc_id, chunk_index) IN (...)
       ↳ 仅取 top_k 条（≤10），O(1) 而非 O(N)
```

| 事件 | 触发 | 操作 |
|:---|:---|:---|
| 文档入库完成 | Celery ingest 末尾 | `DEL bm25_tokens:{kb_id}` + 清除进程内缓存 |
| 文档删除完成 | Celery delete 末尾 | `DEL bm25_tokens:{kb_id}` + 清除进程内缓存 |
| reprocess 触发 | document_service | `DEL bm25_tokens:{kb_id}` + 清除进程内缓存 |
| 查询时缓存未命中 | `get_bm25_index()` | 懒加载重建（MySQL → jieba → Redis → 进程内缓存） |

#### 缓存结构

```json
{
  "doc_ids": [[101, 0], [102, 0], [103, 0]],
  "tokens": [["入职", "指南", "欢迎"], ["报销", "制度"], ["VPN", "配置"]],
  "section_info": [
    {"section_title": "§3.2 入职", "section_path": "HR > §3 > §3.2"},
    {"section_title": "§4.1 报销", "section_path": "财务 > §4 > §4.1"},
    {"section_title": "§5.1 VPN", "section_path": "IT > §5 > §5.1"}
  ]
}
```

> **内存优化（ADR-023）**：缓存中 **不包含 chunk 原文（contents）**。BM25 评分后仅对 top_k 条结果按需从 MySQL 取原文（`SELECT content FROM chunks WHERE (doc_id, chunk_index) IN (...)`，≤10 条），避免全库 chunk 原文驻留内存导致 OOM。

#### 设计要点

- **三级缓存**：进程内 dict（TTL=60s）→ Redis（TTL=300s）→ MySQL 懒加载
- **进程内缓存**：避免 Redis 网络 IO，cache hit 从 ~50ms 降至 <1ms
- **大知识库保护**：chunk 数超过 `BM25_LOCAL_CACHE_MAX_CHUNKS`（默认 5000）时跳过进程内缓存，仅使用 Redis 缓存（每次请求重建 BM25Okapi 后释放内存），避免 OOM
- **按需取原文**：chunk 原文不进入任何缓存层，BM25 评分后批量取 top_k 条（O(1)），彻底消除全库 contents 的 Python 字符串开销（大 KB 可达数百 MB）
- **async Redis**：FastAPI 异步接口避免阻塞事件循环（原同步调用导致 ~2.8s 阻塞）
  - **开发环境（Windows）**：`redis.Redis` 同步客户端 + `asyncio.to_thread()` 线程池包装
  - **生产环境（Linux）**：使用原生 `redis.asyncio.Redis` + `ConnectionPool`
- **Celery 保持同步**：Celery Worker 继续使用同步 `get_redis()`，`invalidate_bm25_cache` 提供同步/异步两个版本
- **缓存 `tokenized_corpus` 而非 pickle BM25Okapi 实例**：JSON 格式跨版本安全、Redis 友好、可人工排查
- **BM25Okapi 构造代价**：对小型 KB（<5000 chunks）极轻量（纯 NumPy 计算，<50ms）；大型 KB 重建时间随 chunk 数线性增长（20000 chunk ~2-5s），但内存峰值仅在请求期间，请求结束后释放
- **TTL=300s** 作为兜底：即使 Celery 未触发 DEL，缓存也会过期重建
- **最终一致性**：文档终态后才触发重建，避免处理中状态污染索引
- **内存监控**：大 KB 加载时打印 RSS 内存日志（MySQL 读取后 / 分词后 / BM25 构建后），用于 OOM 诊断

#### IDF 静默衰减风险

`rank-bm25` 的 IDF 基于语料初始化时固定，文档删除后不会自动衰减已不在语料中的词的 IDF。但对于 RAG 场景，IDF 偏差影响有限——BM25 结果仅作为 RRF 融合的一路信号，最终排序由双路融合 + Rerank 共同决定。

### 2.3 RRF 融合排序

```
score(doc) = Σ 1 / (k + rank_i(doc))   # k=60
```

其中 `k=60` 是平滑常数，降低单一排序中的极端排名对最终结果的过度影响。

---

## 3. Prompt 组装与 Token 预算

**策略**：chunking 阶段控制 + 软上限 + 相关性优先填充

| 层级 | 策略 | 实现 |
|:---|:---|:---|
| Chunking | 固定 chunk_size=1000 chars，overlap=150 | 已实现，Prompt 阶段不二次裁剪 |
| 检索后排序 | 保持 RRF 融合排序（相关性降序） | RRF 已按相关性分数降序排列，相关性优先于长度 |
| Prompt 组装 | 软上限 + 相关性优先填充 | 超预算时跳过当前 chunk 尝试下一个，而非直接 break |
| TopK 控制 | RRF → DashScope Rerank 精排 top_k=5（Phase 5.5） | 控制数量而非逐 chunk 截断 |

**Token 预算计算**（复用 chunker 中英文自适应算法）：
```python
def estimate_tokens(text: str) -> int:
    chinese_ratio = sum(1 for c in text if '一' <= c <= '鿿') / len(text)
    ratio = 1.5 if chinese_ratio > 0.3 else 4.0
    return int(len(text) / ratio)
```

**Prompt 模板结构**（对齐 ROADMAP.md §8.1）：
```python
SYSTEM_PROMPT = """你是一个企业知识库助手。请严格遵循以下规则。

【核心原则：陈述知识 vs 引用知识】
在回答前，你必须先判断每个来源的"写作目的"：
■ 陈述知识（可作为答案依据）：该段文字的主要目的是定义、说明、规定、描述某项事实...
■ 引用知识（不可作为答案依据）：该段文字只是把知识作为示例、测试数据、历史记录...

【判断方法】【拒答规则】【回答要求】
...（完整模板见 prompt_builder.py SYSTEM_PROMPT_TEMPLATE）

参考文档：
{context}

- 引用来源时标注 [来源N]（N 为文档编号）
- 请用中文回答"""

# messages 结构
[
    {"role": "system", "content": formatted_prompt},
    # Phase 4 加入 history（滑动窗口消息）
    {"role": "user", "content": question}
]
```

---

## 4. Query Rewrite（问题重写）

**背景**：Phase 4 初期将问题重写推迟到 Phase 5，假设「历史消息注入 LLM Prompt 后，LLM 自身可结合上下文消解指代」。多轮 RAG 回归测试（`regression_multi_turn_test.py`）证伪了这一假设：**检索发生在 LLM 之前**，检索器拿不到 history，当用户输入含代词/省略主语时，嵌入模型无法消解指代，导致检索出无关文档。

**结论**：问题重写必须前置于检索阶段。已实现于 `backend/app/rag/query_rewriter.py`，集成点在 `chat_service._validate_and_prepare()`。

### 4.1 触发策略

仅检查明确歧义信号词，不使用短问题阈值。中文问题天然短（「病假需要提供医院证明吗」14 字），短问题阈值会导致大量语义完整的独立问题被强制改写。

| 输入 | 历史 | 触发？ | 原因 |
|:---|:---|:---|:---|
| 「入职第一天需要做什么？」 | 无 | 否 | 无历史，无需 rewrite |
| 「新员工入职流程具体包含哪些步骤？」 | 有（不相关） | 否 | 无歧义信号词 |
| 「病假需要提供医院证明吗？」 | 有 | 否 | 14 字但语义完整，无歧义信号词 |
| 「它需要几个人参加？」 | 有 | 是 | 含代词「它」 |
| 「那请假呢？」 | 有 | 是 | 含「那」「呢」 |
| 「刚才说的 VPN，忘记密码怎么办？」 | 有 | 是 | 含「刚才」信号词 |

> **设计决策**：牺牲少数省略主语场景的改写，换取大多数短问题的稳定检索。

### 4.2 Rewrite Prompt

严格约束输出格式：将代词替换为对话历史中对应的实体，补全省略的主语或宾语，保持原问题的核心意图不变，只输出改写后的问题。

| 原始 question | History 上下文 | 改写后 |
|:---|:---|:---|
| 「它需要几个人参加？」 | User:「代码评审的标准是什么？」 | `代码评审需要几个人参加？` |
| 「不通过的话怎么办？」 | User:「……评审不通过需要……」 | `代码评审不通过怎么办？` |
| 「金额限制具体是多少？」 | User:「介绍一下公司的报销制度」 | `报销制度的金额限制是多少？` |

### 4.3 实现要点

| 要点 | 决策 | 原因 |
|:---|:---|:---|
| 触发方式 | 仅检查明确歧义信号词（13 个），不使用短问题阈值 | 正常路径零额外延迟 |
| History 范围 | 仅取最近 2 轮（4 条消息） | 消解指代只需最近一轮上下文 |
| 降级策略 | LLM 失败 → 返回原始 question | 不影响主流程可用性 |
| 输出约束 | Prompt 强调「只输出改写后的问题」 | 防止 LLM 输出解释性文字污染检索 query |
| deep_thinking | `False` | 改写是简单补全任务，无需深度思考 |
| 不落库 | 改写结果不持久化 | 改写是检索优化手段，非用户可见内容 |

### 4.4 已知局限

当前触发策略存在结构性盲区：**纯省略/隐含依赖**。问题语法完整但语义残缺（如「审批流程需要多长时间？」前轮讨论报销），不含任何信号词 → 改写不触发。

**后续优化方向：Retrieval-aware Rewrite** — 检索先行，结果差时再改写重检。检索质量本身就是最准确的 Rewrite 触发信号。

---

## 5. SSE 事件流与心跳机制

**实现方式**：手动 `StreamingResponse`（不用 `sse-starlette`），完全控制事件序列和心跳。

### 5.1 事件序列

> **权威定义**：[API.md §6.1](./API.md#61-sse-事件完整格式) — 包含全部 6 种 SSE 事件的字段表、wire format 示例、发送规则。

### 5.2 sources 引用过滤

> **权威定义**：[API.md §6.1 `event: sources`](./API.md#61-sse-事件完整格式) — 包含 sources 事件的 6 条发送规则（意图过滤、引用过滤、未找到抑制、零引用抑制、检索无结果、LLM 失败回退）。

### 5.3 心跳机制

每 15 秒发送 SSE 注释帧（`: ping\n\n`），浏览器忽略但保持连接，防止 Nginx/Cloudflare 代理超时断连。详见 [API.md §6 问答接口开头注释](./API.md#6-问答接口核心)。

### 5.4 thinking_content 处理

> **权威定义**：[API.md §6.1 `event: thinking`](./API.md#61-sse-事件完整格式) — 包含 thinking 事件的输出条件、落库策略、DeepSeek 参数映射。

---

## 6. 意图识别（Intent Classification）

**背景**：Phase 3 使用 `_is_casual_chat()` 正则 stopgap 覆盖高频闲谈场景。Phase 5 用 LLM 分类替换正则，采用**规则优先 + Flash 模型兜底**的两阶段架构。

### 6.1 分类体系

| 类别 | 标签 | 行为 | 示例 |
|:---|:---|:---|:---|
| 知识查询 | `KNOWLEDGE` | 走完整 RAG 链路 | 「报销制度是什么？」 |
| 闲谈 | `CASUAL` | 跳过检索，使用 `CASUAL_SYSTEM_PROMPT` → LLM 直接回复 | 「你好」「谢谢」 |
| 元问题 | `META` | 不调 LLM，直接返回固定模板响应 | 「你能做什么？」 |

> **设计决策：不做细粒度问题类型分类**。Phase 5 先做 3 类粗分类跑通链路，细粒度分类留给 Phase 6。

### 6.2 两阶段分类架构

```
用户问题
    │
    ▼
Stage 1: 规则分类（<1ms）
    │
    ├─ META      → 直接返回（regex 命中）
    ├─ CASUAL    → 直接返回（regex 命中）
    └─ UNKNOWN   → 进入 Stage 2
            │
            ▼
Stage 2: LLM 兜底（deepseek-v4-flash，~10% 流量）
    ├─ 返回有效标签 → Intent 枚举
    └─ 失败/无效标签 → 降级回退 _is_casual_chat() 正则
```

| 要点 | 决策 | 原因 |
|:---|:---|:---|
| Stage 1 规则 | `_is_meta_question()` + `_is_casual_chat()` 正则 | META/CASUAL 占 ~90% 流量，规则 <1ms 完成 |
| Stage 2 模型 | `deepseek-v4-flash`（非 pro） | flash 模型延迟 ~1-2s，分类任务简单无需 pro |
| 降级策略 | flash 失败 → 正则 → 保守 KNOWLEDGE | 「宁可查了没用，不可该查不查」 |

### 6.3 降级策略

```
classify_intent(question)
  │
  ▼
Stage 1: 规则分类（<1ms）
  ├─ META regex 命中 → Intent.META
  ├─ CASUAL regex 命中 → Intent.CASUAL
  └─ UNKNOWN → 进入 Stage 2
          │
          ▼
Stage 2: Flash 模型兜底（~1-2s）
  ├─ 成功 + 有效标签 → 返回 Intent 枚举
  └─ 失败/无效标签 → 降级回退 _is_casual_chat() 正则
        ├── 命中 → Intent.CASUAL
        └── 未命中 → Intent.KNOWLEDGE（保守策略）
```

### 6.4 已知局限

| 局限 | 说明 | 缓解 |
|:---|:---|:---|
| 分类边界模糊 | 「最近有什么新政策？」可能是闲谈也可能是知识查询 | 保守路由：歧义时走 KNOWLEDGE |
| 多语言混合 | 中英混合问题可能分类不准 | few-shot 示例覆盖 |
| 正则回退盲区 | 正则仅覆盖 6 类高频闲谈 | 分类 LLM 正常时正则仅作降级兜底 |

---

## 7. 句级修辞过滤 + Evidence Highlight

**背景**：旧方案 `_locate_preview()` 在 LLM 生成后从 `assistant_content` 提取 snippet 做子串匹配，有根本性缺陷。Phase 5 重构为 **Evidence Highlight**：将定位时机从「LLM 生成后」前移到「检索时」。

**Phase 5.5 新增句级修辞过滤**：在 Evidence Highlight 之前插入修辞角色过滤步骤，解决 Chunk 内部混合陈述句和引用句的污染问题（对齐 ROADMAP.md §8.2）。详见 [ADR-019](../../docs/decisions/ADR-019-句级修辞过滤.md)。

### 7.1 数据流

```
Vector + BM25 检索（chunk 级）
    ↓
RRF 融合 → Rerank
    ↓
【句级修辞过滤】← sentence_matcher.py detect_sentence_role() + filter_chunk_sentences()
  chunk 切句 → 逐句判断修辞角色（assertive/referential）→ 仅保留陈述句
  规则层：_REFERENTIAL_PATTERNS（示例/测试/用户提问/TODO 等显式标记）
  结构层：JSON/代码块内容 → 大概率是示例
  默认：陈述（宁可放过，不可错杀）
    ↓
【句级 BM25 定位】← sentence_matcher.py match_sentences()
  chunk 切句 → BM25Okapi(sentences) → 取 argmax → 记录 best_sentence + score
    ↓
Prompt 组装 → LLM 生成
    ↓
_build_sources()：matched_sentence → preview_text + preview_range
```

### 7.2 修辞过滤设计要点

| 要点 | 决策 | 原因 |
|:---|:---|:---|
| 过滤时机 | Rerank 后、BM25 定位前 | 先清除引用性句子，再做证据定位，提高证据质量 |
| 判断策略 | 规则层 + 结构层，不用 LLM | 零额外延迟（纯正则 + 字符串判断），确定性结果 |
| 回退策略 | 过滤后为空 → 返回原始 chunk | 宁可放过不可错杀，避免误删陈述知识 |
| 规则维护 | 手工维护 `_REFERENTIAL_PATTERNS` 正则列表 | 当前覆盖高频场景，后续可从审计日志自动挖掘 |
| 性能 | 每 chunk ~0.1ms | 纯正则匹配 + 字符串操作，5 chunks < 1ms |

### 7.3 Evidence Highlight 设计要点

| 要点 | 决策 | 原因 |
|:---|:---|:---|
| 定位时机 | Rerank 后、Prompt 前 | 确保 `used_chunks` 携带 `matched_sentence` |
| 切句策略 | 中文标点 `。！？!?\n` 正则切分 | 覆盖常见句末标点 |
| 搜索算法 | BM25Okapi（每 chunk 独立微型索引，3-8 句） | 复用已有依赖零新增 |
| 确定性 | 同一 question 永远返回同一 sentence | 纯算法，无 LLM 随机性 |
| 性能 | 每 chunk ~1ms | 5 chunks × 1ms = 5ms，无感知影响 |

### 7.4 SSE sources 事件格式

```json
{
  "chunks": [{
    "chunk_index": 1,
    "doc_name": "入职指南.pdf",
    "page": 3,
    "content": "新员工入职流程包括以下步骤：...",
    "preview_text": "入职流程包括以下步骤：第一步，填写个人信息表...",
    "preview_range": {"start": 5, "end": 205},
    "highlight_start": 14,
    "highlight_end": 38
  }],
  "confidence": "high",
  "confidence_note": ""
}
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| `chunks` | array | 引用的 chunk 列表（含 preview 和 highlight 信息） |
| `confidence` | string / 缺省 | 证据审计置信度：`high`（默认）/ `medium` / `low`，由三层审计计算（§9） |
| `confidence_note` | string / 缺省 | 置信度说明，仅在 medium/low 时非空，描述审计发现的问题 |

### 7.5 前端渲染规格

前端 `getSourcePreviewHtml(src)` 基于后端提供的 `highlight_start` / `highlight_end` 做纯切片渲染，**零匹配逻辑**。旧 snippet 体系（~80 行）已全部删除。

### 7.6 降级策略

| 降级场景 | 处理 |
|:---|:---|
| chunk 无有效句子（纯标点/空白） | `matched_sentence = None` → `preview_text = None` |
| chunk.content 为空 | `matched_sentence = None` → `preview_text = None` |
| 检索结果为空 | `match_sentences()` 直接返回，无 chunk 可定位 |

### 7.7 已知局限

| 局限 | 说明 | 缓解 |
|:---|:---|:---|
| BM25 关键词偏好 | 倾向于选择含 question 关键词的句子 | BM25 仅用于句子选择，chunk 级已由双路保证 |
| 纯算法无法感知上下文 | 句级 BM25 对每句独立评分，不考虑句间逻辑 | chunk 级 RRF 已保证 chunk 级相关性 |

---

## 8. Trace 链路追踪

> **设计原则**：Trace 不承担审计职责，仅承担性能观测。完整对话内容通过 `conversation_id` JOIN 查询获取。

### 8.1 数据模型：`traces` 表

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| `id` | BIGINT PK | 自增主键 |
| `trace_id` | VARCHAR(64) UNIQUE | UUID 追踪 ID |
| `user_id` | BIGINT FK | 用户 ID |
| `conversation_id` | BIGINT FK | 会话 ID（可为空） |
| `kb_id` | BIGINT | 知识库 ID |
| `question` | TEXT | 用户问题 |
| `status` | VARCHAR(32) | success / error / partial |
| `intent_type` | VARCHAR(32) | KNOWLEDGE / CASUAL / META |
| `intent_method` | VARCHAR(32) | regex / llm_flash / llm_pro |
| `response_mode` | VARCHAR(32) | RAG / DIRECT_LLM / META / CASUAL / FALLBACK / REJECT |
| `total_duration_ms` | INT | 总耗时（毫秒） |
| `intent` / `rewrite` / `retrieve` / `rerank` / `evidence_review` / `generate` | JSON | 各阶段详情 |
| `error_message` | TEXT | 错误信息（status=error 时） |
| `created_at` | DATETIME | 创建时间（UTC） |

> **顶层字段设计**：`intent_type`、`intent_method`、`response_mode` 作为独立列存储，避免聚合统计时使用 `JSON_EXTRACT` 的性能问题。

### 8.2 JSON 字段结构

| 阶段 | 关键字段 | 说明 |
|:---|:---|:---|
| `intent` | intent_type, method, metadata.model, metadata.confidence | 意图分类结果和方法 |
| `rewrite` | original_question, rewritten_question, metadata.model, metadata.tokens | 改写前后对比 + Token 消耗 |
| `retrieve` | vector, bm25, fusion, match_sentence 各自独立计时 | 细粒度拆分 |
| `rerank` | input_count, output_count, metadata.reranker | 输入输出数量 + reranker 类型 |
| `generate` | model, ttft_ms, input_tokens, output_tokens, finish_reason | LLM 生成指标，**不存 output** |
| `evidence_review` | summary(decision/assertive_count/referential_count/rejected_count/reason), chunk_decisions[], sentence_review, post_audit | 证据审查阶段详情（chunk 分类 + REJECT 决策 + post-LLM 审计补填），chunk_decisions 上限 5 条 |

### 8.3 埋点集成点

```
chat_service._validate_and_prepare()
    ↓
[Intent]  classify_intent()     → trace.intent
    ↓
[Rewrite] rewrite_query()       → trace.rewrite
    ↓
[Retrieval] vector + BM25 + RRF → trace.retrieve
    ↓
[Rerank]  reranker.rerank()     → trace.rerank
    ↓
[LLM]     stream_chat()         → trace.generate
    ↓
trace.record() 写入 traces 表
```

### 8.4 索引设计

```sql
UNIQUE INDEX idx_trace_id (trace_id)
INDEX idx_created_at (created_at)
INDEX idx_created_status (created_at, status)
INDEX idx_created_intent (created_at, intent_type)
INDEX idx_created_response (created_at, response_mode)
INDEX idx_user_created (user_id, created_at)
```

### 8.5 API 设计

| 端点 | 方法 | 说明 |
|:---|:---|:---|
| `/api/admin/traces` | GET | Trace 列表（分页+筛选） |
| `/api/admin/traces/{trace_id}` | GET | Trace 详情 |
| `/api/admin/stats/traces` | GET | Trace 统计 |

---

## 9. 三层证据审计（Evidence Auditor）

**背景**：LLM 以「生成式补全」模式工作，看到与问题相关的文字就默认作为答案输出。v2.1 方案让 LLM 自我评估证据状态（`EVIDENCE_STATUS`），存在根本逻辑漏洞——证据状态的判断者和答案的生成者是同一个模型。v3.0 改为**程序级三层审计**：不让模型证明自己没有幻觉，而让系统验证每一句结论都能回溯到可审计的证据。详见 [ADR-020](../../docs/decisions/ADR-020-三层证据审计.md)。

### 9.1 三层审计架构

```
LLM 生成完成 → assistant_content 完整文本
    ↓
【第一层：引用存在性检查】
  正则匹配 [来源N] 标注 → has_citation + cited_indices
  答案含实质性内容但零引用 → 大概率编造
    ↓
【第二层：来源一致性检查】
  统计引用涉及的唯一文档数 → consistency_status
  1 个文档 → consistent | 2 个 → acceptable | 3+ → dispersed（可疑）
    ↓
【第三层：句级证据回溯】
  对答案切句 → jieba 提取关键词 → 在 used_chunks 中搜索匹配
  ≥50% 事实句无来源支撑 → unsupported | ≤50% → partial | 0% → supported
    ↓
【综合置信度】
  ≥2 问题 or unsupported → low | 1 问题 → medium | 无问题 → high
```

### 9.2 设计要点

| 要点 | 决策 | 原因 |
|:---|:---|:---|
| 执行时机 | LLM 流完成后、sources 事件构建阶段 | 不影响 SSE 流输出延迟，审计结果附加到 sources 事件 |
| 审计粒度 | 三层独立检查，综合计算 | 每层各自发现不同维度的问题 |
| 关键词提取 | jieba 分词 + top-3 长词 | 复用已有依赖，长词区分度高 |
| 匹配阈值 | ≥2/3 关键词命中即认为有证据 | 平衡精确度和召回率 |
| 降级策略 | 审计执行失败 → 跳过，不影响 sources 发送 | 审计是增强功能，不应阻断主流程 |

### 9.3 置信度输出

| `confidence_level` | 含义 | 前端行为 |
|:---|:---|:---|
| `high` | 三层审计均无问题 | 正常展示，无额外提示 |
| `medium` | 有一项问题（如零引用或部分断言无证据） | 黄色警告：「以下答案部分内容可能不准确，请注意核实」 |
| `low` | 两项以上问题或证据状态 unsupported | 黄色警告：「以下答案可能存在偏差，建议核实原始文档」 |

### 9.4 已知局限

| 局限 | 说明 | 缓解 |
|:---|:---|:---|
| 关键词匹配精度 | jieba 分词 + 子串匹配可能漏判或误判 | 仅作为置信度标注，不阻断答案输出 |
| 不检测语义正确性 | 仅检查关键词可追溯性，不验证事实正确性 | Phase 6 可考虑接入 NLI 模型做语义验证 |
| 引用格式依赖 | 第一层依赖 LLM 输出 `[来源N]` 格式 | LLM 未遵守格式时退化为无引用检测 |

---

## 10. 问答核心逻辑（伪代码）

```python
# chat_service.py（入口 + 校验）+ sse_stream.py（SSE 流生成）核心流程
async def chat(question, conversation_id, kb_id, deep_thinking, db, current_user):
    # 0. 会话自动创建
    if not conversation_id:
        conv = Conversation(user_id=current_user.id, kb_id=kb_id)
        db.add(conv)
        await db.flush()
        conversation_id = conv.id
    else:
        conv = await db.get(Conversation, conversation_id)

    # 0. 保存用户消息
    user_msg = Message(conversation_id=conv.id, role="user", content=question)
    db.add(user_msg)

    # 1. 意图识别
    intent = await classify_intent(question)
    if intent == Intent.META:
        raise MetaQuestionException(question)
    skip_retrieval = (intent == Intent.CASUAL)

    # 2. 问题重写（仅 KNOWLEDGE 路径，仅检测到歧义时）
    if not skip_retrieval and needs_rewrite(question, history_messages):
        question = await rewrite_query(question, history_messages)

    # 3. 多路检索
    if not skip_retrieval:
        query_vec = await embedder.embed_query(question)
        vector_results = await vector_retriever.search(query_vec, kb_id, top_k=10)
        bm25_results = await bm25_retriever.search(question, kb_id, top_k=10)
        merged = rrf_fusion(vector_results, bm25_results, k=60)
        reranked = await reranker.rerank(question, merged, top_k=5)
        # 句级修辞过滤（Phase 5.5 ADR-019）→ 返回 FilterStats 统计
        filter_stats_map = {}
        for r in reranked.results:
            r.content, stats = filter_chunk_sentences(r.content)
            filter_stats_map[r.chunk_index] = stats
        reranked = match_sentences(reranked, question)  # Evidence Highlight
    else:
        reranked = []
        filter_stats_map = {}

    # 3.5 证据审查 + 门控（Phase 5.5 ADR-021）
    evidence_result = review_evidence(reranked, filter_stats_map)
    if evidence_result.decision == "REJECT":
        # 无陈述性证据 → 跳过 LLM，直接返回「未找到相关信息」
        return StreamingResponse(_generate_reject_response(...))

    # 4. 拼 Prompt + LLM SSE 流式输出（仅 ALLOW 路径）
    prompt_messages = prompt_builder.build(question, reranked, history=history_messages)
    # ... SSE StreamingResponse ...
    # LLM 流完成后：
    
    # 5. 三层证据审计（Phase 5.5 ADR-020）
    audit_result = audit_evidence(assistant_content, prompt_result.used_chunks)
    # → 补填到 trace.evidence_review.post_audit
    # → sources 事件含 confidence / confidence_note 字段
```

---

## 11. Chunk 元数据增强与章节号 BM25 Boost（§8.7 + §8.8）

### 11.1 Chunk 元数据增强（§8.7）

**目标**：为每个 chunk 标注所属章节标题和路径，帮助 LLM 在判断陈述/引用知识时获得更多上下文。

#### 数据流

```
文档
  ↓
[parser.py] DOCX 标题样式 → Markdown # 标记
  ↓ full_text（含 # 标题）
[chunker.py] detect_sections() → 扫描 #/##/### 标题
  ↓ sections: [(offset, level, title), ...]
[chunker.py] resolve_section(offset, sections) → (section_title, section_path)
  ↓ 写入 ChunkResult.section_title / section_path
[tasks.py] 写入 Chunk.metadata_ JSON → {"page": N, "section_title": "...", "section_path": "..."}
  ↓ 写入 ChromaDB metadata（5 字段）
[retriever.py] _parse_results() → RetrievalResult.section_title / section_path
  ↓ RRF fusion 保留
[prompt_builder.py] _format_chunk_reference() → "文档: X | 章节: Y | 页码: Z"
```

#### 章节检测规则

| 来源 | 检测方式 | 示例 |
|:---|:---|:---|
| Markdown | `^(#{1,6})[^\S\n]+(.+)$` 正则 | `## 1.1 背景` → level=2, title="1.1 背景" |
| DOCX | `_docx_heading_to_markdown()` 样式→Markdown | Heading 1 → `# 标题`; Heading 2 → `## 标题` |
| PDF/TXT | 不支持 | section 字段为 None |

#### 章节路径构建

```
# 概述
## 环境配置       → section_title="环境配置", section_path="概述 > 环境配置"
### 数据库       → section_title="数据库", section_path="概述 > 环境配置 > 数据库"
## 部署          → section_title="部署", section_path="概述 > 部署"（同级替换）
```

### 11.2 章节号 BM25 Boost（§8.8）

**目标**：当用户提问中包含章节号时（如「§3.2」「8.2.1」「第四章」），对匹配章节的 chunk 做 BM25 分数加权，提升检索命中率。

#### 章节号检测模式

| 模式 | 正则 | 示例输入 | 检出 |
|:---|:---|:---|:---|
| § 符号引导 | `§\s*(\d+(?:\.\d+)*)` | 「§3.2 限流」 | `["3.2"]` |
| 显式节编号 | `第\s*(\d+(?:\.\d+)+)\s*节` | 「第4.7节」 | `["4.7"]` |
| 中文章节 | `第([一二三四五六七八九十百千]+)[章节]` | 「第四章」 | `["4"]` |
| 裸数字章节号 | `(?<![a-zA-Z§第])(\d+\.[\d.]+)(?![a-zA-Z])` | 「8.2.1」 | `["8.2.1"]` |

#### Boost 逻辑

```
detect_section_numbers(question) → ["3.2"]
    ↓
对每个 chunk 的 section_info:
    match_section_numbers(section_title, section_path, ["3.2"])
      → "3.2" in "§3.2 限流配置" → True
    ↓
BM25 分数加权：
  - 正分 → score × BM25_SECTION_BOOST_FACTOR（默认 2.0）
  - 负分 → score ÷ BM25_SECTION_BOOST_FACTOR（向零靠近，减少惩罚）
```

#### 缓存结构扩展

```json
{
  "doc_ids": [[1, 0], [1, 1]],
  "tokens": [["入职", "指南"], ["报销", "制度"]],
  "section_info": [
    {"section_title": "§3.2 限流", "section_path": "架构 > §3 > §3.2"},
    {"section_title": "§4.1 数据库", "section_path": "架构 > §4 > §4.1"}
  ]
}
```

> **注意**：chunk 原文（contents）不进入缓存（ADR-023），BM25 评分后按需取 top_k 条。
>
> **向后兼容**：旧缓存无 `section_info` 字段时 `data.get("section_info", [])` 返回空列表，boost 逻辑自动跳过。旧缓存含 `contents` 字段时自动忽略（不参与新逻辑）。

---

## 12. 相关源文件

| 文件 | 职责 |
|:---|:---|
| `backend/app/services/chat_service.py` | 问答入口编排（chat/get_selectable_kbs）+ 校验准备 + re-export 兼容层 |
| `backend/app/services/chat_helpers.py` | 问答辅助函数（历史加载/标题生成/引用提取/sources 构建） |
| `backend/app/services/sse_stream.py` | SSE 流生成器 + 固定响应（meta/reject）+ 消息持久化 |
| `backend/app/rag/query_rewriter.py` | Query Rewrite 触发判断 + LLM 改写 |
| `backend/app/rag/intent.py` | 意图分类（规则 + Flash 模型） |
| `backend/app/rag/sentence_matcher.py` | 句级修辞过滤 + Evidence Highlight 句级 BM25 定位 |
| `backend/app/rag/evidence_auditor.py` | 三层证据审计（引用存在性 + 来源一致性 + 句级证据回溯） |
| `backend/app/rag/evidence_reviewer.py` | Evidence Review 门控（chunk 角色分类 + ALLOW/REJECT 决策） |
| `backend/app/rag/retriever.py` | 向量检索 |
| `backend/app/rag/bm25.py` | BM25 关键词检索 + 三级缓存 |
| `backend/app/rag/fusion.py` | RRF 融合排序 |
| `backend/app/rag/reranker.py` | Rerank（DashScope Rerank API 精排） |
| `backend/app/rag/prompt_builder.py` | Prompt 组装 |
| `backend/app/rag/trace_recorder.py` | Trace 上下文管理器 |
| `backend/app/ingest/delete_tasks.py` | 文档/知识库异步删除 Celery 任务 |
| `backend/app/core/llm.py` | LLM 调用封装（流式/非流式） |

---

## 13. 相关文档

- [架构设计文档](../../docs/ARCHITECTURE.md) — 技术选型、系统架构、基础设施
- [接口文档](API.md) — REST 接口定义、SSE 事件格式、错误码
- [数据库设计文档](DATABASE.md) — 索引策略、Trace 表 JSON 字段
- [前端交互文档](../../frontend/docs/FRONTEND.md) — SSE 消费、聊天界面状态机
- [测试策略文档](../../docs/tests/TESTING.md) — 检索评估、人工评分、压测指标
- [开发排期](../../docs/ROADMAP.md) — Phase 顺序、任务依赖