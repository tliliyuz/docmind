# ARCHITECTURE — 架构设计文档

| 属性 | 值 |
|:---|:---|
| 文档版本 | v0.22 |
| 最后更新 | 2026-06-04 |
| 作者 | yuz |
| 状态 | 草稿（Phase 3 实现完成） |

---

## 当前实现状态说明

本文档包含已实现能力、当前阶段设计、最终目标架构三类内容，使用以下标记区分：

| 标记 | 含义 |
|:---|:---|
| `[Implemented]` | 当前已实现并可用 |
| `[Planned: Phase X]` | 计划在 Phase X 实现 |
| `[Target Architecture]` | 最终目标态，非当前状态 |

**当前开发进度**：Phase 3（核心问答）后端已完成，详见 [ROADMAP.md](ROADMAP.md)。

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
| 用户连续提问"怎么申请"，系统不知道在问什么 | **问题重写** | LLM 结合对话历史补全指代和上下文 | 多轮对话不丢失意图 | [Planned: Phase 4] |
| 用户问"今天天气"走知识库检索是浪费 | **意图识别** | LLM 分类：知识查询 / 闲聊 | 路由到正确处理分支 | [Planned: Phase 5] |
| 长对话 30 轮后 Token 超限 | **会话记忆** | 滑动窗口 + 旧消息 LLM 摘要压缩 | 记忆不丢，Token 受控 | [Planned: Phase 4] |

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

> 当前 Phase 2 尚未实现问答功能。Phase 3 将实现单轮问答核心链路（检索→RRF→NoopReranker→Prompt→LLM SSE），Phase 4 加入多轮对话（问题重写+会话记忆），Phase 5 加入意图识别。

```
用户提问
    ↓
[Intent] 意图识别 → 判断类型（查知识库 / 闲聊）       ← [Planned: Phase 5]
    ↓ （如果是查知识库）
[Rewrite] 问题重写 → 结合对话历史补全上下文              ← [Planned: Phase 4]
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

### 5.1 Phase 3 实际问答流程 [Implemented]

Phase 3 实现的是**单轮问答核心链路**，不含意图识别和问题重写：

```
用户提问
    ↓
[会话自动创建] conversation_id=null → 自动创建会话（不注入历史）
    ↓
[Retrieval] 多路检索 → 向量检索 + BM25 关键词检索   ← §5.1.1
    ↓
[Fusion] RRF 融合排序 → 合并两路结果
    ↓
[Rerank] NoopReranker → 保持 RRF 排序（相关性降序） + 截取 top_k=5
    ↓
[Prompt] 组装 Prompt → 拼接检索结果 + 用户问题，软上限预算控制  ← §5.1.2
    ↓
[LLM] 调用 LLM → 流式 `chat/completions`，解析 content + reasoning_content
    ↓
[SSE] StreamingResponse → 6 事件类型 + 15s 心跳  ← §5.1.3
    ↓
[标题生成] 截取用户问题前 12 字 → event: finish 返回 title
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
- `event: sources` 仅发送被 LLM 实际引用的 chunk（而非进入 Prompt 的全部 chunk）
- LLM 一个都未引用时，sources 事件不发送（与「未找到相关信息」抑制逻辑互补）
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

    # 1. 意图识别 — [Planned: Phase 5]
    # intent = await intent_classifier.classify(question)

    # 2. 问题重写 — [Planned: Phase 4]
    # history = await get_conversation_history(conversation_id)
    # question = await question_rewriter.rewrite(question, history)

    # 3. 多路检索 — [Phase 3]
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
            # 6a. 引用过滤：仅发送 LLM 实际引用的 [来源N] chunk
            cited_indices = _extract_citation_indices(assistant_content)
            cited_chunks = [c for i, c in enumerate(used_chunks)
                            if str(i + 1) in cited_indices]
            if cited_chunks and not _is_not_found(assistant_content):
                yield sse_event("sources", _build_sources(cited_chunks))
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

## 8. 会话记忆策略 [Planned: Phase 4]

- **滑动窗口**：保留最近 N 轮对话（默认 10 轮）
- **摘要压缩**：超过窗口的旧消息用 LLM 生成摘要
- **Token 控制**：总上下文 Token 数不超过模型上限的 80%

---

## 9. 当前决策与已知局限

### 9.1 ChromaDB 规模上限

- **当前方案**：共用 Collection + Metadata 隔离，适用于 **< 5 万 chunk** 总量
- **风险**：共享 Collection 下，`WHERE` 过滤发生在查询阶段而非索引阶段，chunk 数量增大后检索延迟线性增长
- **缓解**：当 total_chunks > 5 万或 P95 检索延迟 > 500ms 时，评估迁移至独立 Collection 方案
- **长期方向**：如业务需要支持 100 万+ chunk 规模，考虑迁移至 Milvus 或 Qdrant

### 9.2 Celery 任务超时

- 单文档入库 soft_time_limit 设为 600s（10 分钟）
- **风险**：超大 PDF（200+ 页）可能在 10 分钟内无法完成 Embedding API 调用
- **缓解**：超大文档在上传前建议拆分为子文档；后续可考虑分页并行 Embedding

### 9.3 BM25 实现

- 使用 rank-bm25 (BM25Okapi) + jieba 中文分词
- **风险**：IDF 基于初始化时语料固定，文档删除后不自动衰减；语料变更需重建实例
- **缓解**：BM25 仅作为 RRF 融合的一路信号，非最终排序依据；Rerank 阶段可修正排序偏差

### 9.4 LLM 幻觉与溯源准确性

- **风险**：LLM 可能引用不存在的文档内容（幻觉），或错误归因来源
- **缓解**：Prompt 中强调「仅基于提供的文档内容回答，无法回答时明确说明」；来源引用以 chunk_id 为准在 MySQL 中回溯文档名和页码

### 9.5 前端 JS/TS

- 当前使用 JavaScript，不引入 TypeScript
- **风险**：随着组件增多，props/events 类型缺少编译期检查
- **缓解**：保持组件数量可控（< 20 个）；如后续扩展团队，可渐进式迁移

> TODO: [待补充] 部署架构图 — 生产环境的 Nginx 反向代理、SSL 终结、静态资源托管策略。
> TODO: [待补充] Refresh Token 设计 — 当前为纯无状态 JWT，access_token 签发后无法主动吊销（如改密/踢下线），token 过期后需重新登录。后续引入 refresh_token（长有效期，哈希存 MySQL/Redis），搭配 access_token（短有效期），支持无感续期和主动吊销。
> TODO: [待补充] 监控与告警方案 — 应用级指标（请求延迟、错误率）+ LLM 调用监控（Token 消耗、API 失败重试）。

---

## 10. 相关文档

- [产品需求文档](PRD.md)
- [数据库设计文档](../backend/docs/DATABASE.md)
- [接口文档](../backend/docs/API.md)
- [开发指南](DEVELOPMENT.md)
- [开发排期](ROADMAP.md)
- [测试策略](TESTING.md)
- [UI 设计规范](../frontend/docs/UIDESIGN.md)
