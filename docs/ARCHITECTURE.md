# ARCHITECTURE — 架构设计文档

| 属性 | 值 |
|:---|:---|
| 文档版本 | v0.38 |
| 最后更新 | 2026-06-11 |
| 作者 | yuz |
| 状态 | 进行中（Phase 5 实现阶段 — 意图识别 ✅ / sources 预览 ✅ / Evidence Highlight ✅ / Admin 后端 ✅） |

---

## 当前实现状态说明

本文档包含已实现能力、当前阶段设计、最终目标架构三类内容，使用以下标记区分：

| 标记 | 含义 |
|:---|:---|
| `[Implemented]` | 当前已实现并可用 |
| `[Planned: Phase X]` | 计划在 Phase X 实现 |
| `[Target Architecture]` | 最终目标态，非当前状态 |

**当前开发进度**：Phase 4（会话与记忆 + 基础设施加固）已全部完成，进入 Phase 5。详见 [ROADMAP.md](ROADMAP.md)。

---

## 1. 技术选型

| 层面 | 技术 | 说明 | 状态 |
|:---|:---|:---|:---|
| 后端框架 | FastAPI | 异步 Python Web 框架，原生支持 SSE | [Implemented] |
| AI 编排 | LangChain | RAG 链路编排，但不依赖其高级封装 | [Implemented] |
| LLM | DeepSeek (OpenAI 兼容接口) | 支持 OpenAI / 通义千问 / DeepSeek 等互换 | [Implemented] |
| Embedding | DashScope text-embedding-v3 | 1024 维向量，中文优化 | [Implemented] |
| 向量数据库 | ChromaDB | 嵌入式运行，零配置，轻量级场景首选 | [Implemented] |
| 关系数据库 | MySQL + aiomysql | 业务数据持久化 | [Implemented] |
| 异步 ORM | SQLAlchemy 2.0 async | Mapped 类型注解 + async session | [Implemented] |
| 缓存 | Redis | 会话缓存 + Celery broker | [Implemented] |
| 异步入库 | Redis + Celery | 文档入库异步任务队列 | [Implemented] |
| 文档解析 | PyPDF2 + python-docx | 多格式文档统一提取纯文本 | [Implemented] |
| 智能分块 | RecursiveCharacterTextSplitter | 固定大小分块，分隔符优先级切分 | [Implemented] |
| 关键词检索 | rank-bm25 (BM25Okapi) + jieba 分词 | 成熟库，支持自定义 tokenizer（见 §7.2） | [Implemented] |
| 文件存储 | 本地磁盘（可扩展至 OSS） | 抽象 StorageBackend 接口，当前本地实现 | [Implemented] |
| 流式输出 | SSE (Server-Sent Events) | 实时推送 LLM 生成内容 | [Implemented] |
| 前端框架 | Vue 3 + Vite | Composition API + SFC | [Implemented] |
| UI 组件库 | Element Plus | 企业级 Vue 3 组件库 | [Implemented] |
| 状态管理 | Pinia | Vue 3 官方推荐 | [Implemented] |
| 前端语言 | JavaScript | SFC + JS（非 TypeScript），见 §7.4 | [Implemented] |
| Markdown 渲染 | markdown-it | 问答内容渲染 | [Implemented] |
| HTTP 客户端 | Axios | 前端请求封装 | [Implemented] |
| 前端路由 | Vue Router | SPA 路由管理 | [Implemented] |
| 图标库 | Font Awesome 6 Free | UI 图标统一方案 | [Implemented] |
| 时区策略 | 四层 UTC 统一 | DB(UTC) → 后端(`datetime.now(timezone.utc)`) → API(ISO 8601+`+00:00`) → 前端(`new Date()` 本地显示)，详见 §12 | [Implemented] |
| 限流 | 固定窗口计数器 + Redis | IP/用户级频率限制，阈值压测后确定，详见 §13.2 | [Planned: Phase 5] |
| 部署方案 | Docker Compose + Nginx | 5 服务编排（MySQL/Redis/Backend/Celery/Nginx），详见 §13.1 | [Planned: Phase 5] |
| 监控告警 | 结构化日志 → Loki + Grafana | 应用级指标 + LLM 调用监控，详见 §13.3 | [Planned: Phase 5] |

---

## 2. 系统架构概览

### 2.1 目标架构 [Target Architecture]

```
┌──────────────────────────────────────────────────────────────┐
│                        前端 (Vue 3)                           │
│  ChatPage  │  LoginPage  │  admin/  │  Sidebar  │  SSE 解析  │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTP + SSE
┌──────────────────────────▼───────────────────────────────────┐
│                      FastAPI 后端                             │
│                                                              │
│  api/auth  api/kb  api/doc  api/chat  api/admin              │
│     │         │       │        │         │                   │
│  services/   services/  services/  services/  services/      │
│     │              │         │        │                      │
│  ┌──▼──────────────▼─────────▼────────▼──────────────────┐   │
│  │                   RAG 核心（问答链路）                   │   │
│  │  Intent → Rewrite → Retriever → RRF → Rerank → Prompt  │   │
│  └────────────────────────┬───────────────────────────────┘   │
│                           │                                   │
│  ┌──────────┬─────────────┼──────────────┬────────────────┐  │
│  │ ChromaDB │   MySQL     │    Redis     │  File Storage  │  │
│  │ (向量)   │  (业务数据)  │  (缓存/队列) │  (文档文件)    │  │
│  └──────────┴─────────────┴──────────────┴────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              Celery Worker（异步入库）                  │    │
│  │  Parser → Chunker → Embedder → ChromaDB + MySQL       │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 当前实现 [Phase 2.5 — 可见性重构]

```
┌──────────────────────────────────────────────────────────────┐
│                        前端 (Vue 3)                           │
│      LoginPage  │  admin/ (KnowledgeList + DocumentList)     │
│                  │  Sidebar  │  AppLayout                     │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTP
┌──────────────────────────▼───────────────────────────────────┐
│                      FastAPI 后端                             │
│                                                              │
│  api/auth ✅  api/kb ✅  api/doc ✅  api/chat ✅              │
│     │            │           │                                │
│  auth_service  kb_service  document_service                  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              Celery Worker（异步入库）                  │    │
│  │  Parser ✅ → Chunker ✅ → Embedder ✅ → Vector Store ✅│    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌──────────┬─────────────┬──────────────┬────────────────┐  │
│  │ ChromaDB │   MySQL     │    Redis     │  File Storage  │  │
│  │ (就绪)   │  (6表就绪)   │  (锁/队列)   │  (本地存储)    │  │
│  └──────────┴─────────────┴──────────────┴────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. 核心功能模块

### 3.1 模块总览：业务痛点 → 技术方案

| 业务痛点 | 对应模块 | 技术方案 | 效果 | 状态 |
|:---|:---|:---|:---|:---|
| 文档格式五花八门（PDF/Word/MD） | **文档解析** | PyPDF2 + python-docx | 统一提取纯文本 | [Implemented] |
| 完整文档太长，无法直接检索 | **智能分块** | 固定大小分块，重叠窗口保留上下文 | 检索粒度精准，不丢上下文 | [Implemented] |
| 大文件（100页PDF）上传后同步处理，用户等很久 | **异步入库** | Redis + Celery 异步任务 | 上传即返回，后台处理 | [Implemented] |
| 关键词搜索"墨盒怎么换"找不到"打印机耗材更换" | **多路检索** | 向量检索（语义）+ BM25（关键词）+ RRF 融合 | 召回率大幅提升 | [Implemented] |
| 搜出来的结果排序不准 | **Rerank 重排序** | 当前 NoopReranker 占位，后续 DashScope Rerank 精排 | 相关文档排在前面 | [Implemented] |
| 用户连续提问"怎么申请"，系统不知道在问什么 | **问题重写** | LLM 结合对话历史补全指代和上下文 | 多轮对话不丢失意图 | [Implemented] |
| 用户问"今天天气"走知识库检索是浪费 | **意图识别** | LLM 分类：知识查询 / 闲聊 / 元问题 | 路由到正确处理分支 | [Designed: Phase 5] |
| 长对话 30 轮后 Token 超限 | **会话记忆** | 滑动窗口 + Token 预算四池子分拆独立截断 | 记忆不丢，Token 受控，RAG 不退化 | [Implemented] |

### 3.2 模块树

```
DocMind
├── 文档入库（Ingestion）
│   ├── 文档上传 & 格式解析
│   ├── 文本分块策略
│   ├── Embedding 向量化
│   └── 向量入库（ChromaDB）
├── 智能问答（Chat）
│   ├── 意图识别
│   ├── 问题重写
│   ├── 多路检索（向量 + BM25）
│   ├── RRF 融合排序
│   ├── Rerank 重排序
│   ├── Prompt 组装 & LLM 调用
│   └── SSE 流式输出
├── 会话管理（Session）
│   ├── 多轮对话上下文
│   ├── 滑动窗口记忆
│   └── 会话 CRUD
├── 知识库管理（Knowledge Base）
│   ├── 知识库 CRUD
│   ├── 文档列表 & 状态
│   └── 分块可视化
└── 意图识别（Intent）
    ├── 意图分类（知识查询 / 闲聊）
    └── 问题重写（多轮上下文补全）
```

---

## 4. 文档入库流程

### 4.0 文档状态机

使用 `DocumentStatus(str, Enum)` 统一管理状态，前后端共享枚举值（详见 DATABASE.md §2.3）。

```
uploaded → parsing → chunking → embedding → vector_storing → completed
              ↓         ↓          ↓            ↓
          ───────────→ failed ←───────────────
              ↓         ↓          ↓            ↓
          success_with_warnings / partial_failed
```

**非终态**（允许轮询/retry）：`uploaded` `parsing` `chunking` `embedding` `vector_storing`

**终态**（`TERMINAL_STATUSES`）：`{completed, success_with_warnings, partial_failed, failed}`

**reprocess 触发**：仅 `partial_failed` / `failed` 允许重新处理。

---

### 4.1 入库流程图

```
用户上传文档
    ↓
FastAPI 接收文件:
  - 格式校验（pdf/docx/md/txt，拒绝 .doc）
  - 大小校验（≤ 50MB）
  - 幂等检查（Redis SET NX）
  - 同名检查（kb_id + filename）
    ├── 无同名 → 保存文件 + 创建记录(status=uploaded)
    ├── 同名 + 处理中 + force=false → 拒绝 E2011
    ├── 同名 + 处理中 + force=true → 拒绝 E2012（无法覆盖处理中文档）
    └── 同名 + 终态 + force=true → 旧文档标记 deleting → commit → dispatch delete_document.delay()
                              → 创建新记录(status=uploaded)
    ↓
dispatch Celery Task: ingest_document(doc_id)
    ↓
立即返回 {"doc_id": 123, "status": "uploaded"} 给前端
    ↓
Celery Worker 异步执行入库流水线:
  Parser → Chunker → Embedder (batch + checkpoint) → Vector Store (batch)
    ↓
每阶段更新 current_stage + last_success_batch（断点恢复）
    ↓
终态判定:
  - 全部成功 → completed
  - 失败 < 20% → success_with_warnings
  - 失败 20-50% → partial_failed
  - 失败 > 50% → failed
    ↓
MySQL chunk_count 事务更新 + kb.chunk_count 同步更新
```

> **注意**：Celery Worker crash 后重启，可根据 `current_stage` 和 `last_success_batch` 从断点恢复，不重复处理已成功的步骤/批次。
> 
> **reprocess 流程**：仅 `partial_failed` / `failed` 终态允许触发。流程为：`collection.delete(where={"doc_id": doc_id})` 清理 ChromaDB 旧向量 → 删除 MySQL 旧 chunk 记录（FK CASCADE）→ 重置 status 为 uploaded → 重新 dispatch `ingest_document`。必须在重置状态前清理 ChromaDB，否则新文档分块数少于旧文档时残留向量无法被覆盖。

