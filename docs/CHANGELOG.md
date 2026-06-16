# Changelog

DocMind 项目所有重要变更。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/)。

设计决策详见 [`docs/decisions/`](docs/decisions/)。

---

## [Unreleased] - 2026-06-16

### Added
- **Chunk 元数据增强（§8.7）**：`chunker.py` 新增 `_detect_sections()` / `_resolve_section()` 从 Markdown 标题提取章节层级；`ChunkResult` 新增 `section_title` / `section_path` 字段；`Chunk.metadata_` 从 `{"page": N}` 扩展为含章节信息；ChromaDB metadata 从 3 字段扩展到 5 字段（+`section_title` / `section_path`）；`RetrievalResult` 新增章节字段并在 `_parse_results()` 中从 ChromaDB 回填；`fusion.py` RRF 融合保留章节字段
- **章节号 BM25 增强（§8.8）**：`bm25.py` 新增 `detect_section_numbers()` 检测用户提问中的章节号模式（§3.2 / 4.7 / 8.2.1 / 第四章 / 第4.7节）；新增 `_match_section_numbers()` 章节元数据匹配；BM25 缓存结构扩展 `section_info` 列表，向后兼容旧缓存；搜索时对匹配 chunk 做分数加权（正分 ×2.0，负分 ÷2.0）
- **DOCX 标题样式→Markdown 标记**：`parser.py` 新增 `_docx_heading_to_markdown()`，将 Word 标题样式（Heading 1-6 / outlineLevel / Title）自动转换为 Markdown `#` 标记，使 chunker 的章节检测跨 MD/DOCX 格式统一工作
- **Prompt 章节信息展示**：`_format_chunk_reference()` 从 `[来源1]（文档: API.md）` 升级为 `[来源1]（文档: API.md | 章节: API > §6 SSE > §6.1）`
- 新增 53 个单元测试覆盖 §8.7 / §8.8（chunker 章节检测 16 + BM25 检测/boost 18 + prompt 格式化 4 + retriever 回填 3 + parser 已由现有测试覆盖）

### Changed
- `BM25Retriever._load_and_cache()` 新增加载 `Chunk.metadata_` 列；进程内缓存结构从 4-tuple 扩展为 5-tuple（含 `section_info`）；`_get_bm25_index()` 返回值增加 `section_info`
- `filter_chunk_sentences()` 返回值从 `str` 改为 `tuple[str, FilterStats]`，影响 `knowledge_pipeline.py` 调用方和 6 个测试用例
- `KnowledgePipelineResult` 新增 `evidence_review: EvidenceReviewResult | None` 字段
- `TraceDetailResponse` 新增 `evidence_review: EvidenceReviewSpan | None` 字段
- `TraceRecorder.finish()` response_mode 推导逻辑增加 REJECT 分支
- `config.py` 新增 `BM25_SECTION_BOOST_FACTOR: float = 2.0` 配置项

### Removed
- **移除 A/B 实验调试开关**：删除 `P0_STRICT_MODE`（严格/宽松 Prompt 切换）、`SENTENCE_ROLE_FILTER`（句级修辞过滤开关）、`DASHSCOPE_RERANK`（DashScope/Noop Reranker 切换）三个配置项。固化生产配置为：宽松 Prompt + DashScopeReranker + 句级修辞过滤（始终启用）
- **移除 `NoopReranker`**：删除占位 Reranker 实现，`DashScopeReranker` API 异常时内部已有 RRF 排序降级逻辑
- **移除 `SYSTEM_PROMPT_TEMPLATE_STRICT`**：删除「陈述知识 vs 引用知识」严格 Prompt 模板，保留宽松 Prompt 作为唯一模板

### Fixed
- **孤儿会话三个备份字段不落库**：`_delete_kb_async` Step 5 的 `update(Conversation).values(kwargs)` ORM 列映射有歧义，`original_kb_id`/`original_kb_name`/`original_kb_uuid` 三个字段在 KB 物理删除前未写入，导致 `_enrich_kb_status` 检测 `original_kb_uuid is None` → `kb_status=None` → 前端 `isKbOrphaned=false` → 孤儿保护全部失效（可重新生成、可发消息）。修复：Step 5 改用 `text()` raw SQL 显式传参，日志新增 `rowcount` 输出
- **空知识库（0 文档）仍可问答且 LLM 无来源生成答案**：KB 文档数检查只在 `execute_knowledge` 内部（仅 KNOWLEDGE 意图触发），CASUAL 意图走 `execute_casual` 完全跳过检查 → LLM 无上下文直接生成答案。修复：后端 `_validate_and_prepare` 将 KB 可检索文档数检查提前到意图分支之前；前端 `chat.js` 新增 `isKbEmpty` 计算属性（KB 存在但不在可选列表）；`ChatPage.vue` 空 KB 警告横幅 + 输入禁用 + `handleSend` 拦截；`MessageItem.vue` 空 KB 时隐藏重新生成按钮
- `_docx_heading_to_markdown()` 防御性设计：MagicMock 等非真实对象导致属性访问异常时降级为普通文本提取，不影响现有测试
- **`list_traces()` status 查询 mock 兼容**：`status_q` 使用 `select(Trace.status, func.count())` 返回多列 Row，测试 mock 中为纯 tuple。将 `row.status`/`row.cnt` 属性访问改为 `row[0]`/`row[1]` 索引访问，同时兼容 SQLAlchemy Row 和 mock tuple
- **`list_traces` 测试 mock 数据不完整**：`list_traces()` 内部最多 5 次 `db.execute` 调用（count → status → avg → durations → data），但测试只 mock 了 2 个 side_effect 值。新增 `_make_execute_chain()` 辅助函数，为 total>0 场景自动生成完整 5 个 mock 结果
- **`test_models.py` KnowledgeBase uuid 缺省值**：`knowledge_bases.uuid` 列仅有 `server_default=text("(UUID())")`，测试用 DB 表未执行迁移导致 INSERT 时缺少默认值。修复：测试显式传入 `uuid=str(uuid4())`
- **ROADMAP.md §8.5 污染问题回归测试标记**：该回归测试已通过验证，状态从 ⬜ 更新为 ✅

---

## [0.7.0] - 2026-06-15

### Added
- **Phase 5.5 — Prompt 陈述知识 vs 引用知识原则**：`SYSTEM_PROMPT_TEMPLATE` 从简单的「请仅基于文档回答」升级为完整的陈述知识/引用知识判断框架，包含核心原则、判断方法、必然属于引用知识的场景枚举、拒答规则。预计单独消除 60-80% 的「引用知识被当成答案」问题
- **Phase 5.5 — 句级修辞过滤**：`sentence_matcher.py` 新增 `detect_sentence_role()` 和 `filter_chunk_sentences()` 函数，基于 `_REFERENTIAL_PATTERNS` 规则层（显式标记 + 结构层 JSON/代码块检测）在 chunk 内部过滤引用性句子，解决 Chunk 内部混合陈述句和引用句的污染问题；`knowledge_pipeline.py` 在 `match_sentences()` 前插入过滤步骤
- **Phase 5.5 — 程序级三层证据审计**：新增 `app/rag/evidence_auditor.py` 模块，实现引用存在性检查（第一层）、来源一致性检查（第二层）、句级证据回溯（第三层）。审计在 LLM 流完成后、sources 事件构建阶段执行，不影响 SSE 流输出。sources 事件新增 `confidence` / `confidence_note` 字段
- **Phase 5.5 — 前端置信度展示**：`MessageItem.vue` 新增置信度警告组件，当证据审计发现 medium/low 置信度时展示警告提示和详细说明；`chat.js` store 从 sources SSE 事件中提取 `confidence` / `confidence_note` 字段
- **Phase 5.5 §8.6 — DashScope Rerank API 接入**：`reranker.py` 新增 `DashScopeReranker(BaseReranker)` 类，调用 DashScope text-rerank API（`gte-rerank-v2`）对 RRF 融合结果做语义精排。支持指数退避重试（默认 3 次）、API 异常降级回退到原始 RRF 排序。`knowledge_pipeline.py` 默认使用 `DashScopeReranker` 替换 `NoopReranker`。`config.py` 新增 `RERANK_BASE_URL`/`RERANK_MODEL`/`RERANK_MAX_RETRIES`/`RERANK_TIMEOUT` 配置项。新增 22 个 DashScopeReranker 单元测试
- **ADR-019 句级修辞过滤**：架构决策记录，覆盖修辞角色判定、过滤策略、Prompt 模板升级设计
- **ADR-020 三层证据审计**：架构决策记录，覆盖三层审计机制、综合置信度计算、容错策略

