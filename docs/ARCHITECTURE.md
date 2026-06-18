# ARCHITECTURE — 架构设计文档

| 属性 | 值          |
|:---|:-----------|
| 文档版本 | v1.0       |
| 最后更新 | 2026-06-18 |

> 本文档描述 DocMind 系统的目标架构设计。实现进度和开发排期见 [ROADMAP.md](ROADMAP.md)。

---

## 1. 技术选型

| 层面 | 技术 | 说明 |
|:---|:---|:---|
| 后端框架 | FastAPI | 异步 Python Web 框架，原生支持 SSE |
| AI 编排 | LangChain | RAG 链路编排，但不依赖其高级封装 |
| LLM | DeepSeek (OpenAI 兼容接口) | 支持 OpenAI / 通义千问 / DeepSeek 等互换 |
| Embedding | DashScope text-embedding-v3 | 1024 维向量，中文优化 |
| 向量数据库 | ChromaDB | 嵌入式运行，零配置，轻量级场景首选 |
| 关系数据库 | MySQL + aiomysql | 业务数据持久化 |
| 异步 ORM | SQLAlchemy 2.0 async | Mapped 类型注解 + async session |
| 缓存 | Redis | 会话缓存 + Celery broker |
| 异步入库 | Redis + Celery | 文档入库异步任务队列 |
| 文档解析 | PyPDF2 + python-docx | 多格式文档统一提取纯文本 |
| 智能分块 | RecursiveCharacterTextSplitter | 固定大小分块，分隔符优先级切分 |
| 关键词检索 | rank-bm25 (BM25Okapi) + jieba 分词 | 成熟库，支持自定义 tokenizer（详见 §7.2） |
| 文件存储 | 本地磁盘（可扩展至 OSS） | 抽象 StorageBackend 接口，当前本地实现 |
| 流式输出 | SSE (Server-Sent Events) | 实时推送 LLM 生成内容 |
| 前端框架 | Vue 3 + Vite | Composition API + SFC |
| UI 组件库 | Element Plus | 企业级 Vue 3 组件库 |
| 状态管理 | Pinia | Vue 3 官方推荐 |
| 前端语言 | JavaScript | SFC + JS（非 TypeScript），见 §7.4 |
| Markdown 渲染 | markdown-it | 问答内容渲染 |
| HTTP 客户端 | Axios | 前端请求封装 |
| 前端路由 | Vue Router | SPA 路由管理 |
| 图标库 | Font Awesome 6 Free | UI 图标统一方案 |
| 时区策略 | 四层 UTC 统一 | DB(UTC) → 后端 → API(ISO 8601) → 前端本地显示，详见 §11 |
| 限流 | 固定窗口计数器 + Redis | IP 级频率限制，4 接口组独立阈值，详见 §12.2 |
| 部署方案 | Docker Compose + Nginx | 5 服务编排，详见 §12.1 |
| 监控告警 | 结构化日志 → Loki + Grafana | 应用级指标 + LLM 调用监控，详见 §12.3 |
| Trace 链路追踪 | MySQL traces 表 + JSON 字段 | 问答全链路各阶段耗时记录 |
| 可视化图表 | ECharts 5 | Admin 统计页图表，从 traces 表聚合 |

---

## 2. 系统架构概览

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
│  │  Intent → KnowledgePipeline（Rewrite→双路检索→RRF→   │   │
│  │           Rerank→Evidence→Prompt）→ LLM SSE            │   │
│  └────────────────────────┬───────────────────────────────┘   │
│                           │                                   │
│  ┌──────────┬─────────────┼──────────────┬────────────────┐  │
│  │ChromaDB  │   MySQL     │    Redis     │  File Storage  │  │
│  │(via      │  (业务数据)  │  (缓存/队列) │  (文档文件)    │  │
│  │BaseVec-  │             │              │                │  │
│  │torStore) └─────────────┴──────────────┴────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              Celery Worker（异步入库）                  │    │
│  │  Parser → Chunker → Embedder → vector_store + MySQL   │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. 核心功能模块

### 3.1 模块总览：业务痛点 → 技术方案

| 业务痛点 | 对应模块 | 技术方案 | 效果 |
|:---|:---|:---|:---|
| 文档格式五花八门（PDF/Word/MD） | **文档解析** | PyPDF2 + python-docx | 统一提取纯文本 |
| 完整文档太长，无法直接检索 | **智能分块** | 固定大小分块，重叠窗口保留上下文 | 检索粒度精准，不丢上下文 |
| 大文件（100页PDF）上传后同步处理，用户等很久 | **异步入库** | Redis + Celery 异步任务 | 上传即返回，后台处理 |
| 关键词搜索"墨盒怎么换"找不到"打印机耗材更换" | **多路检索** | 向量检索（语义）+ BM25（关键词）+ RRF 融合 | 召回率大幅提升 |
| 搜出来的结果排序不准 | **Rerank 重排序** | DashScope Rerank API 语义精排 | 相关文档排在前面 |
| 用户连续提问"怎么申请"，系统不知道在问什么 | **问题重写** | LLM 结合对话历史补全指代和上下文 | 多轮对话不丢失意图 |
| 用户问"今天天气"走知识库检索是浪费 | **意图识别** | 规则优先 + Flash 模型兜底：知识查询 / 闲聊 / 元问题 | 路由到正确处理分支 |
| 长对话 30 轮后 Token 超限 | **会话记忆** | 滑动窗口 + Token 预算四池子分拆独立截断 | 记忆不丢，Token 受控，RAG 不退化 |