---

### 4.2 分块策略

- **算法**：`RecursiveCharacterTextSplitter`
- **分隔符优先级**（从宽到窄逐级切分）：
  ```python
  separators = ["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""]
  #            段落      换行   中文句号 感叹号  问号  英文句号 感叹号 问号  空格  字符级
  ```
  > `RecursiveCharacterTextSplitter` 的 `separators` 参数是**精确字符串匹配**，而非正则或字符类。
  > 旧版文档写作 `["\n\n", "\n", "。！？", ".!?", " ", ""]`，其中 `"。！？"` 作为 3 字符子串在真实文本中几乎不会连续出现，无法在中文标点处切分。因此展开为独立字符，使 splitter 能在每个句号/感叹号/问号处正确断句。
- **keep_separator**：`True`（分隔符保留在 chunk 末尾，中文场景下保持语义完整性，如 `"他说。"` 不会被截断为 `"他说"`）
- **chunk_size**：`800~1200` 字符（默认 `1000`，字符估算，不用精确 token）
- **chunk_overlap**：`150` 字符（≈50 tokens，按 1 token ≈ 1.5-2 中文字符）
- **Token 估算**：`int(len(content) / 1.5)` 字符数估算（不引入 tiktoken）；Embedding 完成后 DashScope API 返回的 `usage.total_tokens` 回写 `chunk.token_count` 覆盖估算值
- **[Planned: Phase 3]** 结构感知分块：Markdown 标题层级感知，Phase 2 仅做固定大小分块

---

### 4.3 ChromaDB 批量写入

- **批次大小**：配置化 `CHROMA_BATCH_SIZE=100`（100~500 chunks/batch）
- **禁止单条循环**：避免高频小写入导致 IO 抖动
- **代码模板**：
  ```python
  for batch in batches(chunks, settings.CHROMA_BATCH_SIZE):
      collection.add(
          documents=[c.content for c in batch],
          embeddings=[c.embedding for c in batch],
          metadatas=[c.metadata for c in batch],
          ids=[c.chroma_id for c in batch]
      )
  ```

### 4.4 Embedding 批量与重试

- **批次大小**：`EMBED_BATCH_SIZE=10`（配置化，DashScope text-embedding-v3 单次上限 10 条）
- **重试**：`max_retries=5`，指数退避（1s → 2s → 4s → 8s → 16s）
- **批次级 checkpoint**：失败时从当前批次恢复，不重新处理已成功的批次
- **失败清理**：ChromaDB `add()` 非原子操作，任一 batch 失败 → 清理所有 batch 数据 → 标记 FAILED，保证 MySQL 与 ChromaDB 一致

### 4.5 KB/文档异步删除

> **[Implemented] 标记 deleting + 返回 202 已实现；[Implemented] Celery Worker 异步清理 ChromaDB 向量 + 磁盘文件 + 物理 DELETE 已实现（delete_document / delete_kb 任务）。**

**删除流程**：
```
接口层: status = deleting → 返回 202 Accepted
         ↓
Celery Worker（异步）:
  1. collection.delete(where={"doc_id": doc_id})  — 清理 ChromaDB 向量
  2. 删除磁盘文件（uploads/{kb_id}/{doc_id}/ 目录）
  3. DELETE FROM documents WHERE id=?  — 物理删除文档记录
     └─ FK ON DELETE CASCADE 自动级联删除 chunks
  4. UPDATE knowledge_bases SET
       doc_count = GREATEST(0, doc_count - 1),
       chunk_count = GREATEST(0, chunk_count - N)  — 原子递减计数
```
> **注意**：`chunk_count` / `doc_count` 须在物理删除文档后使用 `func.greatest(0, col - N)` 原子递减，防止并发场景下计数为负。
> 当前 Celery Worker 已定义 `delete_document` 任务骨架，实际清理逻辑待后续任务实现。

### 4.6 Celery 幂等性

- **幂等键格式**：`doc_lock:{doc_id}`（ingest 与 delete 共享互斥锁，防止并发冲突）
- **实现**：Redis 分布式锁 `SET key "locked" EX 600 NX`
- **锁过期时间**：600s（与 `soft_time_limit` 对齐）
- **触发规则**：
  | 场景 | 行为 |
  |:---|:---|
  | 无锁 | 正常创建任务 |
  | 有锁 + 运行中 | 拒绝，返回 E2011「文档正在处理中」 |
  | 有锁 + Worker crash | 等待锁过期后自动允许重新触发 |
  | 终态 + 无锁 + reprocess | 允许重新触发（清理旧数据） |

### 4.7 chunk_count 事务更新

禁止每插入一个 chunk 更新一次 count。正确流程：

```
所有 batch 成功
→ MySQL 事务:
    UPDATE documents SET chunk_count=?, status='completed' WHERE id=?
    UPDATE knowledge_bases SET chunk_count=chunk_count+? WHERE id=?
→ commit
```

任一 batch 失败 → ChromaDB 向量全清 → 抛出异常 → MySQL 回滚。

### 4.8 文档解析容错

- **策略**：部分容错，按最小处理单元失败跳过并记录 warning
  - PDF：逐页容错（单页 `extract_text` 异常捕获）
  - DOCX：逐段容错（单段 `text` 属性异常捕获，空白段落跳过不计入失败）
  - MD/TXT：整体容错（文件级异常捕获）
- **空文档边界**：`total_pages==0` 或 `full_text` 为空时，直接标记 FAILED，不经过 `failure_rate` 计算，避免误导性错误信息（如"解析失败率 100%（0/0 页失败）"）
- **分级判定**：

| 失败比例 | 结果状态 |
|:---|:---|
| < 20% | `success_with_warnings` |
| 20%~50% | `partial_failed` |
| > 50% | `failed` |

### 4.9 Celery 配置要点

```python
# broker: Redis
CELERY_BROKER_URL = "redis://localhost:6379/2"
CELERY_RESULT_BACKEND = "redis://localhost:6379/1"

# 入库任务（耗时较长，放宽超时）
# 注意：使用 autoretry_for 让 Celery 自动重试未捕获异常，禁止在外层 catch-all except 吞噬异常
@app.task(bind=True, max_retries=3, soft_time_limit=600, autoretry_for=(Exception,), retry_backoff=True)
def ingest_document(self, doc_id):
    ...
```
- **Worker 事件循环**：Celery Worker 进程须使用持久化事件循环（`_get_worker_loop()` 复用同一 `asyncio.new_event_loop()`），禁止每次任务新建/关闭 loop，否则 SQLAlchemy 连接池中的连接会挂在旧 loop 上，后续任务复用时触发 `attached to a different loop` 错误

---

## 5. 问答流程 [Target Architecture]

> Phase 3 实现单轮问答核心链路。Phase 4 加入多轮对话（会话记忆 + 问题重写），Phase 5 加入意图识别。

```
用户提问
    ↓
[Intent] 意图识别 → 判断类型（查知识库 / 闲聊 / 元问题）       ← [Designed: Phase 5]
    ↓ （如果是查知识库）
[Rewrite] 问题重写 → 结合对话历史补全上下文              ← [Implemented: Phase 4]
    ↓
[Retrieval] 多路检索 → 向量检索 + BM25 关键词检索       ← [Implemented]
    ↓
[Fusion] RRF 融合排序 → 合并两路结果                     ← [Implemented]
    ↓
[Rerank] 重排序 → NoopReranker 占位，后续接入 DashScope  ← [Implemented]
    ↓
[Prompt] 组装 Prompt → 拼接检索结果 + 用户问题           ← [Implemented]
    ↓
[LLM] 调用 LLM → SSE 流式返回答案                        ← [Implemented]
```

### 5.1 Phase 4 实际问答流程 [Implemented]

Phase 4 在 Phase 3 单轮链路基础上加入**会话记忆**和**问题重写**，不含意图识别：

```
用户提问
    ↓
[会话管理] conversation_id=null → 自动创建会话；已有会话 → 加载历史
    ↓
[Rewrite 触发判断] _needs_rewrite(question, history) → 有歧义才触发  ← §5.1.5
    ├─ 无历史 / 无歧义 → 跳过，使用原始 question
    └─ 有歧义 → LLM Rewrite → 成功则使用改写后 query，失败降级
    ↓
[Retrieval] 多路检索（使用改写后或原始 question）→ 向量 + BM25  ← §5.1.1
    ↓
[Fusion] RRF 融合排序 → 合并两路结果
    ↓
[Rerank] NoopReranker → 保持 RRF 排序（相关性降序） + 截取 top_k=5
    ↓
[Evidence Highlight] 句级 BM25 定位 → 每个 chunk 内切句 → BM25Okapi → 记录 best_sentence  ← §5.1.7
    ↓
[Prompt] 组装 Prompt → 拼接检索结果 + 历史消息 + 用户问题，软上限预算控制  ← §5.1.2
    ↓
[LLM] 调用 LLM → 流式 `chat/completions`，解析 content + reasoning_content
    ↓
[SSE] StreamingResponse → 6 事件类型 + 15s 心跳  ← §5.1.3
    ↓
[标题生成] 首轮截取前 12 字 → event: finish 返回 title → 异步 LLM 更新
```

#### 5.1.1 多路检索实现

**向量检索**：
- 调用已有 `embedder.embed_chunks()` 将问题向量化（1024 维）
- `collection.query(query_embeddings=[vec], n_results=10, where={"kb_id": kb_id})`
- metadata 值为数值类型（int），入库和查询两端统一使用 int，无需类型转换

**BM25 关键词检索**（索引生命周期）：

```
文档终态（completed/success_with_warnings）
    ↓ Celery ingest task 末尾触发
DEL Redis key: bm25_tokens:{kb_id}
    ↓ 下次查询时
get_bm25_index(kb_id):
  ├── Redis GET bm25_tokens:{kb_id}
  │   ├── 命中 → json.loads → BM25Okapi(tokens)  实例化（轻量，<50ms）
  │   └── 未命中 → 懒加载重建:
  │        1. SELECT content FROM chunks WHERE kb_id=? ORDER BY id
  │        2. [jieba.lcut(c.content) for c in chunks]  ← 最昂贵步骤
  │        3. SETEX bm25_tokens:{kb_id} 300 {"doc_ids":[...], "tokens":[[...],...]}
  │        4. BM25Okapi(tokens)
  └── get_scores(jieba.lcut(question)) → top_k=10
```

| 事件 | 触发 | 操作 |
|:---|:---|:---|
| 文档入库完成 | Celery ingest 末尾 | `DEL bm25_tokens:{kb_id}` |
| 文档删除完成 | Celery delete 末尾 | `DEL bm25_tokens:{kb_id}` |
| reprocess 触发 | document_service | `DEL bm25_tokens:{kb_id}` |
| 查询时缓存未命中 | `get_bm25_index()` | 懒加载重建（MySQL → jieba → Redis） |

**设计要点**：
- **缓存 `tokenized_corpus` 而非 pickle BM25Okapi 实例**：JSON 格式跨版本安全、Redis 友好、可人工排查
- **BM25Okapi 构造极轻量**（纯 NumPy 计算），真正昂贵的是 IO + jieba 分词
- **TTL=300s** 作为兜底：即使 Celery 未触发 DEL，缓存也会过期重建
- **最终一致性**：文档终态后才触发重建，避免处理中状态污染索引

#### 5.1.2 Prompt 组装与 Token 预算

**策略**：chunking 阶段控制 + 软上限 + 相关性优先填充

| 层级 | 策略 | 实现 |
|:---|:---|:---|
| Chunking | 固定 chunk_size=1000 chars，overlap=150 | 已实现，Prompt 阶段不二次裁剪 |
| 检索后排序 | 保持 RRF 融合排序（相关性降序） | RRF 已按相关性分数降序排列，相关性优先于长度 |
| Prompt 组装 | 软上限 + 相关性优先填充 | 超预算时跳过当前 chunk 尝试下一个，而非直接 break |
| TopK 控制 | RRF → NoopReranker 截取 top_k=5 | 控制数量而非逐 chunk 截断 |