### Changed
- **Phase 5.5 知识库质量治理**：句级修辞过滤 + 三层证据审计组合预计消除 85%+ 的污染问题，总代码量 ~200 行，无 DB 变更
- **ROADMAP.md**：新增 Phase 5.5「知识库质量治理」（§8），插入 Phase 5（§7）和 Phase 6（§9）之间，含 §8.1-§8.7 子任务（Prompt 升级 / 修辞过滤 / 证据审计 / 前端置信度 / 测试 / 推迟项 / DashScope Reranker）；Phase 5 状态 → ✅；Phase 6 重编号为 §9
- **ARCHITECTURE.md**：§3.2 模块树新增修辞过滤和证据审计节点；§5.1 管线流程图新增修辞过滤和证据审计步骤；§5.2 设计表新增 3 行；§5.3 降级策略表新增 2 行
- **RAG_PIPELINE.md**：§1.1-§1.2 流程图新增修辞过滤和证据审计步骤；§3 Prompt 模板升级为陈述/引用知识判断框架；新增 §7 句级修辞过滤 + Evidence Highlight；新增 §9 三层证据审计；§10 伪代码更新；§11 源文件表新增 evidence_auditor.py
- **DEVELOPMENT.md**：目录结构树新增 evidence_auditor.py，更新 sentence_matcher.py / prompt_builder.py / knowledge_pipeline.py 描述
- **TEST_CASES.md**：§7.5 标题更新为「句级修辞过滤 + Evidence 定位」，新增 P5.5-SF.1-SF.7（7 用例）；新增 §7.6 三层证据审计，P5.5-EA.1-EA.14（14 用例）；新增 §10 DashScope Reranker 测试用例（10 用例，待实现）；§7.7-§7.11 重编号；覆盖率表更新 sentence_matcher.py / evidence_auditor.py / reranker.py 行
- **TESTING.md**：v1.0→v1.1；新增 §2.3 RAG 管线新增阶段测试原则（分层边界测试 / 回退路径测试 / 确定性验证 / SSE 字段传播）；新增 §9 修辞过滤与证据审计测试策略（含逐层独立测试 / 综合置信度矩阵 / 容错降级 / SSE 传播）；§10 执行计划新增 Phase 5.5 条目（5 行）
- **FRONTEND.md**：sources 事件描述新增 confidence / confidence_note 字段；sources 渲染规范新增置信度警告；MessageItem 组件描述更新
- **文档一致性修复**（D2-D9）：① API.md §3 移除 `selectable` 接口过时的「实现：Phase 3」标注；② API.md 文档列表/详情/分块接口权限描述更新，反映 v0.50 `allow_public_read` 变更；③ DATABASE.md + ORM 模型 `uuid` 列 COMMENT 从「UUID v4」修正为「UUID」；④ ROADMAP.md §4.5 移除已实现的推迟项；⑤ DEVELOPMENT.md 移除已废弃的 `sse-starlette` 依赖、标注 `unstructured` 为死依赖；⑥ PRD.md §6 验收标准 MRR/Precision@5 标注「压测待补充」
- **BaseVectorStore 抽象基类 + ChromaVectorStore 实现**（A1+A3）：定义 `search`/`add`/`delete` 三个核心异步接口。新增 `get_vector_store()` 工厂函数。详见 [ADR-018](decisions/ADR-018-向量存储抽象层.md)
- **KnowledgePipeline 知识管线**（A2）：从 `chat_service.py` 解耦提取检索+上下文构建管线（查询重写→双路检索→RRF融合→Rerank→句子匹配→Prompt构建）
- **共享权限检查函数**（A4）：`require_kb_readable` / `require_kb_writable` / `require_kb_owner`（`core/permissions.py`）
- `VectorRetriever` 依赖 `BaseVectorStore` 抽象而非 ChromaDB `Collection`
- KB 权限检查统一使用 `core/permissions.py` 共享函数
- 前端 `TERMINAL_STATUSES` 消除 `DocumentList.vue` 值重复，新增 `TERMINAL_STATUSES_SET` 导出
- `document_service.py` / `ingest/tasks.py` / `eval_retrieval.py` 使用 `get_vector_store()` 替代 `get_collection()`
- Celery task 别名统一：`_delete_doc_task` → `delete_doc_task`、`_ingest_doc_task` → `ingest_doc_task`（B9）
- `_load_doc()` 返回值从 `Document | None` 改为 `_LoadDocResult` 数据类（B8）
- RAG 硬编码参数移入 `config.py`：`EMBED_TIMEOUT`/`INTENT_MAX_TOKENS`/`REWRITE_MIN_LENGTH`/`REWRITE_HISTORY_MESSAGES`/`BM25_LOCAL_CACHE_TTL`（B7）

### Fixed
- `ThreadedRedisClient.close()` 从 `pass` 改为调用 `asyncio.to_thread(self._sync.close)`，避免资源泄漏（B2）
- `_delete_kb_async` 添加幂等锁，对齐 `_delete_document_async` 并发安全模式（B3）
- `requirements.txt` 移除未使用的 `sse-starlette==2.1.*` 依赖（B5）
- **KnowledgeDetail.vue 多文件上传未调用批量接口**：校验阶段将文件分为无冲突组和需覆盖组，无冲突文件批量上传，有冲突文件单文件覆盖
- **TraceList.vue 概览卡片统计仅基于当前页数据**：后端新增 `TraceListSummary` 模型和 SQL 聚合查询，前端 `summary` 从 `computed` 改为 `ref`
- **Trace 链路 `reranker` 标识硬编码 `"noop"`**（`trace_recorder.py:173` + `knowledge_pipeline.py:178`）：`record_rerank()` 默认参数 `reranker="noop"` 导致 Trace 中永远写入 `"noop"`，Ignore 实际使用的 `DashScopeReranker`。修复：`NoopReranker`/`DashScopeReranker` 各自新增 `name` 类属性（`"noop"`/`"dashscope"`），`knowledge_pipeline.py` 调用时传入 `reranker=self._reranker.name`
- **Trace 链路 `finish_reason` 硬编码 `"stop"`**（`chat_service.py:344`）：`record_generate()` 的 `finish_reason` 写死为 `"stop"`，未捕获 DeepSeek 流式 API 返回的真实 `finish_reason`（`LLMChunk.finish_reason`）。修复：流式循环中捕获 `llm_finish_reason = chunk.finish_reason`，传入 `record_generate()` 时用 `llm_finish_reason or "stop"` 兜底
---

## [0.53] - 2026-06-15

### Fixed
- **3 个测试用例修复**（mock 路径/异常类型过时）：① `test_tasks.py` 幂等锁集成测试 mock 目标从同步 `acquire_idempotency_lock` 改为异步 `acquire_idempotency_lock_async`；② `test_bm25.py` 异步缓存失效测试 patch 路径从定义处 `app.core.redis_client.get_async_redis` 改为使用处 `app.rag.bm25.get_async_redis`；③ `test_embedder.py` 重试失败断言从 `RuntimeError` 对齐为 `EmbeddingTimeoutException`
- **SSE 流 DB 会话生命周期解耦**（N3）：`_generate_sse_stream()`/`_generate_meta_response()` 移除 `db: AsyncSession` 参数，generator 内部 `async with async_session()` 创建独立短生命周期 session。消息 + Trace 单事务提交（`commit=False` → 统一 `await s.commit()`），`yield finish` 在 session 外部。`record_trace()`/`TraceRecorder.finish()` 新增 `commit: bool = True` 参数。详细设计见 [ADR-017](docs/decisions/ADR-017-SSE流DB会话生命周期解耦.md)
- **模板内联 style 清理**（N10）：6 个 Vue 文件（DocumentList/KnowledgeList(admin)/TraceList/AdminUserList/KnowledgeDetail/KnowledgeList）的 ~18 处模板内联 `style` 迁移到 CSS 类（`filter-input-*`/`table-full`/`search-icon`/`icon-gap-*`/`text-*`），消除硬编码布局值和间距值
- **test_sources_preview.py 条件断言**（T1）：2 处 `if ...:` 包裹断言改为 `assert ... is not None` 前置校验 + 无条件断言，消除条件断言反模式
- **test_admin_service.py mock 重复**（T4）：提取 `_setup_db_list_mock()` 辅助函数，替换全部 ~15 处重复的 `count_mock + data_mock + db.execute = AsyncMock(side_effect=[...])` mock 模式
- **test_intent.py 测试名实不符**（T5）：`test_meta_routing_returns_fixed_response` 重命名为 `test_meta_routing_raises_exception_before_retrieval`，更新 docstring 反映实际断言行为（`MetaQuestionException`）
- **test_sentence_matcher.py 弱断言**（T6/T10）：`assert len(...) > 0` 改为 `assert "病假" in ...` 语义断言；4 处 `is not None`/`isinstance` 弱断言改为 `isinstance(score, float)` 类型断言（BM25 单文档语料 IDF 可为负值，不强制正数约束）
- **test_trace_service.py 无意义断言**（T7）：`assert total_duration_ms >= 0` 前添加 `assert isinstance(total_duration_ms, int)` 类型断言
- **test_intent.py 弱断言**（T8）：`assert result.metadata["model"] is not None` 改为 `assert isinstance(..., str)` + `assert len(...) > 0`
- **test_trace_service.py 弱断言**（T9）：`get_trace_detail` 测试中 `is not None` 弱断言改为 Pydantic 模型属性断言（`result.intent.span_name`/`result.retrieve.duration_ms`）
- **test_query_rewriter.py 公共 API 测试**（T11）：新增 2 个通过公共 `rewrite_query()` 的集成测试（无历史时 LLM 调用、完整问题经 LLM 返回不变）