### 3.2 模块树

```
DocMind
├── 文档入库（Ingestion）
│   ├── 文档上传 & 格式解析
│   ├── 文本分块策略
│   ├── Embedding 向量化
│   └── 向量入库（BaseVectorStore/ChromaDB）
├── 智能问答（Chat）
│   ├── KnowledgePipeline（检索+上下文构建管线）
│   │   ├── 意图识别
│   │   ├── 问题重写
│   │   ├── 多路检索（向量 + BM25）
│   │   ├── RRF 融合排序
│   │   ├── Rerank 重排序
│   │   ├── 句级修辞过滤（陈述知识 vs 引用知识，ADR-019）
│   │   ├── Evidence Highlight（句级 BM25 定位）
│   │   └── Prompt 组装（宽松策略，Recall 优先）
│   ├── LLM 调用 & SSE 流式输出
│   └── 证据审计（三层程序级审计，ADR-020）
├── 权限控制（Permissions）
│   ├── require_kb_readable（visibility 优先）
│   ├── require_kb_writable（ownership 基础）
│   └── require_kb_owner（owner-only 写操作）
├── 会话管理（Session）
│   ├── 多轮对话上下文
│   ├── 滑动窗口记忆
│   └── 会话 CRUD
├── 知识库管理（Knowledge Base）
│   ├── 知识库 CRUD
│   ├── 文档列表 & 状态
│   └── 分块可视化
├── 管理后台（Admin）
│   ├── 系统统计（ECharts 可视化）
│   ├── Trace 链路追踪（性能观测）
│   ├── 知识库管理（跨用户）
│   ├── 文档管理（跨库）
│   └── 用户管理（CRUD + 角色 + 审计）
└── 意图识别（Intent）
    ├── 意图分类（知识查询 / 闲聊 / 元问题）
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
> **reprocess 流程**：仅 `partial_failed` / `failed` 终态允许触发。流程为：`vector_store.delete(where={"doc_id": doc_id})` 清理向量存储旧向量 → 删除 MySQL 旧 chunk 记录（FK CASCADE）→ 重置 status 为 uploaded → 重新 dispatch `ingest_document`。必须在重置状态前清理向量存储，否则新文档分块数少于旧文档时残留向量无法被覆盖。

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
- **结构感知分块（扩展）**：Markdown 标题层级感知，当前固定大小分块已满足需求，后续可增强

---

### 4.3 向量存储批量写入

- **批次大小**：配置化 `CHROMA_BATCH_SIZE=100`（100~500 chunks/batch）
- **禁止单条循环**：避免高频小写入导致 IO 抖动
- **代码模板**（通过 `BaseVectorStore.add()` 抽象接口）：
  ```python
  for batch in batches(chunks, settings.CHROMA_BATCH_SIZE):
      await vector_store.add(
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

> **设计要点**：接口层标记 `deleting` + 返回 202；Celery Worker 异步清理 ChromaDB 向量 + 磁盘文件 + 物理 DELETE（`delete_document` / `delete_kb` 任务）。

**删除流程**：
```
接口层: status = deleting → 返回 202 Accepted
         ↓
Celery Worker（异步）:
  1. vector_store.delete(where={"doc_id": doc_id})  — 清理向量存储向量
  2. 删除磁盘文件（uploads/{kb_id}/{doc_id}/ 目录）
  3. DELETE FROM documents WHERE id=?  — 物理删除文档记录
     └─ FK ON DELETE CASCADE 自动级联删除 chunks
  4. UPDATE knowledge_bases SET
       doc_count = GREATEST(0, doc_count - 1),
       chunk_count = GREATEST(0, chunk_count - N)  — 原子递减计数
```
> **注意**：`chunk_count` / `doc_count` 须在物理删除文档后使用 `func.greatest(0, col - N)` 原子递减，防止并发场景下计数为负。API 响应不直接读取这两个缓存列，而是通过 `_get_real_chunk_counts()` / `_get_real_doc_counts()`（`knowledge_base_service.py`）从对应表实时 COUNT，避免脏值残留导致计数与实际不符。

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

## 5. 问答流程

> 各阶段详细设计见 [RAG_PIPELINE.md](../backend/docs/RAG_PIPELINE.md)。

### 5.1 管线阶段总览

```
用户提问
    ↓
[Intent] 意图识别 → 知识查询 / 闲聊 / 元问题
    ↓ （知识查询路径）
┌─ KnowledgePipeline ─────────────────────────────────────────────────────┐
│ [Rewrite] 问题重写 → 结合对话历史补全上下文                                │
│     ↓                                                                    │
│ [Retrieval] 多路检索 → 向量检索 + BM25 关键词检索                          │
│     ↓                                                                    │
│ [Fusion] RRF 融合排序 → 合并两路结果                                       │
│     ↓                                                                    │
│ [Rerank] 重排序 → DashScope Rerank API 精排（Phase 5.5）                    │
│     ↓                                                                    │
│ [句级修辞过滤] 过滤引用性句子 → 仅保留陈述知识（ADR-019）                    │
│     ↓                                                                    │
│ [Evidence] 句级 BM25 定位 → 每个 chunk 内选出最佳证据句                     │
│     ↓                                                                    │
│ [Prompt] 组装 Prompt → 宽松 Prompt 策略 + 检索结果 + 历史 + 用户问题    │
└──────────────────────────────────────────────────────────────────────────┘
    ↓
[LLM] 调用 LLM → SSE 流式返回答案
    ↓
[证据审计] 三层程序级审计 → 引用存在性 + 来源一致性 + 句级证据回溯（ADR-020）
    ↓
[sources] SSE 事件 → 含 confidence / confidence_note 置信度标注 + section_title / section_path 章节元数据
```

### 5.2 各阶段设计要点速览

| 阶段 | 核心决策 | 详见 |
|:-----|:---------|:-----|
| 多路检索 | 向量（BaseVectorStore/ChromaDB 1024 维）+ BM25（rank-bm25 + jieba）双路检索，三级缓存（进程内/Redis/MySQL） | [RAG_PIPELINE.md §2](../backend/docs/RAG_PIPELINE.md) |
| RRF 融合 | `score(doc) = Σ 1/(k + rank_i)`，k=60，合并两路结果 | [RAG_PIPELINE.md §2.3](../backend/docs/RAG_PIPELINE.md) |
| Prompt 组装 | 宽松 Prompt 策略（Recall 优先）+ 软上限 + 相关性优先填充，Token 预算四池子分拆（见 §8 会话记忆） | [RAG_PIPELINE.md §3](../backend/docs/RAG_PIPELINE.md) |
| SSE 事件流 | 6 事件类型（meta/thinking/message/sources/finish/error）+ 15s 心跳；sources 事件含 `confidence`/`confidence_note` 置信度字段 | [RAG_PIPELINE.md §5](../backend/docs/RAG_PIPELINE.md) |
| Query Rewrite | 仅检查 13 个歧义信号词触发，LLM 改写 + 降级，正常路径零额外延迟 | [RAG_PIPELINE.md §4](../backend/docs/RAG_PIPELINE.md) |
| 意图识别 | 规则优先（<1ms, ~90% 流量）+ Flash 模型兜底（~1-2s, ~10% 流量） | [RAG_PIPELINE.md §6](../backend/docs/RAG_PIPELINE.md) |
| 句级修辞过滤 | 规则层 + 结构层判断句子修辞角色（陈述/引用），过滤引用性句子，宁可放过不可错杀 | [RAG_PIPELINE.md §7](../backend/docs/RAG_PIPELINE.md), [ADR-019](decisions/ADR-019-句级修辞过滤.md) |
| Evidence Highlight | 检索时句级 BM25 选句（修辞过滤后执行），解耦 LLM 引用格式，确定性定位 | [RAG_PIPELINE.md §7](../backend/docs/RAG_PIPELINE.md) |
| 三层证据审计 | 程序级三层检查：引用存在性 + 来源一致性 + 句级证据回溯，LLM 流后执行，不影响 SSE 输出 | [RAG_PIPELINE.md §9](../backend/docs/RAG_PIPELINE.md), [ADR-020](decisions/ADR-020-三层证据审计.md) |
| Trace 链路追踪 | MySQL traces 表 + JSON 字段，各阶段独立计时，Admin 统计 + ECharts 可视化 | [RAG_PIPELINE.md §8](../backend/docs/RAG_PIPELINE.md) |

### 5.3 降级策略概览

各阶段均遵循**保守降级**原则：失败时不阻断主流程，回退到上一可用状态。

| 阶段 | 降级行为 |
|:-----|:---------|
| Query Rewrite | LLM 失败 → 使用原始 question |
| 意图识别 | Flash 模型失败 → 正则回退 → 保守 KNOWLEDGE |
| BM25 缓存 | Redis 不可用 → MySQL 懒加载重建 |
| 句级修辞过滤 | 过滤后为空 → 回退到原始 chunk 内容（宁可放过不可错杀） |
| Evidence Highlight | 切句失败 → `preview_text = None`，前端自行降级 |
| LLM 调用 | 流式失败 → `event: error` + 全量 sources |
| 三层证据审计 | 审计执行失败 → 跳过审计，sources 事件不含 confidence 字段，前端不展示警告 |

> **设计决策**：[ADR-022](decisions/ADR-022-问答Service层三模块拆分.md)（2026-06-18 采纳）——`chat_service.py`（1015 行）拆分为 `chat_service.py`（入口+校验+re-export）+ `sse_stream.py`（SSE 流生成+消息持久化）+ `chat_helpers.py`（辅助函数），零破坏性拆分。

### 5.4 SSE 流 DB 会话生命周期解耦

> **设计决策**：[ADR-017](decisions/ADR-017-SSE流DB会话生命周期解耦.md)（2026-06-15 采纳）

SSE 流式期间 Generator 不再持有外部 `db` 连接，持久化阶段自管短生命周期 session，避免连接池被长连接耗尽（15 并发 SSE 即占满 `pool_size=5, max_overflow=10`）。

| 决策点 | 说明 |
|:---|:---|
| Session 自管 | Generator 内部 `async with async_session()` 创建独立短 session，LLM 流式阶段不占用 DB 连接，DB 占用从 30s 降至 ~10ms |
| 单事务提交 | 消息 + Trace 同一事务 `commit()`，`TraceRecorder.finish()` 新增 `commit=False` 参数由外层统一提交，避免部分落库 |
| 对象重查询 | `conv` 跨 session 处于 detached 状态，通过 `await s.get(Conversation, conv.id)` 重新绑定并获取最新状态 |

---

## 6. 多路检索设计

> 详细实现参见 [RAG_PIPELINE.md §2](../backend/docs/RAG_PIPELINE.md)。

| 路径 | 技术 | 关键参数 |
|:---|:---|:---|
| 向量检索 | BaseVectorStore/ChromaDB + DashScope text-embedding-v3 | 1024 维 / cosine / top_k=10 / Per-KB collection `kb_{kb_id}` 路由（`where` 仅用于 doc 级过滤） |
| BM25 关键词 | rank-bm25 (BM25Okapi) + jieba 分词 | 三级缓存（进程内 60s / Redis 300s / MySQL 懒加载）；`BM25_LOCAL_CACHE_MAX_CHUNKS=5000`（大 KB 跳过进程内缓存）；`BM25_MAX_CHUNKS=10000`（超大 KB 完全跳过 BM25，避免 OOM）；详见 [RAG_PIPELINE.md §2.2](../backend/docs/RAG_PIPELINE.md) |
| RRF 融合 | `score(doc) = Σ 1/(k + rank_i(doc))`，k=60 | 合并两路结果，降低单一排序极端排名影响 |

---


## 7. 关键设计决策

### 7.1 向量存储抽象层（BaseVectorStore）

> **设计决策**：[ADR-018](decisions/ADR-018-向量存储抽象层.md)（2026-06-15 采纳）

**架构**：引入 `BaseVectorStore` ABC（定义 `search`/`add`/`delete` 三个核心操作），`ChromaVectorStore` 为当前唯一实现。通过 `get_vector_store()` 工厂函数获取实例，解耦 ChromaDB 依赖。所有向量操作通过 `asyncio.to_thread()` 卸载到线程池，保持异步接口统一。

**Collection 策略**：**Per-KB Collection**（`kb_{kb_id}`），每个知识库独立 ChromaDB collection。通过 `kb_id` 路由到对应 collection，查询时完全消除 `where` metadata 过滤。根因：ChromaDB 的 metadata filter 做全扫描不利用 HNSW 索引，带 `where={"kb_id": kb_id}` 的查询耗时 16.4s vs 无过滤 35ms（~470× 差距）。Per-KB 策略将查询耗时降至 ~35ms。`BaseVectorStore` 接口中 `where` 参数保留仅用于可选的 doc 级过滤（如 `where={"doc_id": 42}`）。

**metadata 类型一致性**：ChromaDB 对 metadata 值的类型敏感（整数 `1` 和字符串 `"1"` 视为不同值）。强制约定 metadata 值统一使用原生 int（`kb_id`/`doc_id`/`chunk_index`），入库和查询两端直接传 int，禁止字符串化。`kb_id` 在 Per-KB collection 的 metadata 中保留（冗余但便于调试和潜在回滚）。

**KB 删除**：`store.delete(kb_id=kb_id)` 直接 drop 整个 `kb_{kb_id}` collection（O(1)），同时清理进程内缓存。doc 级删除 `store.delete(kb_id=kb_id, where={"doc_id": x})` 在指定 KB collection 内按条件删除。

**持久化与初始化**：`PersistentClient`，数据持久化到 `CHROMA_PERSIST_DIR`（默认 `./chroma_data`）。`init_chroma()` 仅创建 `PersistentClient`，不预创建任何 collection。`ChromaVectorStore` 内部按 `kb_id` 懒加载 `get_or_create_collection(f"kb_{kb_id}")`，确保 FastAPI（lifespan）和 Celery Worker（独立进程）两种运行时都能正确初始化。索引 `hnsw:space=cosine`（余弦相似度）。

### 7.2 BM25 实现方案

当前：**rank-bm25 (BM25Okapi) + jieba 中文分词**。选型理由：接受 `tokenizer` 参数传入 `jieba.lcut`；260 行单文件仅依赖 numpy；NumPy 向量化性能优秀。IDF 静默衰减对 RAG 影响有限（仅 RRF 一路信号）。索引缓存详见 [RAG_PIPELINE.md §2.2](../backend/docs/RAG_PIPELINE.md)。

### 7.3 Rerank 策略

**DashScope Rerank API（qwen3-rerank）**：中文场景首选，有免费额度。对 RRF 融合结果做语义精排，按 relevance_score 降序排列。API 异常时降级回退到原始 RRF 排序（`retrieval_output.results[:top_k]`），不阻断检索管线。

### 7.4 前端语言选型

**JavaScript（非 TypeScript）**：个人项目 JS 开发效率更高；前端规模可控（~12 组件）；可渐进式迁移。

### 7.5 LLM 模型选择策略

**双模型架构**：pro 模型用于主回复（高质量长文本 + 深度思考），flash 模型用于辅助任务（意图分类 / 问题改写 / 标题生成，短输出延迟敏感）。共享同一 `base_url` / `api_key`，仅 `model` 参数不同。

### 7.6 文件存储策略

当前：**本地磁盘**（`uploads/{kb_id}/{doc_id}/{uuid}_{sanitized_filename}`），抽象 `StorageBackend` 接口，可扩展 OSS/MinIO。

---

### 7.7 知识库可见性模型（弱混合模式）

> **权威定义**：[PRD.md §5](PRD.md#5-知识库可见性模型) — 包含完整 CRUD 权限矩阵、检索范围规则和设计原理。

**核心原则**：`visibility` 控制 READ（谁能看），`ownership` 控制 WRITE（谁能改），admin 拥有管理级 WRITE 覆盖（可删除/修正元数据，但不上传文档）。

**实现层**：`app/core/permissions.py` 提供三个共享权限函数（`require_kb_readable` / `require_kb_writable` / `require_kb_owner`），所有 KB 接口和 service 层统一调用。两步校验不可合并：先判断 visibility（能否读），再判断 ownership（能否写）。禁止硬编码「只有 owner 能看/改 KB」的假设。

---

## 8. 会话记忆策略

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

system prompt → 历史消息 → 当前 question。`load_history()` 从 DB 查询最近 40 条消息，反转为时间正序，从旧到新累加 token 直到 `HISTORY_BUDGET`。

### 8.3 窗口截断策略

Token 优先（从旧到新逐条移除）+ 条数硬上限 20 条兜底。摘要压缩为扩展功能。

### 8.4 `[来源N]` 标记处理

注入历史时**去除** assistant 消息中的 `[来源N]`：旧轮次编号指向旧 chunk，与新检索结果编号冲突。

### 8.5 `thinking_content` 处理

不注入：DeepSeek 思考链 token 开销大（2-5K），与当前轮次无关。

### 8.6 `conversation.updated_at` 更新规则

每次新增 Message 后同步更新，否则 Sidebar 会话列表排序错乱。

### 8.7 会话删除策略

**硬删除**：项目规模无需软删除，软删除会污染所有查询条件和统计逻辑。

### 8.8 Message 元数据预留

`messages.metadata JSON NULL` 为后续 Tool Call / Web Search 等场景预留。

### 8.9 闲谈路径下的历史消息注入

**闲谈路径同样注入历史消息**：`load_history()` 在意图判断之前执行，保证对话连续性。闲谈用 `CASUAL_SYSTEM_PROMPT`（定义于 `app/rag/knowledge_pipeline.py`）+ 历史 + 当前问题，跳过检索但保留上下文。

### 8.10 问题重写

设计细节见 [RAG_PIPELINE.md §4](../backend/docs/RAG_PIPELINE.md)。要点：轻量 `needs_rewrite()` 触发判断（正常路径零额外延迟），仅取最近 2 轮（4 条消息），LLM 失败降级到原始 question。

### 8.11 外部资源 UUID 化

> **表结构详见**：[DATABASE.md §2.5](../backend/docs/DATABASE.md#25-会话表-conversations)（双字段方案的存储格式、UUID 生成策略和索引设计）。

**双字段方案**：`id BIGINT AUTO_INCREMENT`（内部主键）+ `uuid CHAR(36) UNIQUE`（外部标识符）。

| 资源 | 决策 | 原因 |
|:---|:---|:---|
| KB / Document / Conversation | ✅ 改造 | 天然共享资源，ID 枚举风险 |
| Trace | ✅ 移除自增 id | 已有 UUID（trace_id） |
| User | ⚠️ 暂缓 | Admin 接口仅开发者使用，收益极低 |
| Message / Chunk | ❌ 不改造 | 无独立接口 / 数据量大 |

优势：零影响外键关系；内部 JOIN 保持 BIGINT 性能；UUID 仅在 API 边界解析。

---

## 9. 基础设施加固设计

### 9.1 错误处理加固

`AppException` 基类 + 全局 handler：`RequestValidationError`→422/E9003，`Exception`→500/E9001。响应格式统一 `{code, message, detail}`。生产环境屏蔽堆栈，开发环境透出。handler 中集成结构化日志（§9.3），记录 `request_id`+`user_id`+`exception_type`+`traceback`。

> 错误码详见 [API.md §1.4](../backend/docs/API.md#14-统一错误码)。

### 9.2 Refresh Token 机制

**决策**：`access_token` 15min（短，无状态）+ `refresh_token` 7 天（长，哈希存 MySQL `refresh_tokens` 表）。

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

| 端点 | 说明 |
|:---|:---|
| `POST /api/auth/refresh` | 验证 refresh_token → 签发新 token 对 + 吊销旧 token（Rotation 防重放） |
| `POST /api/auth/logout` | 吊销当前 refresh_token |
| `PUT /api/auth/password` | 改密后吊销该用户全部 refresh_token（强制下线） |

**Rotation 安全机制**：用已吊销的旧 token 请求刷新 → 判定泄露 → 吊销该用户全部 token。前端 Axios 拦截器自动静默刷新（401+E5003 触发），access_token 到期前 1 分钟主动刷新。

**共享基础设施**：`revoke_all_user_tokens(db, user_id)` 由 `auth_service` 和 `admin_service` 共用（改密/禁用/重置密码后强制下线）。

> 数据模型详见 [DATABASE.md §2.7](../backend/docs/DATABASE.md#27-refresh_tokens)，前端交互详见 [FRONTEND.md §1.3.1](../frontend/docs/FRONTEND.md#131-axios-拦截器自动刷新流程)。

### 9.3 结构化日志

JSON 格式日志，每条自包含 `request_id`+`user_id`+`phase`+`extra`，可被 ELK/Loki 索引。中间件注入 `request_id`（`uuid4`）。

**日志格式示例**：
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

| 埋点 | 关键字段 | 用途 |
|:---|:---|:---|
| 请求入口 | method, path, user_id, client_ip | 追踪起点 |
| 意图识别 | intent, latency_ms, fallback | 分类准确率监控 |
| Query Rewrite | original_q, rewritten_q, latency_ms | 改写覆盖率监控 |
| 检索 | vector_ms, bm25_ms, rrf_ms, total_chunks | 慢检索定位 |
| LLM 调用 | model, prompt_tokens, completion_tokens, ttft_ms, total_ms | Token 消耗、慢 LLM |
| 异常 | exception_type, traceback | 错误追踪 |
| 限流 | client_ip, endpoint_group, current_count | 限流触发监控 |

实现：Python `logging` + 自定义 `JSONFormatter`（`backend/app/core/logging.py`），中间件注入 `request_id`。生产推荐 Loki + Grafana（Docker Compose 增加 `loki`/`grafana` 服务），ELK 太重不适合小规模部署。

---

## 9a. ECharts 可视化集成

Admin 统计页使用 ECharts 5 渲染图表，数据从 `traces` 表聚合（`/api/admin/stats/traces`）。

| 图表 | 数据源 | 说明 |
|:---|:---|:---|
| 问答量趋势 | `traces.status` 按天 GROUP BY | 折线图（成功绿/失败红） |
| 响应时间分布 | `traces.total_duration_ms` 分位数 | P50/P95/P99 折线图 |
| Token 使用统计 | `traces.generate` JSON 提取 | 堆叠柱状图（Input/Output） |

> 前端封装 `useECharts()` 组合式函数（响应式 resize + dispose）。

---

## 9b. 用户管理模块

**设计原则**：复用 `users` 表，admin 专属，v1 不新增审计日志表。API 详见 [API.md §7](../backend/docs/API.md#7-管理后台接口)。

### 9b.1 认证链路分层

三层职责分离，保持关注点独立：

| 层级 | 组件 | 职责 | 查 DB |
|:---|:---|:---|:---|
| L1 | `AuthMiddleware` | JWT 解码 → `request.state` | 否 |
| L2 | `get_current_user` | 查 `user.status`，disabled→401 E5010 | 是 |
| L3 | `require_admin` | 检查 `role==admin`，非 admin→403 | 否 |

**决策**：禁用检查放 L2（`get_current_user` 依赖）而非 L1（Middleware）。Middleware 保持无状态无 DB 依赖，L2 天然可用 `Depends(get_db)`。

### 9b.2 禁用用户三层拦截

| 入口 | 拦截点 | 错误码 |
|:---|:---|:---|
| `POST /api/auth/login` | 密码验证通过后、签发 token 前 | E5010 |
| `POST /api/auth/refresh` | `db.get(User)` 后 | E5010 |
| 任意认证 API | `get_current_user` 依赖 | E5010 |

**三端协同**：login 拦截获取新 token、refresh 拦截续期、API 拦截兜底（15min 内生效）。禁用/重置密码后吊销全部 refresh_token（复用 §9.2 `revoke_all_user_tokens`）。

---

## 10. 已知局限

| 局限 | 说明 | 缓解 |
|:-----|:-----|:-----|
| 向量存储规模上限 | ChromaDB 单实例总向量数上限受 SQLite 性能约束 | 单 collection 规模问题已通过 Per-KB Collection 策略解决（§7.1）；总体规模限制取决于磁盘和内存；BaseVectorStore 抽象层（ADR-018）已支持未来切换向量库 |
| Celery 任务超时 | 单文档入库 soft_time_limit=600s，超大 PDF（200+ 页）可能超限 | 建议超大文档拆分为子文档上传 |
| LLM 幻觉 | LLM 可能引用不存在的文档内容 | Prompt 强调仅基于文档回答；来源以 chunk_id 回溯 |

> 各 RAG 管线阶段的已知局限详见 [RAG_PIPELINE.md](../backend/docs/RAG_PIPELINE.md) 对应章节。
> 部署架构、限流策略、监控告警方案详见 [§12 部署与运维设计](#12-部署与运维设计)。

---

## 11. 时区策略

> **ORM 层实现详见**：[DATABASE.md §0](../backend/docs/DATABASE.md#0-时区约定)（`UTCDateTime` TypeDecorator 的 aware ↔ naive 双向转换机制）。

**四层 UTC 统一**，确保时间数据在全链路中一致、可比较、可跨时区部署。

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

| 层 | 约定 | 实施方式 |
|:---|:---|:---|
| 数据库 | 所有 DATETIME 存储 UTC | 连接 `init_command=SET time_zone='%2B00:00'`；ORM `UTCDateTime` TypeDecorator |
| 后端 | `datetime.now(timezone.utc)` | CLAUDE.md 强制，禁止 `datetime.utcnow()` |
| API | ISO 8601 + `+00:00` | Pydantic 序列化 aware datetime |
| 前端 | 本地时区显示 | `new Date(isoString)` 自动转换 |

**关键约束**：禁止 naive datetime 写入 DB；用 `DATETIME`（值不变+约定 UTC）而非 `TIMESTAMP`（自动转换不透明）；Celery `timezone="Asia/Shanghai"` + `enable_utc=True`（调度用本地时间，消息传输用 UTC）；MySQL 服务器建议 `default_time_zone='+00:00'`，连接串 `init_command` 确保会话级 UTC。


## 12. 部署与运维设计

### 12.1 部署架构

**5 服务编排**：MySQL + Redis + Backend（uvicorn）+ Celery Worker + Nginx（前端托管 + 反向代理）。

```
┌─────────────────────────────────────────────────────────────┐
│                      Nginx (port 80)                          │
│  反向代理 + 静态资源托管（SSL 终结）                              │
│  /api/*  → backend:8000     /  → frontend dist/              │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   FastAPI (uvicorn, port 8000)               │
│  api/ + services/ + rag/ + core/                            │
│  新增：rag/vector_store.py（BaseVectorStore ABC + ChromaVectorStore）  │
│       rag/knowledge_pipeline.py（检索+上下文构建管线）        │
│       core/permissions.py（KB 权限共享函数）                 │
│  依赖: MySQL + Redis + ChromaDB（via BaseVectorStore）       │
└──────────┬──────────┬──────────┬────────────────────────────┘
           │          │          │
┌──────────▼──┐ ┌─────▼──────┐ ┌▼────────────────────────────┐
│   MySQL 8.0 │ │  Redis 7   │ │  ChromaDB (PersistentClient) │
│   port 3306 │ │  port 6379 │ │  嵌入式运行，挂卷持久化        │
│   volume 持久化│ │  volume 持久化│ │  ./chroma_data/               │
└─────────────┘ └────────────┘ └─────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│              Celery Worker（独立进程，同镜像）                  │
│  broker: Redis (db 0)    result_backend: Redis (db 1)        │
│  Windows: --pool=solo                                        │
└──────────────────────────────────────────────────────────────┘
```

**服务清单**：

| 服务 | 镜像 | 端口 | 环境变量 | 持久化 |
|:---|:---|:---|:---|:---|
| `mysql` | `mysql:8.0` | 3306 | `MYSQL_ROOT_PASSWORD` / `MYSQL_DATABASE` | `mysql_data:/var/lib/mysql` |
| `redis` | `redis:7.0-alpine` | 6379 | — | `redis_data:/data` |
| `backend` | 自建（`Dockerfile.backend`） | 8000 | `.env` 文件注入（DB/Redis/LLM API Key 等） | — |
| `celery` | 同 backend 镜像，不同 `command` | — | 同 backend | — |
| `frontend` | 自建（`Dockerfile.frontend`，Nginx + 静态资源） | 80 | — | — |

**Nginx 配置要点**：

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

**部署约束**：

| 约束 | 说明 |
|:---|:---|
| ChromaDB 嵌入式运行 | 无需独立服务，挂卷 `chroma_data/` 目录即可持久化向量数据 |
| Celery Worker Windows | `--pool=solo`（Windows 不支持 fork），Linux 生产环境用默认 prefork |
| 时区 | 所有服务容器 `TZ=Asia/Shanghai`，MySQL `time_zone='+00:00'` |
| JWT 密钥 | 通过环境变量注入，禁止硬编码；生产环境须更换默认值 |
| CORS | 生产环境 `CORS_ORIGINS` 设为实际域名，禁止 `*` |

---

### 12.2 限流策略

#### 12.2.1 算法与 Redis Key 设计

**固定窗口计数器** + Redis 原子操作（`INCR`+`EXPIRE`）。

| 候选方案 | 优点 | 缺点 | 结论 |
|:---|:---|:---|:---|
| 固定窗口 | 简单、Redis 原子操作、内存占用小 | 窗口边界突发 | ✅ 首选——上线初期够用 |
| 滑动窗口日志 | 精确、无边界效应 | 每请求写一条 Redis record | ❌ 过度设计 |
| 令牌桶 | 允许短时突发 | 需后台 replenish 进程 | ❌ 过度设计 |

Key 格式 `rate_limit:{ip}:{endpoint_group}:{window_ts}`，TTL `window_seconds+1` 自动过期。

#### 12.2.2 限流维度

| 接口组 | 包含端点 | 默认限制 | 说明 |
|:---|:---|:---|:---|
| `chat` | `POST /api/chat` | 60/min（压测后修正） | 核心功能，限制较宽松 |
| `upload` | `POST /api/documents` / `POST /api/documents/batch-upload` | 20/min（压测后修正） | 入库消耗大（Embedding API + 磁盘 IO） |
| `login` | `POST /api/auth/login` / `POST /api/auth/register` | 10/min | 防暴力破解，已有安全共识 |
| `default` | 其他所有 API | 120/min | 通用限制 |

> **阈值设定流程**：压测确定系统容量 → 取 P99 并发数的 70% 作为限流阈值 → 配置到 `.env` → 上线后根据监控数据迭代调整。开发阶段所有默认值设为极大（如 9999），防止干扰开发调试。

#### 12.2.3 响应格式

```http
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1718006460
Content-Type: application/json

{
  "code": "E9004",
  "message": "请求频率超限",
  "detail": "聊天接口限制 60 次/分钟，请稍后重试"
}
```

#### 12.2.4 配置项

```python
# backend/app/config.py
RATE_LIMIT_ENABLED: bool = True
RATE_LIMIT_CHAT_PER_MINUTE: int = 60
RATE_LIMIT_UPLOAD_PER_MINUTE: int = 20
RATE_LIMIT_LOGIN_PER_MINUTE: int = 10
RATE_LIMIT_DEFAULT_PER_MINUTE: int = 120
RATE_LIMIT_WINDOW_SECONDS: int = 60
```

开发阶段所有默认值设为极大（如 9999），防止干扰开发调试。实现文件：`backend/app/middleware/rate_limit_middleware.py`（纯 ASGI middleware）。

---

### 12.3 监控与告警

在结构化日志框架基础上（§9.3），生产环境推荐 Loki + Grafana（Docker Compose 增加 `loki`/`grafana` 服务），ELK 太重不适合小规模部署。

| 指标 | 计算方式 | 告警阈值 |
|:---|:---|:---|
| 请求延迟 P99 | 结构化日志 `latency_ms` 聚合 | > 10s |
| 错误率 | `level=ERROR` 日志占比 | > 1% |
| LLM Token 日消耗 | `prompt_tokens + completion_tokens` 按小时聚合 | > 预算 80% |
| 检索延迟 P99 | `vector_ms + bm25_ms + rrf_ms` 聚合 | > 2s |
| 限流触发 | `level=WARNING` + `rate_limit` 计数 | > 50/min |

> 关键埋点字段详见 [§9.3 结构化日志](#93-结构化日志)。Phase 5 优先完成埋点接入，Loki + Grafana 部署作为可选增强——结构化日志已就绪，`jq` 命令行也能做基本聚合分析。


---

## 13. 相关文档

- [产品需求文档](PRD.md)
- [RAG 管线详细设计](../backend/docs/RAG_PIPELINE.md)
- [数据库设计文档](../backend/docs/DATABASE.md)
- [接口文档](../backend/docs/API.md)
- [开发指南](DEVELOPMENT.md)
- [开发排期](ROADMAP.md)
- [测试策略](tests/TESTING.md)
- [UI 设计规范](../frontend/docs/UIDESIGN.md)

---