**Token 预算计算**（复用 chunker 中英文自适应算法）：
```python
def estimate_tokens(text: str) -> int:
    chinese_ratio = sum(1 for c in text if '一' <= c <= '鿿') / len(text)
    ratio = 1.5 if chinese_ratio > 0.3 else 4.0
    return int(len(text) / ratio)
```

**Prompt 模板结构**：
```python
SYSTEM_PROMPT = """你是一个企业知识库助手。请仅基于以下文档内容回答问题。
如果文档中没有相关信息，请明确说明"知识库中未找到相关信息"，不要编造。

参考文档：
{context}

请用中文回答，引用来源时标注 [来源N]（N 为文档编号）。"""

# messages 结构
[
    {"role": "system", "content": formatted_prompt},
    # Phase 4 加入 history（滑动窗口消息）
    {"role": "user", "content": question}
]
```

#### 5.1.3 SSE 事件流与心跳机制

**实现方式**：手动 `StreamingResponse`（不用 `sse-starlette`），完全控制事件序列和心跳。

**事件序列**：
```
event: meta
data: {"conversation_id": 1, "task_id": "uuid"}

event: thinking          ← 仅 deep_thinking=true 时
data: {"delta": "..."}

event: message           ← 逐 token 流式
data: {"delta": "..."}

event: sources           ← 仅含 LLM 实际引用的 [来源N] chunk
data: {"chunks": [...]}

event: finish
data: {"message_id": 2, "title": "...", "token_usage": {...}}

event: error             ← 仅异常时
data: {"code": "E4xxx", "message": "...", "detail": "..."}
```

**sources 引用过滤**：
- LLM 流式结束后，从 `assistant_content` 中提取所有 `[来源N]` 引用编号
- LLM 写了 `[来源N]`：`event: sources` 仅发送被实际引用的 chunk（引用过滤优化）
- LLM 未引用任何 `[来源N]`：回退发送全部 `used_chunks`（防止因 LLM 格式问题导致 sources 消失）
- 引用过滤是**优化**而非~~必须~~——sources 数据源是 `used_chunks`（检索结果），而非 LLM 输出格式
- LLM 流式失败（error 路径）：无 `assistant_content`，回退到全量发送
- 幻觉编号（LLM 引用不存在的 [来源N]）：忽略，仅取有效范围内的编号

**心跳机制**：
```python
# 每 15 秒发送 SSE 注释帧，浏览器忽略但保持连接
# 防止 Nginx proxy_read_timeout(60s) / Cloudflare(100s) 断连
async def heartbeat_generator(interval: int = 15):
    while True:
        await asyncio.sleep(interval)
        yield ": ping\n\n"  # SSE 注释行，浏览器忽略
```

**thinking_content 处理**：
- DeepSeek API 流式响应中 `delta.reasoning_content` → `event: thinking`
- 仅 `deep_thinking=true` 时输出 thinking 事件
- **参数映射**：`deep_thinking=true` → `extra_body={"thinking": {"type": "enabled"}}` + `reasoning_effort="high"`，`deep_thinking=false` → `extra_body={"thinking": {"type": "disabled"}}` 且不传 `reasoning_effort`
- **默认值风险**：DeepSeek 官方默认 `thinking=enabled`，后端在 `false` 时必须显式传 `disabled`，否则每次请求都触发思考模式
- **思考强度**：仅 thinking enabled 时传 `reasoning_effort="high"`（DeepSeek 支持 high/max，low/medium→high，xhigh→max）；thinking disabled 时禁止同时传 `reasoning_effort`
- **不落库**：`messages.thinking_content` 写入 `null`，仅前端实时展示
- 原因：内容巨大、可能泄露系统 prompt/chain、数据库膨胀

#### 5.1.5 Query Rewrite（问题重写）[Implemented]

**背景**：Phase 4 初期将问题重写推迟到 Phase 5，假设「历史消息注入 LLM Prompt 后，LLM 自身可结合上下文消解指代」。多轮 RAG 回归测试（`regression_multi_turn_test.py`）证伪了这一假设：**检索发生在 LLM 之前**，检索器拿不到 history，当用户输入含代词/省略主语时（如「它需要几个人参加？」），嵌入模型无法消解指代，导致检索出无关文档。LLM 即使结合 history 理解了用户意图，也无正确上下文可用。

**结论**：问题重写必须前置于检索阶段，不能仅依赖 LLM Prompt 侧的 history 注入。Phase 4 立即补上。**已实现**：`backend/app/rag/query_rewriter.py`，集成点在 `chat_service._validate_and_prepare()`。

---

**触发策略：仅检查明确歧义信号词，不使用短问题阈值**

为避免给所有请求增加额外 LLM 延迟，Rewrite 仅在检测到明确歧义信号词时触发。**不使用短问题阈值**：中文问题天然短（「病假需要提供医院证明吗」14 字、「VPN 密码忘了怎么办」11 字），短问题阈值会导致大量语义完整的独立问题被强制改写，引入噪声。

```python
# backend/app/rag/query_rewriter.py

# 歧义信号词列表：代词/指示词/上下文引用
AMBIGUOUS_SIGNALS = [
    "它", "这个", "那个", "该", "此", "呢", "那",
    "他们", "这些", "那些",
    "上面", "前面说的", "刚才",
]

def _needs_rewrite(question: str, history: list[dict[str, str]] | None) -> bool:
    """判断是否需要 Query Rewrite。

    仅当同时满足以下条件时返回 True：
    1. 存在历史对话（有可参考的上下文）
    2. 当前问题含明确的歧义信号词（代词/指示词/上下文引用）
    """
    if not history:
        return False

    # 仅检查明确歧义信号词
    return any(s in question for s in AMBIGUOUS_SIGNALS)
```

| 输入 | 历史 | 触发？ | 原因 |
|:---|:---|:---|:---|
| 「入职第一天需要做什么？」 | 无 | ❌ | 无历史，无需 rewrite |
| 「新员工入职流程具体包含哪些步骤？」 | 有（不相关） | ❌ | 无歧义信号词 |
| 「病假需要提供医院证明吗？」 | 有 | ❌ | 14 字但语义完整，无歧义信号词 |
| 「它需要几个人参加？」 | 有 | ✅ | 含代词「它」 |
| 「不通过的话怎么办？」 | 有 | ❌ | 无歧义信号词（问题虽短但语义独立，原文可直接检索） |
| 「那请假呢？」 | 有 | ✅ | 含「那」「呢」 |
| 「刚才说的 VPN，忘记密码怎么办？」 | 有 | ✅ | 含「刚才」信号词 |
| 「前面说的内部培训费用谁出？」 | 有 | ✅ | 含「前面说的」信号词 |

> **设计决策**：`「不通过的话怎么办？」` 在多轮语境下可能确实需要补全为「代码评审不通过怎么办？」，但「把短问题全量送去改写」的代价远大于收益——大量「病假需要提供医院证明吗」这类完全独立的问题被强制改写后会偏离原始检索意图。牺牲少数省略主语场景的改写，换取大多数短问题的稳定检索。

---

**Rewrite Prompt：严格约束输出格式**

```python
REWRITE_SYSTEM_PROMPT = """你是一个查询改写助手。根据对话历史，将用户的最新问题改写为一个完整、独立、可直接用于检索的问题。

规则：
- 将代词（它、这个、那个、该、此）替换为对话历史中对应的实体
- 补全省略的主语或宾语
- 保持原问题的核心意图不变
- 只输出改写后的问题，不要解释，不要其他内容"""

REWRITE_USER_TEMPLATE = """对话历史：
{history}

用户问题：{question}
改写后的问题："""
```

**输出示例**：

| 原始 question | History 上下文 | 改写后 |
|:---|:---|:---|
| 「它需要几个人参加？」 | User:「代码评审的标准是什么？」Assistant:「代码评审需要……」 | `代码评审需要几个人参加？` |
| 「不通过的话怎么办？」 | User:「代码评审的标准是什么？」Assistant:「……评审不通过需要……」 | `代码评审不通过怎么办？` |
| 「金额限制具体是多少？」 | User:「介绍一下公司的报销制度」Assistant:「报销制度包括……金额……」 | `报销制度的金额限制是多少？` |

---

**实现：一次无状态 LLM 调用 + 降级**

```python
# backend/app/rag/query_rewriter.py

from app.core.llm import chat_completion

async def rewrite_query(
    question: str,
    history: list[dict[str, str]],
) -> str:
    """对歧义问题进行上下文补全改写。

    Args:
        question: 用户原始问题
        history: 历史消息（已由 _load_history() 处理，不含 [来源N]）

    Returns:
        改写后的问题。LLM 调用失败时降级返回原始 question。
    """
    # 仅取最近 2 轮（4 条消息）作为改写上下文
    recent = history[-4:] if len(history) > 4 else history

    # 格式化历史为纯文本
    history_text = "\n".join(
        f"{'用户' if m['role'] == 'user' else '助手'}: {m['content']}"
        for m in recent
    )

    try:
        result = await chat_completion(
            messages=[
                {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
                {"role": "user", "content": REWRITE_USER_TEMPLATE.format(
                    history=history_text,
                    question=question,
                )},
            ],
            deep_thinking=False,  # 改写不需要深度思考
        )
        rewritten = result.content.strip().strip('"\'""')
        if rewritten and len(rewritten) >= 2:
            logger.info("Query Rewrite 成功: %s → %s", question[:50], rewritten[:80])
            return rewritten
        else:
            logger.warning("Query Rewrite 输出异常（空或过短），降级使用原始 query")
            return question
    except Exception:
        logger.exception("Query Rewrite LLM 调用失败，降级使用原始 query")
        return question
```

**调用位置**：`chat_service._validate_and_prepare()` 中，检索之前（§5.1 流程图 [Rewrite] 步骤）：

```python
# chat_service.py _validate_and_prepare() 中，检索之前插入

from app.rag.query_rewriter import _needs_rewrite, rewrite_query

# 问题重写：仅在检测到歧义时调用 LLM
if _needs_rewrite(question, history_messages):
    question = await rewrite_query(question, history_messages)
# 否则 question 保持原值，零额外延迟
```

**设计要点**：

| 要点 | 决策 | 原因 |
|:---|:---|:---|
| 触发方式 | 仅检查明确歧义信号词（13 个），不使用短问题阈值 | 正常路径零额外延迟；避免短问题过度触发导致改写偏离 |
| History 范围 | 仅取最近 2 轮（4 条消息） | 消解指代只需最近一轮上下文；全量 history 浪费 token + 引入噪声 |
| 降级策略 | LLM 失败 → 返回原始 question | 不影响主流程可用性；最坏情况 = 当前状态 |
| 输出约束 | Prompt 强调「只输出改写后的问题」 | 防止 LLM 输出解释性文字污染检索 query |
| 结果长度校验 | ≥ 2 字符才采用 | 防止 LLM 输出空字符串或单个标点 |
| deep_thinking | `False` | 改写是简单补全任务，无需深度思考 |
| 不落库 | 改写结果不持久化 | 改写是检索优化手段，非用户可见内容 |

**已知局限**：

当前 v2 触发策略（仅检查信号词）存在结构性盲区：**纯省略/隐含依赖**。问题语法完整但语义残缺（如「审批流程需要多长时间？」前轮讨论报销），不含任何信号词 → `_needs_rewrite()` 返回 `False` → 改写不触发 → 检索跑偏。

| 案例 | 前轮 | 问题 | 信号词？ | 期望改写 |
|:---|:---|:---|:---|:---|
| multi-001 T2 | 报销制度 | 审批流程需要多长时间？ | ❌ 无 | 报销审批流程需要多长时间？ |

**后续优化方向：Retrieval-aware Rewrite** — 检索先行，结果差时再改写重检，而非预先判断。检索质量本身就是最准确的 Rewrite 触发信号。