### Changed
- **test_intent.py import 顺序**（N25）：`from unittest.mock import MagicMock` 从文件末尾移至顶部统一导入
- **test_query_rewriter.py 技术债务标注**（N26/T11）：`TestNeedsRewrite` 类添加技术债务注释，说明直接测试私有函数 `_needs_rewrite()` 的原因及后续改进方向
- **test_trace_service.py 私有属性访问**（N27）：4 个 TraceRecorder 测试改为通过 `finish(db)` 公共接口写入后验证 `db.add.call_args`，不再直接访问 `_generate_data`/`_intent_data` 等私有属性；`TestTraceRecorder` 类添加技术债务注释
- **test_document_service.py / test_bm25.py 技术债务标注**（T2）：为私有方法测试类添加技术债务注释，说明保留原因及后续改进方向
- **.env 配置同步**（N14 关联）：`JWT_EXPIRE_MINUTES=1440` → `ACCESS_TOKEN_EXPIRE_MINUTES=15`，与 config.py 默认值对齐

## [0.52] - 2026-06-15

### Fixed
- **bm25.py 局部导入**（`backend/app/rag/bm25.py:314`）：`get_async_redis` 在 `invalidate_bm25_cache_async()` 内局部导入（违反 CLAUDE.md 禁止函数内局部导入）。修复：`get_async_redis` 移至顶部 `from app.core.redis_client import` 统一导入
- **admin_service.py 未使用导入**（`backend/app/services/admin_service.py:7-8`）：`import os` 和 `from pathlib import Path` 从未使用。修复：直接移除
- **document_service.py logger 导入顺序**（`backend/app/services/document_service.py:4-6`）：`logger = logging.getLogger(__name__)` 夹在两个 import 语句中间（违反 PEP 8 导入顺序）。修复：logger 移至全部导入完成后
- **schemas/__init__.py 相对导入**（`backend/app/schemas/__init__.py:3-40`）：5 处 `from .xxx import` 相对导入。修复：全部改为 `from app.schemas.xxx import` 绝对导入
- **embedder.py 裸 RuntimeError/ValueError**（`backend/app/rag/embedder.py:84,98,104`）：Embedding API 重试耗尽抛 `RuntimeError`，响应格式异常/数量不匹配抛 `ValueError`（违反 CLAUDE.md 业务异常继承 AppException）。修复：分别改为 `EmbeddingTimeoutException`（E2008）和 `VectorStoreErrorException`（E2007）
- **document_service.py ChromaDB 同步调用阻塞事件循环**（`backend/app/services/document_service.py:148-151, 453-455`）：`collection.delete()` 为 ChromaDB 同步 SQLite IO，直接调用阻塞 async 事件循环。修复：包装到 `asyncio.to_thread(collection.delete, ...)`
- **storage.py 同步文件 IO 未包装**（`backend/app/core/storage.py:66,70,77,82,87`）：`async def save/read/delete` 内直接调用同步 `mkdir/write_bytes/read_bytes/unlink/rmdir`，阻塞事件循环。修复：5 处同步 IO 全部包装到 `asyncio.to_thread()`
- **Celery 异步任务内同步 Redis**（`backend/app/ingest/tasks.py:110,472,481,506,562,567` + `backend/app/ingest/lock.py` + `backend/app/core/redis_client.py`）：`_ingest_document_async()` / `_delete_document_async()` 内调用同步 `acquire_idempotency_lock()` / `invalidate_bm25_cache()` / `release_idempotency_lock()`，阻塞 Celery worker 内的事件循环。修复：`lock.py` 新增 `acquire_idempotency_lock_async()` / `release_idempotency_lock_async()`；`tasks.py` async 函数内改用异步版；`ThreadedRedisClient` 新增 `set()` 方法支持 `EX`/`NX` 参数
- **AdminLayout 侧边栏宽度硬编码**（`frontend/src/components/layout/AdminLayout.vue:120`）：`width: 220px` 未引用 Design Token（`--dm-sidebar-width-admin: 240px`）。修复：替换为 `var(--dm-sidebar-width-admin)`
- **chat.js 不必要的动态导入**（`frontend/src/api/chat.js:55`）：`fetchSelectableKBs()` 内 `await import('./index.js')` 非循环导入、非可选依赖场景。修复：改为顶部静态 `import api from './index.js'`
- **MessageItem.vue evidence highlight 硬编码**（`frontend/src/components/chat/MessageItem.vue:574`）：`background: #FFF3B0` 硬编码未引用 Design Token（`--dm-warning-light` 过淡不可辨）。修复：`global.css` 新增 `--dm-evidence-highlight-bg: #FFF3B0`，组件引用 `var(--dm-evidence-highlight-bg)`
- **LoginPage.vue box-shadow 硬编码**（`frontend/src/views/LoginPage.vue:214`）：`box-shadow: 0 1px 3px rgba(0,0,0,0.10)` 未引用 Token。修复：替换为 `var(--dm-shadow-sm)`
- **chunker.py 页分隔符隐式依赖**（`backend/app/rag/chunker.py:110`）：`pos += len(page.content) + 2` 的 `+2` 隐式依赖 `parser.py` 的 `"\n\n"` 分隔符（脆弱跨模块耦合）。修复：提取 `_PAGE_SEPARATOR = "\n\n"` + `_PAGE_SEPARATOR_LEN = 2` 常量，添加与 `parser.py` 同步的注释说明。

### Security
- **admin_service.py LIKE 查询通配符注入**（`backend/app/services/admin_service.py:122,196,278`）：3 处 `.like(f"%{search}%")` 未转义用户输入中的 `%`/`_`，攻击者可构造通配符遍历/消耗数据库。修复：新增 `_escape_like()` 函数，所有 LIKE 查询添加 `escape="\\"` 参数
- **TraceDetail.vue v-html XSS 纵深防御**（`frontend/src/views/admin/TraceDetail.vue:147`）：`highlightJson()` 虽经 `JSON.stringify` 转义，但缺少额外消毒层。修复：输出端添加正则剥离非 `<span>` 标签（`replace(/<(?!\/?span[ >])[^>]*>/gi, '')`），纵深防御

### Changed
- **formatDateTime/formatFileSize 重复定义消除**（`frontend/src/utils/format.js` 新建 + 5 个 Vue 文件）：`formatDateTime()` 在 5 个文件中重复定义、`formatFileSize()` 在 2 个文件中重复定义。重构：提取到 `@/utils/format.js` 共享模块，5 文件统一 `import` 引用并删除本地定义
- **charts.js 图表颜色运行时同步**（`frontend/src/constants/charts.js` + 3 个图表组件）：14 个 hex 颜色值硬编码，声称对齐 Design Token 但无同步机制。重构：新增 `getChartColors()`/`getTooltipConfig()`/`getLegendConfig()`/`getXAxisConfig()`/`getYAxisConfig()` 函数，运行时从 CSS 自定义属性读取颜色；3 个图表组件同步更新调用方式
- **chunker.py Token 估算参数配置化**（`backend/app/rag/chunker.py:142` + `backend/app/config.py`）：中英文自适应比率的阈值 `0.3`、中文比率 `1.5`、英文比率 `4.0` 硬编码。重构：新增 `TOKEN_CHINESE_THRESHOLD`/`TOKEN_CHINESE_RATIO`/`TOKEN_ENGLISH_RATIO` 三个 Settings 字段，`estimate_tokens()` 从 `settings` 读取

### Removed
- **config.py 配置冗余**（`backend/app/config.py:51`）：`JWT_EXPIRE_MINUTES` 与 `ACCESS_TOKEN_EXPIRE_MINUTES` 重复，前者全项目零引用。修复：移除 `JWT_EXPIRE_MINUTES`，保留 `ACCESS_TOKEN_EXPIRE_MINUTES`