```
Question → Retrieval → 结果好 → 直接回答
                      → 结果差 → Rewrite → Retrieval → 回答
```

计划 Phase 5 或后续 Phase 实施。

#### 5.1.6 意图识别（Intent Classification）[Implemented]

**背景**：Phase 3 使用 `_is_casual_chat()` 正则 stopgap（6 类模式：问候/致谢/告别/极短输入等）覆盖高频闲谈场景，跳过检索直接回复。但正则无法区分「知识查询」与「真正的闲聊」——「你能做什么」被误判为知识查询走完整 RAG 链路浪费 token，「最近有什么新政策」被正则误判为闲谈跳过检索。Phase 5 用 LLM 分类替换正则，提升分类准确率。

**设计目标**：
- 分类准确率 > 95%（相比正则 stopgap 的 ~70%）
- 分类延迟 < 300ms（轻量 Prompt + `deep_thinking=False` + `max_tokens=10`）
- LLM 分类失败时回退正则 stopgap，不影响主流程可用性

---

**分类体系：3 类**

| 类别 | 标签 | 行为 | 示例 |
|:---|:---|:---|:---|
| 知识查询 | `KNOWLEDGE` | 走完整 RAG 链路（检索→RRF→Rerank→Prompt→LLM） | 「报销制度是什么？」「VPN 怎么配置？」 |
| 闲谈 | `CASUAL` | 跳过检索，使用 `CASUAL_SYSTEM_PROMPT` + 历史消息 → LLM 直接回复 | 「你好」「谢谢」「今天天气真好」 |
| 元问题 | `META` | 不调 LLM，直接返回固定模板响应（毫秒级） | 「你能做什么？」「支持什么格式？」 |

> **设计决策：不做细粒度问题类型分类**（如事实型/对比型/总结型）。细分类型对 Prompt 组装策略有价值，但分类体系越细、准确率越低。Phase 5 先做 3 类粗分类跑通链路，细粒度分类留给 Phase 6。

---

**分类 Prompt（约 200 tokens）**

```python
INTENT_SYSTEM_PROMPT = """你是一个查询意图分类器。将用户问题分为以下三类之一：

- KNOWLEDGE：需要使用知识库文档来回答的问题（政策、流程、制度、技术规范等）
- CASUAL：日常闲聊、问候、致谢、与知识库无关的对话
- META：询问助手本身能力的问题（你能做什么、支持什么功能等）

仅输出类别标签，不要解释。"""

# few-shot 示例嵌入 user message
INTENT_USER_TEMPLATE = """示例：
Q: 报销需要提交哪些材料？ → KNOWLEDGE
Q: 你好 → CASUAL
Q: 你能做什么？ → META
Q: 谢谢你的帮助 → CASUAL
Q: VPN 密码忘了怎么办？ → KNOWLEDGE

用户问题：{question}
分类："""
```

---

**路由逻辑**

```python
# chat_service._validate_and_prepare() 中，Rewrite 之前插入

from app.rag.intent import classify_intent, Intent

intent = await classify_intent(question)

if intent == Intent.META:
    # 元问题：不调 LLM，直接返回固定模板
    raise MetaQuestionException(question)  # chat() 捕获后返回固定 SSE 响应

if intent == Intent.CASUAL:
    # 闲谈：跳过检索，使用 CASUAL_SYSTEM_PROMPT
    search_results = []  # 空检索结果
    system_prompt = CASUAL_SYSTEM_PROMPT  # Phase 3 已有
else:  # KNOWLEDGE
    # 知识查询：走完整 RAG 链路（现有流程不变）
    ...

# 后续 Rewrite → Retrieval → RRF → Rerank → Prompt → LLM 流程不变
# 闲谈路径的 search_results=[] 自然触发 prompt_builder 的「无检索结果」分支
```

---

**延迟优化**

| 要点 | 决策 | 原因 |
|:---|:---|:---|
| deep_thinking | `False` | 分类是简单任务，无需深度思考 |
| max_tokens | `10` | 输出仅需 1 个词（`KNOWLEDGE` / `CASUAL` / `META`），10 tokens 绰绰有余 |
| 独立 LLM 调用 | ✅ 是 | 分类必须在 Rewrite 和 Retrieval 之前，无法与主 LLM 调用合并 |
| 预期延迟 | < 300ms | 轻量 Prompt + 短输出，实测应在此范围内 |

> **设计决策：选择一次额外 LLM 调用而非复用主 LLM**。分类结果决定是否触发检索——检索是 RAG 链路中最昂贵的步骤（向量查询 + BM25 + RRF），用 ~300ms 的分类避免不必要的检索是净收益。闲谈和元问题占日常对话的 10-20%，分类可为这些请求节省 2-5s 的检索耗时。

---

**降级策略**

```
classify_intent(question)
  ↓ try
LLM 调用（deep_thinking=False, max_tokens=10）
  ↓ 成功 + 有效标签 → 返回 Intent 枚举
  ↓ 失败（网络/API异常/返回无效标签）
  ↓ except / invalid
回退 _is_casual_chat(question)  ← Phase 3 正则 stopgap（已有 6 类模式）
  ├── 命中 → Intent.CASUAL
  └── 未命中 → Intent.KNOWLEDGE（保守策略：宁可查了没用，不可该查不查）
  
日志记录分类失败原因（WARNING 级别），便于线上观察分类 LLM 可用性
```

**降级原则**：**保守路由**。分类失败时走 `KNOWLEDGE` 路径（触发检索），确保用户的知识查询不会被误判为闲谈而跳过检索。代价是闲谈被误判为知识查询时多走一次检索（~1-2s），但「该查的没查」比「不该查的查了」严重得多。

---

**实现文件**

```
backend/app/rag/intent.py              ← 实现：classify_intent() + Intent 枚举 + Prompt 常量（复用已有占位文件）
backend/app/services/chat_service.py   ← 修改：_validate_and_prepare() 集成（Rewrite 之前）
```

**集成点**：`chat_service._validate_and_prepare()` 中，在 Query Rewrite（§5.1.5）之前：
```python
# 0. 意图识别 — [Phase 5]
intent = await classify_intent(question)
if intent == Intent.META:
    raise MetaQuestionException(question)
skip_retrieval = (intent == Intent.CASUAL)

# 1. 问题重写 — [Implemented: Phase 4]（仅 KNOWLEDGE 路径触发）
if not skip_retrieval and _needs_rewrite(question, history_messages):
    question = await rewrite_query(question, history_messages)
```

---

**已知局限**

| 局限 | 说明 | 缓解 |
|:---|:---|:---|
| 额外 LLM 调用延迟 | 每次问答增加 ~300ms 分类延迟 | 闲谈/元问题节省的检索耗时（2-5s）远超分类开销 |
| 分类边界模糊 | 「最近有什么新政策？」可能是闲谈也可能是知识查询 | 保守路由：歧义时走 KNOWLEDGE |
| 多语言混合 | 中英混合问题可能分类不准 | few-shot 示例覆盖中英混合场景 |
| 正则回退的覆盖盲区 | 正则仅覆盖 6 类高频闲谈，新型闲谈模式可能漏判 | 分类 LLM 正常时正则仅作降级兜底；线上观察分类失败率 |


#### 5.1.7 Evidence Highlight — 句级 BM25 定位 [Implemented]

**背景**：旧方案 `_locate_preview()` 在 LLM 生成回答后，从 `assistant_content` 提取 `[来源N]` 前后的 snippet，再回 chunk 做子串匹配定位引用位置。这有根本性缺陷：①「事后猜 LLM 引用了哪里」不可靠——snippet 非原文时定位失败 → 全部降级到 chunk 前 200 字符盲取；② 定位质量依赖 LLM 引用格式（句首/句末），DeepSeek/Qwen 在不同场景下行为不一致；③ `_locate_preview` + 双向 snippet 提取 + 规范化匹配共 ~100 行业务逻辑内嵌在 chat_service 中，职责混杂。

Phase 5.5 重构为 **Evidence Highlight**：将定位时机从「LLM 生成后」前移到「检索时」，在 chunk 内部用 BM25 直接选出与 question 最相关的句子作为「证据句」。核心原则：**检索时就确定证据句，而非事后猜 LLM 引用了哪里**。

**设计目标**：
- 证据句定位在 Rerank 之后、Prompt 组装之前完成（`match_sentences()`）
- 复用已有 `rank-bm25`（BM25Okapi）+ `jieba` 分词，不引入新算法依赖
- 确定性：同一 question 对同一 chunk 永远返回同一句子（无 LLM 随机性）
- `preview_text` 语义从「LLM 引用定位」变为「Evidence 定位」，API 字段和前端渲染零改动

---

**数据流**

```
用户问题
    ↓
Vector + BM25 检索（chunk 级，不变）
    ↓
RRF 融合（不变）
    ↓
Rerank（不变）
    ↓
【句级 BM25 定位】← 新增：sentence_matcher.py
  chunk 切句 → BM25Okapi(sentences) → 取 argmax → 记录 best_sentence + score
    ↓
Prompt 组装（不变，RetrievalResult 透传 matched_sentence）
    ↓
LLM 生成（不变）
    ↓
_build_sources()：matched_sentence → preview_text + preview_range
  （已经保证是 chunk 子串，find() 必然命中）
```

---

**句级定位算法：BM25 在 chunk 内部选句**

```python
# backend/app/rag/sentence_matcher.py

import jieba
from rank_bm25 import BM25Okapi

_SENTENCE_SEP = re.compile(r'[。！？!?\n]+')

def match_sentences(output: RetrievalOutput, question: str) -> RetrievalOutput:
    """对每个 chunk 内部做句级 BM25 定位，记录最佳证据句。"""
    question_tokens = jieba.lcut(question)

    for result in output.results:
        # 切句
        raw = _SENTENCE_SEP.split(result.content)
        sentences = [s.strip() for s in raw if s.strip()]
        if not sentences:
            continue

        # 句级 BM25（每 chunk 独立索引，~1ms）
        tokenized = [jieba.lcut(s) for s in sentences]
        bm25 = BM25Okapi(tokenized)
        scores = bm25.get_scores(question_tokens)

        # 取 argmax → 最佳证据句
        best_idx = max(range(len(scores)), key=lambda i: scores[i])
        result.matched_sentence = sentences[best_idx]
        result.matched_sentence_score = float(scores[best_idx])

    return output
```

| 要点 | 决策 | 原因 |
|:---|:---|:---|
| 定位时机 | Rerank 后、Prompt 前 | 确保 `used_chunks` 携带 `matched_sentence` |
| 切句策略 | 中文标点 `。！？!?\n` 正则切分 | 覆盖常见句末标点，跨行文本统一处理 |
| 搜索算法 | BM25Okapi（每 chunk 独立微型索引，3-8 句） | IDF 天然区分「审批流程」和「经审批后」的关键词权重差异；复用已有依赖零新增 |
| 确定性 | 同一 question 永远返回同一 sentence | 纯算法，无 LLM 随机性 |
| 性能 | 每 chunk ~1ms（轻量 NumPy 计算） | 5 chunks × 1ms = 5ms，对检索链路延迟无感知影响 |

> **设计决策：用 BM25 在 chunk 内部选句而非依赖 LLM 引用格式**。旧方案 `_locate_preview` 依赖 LLM 在回答中写 `[来源N]` 且 snippet 必须是原文，这在以下场景会系统性失败：① LLM 用自己的话概括而非原文引用；② `[来源N]` 放在句末时 snippet 是标点/换行/下一句；③ LLM 未引用任何 `[来源N]`（常见于 DeepSeek/Qwen）。Evidence 方案将定位前移到检索阶段，完全解耦 LLM 行为。

---

**SSE sources 事件格式**

Phase 5.5 新增 `highlight_start` / `highlight_end` 字段，前端纯切片渲染，不再做 indexOf 匹配：

```json
{
  "chunks": [{
    "chunk_index": 1,
    "doc_name": "入职指南.pdf",
    "page": 3,
    "content": "新员工入职流程包括以下步骤：第一步，填写个人...",
    "preview_text": "入职流程包括以下步骤：第一步，填写个人信息表并提交身份证复印件...",
    "preview_range": {"start": 5, "end": 205},
    "highlight_start": 14,
    "highlight_end": 38
  }]
}
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| `preview_text` | string \| null | Evidence 定位后的预览文本（以 `matched_sentence` 为中心的 ±100 字符窗口） |
| `preview_range.start` | int | 预览窗口在 chunk.content 中的起始位置 |
| `preview_range.end` | int | 预览窗口在 chunk.content 中的结束位置 |
| `highlight_start` | int \| null | 高亮区间在 preview_text 内的起始偏移（含），前端 `slice(0, start)` 切片 |
| `highlight_end` | int \| null | 高亮区间在 preview_text 内的结束偏移（不含），前端 `slice(start, end)` 切片 |

> **兼容性约束**：`content` 字段保留（完整 chunk 内容）。旧版前端不解析 `preview_text` / `highlight_start` / `highlight_end` 时仍可展示 `content` 截断，完全向前兼容。

---

**前端渲染规格（纯切片渲染）**

前端 `MessageItem.vue` 的 `getSourcePreviewHtml(src)` 基于后端提供的 `highlight_start` / `highlight_end` 做纯切片渲染，**零匹配逻辑**。旧 snippet 体系（`extractSnippet()` / `extractSnippetAfter()` / `normalizeWhitespace()` / `buildNormPosMap()` / `isNormCharStart()` 共 ~80 行）已全部删除。

```
getSourcePreviewHtml(src):
  displayText = src.preview_text || src.content.slice(0, 200)
  if highlight_start/end 存在:
    → escapeHtml(slice(0, start)) + <mark> + escapeHtml(slice(start, end)) + </mark> + escapeHtml(slice(end))
  else:
    → escapeHtml(displayText)
```

| 要素 | 行为 |
|:---|:---|
| 默认展示 | 显示 `preview_text`（Evidence 定位后的智能预览） |
| 降级展示 | `preview_text` 为 None 时前端自行取 `content` 前 200 字符 |
| 高亮渲染 | 后端 `highlight_start/end` → 前端 `slice` 切片 + `<mark>` 包裹（黄色背景），零 indexOf/normalize |
| 引用编号 | `[来源N]` 编号保持不变，LLM Prompt 和 sources 事件中的编号一一对应 |

---

**降级策略**

```
定位流程:
  match_sentences(reranked_output, question):
    if output.results 为空:
      → 直接返回（无 chunk 可定位）
    for each chunk:
      if content 为空/纯空白:
        → matched_sentence 保持 None
      if 切句后无有效句子:
        → matched_sentence 保持 None
      else:
        → BM25Okapi 评分 → 记录 best_sentence + score
        
_build_sources():
  if matched_sentence 非空且 content 非空:
    → content.find(matched_sentence)  # 保证命中（句子来自 chunk 原文）
    → 以匹配位置为中心取 ±100 字符窗口
  else:
    → preview_text = None, preview_range = None  # 前端自行降级
```

| 降级场景 | 处理 |
|:---|:---|
| chunk 无有效句子（纯标点/空白） | `matched_sentence = None` → `preview_text = None` |
| chunk.content 为空 | `matched_sentence = None` → `preview_text = None` |
| 检索结果为空 | `match_sentences()` 直接返回，无 chunk 可定位 |

---

**实现文件**

```
backend/app/rag/sentence_matcher.py        ← 新建：match_sentences()（~50 行）
backend/app/rag/retriever.py               ← 修改：RetrievalResult +2 字段（matched_sentence / matched_sentence_score）
backend/app/services/chat_service.py        ← 修改：删除 5 个旧函数（~100 行），_build_sources() 基于 matched_sentence 重写
backend/tests/test_sentence_matcher.py      ← 新建：14 用例
backend/tests/test_sources_preview.py       ← 重写：Evidence 集成测试
```

**零改动文件**：`schemas/chat.py`、`fusion.py`、`reranker.py`、`prompt_builder.py`、前端 `MessageItem.vue` — 字段透传，API 完全向前兼容。

---

**已知局限**

| 局限 | 说明 | 缓解 |
|:---|:---|:---|
| BM25 关键词偏好 | 句级 BM25 倾向于选择含 question 关键词的句子，可能忽略语义相关但不含关键词的句子 | BM25 仅用于句子选择（chunk 级检索已由向量语义 + BM25 双路保证），误选概率低 |
| 短 chunk 窗口覆盖全量 | chunk < 200 字符时 ±100 窗口覆盖全 chunk，不同 question 的 `preview_text` 可能相同 | matched_sentence 仍不同（可用于调试/可观测），前端展示差异由 `<mark>` 高亮体现 |
| 纯算法无法感知上下文 | 句级 BM25 对每句独立评分，不考虑句间逻辑关系（如因果/转折） | chunk 级 RRF 已保证 chunk 级相关性；句级定位是锦上添花，非核心召回 |

---

### 5.2 问答核心逻辑（伪代码，含阶段标注）

```python
# chat_service.py 核心流程
async def chat(question, conversation_id, kb_id, deep_thinking, db, current_user):
    # 0. 会话自动创建（Phase 3 单轮，不注入历史）
    if not conversation_id:
        conv = Conversation(user_id=current_user.id, kb_id=kb_id)
        db.add(conv)
        await db.flush()
        conversation_id = conv.id
    else:
        conv = await db.get(Conversation, conversation_id)
        # Phase 4: 读取 conv.messages 作为 history

    # 0. 保存用户消息
    user_msg = Message(conversation_id=conv.id, role="user", content=question)
    db.add(user_msg)

    # 1. 意图识别 — [Designed: Phase 5]
    # intent = await intent_classifier.classify(question)

    # 2. 问题重写 — [Implemented: Phase 4]
    # 仅在检测到歧义时调用 LLM（详见 §5.1.5）
    if _needs_rewrite(question, history_messages):
        question = await rewrite_query(question, history_messages)

    # 3. 多路检索 — [Phase 3]（使用改写后或原始 question）
    query_vec = await embedder.embed_query(question)  # 复用已有 embedder
    vector_results = await vector_retriever.search(query_vec, kb_id, top_k=10)
    bm25_results = await bm25_retriever.search(question, kb_id, top_k=10)
    merged = rrf_fusion(vector_results, bm25_results, k=60)

    # 4. 重排序 — [Phase 3] NoopReranker：保持 RRF 排序 + 截取
    reranked = await reranker.rerank(question, merged, top_k=5)

    # 5. 拼 Prompt — [Phase 3] 软上限 + 择优填充
    # Phase 4: history 参数传入历史消息
    prompt_messages = prompt_builder.build(question, reranked, history=[])

    # 6. LLM SSE 流式输出 — [Phase 3]
    extra_body = {"thinking": {"type": "enabled" if deep_thinking else "disabled"}}
    llm_kwargs = {"extra_body": extra_body}
    if deep_thinking:
        llm_kwargs["reasoning_effort"] = "high"
    async def event_stream():
        yield sse_event("meta", {"conversation_id": conv.id, "task_id": uuid4()})
        assistant_content = ""
        try:
            async for chunk in llm.stream_chat(
                prompt_messages,
                **llm_kwargs,
            ):
                if chunk.reasoning_content and deep_thinking:
                    yield sse_event("thinking", {"delta": chunk.reasoning_content})
                if chunk.content:
                    assistant_content += chunk.content
                    yield sse_event("message", {"delta": chunk.content})
            # 6a. 引用过滤：LLM 写了 [来源N] 时仅发送被引用 chunk
            # 未引用时回退发送全部 used_chunks（防 LLM 格式脆弱耦合）
            cited_indices = _extract_citation_indices(assistant_content)
            if cited_indices:
                cited_chunks = [c for i, c in enumerate(used_chunks)
                                if str(i + 1) in cited_indices]
                yield sse_event("sources", _build_sources(cited_chunks))
            else:
                yield sse_event("sources", _build_sources(used_chunks))
            title = _generate_title(question)  # 截取前 12 字
            yield sse_event("finish", {
                "message_id": assistant_msg.id,
                "title": title,
                "token_usage": llm.last_usage
            })
        except LLMException as e:
            # 失败时无 assistant_content，回退到全量发送
            yield sse_event("sources", _build_sources(reranked))
            yield sse_event("error", {"code": "E4002", "message": str(e)})

    return StreamingResponse(
        stream_with_heartbeat(event_stream(), interval=15),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )
```

---

## 6. 多路检索设计

### 6.1 向量检索

| 项目 | 说明 |
|:---|:---|
| 技术 | ChromaDB `collection.query()` + DashScope text-embedding-v3 |
| 维度 | 1024 |
| 相似度 | cosine |
| top_k | 10 |
| 过滤 | `where={"kb_id": kb_id}` — metadata 值为 int 类型，入库/查询两端统一 |

### 6.2 BM25 关键词检索

| 技术 | rank-bm25 (BM25Okapi) + jieba 分词 |
|:---|:---|

**索引生命周期**（详见 §5.1.1）：

| 事件 | 触发 | 操作 |
|:---|:---|:---|
| 文档入库完成 | Celery ingest 末尾 | `DEL bm25_tokens:{kb_id}`（下次查询懒加载重建） |
| 文档删除完成 | Celery delete 末尾 | `DEL bm25_tokens:{kb_id}` |
| reprocess 触发 | document_service | `DEL bm25_tokens:{kb_id}` |
| 查询时缓存未命中 | `get_bm25_index()` | 懒加载重建（MySQL → jieba 分词 → Redis SETEX 300） |

**缓存结构**（Redis key: `bm25_tokens:{kb_id}`，TTL=300s）：
```json
{
  "doc_ids": [101, 102, 103],
  "tokens": [["入职", "指南", "欢迎"], ["报销", "制度"], ["VPN", "配置"]]
}
```
- 缓存 `tokenized_corpus`（分词结果列表），**禁止** pickle BM25Okapi 实例
- 查询时 `BM25Okapi(tokens)` 实时实例化（轻量，纯 NumPy 计算）
- 真正昂贵的是 jieba 分词 + MySQL IO

### 6.3 RRF 融合排序

```
score(doc) = Σ 1 / (k + rank_i(doc))   # k=60
```

其中 `k=60` 是平滑常数，降低单一排序中的极端排名对最终结果的过度影响。

---

## 7. 关键设计决策

### 7.1 ChromaDB Collection 策略

| 阶段 | 方案 | 说明 |
|:---|:---|:---|
| 当前 | **共用 Collection + Metadata 隔离** | 所有知识库共用一个 `docmind` collection，通过 metadata 中的 `kb_id` 字段在查询时做 WHERE 过滤 |
| 扩展条件 | 评估是否需要独立 Collection | 当知识库数量增多或业务隔离需求明显时考虑 |
| 生产标准 | 3 个以上完全独立的业务线 → 独立 Collection；否则共用 | 独立 Collection 物理隔离、可单独配置索引参数；代价是内存占用增加 |

**实现要点**：
- ChromaDB 只有一个 collection：`docmind`
- 每个 chunk 写入时带 metadata：`{"kb_id": 1, "doc_id": 5, "chunk_index": 3, "page": 2}`
- 检索时加 where 条件过滤 kb_id：

```python
collection.query(
    query_embeddings=[query_vector],
    n_results=10,
    where={"kb_id": kb_id}
)
```

**KB 删除时的向量清理**（单 Collection 架构）：
```python
# 通过 metadata filter 批量删除，而非 drop collection
collection.delete(where={"kb_id": kb_id})
```
- KB 删除流程：标记 `kb.status=deleting` → Celery Worker 执行 `collection.delete(where={"kb_id": x})` + 删除文件 → `DELETE FROM knowledge_bases WHERE id=?`（FK CASCADE 自动清理子记录）
- 禁止使用 API 级联同步删除，避免大数据量场景接口超时

**metadata 类型一致性**：
- ChromaDB 对 metadata 值的类型敏感：整数 `1` 和字符串 `"1"` 被视为不同值
- **强制约定**：metadata 值统一使用原生数值类型（int），入库直接写入 `kb_id`/`doc_id`/`chunk_index` 整数值，查询时 `where={"kb_id": kb_id}` 直接传 int。无需 `_normalize_metadata()` 转换
- 入库示例：
```python
collection.add(
    metadatas=[{
        "kb_id": kb_id,          # int
        "doc_id": doc_id,        # int
        "chunk_index": i,        # int
    } for ...]
)