---
	
## [0.51] - 2026-06-15

### Fixed
- **test_uuid_helpers.py 2 个遗留失败用例断言与实现不一致**（`backend/tests/unit/core/test_uuid_helpers.py`）：`validate_uuid_format()` 已在 v0.48 放宽为支持 RFC 4122 v1/v3/v4/v5（对齐 MySQL `UUID()` 生成 v1），但测试仍按仅 v4 断言。修复：`test_invalid_uuid_v1` → `test_valid_uuid_v1`（v1 合法），`test_invalid_variant_field` → `test_valid_non_rfc4122_variant`（variant `c` 属 RFC 4122 Microsoft 向后兼容变体，合法）
- **Admin 路由守卫安全漏洞**（`frontend/src/router/index.js:114`）：Vue Router 4 子路由不继承父路由 `meta`，`to.meta.requiresAdmin` 读取叶子路由 meta（undefined），导致非管理员可访问全部 Admin 页面。修复：改用 `to.matched.some(record => record.meta.requiresAdmin)` 遍历所有匹配路由记录
- **JWT refresh_token payload 异常导致 500 而非 401**（`backend/app/services/auth_service.py:114`）：`int(payload["sub"])` 在 `try/except JWTError` 块外，当 JWT 签名有效但缺少 `sub` 字段或格式错误时抛出未捕获 `KeyError`/`ValueError`，经全局异常处理器返回 500/E9001。修复：将 `int(payload["sub"])` 移入 try 块，新增 `except (KeyError, ValueError, TypeError)` 抛出 `InvalidRefreshTokenException`
- **公开 KB 文档详情/分块接口拒绝非 owner 访问**（`backend/app/services/document_service.py:340, 372`）：`get_document()` 和 `get_document_chunks()` 调用 `_check_kb_ownership()` 时缺少 `allow_public_read=True`，与 v0.50 引入的 public KB 只读开放语义矛盾。修复：两处均添加 `allow_public_read=True`
- **`get_selectable_kbs()` 返回裸 dict**（`backend/app/services/chat_service.py:899-968`）：函数签名 `-> dict` 手动构建原生字典返回，`schemas/chat.py` 已定义 `SelectableKBResponse`/`SelectableKBItem` 但从未使用（违反 CLAUDE.md Pydantic schema 约定）。修复：返回类型改为 `SelectableKBResponse`，构造 Pydantic 模型实例返回
- **ChatPage 孤儿 KB 横幅 + Sidebar 孤儿图标硬编码颜色**（`frontend/src/views/ChatPage.vue:324-365` + `frontend/src/components/layout/Sidebar.vue:933-937`）：7+2 个色值硬编码无法支持暗色模式。修复：在 `global.css` 新增 `--dm-orphan-bg/border/accent/text/hover-bg/hover-accent/lock` 七个 Design Token，两文件全部引用 `var(--dm-orphan-*)`
- **知识库详情页文档列表整行可点击触发分块预览**（`frontend/src/views/KnowledgeDetail.vue:162`）：`el-table` 绑定 `@row-click="toggleRowExpand"` 导致点击行内任意列（状态、大小、上传时间等）均触发分块预览弹窗，交互不符合预期。修复：移除 `@row-click` 事件及 `toggleRowExpand` 函数；文件名前增加文件类型图标（pdf/docx/md/txt 各有对应 icon），图标与文件名作为唯一可点击区域触发 `openChunksDialog`；补充 `.doc-filename-icon` 样式，可点击状态为主题色、不可点击时为灰色

### Added
- **P2-C2.4 KnowledgeList 删除确认测试**（`frontend/tests/KnowledgeList.test.js`，3 用例）：确认删除调 `store.deleteKb` 并显示成功提示 / 用户取消不调 API / 删除失败显示错误提示。直接调 `vm.confirmDelete()` + mock `ElMessageBox.confirm`，绕过 el-dropdown 交互。补齐 `ElLoading.service` mock 避免 DOM 副作用
- **P3-U7.83 SSE 客户端断开测试**（`backend/tests/unit/rag/test_sse_helpers.py`，2 用例）：`asyncio.create_task` + `task.cancel()` 模拟客户端断连，验证 `stream_with_heartbeat` 的 `finally` 块正确取消 pending fetch 任务（无泄漏）+ 底层 async generator `finally` 清理生效（`generator_closed=True`）

### Removed
- **ConversationList.vue 死代码**（`frontend/src/views/admin/ConversationList.vue` + `frontend/tests/ConversationList.test.js`）：216 行纯模板+样式的占位页面，无 `<script setup>` 块，无会话列表逻辑，无 API 调用，无路由引用；配套测试文件一并删除（4 用例→3 用例原占位页面测试已无意义）

### Changed
- **TEST_CASES.md**：P2-C2.4 / P3-U7.83 状态 ⬜ → ✅，`test_uuid_helpers.py` 用例数 30 → 36，`test_sse_helpers.py` 用例数 17 → 20
- **DEVELOPMENT.md §2 项目结构树同步更新**：补充后端缺失文件（`_types.py`/`refresh_token.py`/`trace.py`/`bm25.py`/`fusion.py`/`query_rewriter.py`/`sentence_matcher.py`/`trace_recorder.py`/`llm.py`/`uuid_helpers.py`/`logging_config.py`/`admin_service.py`/`trace_service.py` 等）、前端缺失文件（6 个 views、AdminLayout/Sidebar、Charts 组件、composables/constants 等）、全部测试文件列表、Docker 部署文件

## [0.50] - 2026-06-15

### Changed
- **公开知识库详情页开放文档列表只读查看**（`backend/app/services/document_service.py` + `frontend/src/views/KnowledgeDetail.vue`）：公开 KB 的非 owner 用户现可查看文档列表（文件名/类型/大小/状态/分块数/上传时间），支持筛选/排序/分页。上传区、操作列（删除/重新处理/查看分块）和分块预览弹窗对非 owner 隐藏。后端 `_check_kb_ownership()` 新增 `allow_public_read` 参数，`list_documents` 对 public KB 开放任意登录用户只读访问。PRD.md §5.4 权限矩阵「查看文档/分块」拆分为「查看文档列表」+「查看文档分块」两行

## [0.49] - 2026-06-15

### Fixed
- **知识库创建 500 错误 — UUID 列 server_default 在 aiomysql 下未回填**（`backend/app/services/knowledge_base_service.py`）：`KnowledgeBase` 模型的 `uuid` 列使用 MySQL `UUID()` 作为 `server_default`，但 aiomysql 驱动在 `db.refresh()` 后无法正确返回服务端生成值，导致 `kb.uuid` 为 `None`，`KnowledgeBaseResponse.model_validate(kb)` 时 Pydantic 校验失败（`uuid` 字段期望 `str`，收到 `None`）。修复：在 Python 端通过 `uuid.uuid4()` 显式生成 UUID 传给 `KnowledgeBase()` 构造函数，不依赖数据库默认值。同步修复 `conversation_service.py`、`chat_service.py`、`document_service.py` 中相同模式的创建点

### Added
- **知识库名称后端兜底校验**（`backend/app/schemas/knowledge_base.py`）：`KnowledgeBaseCreate` 和 `KnowledgeBaseUpdate` 新增 `@field_validator("name")`，纯数字/纯空格名称在 Pydantic 层返回 422
- **用户注册纯数字用户名校验**（`backend/app/schemas/auth.py` + `frontend/src/views/LoginPage.vue`）：`RegisterRequest` 新增 `@field_validator("username")`，前端 `handleSubmit()` 新增 `^\d+$` 检查，拒绝纯数字/纯空格用户名

## [0.48] - 2026-06-15