# 查询时
collection.query(where={"kb_id": kb_id})  # 直接传 int
```

**持久化与连接**：
- ChromaDB 使用 `PersistentClient`，数据持久化到 `backend/chroma_data/chroma.sqlite3`
- 持久化目录由 `.env` 中的 `CHROMA_PERSIST_DIR` 配置（默认 `./chroma_data`）
- ChromaDB 采用**懒加载自动初始化**：`get_collection()` / `get_client()` 首次调用时自动初始化 PersistentClient 并获取/创建 collection，无需显式调用 `init_chroma()`。这确保 FastAPI（lifespan）和 Celery Worker（独立进程）两种运行时都能正确初始化
- Collection 索引使用 `hnsw:space=cosine`（余弦相似度）

### 7.2 BM25 实现方案

**当前决策**：使用 **`rank-bm25` (BM25Okapi) + jieba 中文分词**。

**选型理由**：

- `rank-bm25` 构造函数接受 `tokenizer` 参数，传入 `jieba.lcut` 即可完美支持中文分词，并非文档此前判断的「仅空格分词」
- 库源码仅 260 行单文件，仅依赖 `numpy`，体积极小且无供应链风险
- 三种 BM25 变体（Okapi/Plus/L）均经过广泛验证，公式正确性有保障
- NumPy 向量化计算，性能远超纯 Python 循环实现
- 内置 `get_batch_scores()` 方法，适合知识库范围内的局部检索
- BM25 公式已稳定数十年，最后更新 2022-02 不构成弃用理由

**索引生命周期**（详见 §5.1.1）：

| 事件 | 触发 | 操作 |
|:---|:---|:---|
| 文档入库完成 | Celery ingest 末尾 | `DEL bm25_tokens:{kb_id}` |
| 文档删除完成 | Celery delete 末尾 | `DEL bm25_tokens:{kb_id}` |
| reprocess 触发 | document_service | `DEL bm25_tokens:{kb_id}` |
| 查询时缓存未命中 | `get_bm25_index()` | 懒加载重建（MySQL → jieba → Redis SETEX 300） |

**缓存结构**（Redis key: `bm25_tokens:{kb_id}`，TTL=300s）：
- 存储 `{"doc_ids": [...], "tokens": [[...], ...]}` JSON
- **禁止** pickle BM25Okapi 实例（跨版本不安全、Redis 不友好）
- 查询时 `BM25Okapi(tokens)` 实时实例化（轻量，纯 NumPy 计算，<50ms）
- 真正昂贵的步骤是 jieba 分词 + MySQL IO

**IDF 静默衰减风险**：`rank-bm25` 的 IDF 基于语料初始化时固定，文档删除后不会自动衰减已不在语料中的词的 IDF。但对于 RAG 场景，IDF 偏差影响有限——BM25 结果仅作为 RRF 融合的一路信号，最终排序由双路融合 + Rerank 共同决定。

### 7.3 Rerank 策略

| 阶段 | 方案 | 说明 |
|:---|:---|:---|
| Phase 3 | **NoopReranker（占位）** | 保持 RRF 融合排序（已按相关性降序），截取 top_k=5 |
| Phase 3+ | **DashScope Rerank API** | 中文场景首选，阿里通义千问的 Rerank 模型对中文长文本效果好，有免费额度 |

**NoopReranker 逻辑**：
```python
class NoopReranker(BaseReranker):
    """占位实现：保持 RRF 融合排序，截取 top_k"""
    async def rerank(self, query: str, documents: list, top_k: int = 5) -> list:
        # 保持 RRF 原始排序（已按相关性分数降序），仅截取 top_k
        # 不再按长度重排：短 chunk 优先策略在语义匹配/跨文档场景下会破坏相关性排名
        return documents[:top_k]
```
- 保持 RRF 排序：RRF 融合已按相关性分数降序排列，相关性优先于长度
- 不再按长度重排：短 chunk 优先策略在语义匹配/跨文档场景下导致 LLM 拿到不相关短 chunk，误判"未找到"
- 输入不足 top_k 时返回全部
- 不改变 chunk 内容，仅截取数量

### 7.4 前端语言选型

**当前决策**：使用 **JavaScript（非 TypeScript）**。

**原因**：
- 项目为个人开发（校招简历项目），JS 开发效率更高，无需额外配置类型系统
- 前端规模可控（~12 个组件、~3 个页面），类型检查收益有限
- 如后续团队协作或规模增长，可渐进式迁移（Vue 3 支持 JS + TS 混用）

### 7.5 文件存储策略

| 阶段 | 方案 | 说明 |
|:---|:---|:---|
| 当前 | **本地磁盘存储** | 文件保存在 `backend/uploads/` 目录 |
| 扩展 | **S3 兼容对象存储（OSS/MinIO）** | 抽象 `StorageBackend` 接口，本地实现和 OSS 实现可互换 |

**文件目录结构**：
```
uploads/{kb_id}/{doc_id}/{uuid}_{sanitized_filename}
```
- 例：`uploads/1/5/a1b2c3d4_入职指南.pdf`
- `sanitized_filename`：去除特殊字符后的安全文件名
- `uuid`：防重名，同时保留原始文件名便于排查

```python
# 当前：本地存储
UPLOAD_DIR = Path("uploads")
file_path = UPLOAD_DIR / str(kb_id) / str(doc_id) / f"{uuid}_{sanitized_filename}"

# 扩展接口
class StorageBackend(ABC):
    async def save(self, file, kb_id: int, doc_id: int, filename: str) -> str: ...
    async def read(self, path: str) -> bytes: ...
    async def delete(self, path: str) -> None: ...

class LocalStorage(StorageBackend): ...    # 当前使用
class OSSStorage(StorageBackend): ...      # 后续扩展
```

---

### 7.6 知识库可见性模型（弱混合模式）

**设计原则**：`visibility` 控制 READ（谁能看），`ownership` 控制 WRITE（谁能改）。

**决策背景**：当前权限模型为「仅 owner 能看自己的 KB + admin 全局只读」。PRD 描述的跨部门知识共享场景（如技术查财务文档）要求非 owner 也能检索特定 KB，但完整多租户/ACL 方案复杂度远超当前项目阶段需要。

**方案**：`knowledge_bases` 表新增 `visibility` 字段（`ENUM('private', 'public')`，默认 `'private'`）。

| 维度 | 控制字段 | 规则 |
|:---|:---|:---|
| READ（查看/检索） | `visibility` | `private` → 仅 owner + admin；`public` → 所有登录用户 |
| WRITE（编辑/删除/上传） | `ownership` (`user_id`) | 仅 owner 可编辑/上传文档；admin 可删除 KB/文档（违规清理）和修正 KB 元数据（名称/描述/visibility），但不上传文档 |

**代码约束**：所有 KB 接口必须先判断 visibility（能否读）再判断 ownership（能否写），两步校验不可合并。admin 角色拥有管理级写权限（删除 + 元数据修改），但不是 owner 的完全替代（不上传文档）。禁止在代码中硬编码「只有 owner 能看/改 KB」的假设。

**详细规则**：见 PRD.md §5 知识库可见性模型。

---

## 8. 会话记忆策略 [Implemented: Phase 4]

### 8.1 Token 预算四池子分拆

> **设计原则**：各池子独立控制预算，互不侵蚀。避免「历史很长 → 检索结果被挤没 → RAG 退化」。

```
MAX_CONTEXT = 20000（DeepSeek 上限 32K，留 12K 给 completion）
├── SYSTEM_BUDGET   = 2000
├── HISTORY_BUDGET  = 6000
├── RETRIEVAL_BUDGET = 10000
└── QUESTION_BUDGET  = 2000
```

| 池子 | 预算 | 超限策略 |
|:---|:---|:---|
| System Prompt | ≤ 2000 tokens | 固定模板，不会超 |
| History | ≤ 6000 tokens | 从旧到新逐条移除直到预算内 |
| Retrieval Chunks | ≤ 10000 tokens | 从低分 chunk 开始丢弃直到预算内 |
| Current Question | ≤ 2000 tokens | 前端 2000 字符限制兜底 |

### 8.2 历史消息注入

**格式**：`chat_service.py` 已是 OpenAI `[{role, content}]` 格式，Phase 4 在 system prompt 之后、当前 question 之前插入历史：

```python
# Phase 4 改造后
history_messages = await _load_history(db, conv.id,
    max_tokens=HISTORY_BUDGET,  # 6000
    max_messages=20,            # 硬上限兜底
)
messages = [
    {"role": "system", "content": prompt_result.system_prompt},
    *history_messages,          # ← Phase 4 新增
    {"role": "user", "content": prompt_result.user_prompt},
]
```

**`_load_history()` 约 40 行**：
1. 从 DB 查询最近 N 条消息（`ORDER BY created_at DESC LIMIT 40`）
2. 反转为时间正序
3. 从旧到新逐条用 `estimate_tokens()` 累加，超过 `HISTORY_BUDGET` 停止
4. assistant 消息去除 `[来源N]` 标记（`re.sub(r'\[来源\d+\]', '', content)`，见 §8.4）
5. 返回 `[{role, content}, ...]`

### 8.3 窗口截断策略

- **Token 优先**：纯按消息条数截断不可靠（消息长短不一），从旧到新逐条移除直到 token 预算内
- **条数硬上限**：最多 20 条消息作为兜底（防止极端长消息撑爆上下文）
- **摘要压缩**：推迟到 Phase 6（P1）。额外 LLM 调用开销大，截断先够用

### 8.4 历史消息中 `[来源N]` 标记处理

**决策**：注入历史时**去除** assistant 消息中的 `[来源N]` 标记。

**理由**：旧轮次的 `[来源1]` 指向旧检索结果的 chunk A，本轮新检索结果的 `[来源1]` 指向不同的 chunk B——跨轮次编号冲突导致 LLM 混淆。用户说「来源3展开说说」的场景应由前端传递当前 sources 列表，而非依赖历史注入中的旧标记。

### 8.5 历史中 `thinking_content` 处理

**决策**：不注入。DeepSeek 思考链 token 开销大（通常 2-5K tokens），且与当前轮次无关。

### 8.6 `conversation.updated_at` 更新规则

**决策**：**每次新增 Message 后同步更新 `conversation.updated_at = now()`**。

否则 Sidebar 会话列表按更新时间倒序排列会出现错乱——创建于 3 天前但刚刚聊了 20 轮的会话会沉到底部。

### 8.7 会话删除策略

**决策**：**硬删除**。

```sql
DELETE FROM messages WHERE conversation_id = :id;
DELETE FROM conversations WHERE id = :id;
```

**理由**：项目规模无需软删除。软删除会污染所有查询条件、唯一索引和统计逻辑。

### 8.8 Message 元数据预留

**决策**：`messages` 表新增 `metadata JSON NULL DEFAULT NULL` 列，Phase 4 不使用。

**理由**：未来 Tool Call / Web Search / Agent 等场景需要存放 `tool_name` / `tool_result` / `latency` 等非结构化数据。现在加是一行 alembic migration，以后加是数据迁移 + 兼容处理。

### 8.9 闲谈路径下的历史消息注入

**问题场景**：

```
Q1: "报销制度是什么？"  →  知识查询，检索 + 注入历史
Q2: "谢谢"             →  闲谈（命中 _is_casual_chat），跳过检索
Q3: "审批时间呢？"       →  知识查询，需要 Q1 上下文才能理解
```

如果 Q2 闲谈路径不注入历史，LLM 在 Q2 回复时看不到 Q1 的对话上下文，可能给出「不客气！有什么可以帮助你的吗？」这样与业务无关的泛化回复。更重要的是，这会导致对话连续性断裂——用户在 Q2 后感知到「助手忘了我们在聊什么」。

**决策**：**闲谈路径同样注入历史消息**。

**实现要点**：
1. `_load_history()` 调用在 `_is_casual_chat()` 判断**之前**执行，历史消息对两条路径均可用
2. 闲谈路径：`CASUAL_SYSTEM_PROMPT` + 历史消息 + 当前问题 → LLM。检索步骤跳过，但对话上下文保留
3. 知识查询路径：`SYSTEM_PROMPT` + 历史消息 + 检索结果 + 当前问题 → LLM（不变）

**理由**：
- **对话连续性**：闲谈也是对话的一部分，LLM 需要上下文才能给出恰当的社交回应（如知道刚才在聊报销，回复「报销流程不客气！还有其他问题随时问我。」而非泛化问候）
- **下游轮次受益**：Q2 的 assistant 回复本身也会成为 Q3 的历史上下文。如果 Q2 回复脱离业务语境，Q3 的上下文质量也会下降
- **实现成本极低**：`_load_history()` 已实现（~40 行），闲谈路径复用即可，零额外代码
- **Token 开销可控**：历史注入已受 `HISTORY_BUDGET`（6000 tokens）独立截断，不会因闲谈路径额外膨胀

**`CASUAL_SYSTEM_PROMPT` 保持不变**：
```
你是 DocMind，一个企业知识库助手。请友好、简洁地回答用户的问题。
```
> System Prompt 本身不需要修改——对话语境通过历史消息自然传递。LLM 看到 `[user: 报销制度是什么?] [assistant: 根据...] [user: 谢谢]` 自然会在回复中体现上下文关联。

### 8.10 问题重写

**决策**：Phase 4 立即实现。原决策「推迟到 Phase 5，DeepSeek 结合 history 可自然消解指代」被多轮 RAG 回归测试证伪——检索发生在 LLM 之前，history 注入无法解决检索阶段的 query 歧义问题。

**设计细节见 §5.1.5**。要点：
- 轻量 `_needs_rewrite()` 触发判断（正常路径零额外延迟）
- History 仅取最近 2 轮（4 条消息）
- LLM 失败降级到原始 question
- 约 30 行实现（一次无状态 LLM 调用 + prompt + 降级）
- 不需要独立 API、不需要 SSE 事件、不需要前端展示

---

## 9. 基础设施加固设计 [Implemented: Phase 4]

> Phase 4 从 Phase 5 提前三项独立基础设施：错误处理 / Refresh Token / 结构化日志。均不依赖会话管理功能，可并行开发。

### 9.1 错误处理加固

#### 9.1.1 当前状态

已具备 `AppException` 基类（31 个子类）+ 全局 `RequestValidationError`（422/E9003）和 `Exception`（500/E9001）handler。响应格式统一为 `{code, message, detail}`。

#### 9.1.2 Phase 4 补充

| 任务 | 说明 |
|:---|:---|
| 异常→HTTP 状态码映射审计 | 遍历全部 31 个 `AppException` 子类，确认 `status_code` 与 API.md 错误码表一致 |
| 未知异常兜底 | `Exception` handler 增加 `DEBUG` 模式判断：生产环境返回 500 E9001 + 通用提示，屏蔽堆栈；开发环境返回完整 traceback |
| 异常日志 | 所有 handler 中调用结构化日志（见 §9.3），记录 `request_id` + `user_id` + `exception_type` + `traceback` |

#### 9.1.3 代码位置

```
backend/app/core/exceptions.py   ← 已有，不变
backend/app/main.py              ← handler 增强（堆栈屏蔽 + 日志）
```

### 9.2 Refresh Token 机制

#### 9.2.1 当前状态

纯无状态 JWT，`access_token` 有效期 24h，签发后无法主动吊销。用户改密/被踢下线后旧 token 仍有效，存在安全风险。

#### 9.2.2 设计方案

```
           ┌─────────────┐
登录/注册    │ access_token │  15min（短）
──→        │ refresh_token│  7天（长，哈希存 MySQL）
           └──────┬──────┘
                  │
    access_token 过期
    ──→ POST /api/auth/refresh  { refresh_token }
         │
         ├─ 验证 refresh_token 有效 + 未吊销
         ├─ 签发新 access_token + 新 refresh_token（Rotation）
         └─ 旧 refresh_token 标记失效
```

| 端点 | 方法 | 说明 |
|:---|:---|:---|
| `/api/auth/refresh` | POST | 用 refresh_token 换取新 token 对（Rotation） |
| `/api/auth/logout` | POST | 吊销当前 refresh_token |
| `/api/auth/password` | PUT | 改密后吊销该用户全部 refresh_token（强制下线） |

#### 9.2.3 存储方案

| 存储 | 内容 | 说明 |
|:---|:---|:---|
| MySQL `refresh_tokens` 表 | `id, user_id, token_hash, expires_at, revoked_at, created_at` | 持久化，查是否存在 + 是否过期 + 是否已吊销 |
| Redis（可选） | `refresh_token:{user_id}` → 最新 token_hash | 加速校验，命中跳过 MySQL 查询 |

> Phase 4 优先 MySQL 方案。Redis 缓存层作为可选优化，不阻塞进度。

#### 9.2.4 Rotation 安全机制

每次刷新时旧 refresh_token 立即失效，签发新 token 对：
- **防重放**：即使攻击者截获 refresh_token，用户正常刷新后攻击者的旧 token 已失效
- **泄露检测**：如果用已吊销的旧 token 请求刷新 → 说明 token 可能泄露 → 吊销该用户全部 refresh_token

#### 9.2.5 前端适配

- `api/index.js` 响应拦截器：收到 401 + `code=E5003`（Token 过期）时自动调 `/api/auth/refresh`
- 刷新成功后重放原请求，刷新失败（refresh_token 也过期/吊销）→ 跳转登录页
- Pinia `authStore` 新增 `refreshToken()` action + `scheduleRefresh()` 定时器（access_token 到期前 1 分钟自动刷新）

### 9.3 结构化日志

#### 9.3.1 设计目标

上线后定位问题不依赖「用户复述 + 翻代码猜测」。每条日志自包含上下文，可被日志聚合系统（ELK/Loki）索引。

#### 9.3.2 日志格式

```json
{
  "timestamp": "2026-06-05T10:30:00.123Z",
  "level": "INFO",
  "request_id": "a1b2c3d4",
  "user_id": 1,
  "phase": "retrieval",
  "message": "检索完成",
  "extra": {
    "kb_id": 1,
    "vector_ms": 120,
    "bm25_ms": 45,
    "rrf_ms": 2,
    "total_chunks": 8
  }
}
```

#### 9.3.3 关键埋点

| 阶段 | 记录内容 | 用途 |
|:---|:---|:---|
| 请求入口 | method + path + user_id + request_id | 请求追踪起点 |
| 检索 | kb_id + 向量耗时 + BM25 耗时 + RRF 耗时 + chunk 数 | 慢检索定位 |
| LLM 调用 | model + prompt_tokens + completion_tokens + 首 token 延迟 + 总耗时 | Token 消耗监控、慢 LLM 定位 |
| 异常 | request_id + user_id + exception_type + traceback | 错误追踪 |
| 入库流水线 | doc_id + 阶段 + 耗时 + 成功/失败 | 入库问题排查 |

#### 9.3.4 实现方案

使用 Python 标准库 `logging` + `python-json-logger`（如有）或自定义 `JSONFormatter`。通过中间件注入 `request_id`（`uuid4`），跨请求传递。

```
backend/app/core/logging.py   ← 新增：日志配置 + JSONFormatter
backend/app/main.py           ← 中间件注入 request_id
```

---

## 10. 当前决策与已知局限

### 10.1 ChromaDB 规模上限

- **当前方案**：共用 Collection + Metadata 隔离，适用于 **< 5 万 chunk** 总量
- **风险**：共享 Collection 下，`WHERE` 过滤发生在查询阶段而非索引阶段，chunk 数量增大后检索延迟线性增长
- **缓解**：当 total_chunks > 5 万或 P95 检索延迟 > 500ms 时，评估迁移至独立 Collection 方案
- **长期方向**：如业务需要支持 100 万+ chunk 规模，考虑迁移至 Milvus 或 Qdrant

### 10.2 Celery 任务超时

- 单文档入库 soft_time_limit 设为 600s（10 分钟）
- **风险**：超大 PDF（200+ 页）可能在 10 分钟内无法完成 Embedding API 调用
- **缓解**：超大文档在上传前建议拆分为子文档；后续可考虑分页并行 Embedding

### 10.3 BM25 实现

- 使用 rank-bm25 (BM25Okapi) + jieba 中文分词
- **风险**：IDF 基于初始化时语料固定，文档删除后不自动衰减；语料变更需重建实例
- **缓解**：BM25 仅作为 RRF 融合的一路信号，非最终排序依据；Rerank 阶段可修正排序偏差

### 10.4 LLM 幻觉与溯源准确性

- **风险**：LLM 可能引用不存在的文档内容（幻觉），或错误归因来源
- **缓解**：Prompt 中强调「仅基于提供的文档内容回答，无法回答时明确说明」；来源引用以 chunk_id 为准在 MySQL 中回溯文档名和页码

### 10.5 前端 JS/TS

- 当前使用 JavaScript，不引入 TypeScript
- **风险**：随着组件增多，props/events 类型缺少编译期检查
- **缓解**：保持组件数量可控（< 20 个）；如后续扩展团队，可渐进式迁移

> 部署架构、限流策略、监控告警方案详见 [§13 部署与运维设计](#13-部署与运维设计-planned-phase-5)。

---

## 11. 时区策略 [Implemented]

### 11.1 设计原则

项目采用**四层 UTC 统一**策略，确保时间数据在全链路中一致、可比较、可跨时区部署。

```
┌─────────────────────────────────────────────────────────────────┐
│                      时区数据流                                  │
│                                                                 │
│  MySQL                   后端                    前端           │
│  ┌──────────┐    ┌──────────────────┐    ┌──────────────────┐   │
│  │ DATETIME │───▶│ datetime.now(    │───▶│ new Date(        │   │
│  │ (UTC)    │    │   timezone.utc)  │    │   isoString)     │   │
│  │          │◀───│                  │    │                  │   │
│  │ CURRENT_ │    │ API: ISO 8601    │    │ 显示: 本地时区    │   │
│  │ TIMESTAMP│    │ +00:00           │    │                  │   │
│  └──────────┘    └──────────────────┘    └──────────────────┘   │
│       ▲                ▲                        ▲               │
│       │                │                        │               │
│  time_zone=     DateTime(timezone   new Date() 自动             │
│  '+00:00'       =True) 自动附加     转换为本地时区               │
│                  UTC tzinfo                                     │
└─────────────────────────────────────────────────────────────────┘
```

### 11.2 各层约定

| 层 | 约定 | 实施方式 |
|:---|:---|:---|
| **数据库** | 所有 DATETIME 列存储 UTC | MySQL 连接 `init_command=SET time_zone='%2B00:00'`；ORM `UTCDateTime` TypeDecorator（写入剥离 tzinfo / 读取附加 UTC tzinfo） |
| **后端** | 统一使用 `datetime.now(timezone.utc)` | CLAUDE.md 编码规范强制，禁止 `datetime.utcnow()` |
| **API** | 返回 ISO 8601 + `+00:00` 格式 | Pydantic 序列化 aware datetime → `2026-06-09T11:26:20+00:00` |
| **前端** | 按用户本地时区显示 | `new Date(isoString).toLocaleString('zh-CN', {...})` |

### 11.3 关键约束

- **禁止 `datetime.utcnow()`**（Python 3.12+ 已弃用）
- **禁止 `datetime.utcfromtimestamp()`**（同上）
- **禁止 naive datetime 写入数据库**：ORM `DateTime(timezone=True)` 在读取时自动附加 UTC tzinfo，写入时自动剥离
- **MySQL `DATETIME` vs `TIMESTAMP`**：项目使用 `DATETIME`（值不变）+ 约定 UTC，不使用 `TIMESTAMP`（会随会话时区自动转换，行为不透明）
- **Celery**：`timezone="Asia/Shanghai"` + `enable_utc=True`（调度用本地时间，消息传输用 UTC，仅影响日志/调度感知）

### 11.4 部署约束

- MySQL 服务器建议 `default_time_zone='+00:00'`
- 如无法修改全局配置，连接串 `init_command` 已确保会话级 UTC
- 开发和测试环境共用相同约定


## 13. 部署与运维设计 [Planned: Phase 5]

> Phase 5 需要完成三项运维基础设施：部署架构（Docker Compose + Nginx）、限流策略（滑动窗口 + Redis）、监控告警（结构化日志接入）。

### 13.1 部署架构

#### 13.1.1 Docker Compose 服务编排

```
┌─────────────────────────────────────────────────────────────┐
│                      Nginx (port 80/443)                     │
│  SSL 终结 + 反向代理 + 静态资源托管                            │
│  /api/*  → backend:8000     /  → frontend dist/              │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   FastAPI (uvicorn, port 8000)               │
│  api/ + services/ + rag/ + core/                            │
│  依赖: MySQL + Redis + ChromaDB                              │
└──────────┬──────────┬──────────┬────────────────────────────┘
           │          │          │
┌──────────▼──┐ ┌─────▼──────┐ ┌▼────────────────────────────┐
│   MySQL 8.0 │ │  Redis 7   │ │  ChromaDB (PersistentClient) │
│   port 3306 │ │  port 6379 │ │  嵌入式运行，挂卷持久化        │
│   volume 持久化│ │  volume 持久化│ │  ./chroma_data/               │
└─────────────┘ └────────────┘ └─────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│              Celery Worker（独立进程，同镜像）                  │
│  broker: Redis (db 2)    result_backend: Redis (db 1)        │
│  Windows: --pool=solo                                        │
└──────────────────────────────────────────────────────────────┘
```

#### 13.1.2 服务清单

| 服务 | 镜像 | 端口 | 环境变量 | 持久化 |
|:---|:---|:---|:---|:---|
| `mysql` | `mysql:8.0` | 3306 | `MYSQL_ROOT_PASSWORD` / `MYSQL_DATABASE` | `mysql_data:/var/lib/mysql` |
| `redis` | `redis:7-alpine` | 6379 | — | `redis_data:/data` |
| `backend` | 自建（`Dockerfile.backend`） | 8000 | `.env` 文件注入（DB/Redis/LLM API Key 等） | — |
| `celery` | 同 backend 镜像，不同 `command` | — | 同 backend | — |
| `frontend` | 自建（`Dockerfile.frontend`，Nginx + 静态资源） | 80/443 | — | — |

#### 13.1.3 Nginx 配置要点

```nginx
# /api/* → FastAPI backend
location /api/ {
    proxy_pass http://backend:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # SSE 支持：禁用缓冲
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 300s;  # SSE 长连接超时
}

# 静态资源（Vite 构建产物）
location / {
    root /usr/share/nginx/html;
    try_files $uri $uri/ /index.html;  # SPA fallback
}

# 上传文件大小限制
client_max_body_size 50M;
```

#### 13.1.4 部署约束

| 约束 | 说明 |
|:---|:---|
| ChromaDB 嵌入式运行 | 无需独立服务，挂卷 `chroma_data/` 目录即可持久化向量数据 |
| Celery Worker Windows | `--pool=solo`（Windows 不支持 fork），Linux 生产环境用默认 prefork |
| 时区 | 所有服务容器 `TZ=Asia/Shanghai`，MySQL `time_zone='+00:00'`（对齐 §12） |
| JWT 密钥 | 通过环境变量注入，禁止硬编码；生产环境须更换默认值 |
| CORS | 生产环境 `CORS_ORIGINS` 设为实际域名，禁止 `*` |

---

### 13.2 限流策略

#### 13.2.1 算法选型

**选择：固定窗口计数器（Fixed Window Counter）+ Redis 原子操作。**

| 候选方案 | 优点 | 缺点 | 结论 |
|:---|:---|:---|:---|
| 固定窗口 | 简单、Redis 原子操作（`INCR` + `EXPIRE`）、内存占用小 | 窗口边界突发（如 14:59:59 和 15:00:01 各发 N 次） | ✅ Phase 5 首选——上线初期够用，边界突发概率低 |
| 滑动窗口日志 | 精确、无边界效应 | 每个请求写一条 Redis record、内存占用大 | ❌ 过度设计 |
| 令牌桶 | 允许短时突发、平滑限流 | 需要后台 replenish 进程 | ❌ 过度设计 |

#### 13.2.2 Redis Key 设计

```
Key 格式:  rate_limit:{ip}:{endpoint_group}:{window_ts}
           例如: rate_limit:192.168.1.1:chat:1718006400

TTL:       window_seconds + 1（自动过期清理）

操作:
  INCR key        ← 原子递增计数器
  EXPIRE key TTL  ← 首次设置过期时间
  TTL key          ← 查询剩余时间（用于 X-RateLimit-Reset header）
```

#### 13.2.3 限流维度

| 接口组 | 包含端点 | 默认限制 | 说明 |
|:---|:---|:---|:---|
| `chat` | `POST /api/chat` | 30/min（压测后修正） | 核心功能，限制较宽松 |
| `upload` | `POST /api/documents` / `POST /api/documents/batch-upload` | 20/min（压测后修正） | 入库消耗大（Embedding API + 磁盘 IO） |
| `login` | `POST /api/auth/login` / `POST /api/auth/register` | 10/min | 防暴力破解，已有安全共识 |
| `default` | 其他所有 API | 120/min | 通用限制 |

> **阈值设定流程**：压测确定系统容量 → 取 P99 并发数的 70% 作为限流阈值 → 配置到 `.env` → 上线后根据监控数据迭代调整。开发阶段所有默认值设为极大（如 9999），防止干扰开发调试。

#### 13.2.4 响应格式

```http
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1718006460
Content-Type: application/json

{
  "code": "E9004",
  "message": "请求频率超限",
  "detail": "聊天接口限制 30 次/分钟，请稍后重试"
}
```

#### 13.2.5 配置项（config.py）

```python
# 限流
RATE_LIMIT_ENABLED: bool = True          # 限流开关
RATE_LIMIT_CHAT_PER_MINUTE: int = 30     # 聊天接口（压测后修正，当前占位 30）
RATE_LIMIT_UPLOAD_PER_MINUTE: int = 20   # 上传接口
RATE_LIMIT_LOGIN_PER_MINUTE: int = 10    # 登录接口
RATE_LIMIT_DEFAULT_PER_MINUTE: int = 120 # 其他接口
RATE_LIMIT_WINDOW_SECONDS: int = 60      # 窗口大小（秒）
```

#### 13.2.6 实现文件

```
backend/app/middleware/rate_limit.py   ← 新建：RateLimitMiddleware（纯 ASGI middleware）
backend/app/config.py                  ← 新增 6 个配置项
backend/app/main.py                    ← app.add_middleware(RateLimitMiddleware)
```

---

### 13.3 监控与告警

#### 13.3.1 设计原则

Phase 4 已完成结构化日志框架（`logging_config.py` — JSONFormatter + RequestIDFilter），Phase 5 在此基础上补充：
1. **关键埋点接入**（检索耗时、LLM 调用耗时）
2. **日志聚合方案**（开发/测试环境直接看 JSON 日志，生产环境对接 ELK/Loki）
3. **告警规则定义**（哪些指标异常时需要通知）

#### 13.3.2 关键埋点

| 阶段 | 记录内容 | 日志级别 | 用途 |
|:---|:---|:---|:---|
| 请求入口 | `request_id` + `method` + `path` + `user_id` + `client_ip` | INFO | 请求追踪起点 |
| 意图识别 | `request_id` + `intent` + `latency_ms` + `fallback`（是否降级） | INFO | 分类准确率监控 |
| Query Rewrite | `request_id` + `original_q` + `rewritten_q` + `latency_ms` | INFO | 改写覆盖率监控 |
| 检索 | `request_id` + `kb_id` + `vector_ms` + `bm25_ms` + `rrf_ms` + `total_chunks` | INFO | 慢检索定位 |
| LLM 调用 | `request_id` + `model` + `prompt_tokens` + `completion_tokens` + `ttft_ms`（首 token 延迟）+ `total_ms` | INFO | Token 消耗监控、慢 LLM 定位 |
| 异常 | `request_id` + `user_id` + `exception_type` + `traceback` | ERROR | 错误追踪 |
| 限流 | `client_ip` + `endpoint_group` + `current_count` + `limit` | WARNING | 限流触发监控 |

#### 13.3.3 日志聚合方案

| 环境 | 方案 | 说明 |
|:---|:---|:---|
| 开发/测试 | 控制台输出 JSON 日志 + `jq` 格式化查看 | 无需额外组件 |
| 生产 | Filebeat → Elasticsearch + Kibana（ELK）/ Promtail → Loki + Grafana | 推荐 Loki——轻量、与 Prometheus 集成好、存储成本低 |

> Phase 5 生产环境先部署 Loki + Grafana 方案（Docker Compose 增加 `loki` 和 `grafana` 服务），ELK 太重不适合小规模部署。

#### 13.3.4 应用级指标

| 指标 | 计算方式 | 告警阈值 | 仪表盘 |
|:---|:---|:---|:---|
| 请求延迟 P50/P99 | 从结构化日志 `latency_ms` 聚合 | P99 > 10s 告警 | Grafana 折线图（按 endpoint 分组） |
| 错误率 | `level=ERROR` 的日志占比 | > 1% 告警 | Grafana 单值 + 折线图 |
| LLM Token 消耗 | `prompt_tokens` + `completion_tokens` 按小时聚合 | 日消耗 > 预算 80% 告警 | Grafana 柱状图 |
| LLM API 失败重试 | `exception_type=LLMException` 计数 | 连续 5 次告警 | Grafana 计数 |
| 检索延迟 P99 | `vector_ms + bm25_ms + rrf_ms` 聚合 | P99 > 2s 告警 | Grafana 折线图 |
| 限流触发次数 | `level=WARNING` + `rate_limit` 计数 | 频繁触发（>50/min）告警 | Grafana 计数 |

#### 13.3.5 实现文件

```
backend/app/services/chat_service.py   ← 修改：检索阶段 + LLM 调用阶段埋点接入
backend/app/core/llm.py                ← 修改：LLM 调用埋点（ttft + 总耗时 + token 数）
docker-compose.yml                     ← 新增 loki + grafana 服务（可选）
```

> Phase 5 优先完成埋点接入。Loki + Grafana 部署作为可选增强——结构化日志已就绪，即使没有可视化仪表盘，`jq` 命令行也能做基本聚合分析。


---

## 12. 相关文档

- [产品需求文档](PRD.md)
- [数据库设计文档](../backend/docs/DATABASE.md)
- [接口文档](../backend/docs/API.md)
- [开发指南](DEVELOPMENT.md)
- [开发排期](ROADMAP.md)
- [测试策略](TESTING.md)
- [UI 设计规范](../frontend/docs/UIDESIGN.md)

---