### Fixed
- **UUID 校验正则仅支持 v4 导致所有 API 返回 404**（`backend/app/core/uuid_helpers.py`）：MySQL `UUID()` 生成 UUID v1（第三段版本号 `1`），旧正则 `4[0-9a-f]{3}` 仅接受 v4（版本号 `4`），导致 `validate_uuid_format()` 对数据库实际存储的 UUID 一律返回 `False`，`resolve_uuid_to_id()` 直接抛 NotFoundException 而不查数据库。修复：正则改为 `[0-9a-f]{4}` + `uuid.UUID()` 构造函数双重校验，支持 RFC 4122 全版本（v1/v3/v4/v5）
- **KnowledgeDetail 文档表格 `row-key` 遗漏**（`frontend/src/views/KnowledgeDetail.vue`）：UUID 重构时 `row-key="id"` 未改为 `row-key="uuid"`，导致 el-table 行 key 解析为 `undefined`
- **侧边栏点击会话后页面卡死在 Chat 原始页**（`frontend/src/views/ChatPage.vue`）：`watch(conversation_id)` 缺少 try-catch 错误处理，当 `loadConversation()` API 调用失败时异常静默吞掉，页面停留在 WelcomeScreen 无任何提示。补齐错误处理：失败时弹提示 + 清除无效 URL 参数 + 降级为新对话
- **Trace 记录 `kb_id` 始终为 NULL 导致管理后台知识库列显示 `--`**（`backend/app/services/chat_service.py`）：`TraceRecorder` 初始化时 `kb_id=None`，`_validate_and_prepare` 内部将 UUID 解析为整数 ID 后未回写 `recorder.kb_id`（`conversation_id` 有回写但 `kb_id` 遗漏），导致 traces 表 `kb_id` 永远为 NULL，`list_traces` / `get_trace_detail` 的 LEFT JOIN knowledge_bases 无法匹配。修复：在正常路径和 MetaQuestionException 路径各补一行 `recorder.kb_id = conv.kb_id`。注意：历史 trace 数据 `kb_id` 为 NULL 无法追溯，仅影响修复后新产生的记录
- **KnowledgeDetail 文档名点击无响应**（`frontend/src/views/KnowledgeDetail.vue`）：`.doc-filename` 设了 `cursor: pointer` + hover 变色暗示可点击，但 `toggleRowExpand` 函数体为空（仅注释"预留"），点击文件名无任何反馈。修复：文件名加条件 class `clickable`（仅终态且有分块时生效）+ `@click.stop` 触发 `openChunksDialog`；`toggleRowExpand` 补全逻辑同步打开分块预览弹窗；非终态/无分块的文档不再显示手型光标

## [0.47] - 2026-06-15

### Added
- **前端 UUID 适配测试**（TEST_CASES §7.10.5，P5-C10.1-P5-C10.8）：
  - 新增 `frontend/tests/UuidAdaptation.test.js`：8 个 describe 块、23 个测试用例，覆盖 KB 详情路由、Chat 路由、Sidebar 会话切换、KB 列表导航、ChatStore sendMessage、ConversationStore、Admin TraceList/TraceDetail 的 UUID 适配验证

### Changed
- **前端组件测试 mock 数据 UUID 化**（消除测试数据与生产环境形态不一致的隐患）：
  - `KnowledgeDetail.test.js`：路由参数 `params: { id: '1' }` → `{ uuid: '...' }`，`mockKb.id` → `mockKb.uuid`，文档列表 `id` → `uuid`
  - `Sidebar.test.js`：所有会话 `uuid` 字段从数字（1/2/3/4/5/7/42）替换为 UUID 字符串，`kb_uuid` 同步更新，断言值（`mockPush`/`mockRenameConversation`/`mockDeleteConversation` 参数）同步修正
  - `TraceList.test.js`：移除 mock 数据中的自增 `id` 字段，`kb_id` 从数字改为 UUID 字符串
  - `ChatPage.test.js`：KB 列表项 `{ id: 1 }` → `{ uuid: '...' }`，`selectedKBId` 从数字改为 UUID，`handleKBChange`/`mockSetSelectedKB` 断言同步更新
  - `KnowledgeList.test.js`：KB 列表 `uuid` 从数字改为 UUID 字符串，导航断言 `/knowledge-bases/5` → `/knowledge-bases/<uuid>`
- **TEST_CASES.md**：P5-C10.1-P5-C10.8 状态 ⬜ → ✅，覆盖率行标记为 ✅ 23 用例

## [0.46] - 2026-06-14

### Changed
- **前端 UUID 迁移**（ROADMAP §7.7 外部资源 UUID 化 — 前端适配，406 测试全绿）：
  - **API 层**：`api/chat.js`、`api/conversation.js` JSDoc 类型 `number` → `string`
  - **Router**：`router/index.js` 路由参数 `:id` → `:uuid`
  - **Pinia Store**：
    - `stores/chat.js`：移除 `Number()` 强制转换，`.id` → `.uuid`（KB 项），`id/kb_id` → `uuid/kb_uuid`（会话响应字段）
    - `stores/knowledge.js`：JSDoc `Map<number, number>` → `Map<string, number>`，所有 `.id` → `.uuid`（findIndex/filter/find）
    - `stores/conversation.js`：所有 `c.id` → `c.uuid`（renameConversation/deleteConversation/addConversation/updateConversationTitle）
  - **视图组件**：
    - `views/ChatPage.vue`：移除 5 处 `Number()` 强制转换，`.id` → `.uuid`（KB 选项），`kb_id` → `kb_uuid`（加载会话响应）
    - `views/KnowledgeDetail.vue`：`Number(route.params.id)` → `route.params.uuid`，所有 `row.id/doc.id` → `.uuid`
    - `views/KnowledgeList.vue`：`kb.id` → `kb.uuid`（模板 + 脚本）
    - `views/PublicKnowledgeList.vue`：`kb.id` → `kb.uuid`
  - **Sidebar 组件**：`components/layout/Sidebar.vue` 全部 `conv.id` → `conv.uuid`（~30+ 处）
  - **Admin 页面**：
    - `views/admin/DocumentList.vue`：移除 ID 列（60px），`row-key` 改为 `uuid`，`row.kb_id` → `row.kb_uuid`，`deleteDocument(row.kb_uuid, row.uuid)`
    - `views/admin/KnowledgeList.vue`：移除 ID 列（70px），`row-key` 改为 `uuid`，`updateKnowledgeBase(editingRow.uuid)`，`deleteKnowledgeBase(row.uuid)`
    - `views/admin/TraceDetail.vue`：`trace.conversation_id` → `trace.conversation_uuid`
    - `views/admin/TraceList.vue`：`row-key` 改为 `trace_id`
  - **测试适配**（7 个测试文件、13 个用例修复）：mock 数据 `id` → `uuid`、`kb_id` → `kb_uuid`、`conversation_id` → `conversation_uuid`，断言值同步更新

## [0.45] - 2026-06-14

### Changed
- **文档去重与分层治理**（审查报告见本次变更）：
  - **DATABASE.md §2.3**：删除重复的 `DocumentStatus` Python 代码块，替换为对 API.md §4.0 的交叉引用
  - **RAG_PIPELINE.md §5**：删除 §5.1-5.4 的 SSE 事件序列、sources 过滤规则、心跳机制、thinking_content 处理，替换为对 API.md §6.1 的交叉引用
  - **TESTING.md §8**：操作层内容（环境准备、测试场景、Locust CLI 命令、脚本设计要点、执行流程）迁移到 `backend/tests/performance/README.md`，TESTING.md 保留纯策略层（目标/标准/风险），节号重编为 8.1-8.4
  - **FRONTEND.md §9.4**：事件处理表格末尾新增对 API.md §6.1 的交叉引用
  - **CLAUDE.md**：新增「文档归属矩阵」表（明确每类信息的权威文档）+ 交叉引用格式规范 + 写文档前查归属矩阵规则

### Added
- `backend/tests/performance/README.md`：压测操作手册（环境准备、测试场景、Locust 命令、脚本设计要点、执行流程）

### Changed
- **测试形式主义重构**（对齐 CLAUDE.md §测试质量约束，审查报告见 `docs/REVIEW-TEST-FORMALISM-2026-06-14.md`）：
  - **P0 消除不验证目标行为的测试**：
    - `ConversationList.test.js` 15 个静态占位测试压缩为 3 个（数组断言替代逐个检查）
    - `ChatPage.test.js` 删除名实不符的 regenerate 测试（只检查元素存在，未触发事件）
    - `AdminUserList.test.js` 删除名实不符的 row-click 测试（只检查表格存在，未触发点击）
    - `AdminUserDetail.test.js` 删除 2 个精确重复的禁用/启用测试
    - `test_idempotent_lock.py` 重写误导性「释放后再次获取」测试为真正的 release→acquire 生命周期；删除重言式 key 唯一性测试；补充 `test_释放_不存在的_key` 的 delete 断言
  - **P1 弱断言修复**：
    - `test_constants.py` 10 个配置重言式重写为约束关系测试（`CHUNK_OVERLAP < CHUNK_SIZE`、`RERANK_TOP_K ≤ BM25_TOP_K + VECTOR_TOP_K` 等）+ 参数化正数校验
    - `test_security.py` `exp > 0` 改为 `abs(exp - expected_exp) < 5`（验证 JWT TTL 范围）
    - `test_auth_service.py` truthy 断言改为 `decode_access_token` + claims 验证
    - `test_auth_api.py` 对冲式 `status_code in (200, 404, 405)` 改为精确 `== 405`
    - `test_refresh_token.py` `isinstance(token, str)` + truthy 改为 decode + claims 验证
    - `test_chat_api.py` `any(e["event"] == "meta")` 改为完整事件类型列表验证
    - `test_admin_user_api.py` `or` 对冲断言改为确定性 `call_kwargs.kwargs.get("role")`
  - **P2 合并/压缩**：
    - `test_schemas.py` TokenResponse 3 个框架行为测试合并为 1 个；删除 `test_str_subclass`、`test_terminal_statuses_is_frozenset`
    - `test_uuid_schemas.py` 删除 3 个 `isinstance(field, str)` 重言式
    - `test_uuid_helpers.py` 删除冗余 `isinstance(result, int)`
  - **Bug 修复**：`test_conversation_service.py` `kb_uuid` 断言从硬编码 UUID 改为 mock 实际值 `"kb-uuid-1"`（`@property` 从 `knowledge_base.uuid` 读取）

### Added
- `docs/REVIEW-TEST-FORMALISM-2026-06-14.md`：测试形式主义审查报告（75 个文件、~600+ 用例、135 个形式主义问题、28 条重构建议）

## [0.43] - 2026-06-14

### Fixed
- **ARCHITECTURE.md 断链修复与架构决策恢复**：
  - 修复 4 处断链引用：§9.3→DEVELOPMENT.md §9.3（替换为实际结构化日志内容）、§11→ADR-009（替换为时区约束原文）、§12.2.4→DEVELOPMENT.md §9.5（替换为实际配置项）、§12.3→DEVELOPMENT.md §9（替换为指标计算表）
  - 修复 §1 技术选型表「§6.2」→「§7.2」（§6 已无子节编号）
  - **恢复丢失的架构图**：§8.1 Token 预算四池子树图；§9.2 Refresh Token Rotation 流程图；§11 时区四层数据流图
  - **恢复丢失的架构决策**：§7.1 ChromaDB metadata 类型一致性/lazy init/KB 删除约束；§9.3 结构化日志 JSON 格式示例+7 行埋点表；§12.2.1 限流算法三方案对比表；§12.2.4 配置项代码；§12.3 监控指标计算方式
  - 文档版本 v1.4→v1.6，行数 757→839（+82 行，仅恢复唯一真理源内容）

## [0.42] - 2026-06-14

### Changed
- **文档体系审查与重构**（第三轮）：
  - **断链修复**：8 份 ADR 关联文档引用更新（ARCHITECTURE.md 旧 §5.1.x/§12/§13 → RAG_PIPELINE.md 或新编号）；CLAUDE.md §12→§11；API.md §1.3→§1.4；`.claude/commands/review.md` CHANGE.md→CHANGELOG.md
  - **快照引用摘除**：CHANGELOG.md 中移除对 REVIEW-FINAL/REVIEW-FINAL-2026-06-14 章节的引用；ARCHITECTURE.md/TEST_CASES.md 移除对 `Admin_设计补全_最终方案.md` 的引用
  - **部署架构迁回**：ARCHITECTURE.md §12.1 恢复完整部署架构（架构图+服务清单+Nginx 配置+部署约束），DEVELOPMENT.md §9.7-§9.10 删减为引用行
  - **ARCHITECTURE.md 第一轮精简**：§6-§8 摘要化（合并表格 + 压缩代码/重复解释），整体 1080→984 行（-96 行）
  - **ARCHITECTURE.md 第二轮精简**：§9 基础设施/Refresh Token/结构化日志摘要化，§9a ECharts/§9b 用户管理压缩，§11 时区去 ASCII 图，§12.2 限流合并算法+Key，§12.3 监控压为指标表；984→757 行（-227 行，累计 -323 行）
  - **README.md** CHANGE.md→CHANGELOG.md 引用更新
  - **UIDESIGN.md** 补充 FRONTEND.md 反向引用；文档版本 v0.11→v0.12

## [0.41] - 2026-06-14

### Fixed
- API.md L744 `{kb_id}` → `{kb_uuid}` 路径参数修复（与代码实际路由一致）
- CHANGELOG.md v0.32 双 `### Changed` 合并为一

### Changed
- ARCHITECTURE.md §12.1 部署架构细节迁入 DEVELOPMENT.md §9.7-§9.10：瘦身 67 行（57→53 KB），ARCHITECTURE 保留摘要+引用
- DEVELOPMENT.md 新增 §9.7 部署架构图、§9.8 服务清单、§9.9 Nginx 配置要点、§9.10 部署约束
- **STRESS_TEST_PLAN.md 合入 TESTING.md §8**：删除独立文件（-524 行），§8 扩展为 9 个子节（目标/环境/场景/指标/脚本/执行/分析/风险）
- TESTING.md 示例代码精简：§2.1/§3.1/§4 各减至单示例，§5.2 伪代码→脚本引用，§7.2/§7.4 JSON 截断+引用，整体 590→535 行（-55 行）

## [0.40] - 2026-06-14

### Changed
- **TEST_CASES.md ID 体系重构**：解决 ~12 组跨 Phase ID 冲突
  - 全部 ID 增加 Phase 前缀（`P1-`/`P2-`/`P25-`/`P3-`/`P4-`/`P5-`/`SP-`）确保全局唯一性
  - 修复 P3 内部 U7.30 重复（BM25 缓存 vs RRF 融合）→ RRF 段重新编号为 U7.31-U7.37
  - 修复非标准 ID 格式 A7.7.1/A7.7.2/A7.7.3-5/A7.7.6-7 → A7.10-A7.13
  - 更新 §1 ID 编号约定说明 + §9 覆盖率表 ID 引用 + 文档版本 v0.76→v0.80

## [0.39] - 2026-06-14

### Changed
- **ARCHITECTURE.md 重构**：移除进度跟踪内容，聚焦纯架构设计
  - 删除「当前实现状态说明」章节（三标记体系 + 全局状态矩阵）→ 进度跟踪职责归入 ROADMAP.md
  - 合并 §2.1 目标架构 + §2.2 当前实现 → 单一「系统架构」图（架构文档本身即目标，不需要对照）
  - 清理全文 `[Implemented]`/`[Designed]`/`[Planned]` 标记和 Phase 进度描述
  - 文档版本 v1.0 → v1.1

## [0.38] - 2026-06-14

### Changed
- **ROADMAP.md 标题号重构**：统一为全文档两级编号体系
  - Phase 5 三级标题全部扁平化（7.4.1~7.4.4 → 7.4~7.7）
  - 所有 Phase 🚫 推迟项补编号（3.4/4.5/5.4/6.4/7.9）
  - Phase 4 重排消除历史缺口（6.4→6.3, 6.6→6.5, 6.7→6.6）
  - 更新编号规范说明（移除「不保证连续」，改为「序号连续」）

## [0.37] - 2026-06-14

### Added
- U7.54 Prompt `history_messages` 参数透传测试（4 用例，`test_prompt_builder.py`: `TestHistoryMessages`）
- A10.8 文档上传 UUID multipart 测试（`test_uuid_api.py`: `TestDocumentUuidAPI.test_upload_doc_with_kb_uuid`）
- A10.14 Chat `conversation_id` UUID 历史加载测试（`test_uuid_api.py`: `TestChatUuidAPI.test_chat_with_conversation_id_uuid`）

### Fixed
- `docs/TEST_CASES.md` 文档不一致修复：U7.77 ⬜→✅（已覆盖）、§8.1 E1-E5 ⬜→✅（与 §5.20 重复）、§9 `rate_limit` 覆盖率 ⬜→✅
- U7.74/U7.75 ⬜ 补充备注说明（LLM 重试功能未实现，非测试遗漏）
- 测试文件计数更新（`test_uuid_api.py` 20→22 用例、`test_prompt_builder.py` 13→17 用例）

## [0.36] - 2026-06-14

### Changed
- 回归测试脚本适配 UUID 化 API（`kb_id` → `kb_uuid`，`conversation_id` → UUID 字符串）

## [0.35] - 2026-06-14

### Fixed
- UUID 化后 5 个测试文件 40 个失败用例修复（Admin/Chat Schema/Service 字段名和类型同步）

## [0.34] - 2026-06-13

### Added
- 外部资源 UUID 化后端实现：Alembic 迁移 + ORM 模型 + Pydantic Schema + Service/API 层 UUID↔ID 转换 + Chat API + Trace 响应（[ADR-001](docs/decisions/ADR-001-外部资源UUID化.md)）

## [0.33] - 2026-06-13

### Added
- 外部资源 UUID 化设计文档更新（API/DATABASE/ARCHITECTURE/FRONTEND/TEST_CASES/ROADMAP）

## [0.32] - 2026-06-13

### Added
- 孤儿会话交互优化：Banner 按钮「新建对话」、Sidebar 图标替换、MessageItem 隐藏重新生成

### Changed
- 孤儿会话检测：`original_kb_id` 备份字段恢复 FK SET NULL 擦除的历史信息（[ADR-003](docs/decisions/ADR-003-孤儿会话检测original_kb_id备份.md)）
- 会话与知识库生命周期解耦：`last_message_at` 独立排序 + `kb_status` 动态计算 + 孤儿会话 Banner（[ADR-002](docs/decisions/ADR-002-会话与知识库生命周期解耦.md)）
- §6.2 滑动窗口记忆 U8.2/U8.3 补全 + §6.7 结构化日志 U12.4 补全
- 限流中间件实现：纯 ASGI + Redis Lua + 4 接口组独立阈值（[ADR-011](docs/decisions/ADR-011-Docker部署方案.md)）
- §8 交互规范补全 + 全项目危险操作交互对齐（全屏 loading + 本地即时移除）
- Admin Trace 会话字段：移除跨域跳转，改为纯文本审计信息

### Fixed
- 会话接口 500：MySQL 不支持 `NULLS LAST` / async lazy load `MissingGreenlet`
- Sources 链路「未找到+有引用」误抑制：两级匹配均加 `and not _has_citation`
- 检索评估脚本 BM25 初始化参数错误 + ChromaDB 遥测噪音

## [0.31] - 2026-06-13

### Added
- Phase 5 用户管理后端实现：users `status` 字段 + 禁用全链路拦截 + Admin CRUD（[ADR-016](docs/decisions/ADR-016-用户禁用全链路拦截策略.md)）
- Phase 5 用户管理前端实现：AdminUserList + AdminUserDetail + API 封装 + 路由
- Phase 5 用户管理前端组件测试 + Service/API 测试
- chat_service 集成埋点测试（5 用例）

### Changed
- Admin 角色变更端点移除（[ADR-015](docs/decisions/ADR-015-Admin角色变更端点移除.md)）
- 架构文档补充：用户管理认证链路设计（§9b.4-§9b.6）

### Fixed
- 前端架构审查：E5010 被 axios 拦截器吞掉 + api/user.js 文件名冲突

## [0.30] - 2026-06-12

### Added
- Phase 5 Trace 链路追踪后端实现：ORM 模型 + Pydantic Schema + Service + TraceRecorder 埋点 + Admin API
- Phase 5 Trace 链路追踪前端实现：TraceList + TraceDetail + API 封装 + AdminLayout 菜单项
- Phase 5 ECharts 统计后端实现：`StatsChartsData` Schema + trend/latency/tokens 数据
- Phase 5 ECharts 系统统计前端实现：3 个图表组件 + `useECharts` composable + 配置常量
- Phase 5 Docker 部署方案：Dockerfile.backend/frontend + docker-compose.yml + nginx.conf（[ADR-011](docs/decisions/ADR-011-Docker部署方案.md)）
- Trace 前端组件测试 + ECharts 图表组件测试（69 用例）
- Trace 链路追踪测试（Service 23 + API 17 用例）

### Changed
- Trace 对齐架构文档：`intent_method`/`metadata`/`fusion.method` 从硬编码改为数据驱动
- Redis 客户端自动切换：Linux 原生 async / Windows ThreadedRedisClient（[ADR-014](docs/decisions/ADR-014-Redis异步接口Windows兼容方案.md)）

### Fixed
- Trace 实现对齐：`start_time` / `bm25_stats` / `fusion.method` 字段补全

## [0.29] - 2026-06-11

### Added
- Phase 5 意图识别实现：LLM 分类器 + 规则快速通道 + Flash 兜底 + 3 类分流（[ADR-013](docs/decisions/ADR-013-意图识别规则快速通道Flash模型兜底.md)）
- Phase 5 Admin 后端 + 前端联调：3 个 GET 端点 + AdminLayout 独立布局 + 4 个管理页面对接
- Evidence Highlight 句级 BM25 定位重构 + highlight_start/end 纯渲染（[ADR-010](docs/decisions/ADR-010-Evidence-Highlight句级BM25替代LLM引用定位.md)）

### Changed
- P0 性能优化：意图识别规则+Flash / BM25 异步 Redis+进程内缓存
- Redis 异步接口 Windows 兼容：ThreadedRedisClient + asyncio.to_thread（[ADR-014](docs/decisions/ADR-014-Redis异步接口Windows兼容方案.md)）

### Fixed
- Redis 性能问题：连接池优化 + 预热 + 优雅关闭（2s 延迟根因解决）
- 前端多处交互优化（8 项：引用编号/重新生成/侧边栏/删除 loading 等）

## [0.28] - 2026-06-10

### Added
- Phase 5 Sources 智能预览后端：`preview_text` + `preview_range` + `_locate_preview` 定位算法
- Phase 5 Sources 智能预览前端 + `<mark>` 高亮渲染
- Phase 5 Admin 后端接口：`require_admin` + 3 个 GET 端点 + AdminService
- Phase 5 Admin 前端联调：StatsPage + KnowledgeList + DocumentList 对接真实 API
- Phase 5 测试用例：sources_preview 27 + admin_service 21 + admin_api 27
- 前端测试覆盖审计修复（5 个新测试文件 90 用例）

### Changed
- Admin 布局重构：独立 AdminLayout + Sidebar 用户菜单「管理后台」入口 + 文档删除交互优化

### Fixed
- Admin 布局双栏嵌套：App.vue 不再包裹 AdminLayout
- Sources 智能预览双向定位：增加 `_extract_snippet_before` 处理句末引用模式

## [0.27] - 2026-06-09

### Added
- Phase 5 入场设计补齐：ARCHITECTURE §5.1.6 意图识别 + §13 部署/限流/监控设计
- Phase 5 设计补齐 P1/P2：sources 智能预览 + TESTING/PRD/DATABASE 补充

### Changed
- 时区标准化四层 UTC 统一：`UTCDateTime` TypeDecorator + MySQL time_zone + Pydantic 透明序列化（[ADR-009](docs/decisions/ADR-009-时区标准化四层UTC统一.md)）
- Phase 4 全部完成 + 第 2 轮人工评分（综合分 4.76/5.0）

### Fixed
- Phase 4 文档审查问题：TEST_CASES 重复表格/覆盖率标注/版本号
- 前端对话页 Bug：重新生成重复用户消息 / 会话标题不更新

## [0.26] - 2026-06-08

### Added
- Query Rewrite（问题重写）实现：信号词触发 + LLM 改写 + 降级回退（[ADR-006](docs/decisions/ADR-006-Query-Rewrite提前至Phase4.md)）
- 多轮 RAG 回归测试脚本 + 测试集 + 第 2 轮人工评分模板

### Changed
- Query Rewrite 触发策略：移除短问题阈值，仅信号词触发（13 个）
- Sources 事件发送策略：citation filter 降级为优化，零引用回退全量（[ADR-007](docs/decisions/ADR-007-Sources事件发送策略citation-filter降级.md)）

### Fixed
- Sources 事件脆弱耦合：LLM 不写 `[来源N]` 时 sources 消失
- Query Rewrite 触发策略过度触发：短问题阈值导致语义完整问题被强制改写

## [0.25] - 2026-06-07

### Added
- 用户菜单卡片：Sidebar 头像交互重构（菜单卡片替代点头像直接改密）

## [0.24] - 2026-06-06

### Added
- Phase 4.4 前端：会话列表 Store + 4 个会话 API + Axios 401 自动刷新 + SSE Token 刷新
- Phase 4.2 后端：Refresh Token Rotation + 结构化日志 + 错误处理加固 + RequestIDMiddleware
- 修改密码前端 + Sidebar 修改密码弹窗
- 前端测试补充：Sidebar 21 + tokenRefresh 20 用例

### Changed
- 配置集中化：21 个配置字段移入 `config.py`，消除 12 个模块的硬编码常量

### Fixed
- 改密原密码错误被踢下线：E5002 加入 401 透传白名单
- 侧边栏收起态按钮尺寸 / Token 刷新并发踢下线 / 对话历史展示
- Sidebar 知识库导航固定 + Conversation 删除 FK 级联（`passive_deletes=True`）

## [0.23] - 2026-06-05

### Added
- Phase 4.1 后端：会话 CRUD + 多轮上下文（`_load_history` Token 截断 + LLM 标题生成）

### Changed
- ROADMAP Phase 4/5/6 任务重分配：Phase 4 扩充为 18 项，Phase 5 精简为 14 项

### Fixed
- Phase 4.1 代码审查修复：history 截断 break→continue / system 消息过滤 / 首轮判定 flag

## [0.22] - 2026-06-04

### Added
- Phase 3 评估基础设施：30 题共享测试集 + 离线检索评估脚本 + 端到端回归脚本
- Sources 引用过滤：仅发送 LLM 实际引用的 chunk
- Sources `chunk_index` 字段 + 前端 `[来源N]` 标签

### Changed
- Phase 3 第 1 轮人工评分完成（综合分 4.38/5.0）

### Fixed
- NoopReranker 策略修正：保持 RRF 相关性排序，不再按长度重排（[ADR-008](docs/decisions/ADR-008-NoopReranker策略保持RRF相关性排序.md)）
- 「未找到相关信息」时仍显示不相关引用来源
- Sources 抑制关键词从全文匹配改为前缀匹配（前 35 字符）
- prompt_builder 移除第二层 `sorted(key=len)`

## [0.21] - 2026-06-03

### Added
- Phase 3 前端问答界面：ChatInput + MessageItem + MessageList + ChatPage 完整集成
- Phase 3 前端组件测试：7 个文件 109 用例

### Changed
- Phase 3 前端优化：KB 选择器双下拉框 / 分组标签样式 / Sidebar 折叠展开

### Fixed
- Phase 3 后端修复：公共 KB 文档状态（`RETRIEVABLE_STATUSES` + `EXISTS` 子查询）/ 闲谈跳过检索
- Phase 3 前端审查修复：Sources 展示 / 输入框固定底部 / 会话隔离 / 空 KB 提示
- KB chunk_count 僵尸计数：API 响应改用实时 `COUNT(*)` 查询
- 测试体系修复：补齐 KB/Document Service 层测试 + `_mock_chat_pipeline` 样板提取
- 公共 KB 详情返回按钮硬编码路径

## [0.20] - 2026-06-02

### Added
- Phase 3 Chat API 与 SSE 流式输出：ChatRequest Schema + SSE 工具模块 + chat_service 全链路
- Phase 3 Chat API 测试：Schema 6 + SSE 16 + Service 19 + API 12 + KB 选择器 6 用例

### Changed
- Phase 3 Chat API 与 SSE 审查修复：心跳重写 + `chat()` 函数重构为 `_validate_and_prepare` + `_generate_sse_stream`

### Fixed
- DeepSeek thinking 与 `reasoning_effort` 参数冲突

## [0.19] - 2026-06-01

### Added
- Phase 3 RRF 多路融合 + NoopReranker + Prompt 组装 + LLM 调用实现
- ChromaDB metadata 类型一致性保障

### Fixed
- Phase 3 代码审查修复：Embedder JSON 解析 + BM25 返回类型 + embedder 维度校验

## [0.18] - 2026-05-29

### Fixed
- BM25 负分阈值 + 真实分词集成测试 + test_tasks 断言精确化

## [0.17] - 2026-05-28

### Added
- Phase 3 BM25 关键词检索器实现（BM25Okapi + jieba + Redis 缓存）
- Phase 3 向量检索器实现（ChromaDB cosine）

## [0.16] - 2026-05-25

### Added
- Phase 2.5 前端实现：公共知识库浏览页 + KB 可见性选择 + 非 owner 只读展示
- Phase 2.5 后端实现：`visibility` 字段 + 权限重构 + `GET /public` 端点（[ADR-004](docs/decisions/ADR-004-知识库可见性弱混合模式.md)）

### Fixed
- 上传文档后状态一直停在「解析中」（轮询未启动）
- 知识库 doc_count 上传不递增 + deleting 状态文档无法重新上传
- KnowledgeDetail 编辑弹窗缺少可见性选项 + 非 owner 访问公开 KB 误报错

## [0.15] - 2026-05-24

### Added
- 知识库可见性弱混合模式文档体系建立（[ADR-004](docs/decisions/ADR-004-知识库可见性弱混合模式.md)）

## [0.14] - 2026-05-22

### Added
- Phase 2.3.3 前端开发：知识库管理 + 文档管理（KB CRUD + 文档上传/状态轮询/分块预览）
- Phase 2.3.3 前端测试：KnowledgeList 11 + KnowledgeDetail 12 用例

### Changed
- UI 配色体系重构：极简黑白风格（Design Token 全局重写）
- UI 配色二轮调整：去除蓝色点睛色 + 加强层次边界

### Fixed
- Windows Celery Worker 启动修复：solo pool + Selector 事件循环 + ChromaDB 懒加载 + 命名冲突 + commit 前分发 + passive_deletes（6 个问题）

## [0.13] - 2026-05-21

### Added
- Phase 2 Embedding 向量化 + ChromaDB 入库完成
- 文件存储服务测试补全（37 用例）

### Fixed
- 审查报告 10 项质量修复：force 覆盖 Celery 删除 / doc_count 递减 / KB 删除异步 / ChromaDB 旧向量清理等
- delete_document Celery 异步任务完整实现
- Phase 2 入库流水线 6 项质量修复：断点恢复 / chunk_count 原子更新 / Token 回写防御

## [0.12] - 2026-05-20

### Added
- Phase 2 智能分块开发（RecursiveCharacterTextSplitter + 页码回溯 + Token 估算）

### Changed
- 架构文档实现状态标记重构（13 处不一致修复）

### Fixed
- 跨文档一致性修复（4 处）

## [0.11] - 2026-05-19

### Added
- Phase 2 文档解析开发（PDF/DOCX/MD/TXT + 容错机制）
- Phase 2 Celery 幂等锁开发（Redis SET NX EX）

## [0.10] - 2026-05-18

### Added
- Phase 2 文档上传 API 开发（7 个端点 + 文件存储服务）

### Changed
- BM25 方案切换为 rank-bm25（[ADR-012](docs/decisions/ADR-012-BM25方案选型rank-bm25.md)）

### Fixed
- DocumentStatus ENUM 映射修复（大小写不一致）

## [0.9] - 2026-05-17

### Added
- Phase 2 KB CRUD 实现 + 接口测试（28 用例）
- Phase 2 文档状态枚举 + Schema（18 用例）
- Phase 1 模型测试补齐（U4.1-U4.3）

### Fixed
- 代码审查问题修复 + 权限标注修正（GET /{kb_id} 缺少 owner 校验）

## [0.8] - 2026-05-16

### Added
- Phase 2 知识库 CRUD 实现（5 个端点 + idx_user_name 唯一索引）

### Fixed
- 文档规范修复 + 代码合规修复：server_default / LoginRequest min_length / code 字符串格式 / UIDESIGN 硬编码颜色

## [0.7] - 2026-05-15

### Added
- 测试体系补全：TESTING.md 6 层体系 + TEST_CASES.md + 后端 44 + 前端 23 用例

### Changed
- KB/文档删除流程统一为物理删除 + FK CASCADE 兜底（[ADR-005](docs/decisions/ADR-005-KB文档删除策略物理删除FK_CASCADE.md)）

### Fixed
- 测试修复：Mock 适配 & Pydantic V2 兼容（8 项）

## [0.6] - 2026-05-14

### Changed
- 响应格式补全：所有成功响应统一 `{code, message, data}`
- Phase 2 前置准备：API/DATABASE/ARCHITECTURE/ROADMAP/FRONTEND/UIDESIGN 文档全面补全

## [0.5] - 2026-05-13

### Added
- Phase 1 前端布局框架：AppLayout + Sidebar
- Phase 1 前端登录页 + 路由 + 全局样式（Design Token）

### Fixed
- 错误响应格式统一（AppException 去嵌套）
- 前端登录页交互修复：Tab 切换清空表单 / 用户名长度校验 / 注册成功反馈
- Phase 1 交互补漏：登录/退出反馈 + 用户栏行为修正

## [0.4] - 2026-05-12

### Added
- Phase 1 JWT 认证：注册/登录 + AuthMiddleware + 异常类体系（31 错误码）
- Phase 1 ChromaDB 连接 & collection 创建

### Changed
- Phase 1 代码规范修正：相对导入→绝对导入 / `utcnow()` 禁用 / JWT payload 异常防护 / 全局异常处理器

### Fixed
- 6 张模型表补充 `sa.ForeignKey` + `relationship` + `server_default`

## [0.3] - 2026-05-11

### Changed
- Embedding 方案切换为 DashScope text-embedding-v3

## [0.2] - 2026-05-11

### Added
- Phase 1 数据库连接 & ORM 模型（6 张表）& Alembic 迁移环境

## [0.1] - 2026-05-10

### Added
- 项目初始化：FastAPI 后端脚手架 + Vue 3 前端脚手架 + Git 版本控制
