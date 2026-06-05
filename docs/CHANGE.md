# DocMind 变更日志

## 2026-06-05 — Phase 4 设计文档补充 + Schema 准备 + 代码修复

### 新增

| 文件 | 变更 |
|:---|:---|
| `backend/alembic/versions/9a1b2c3d4e5f_*.py` | alembic migration：`messages` 表新增 `metadata JSON NULL DEFAULT NULL` 列 + `conversations` 表新增 `(user_id, updated_at)` 复合索引 |
| `backend/app/models/message.py` | 新增 `metadata_: Mapped[dict\|None]` 字段（`"metadata"` 列映射），Phase 4 不使用，为 Phase 5+ 预留 |
| `backend/app/config.py` | 新增 `CORS_ORIGINS` / `UPLOAD_MAX_SIZE` / `ALLOWED_EXTENSIONS` 三个配置项，消除 main.py 和 document_service.py 中的硬编码 |
| `frontend/src/styles/global.css` | 新增 `--dm-sidebar-width-collapsed: 64px` / `--dm-bg-elevated: #EBEBEB` 两个缺失的 Design Token |

### 修改

| 文件 | 变更 |
|:---|:---|
| `docs/ARCHITECTURE.md` | v0.22→v0.23。§8 重写：Token 预算四池子分拆 + 截断策略 + `[来源N]` 去除决策 + `updated_at` 更新规则 + 硬删除策略 + metadata 预留 + 问题重写推迟；§3.1 状态标记同步 |
| `docs/ROADMAP.md` | v0.29→v0.30。Phase 4 从 6 项展开为 P0/P1/P2 三级共 11 项；问题重写推迟到 Phase 5；Phase 5 拆分为上线必需（8 项）+ Phase 5+ 迭代（12 项）；总体时间线更新 |
| `docs/phase4_prereview.md` | Phase 4 入场审查报告大幅修订：代码修复全员降级、设计文档精简、排期替换为优先级列表、Phase 5 拆分方案、检查清单重写 |
| `docs/TESTING.md` | v0.10→v0.11。新增 §7.4 多轮 RAG 回归测试设计（报销制度三连问）；§9 Phase 4 测试计划更新 |
| `docs/TEST_CASES.md` | v0.42→v0.43。Phase 4 用例从 8 条占位扩充为 22 条（会话 CRUD ×4 + 滑动窗口 ×7 + 多轮 RAG ×5 + 前端组件 ×6） |
| `backend/docs/DATABASE.md` | v0.8→v0.9。§2.6 `messages` 表新增 `metadata` 列；§3 索引策略新增 `idx_conversations_user_updated` |
| `backend/app/main.py` | CORS `allow_origins` 改用 `settings.CORS_ORIGINS` 解析（逗号分隔）；lifespan 增加 JWT 密钥默认值校验（开发环境 warning，生产环境拒绝启动） |
| `backend/app/services/document_service.py` | `ALLOWED_EXTENSIONS` 从硬编码 set 改为 `settings.ALLOWED_EXTENSIONS` 解析；`MAX_FILE_SIZE` 硬编码移除，改用 `settings.UPLOAD_MAX_SIZE` |
| `backend/tests/test_document_service.py` | 适配 `MAX_FILE_SIZE` → `settings.UPLOAD_MAX_SIZE` 导入变更 |
| `frontend/src/views/LoginPage.vue` | 2 处硬编码颜色替换为 Design Token：tab 背景 `#E8E8E8` → `var(--dm-border-light)`，按钮 hover `#000` → `var(--dm-primary-hover)` |
| `frontend/src/views/KnowledgeDetail.vue` | 1 处硬编码颜色替换：danger hover `#FEE2E2` → `var(--dm-danger-light)` |

### 修复

| 文件 | 变更 |
|:---|:---|
| `frontend/src/styles/global.css` | 2 处硬编码颜色替换为 Token（滚动条 `#D4D4D4` → `var(--dm-border)` / `#A3A3A3` → `var(--dm-text-tertiary)`）；`.form-input` border-radius 从 `--dm-radius-sm`（8px）修正为 `--dm-radius-md`（12px），对齐 UIDESIGN 规范 |

## 2026-06-05 — Phase 3 审查报告修复（代码审查 → 修复清单）

### 修改

| 文件 | 变更 |
|:---|:---|
| `backend/app/services/chat_service.py` | R1: 局部导入 `uuid4`/`and_`/`exists` 移至文件顶部；R3: `_build_sources()` 改用 `ChatSourceChunk` Pydantic 模型替代裸 dict，`sources` SSE 序列化走 `.model_dump()` |
| `backend/app/schemas/chat.py` | R3: `ChatSourceChunk` 新增 `chunk_index: int` 字段（对齐 API.md §6.1） |
| `backend/app/core/llm.py` | M5: `_get_llm_client()` 改为模块级惰性单例，避免每次请求新建 `AsyncOpenAI` 实例 |
| `backend/app/rag/reranker.py` | M2: `NoopReranker.rerank()` docstring 修正为「保持 RRF 融合原始排序，截取 top_k」 |
| `backend/docs/DATABASE.md` | R2: 文档版本 v0.7→v0.8，最后更新 2026-05-22→2026-06-05 |
| `frontend/src/components/chat/MessageItem.vue` | M1: 5 处硬编码颜色/字号替换为 Design Token；M4: 代码复制按钮改为事件委托（`onMounted` 绑定 click），替代内联 `onclick` |
| `frontend/src/utils/markdown.js` | M4: `wrapCodeBlocks` 移除内联 `onclick` 属性，仅保留纯 HTML 按钮结构 |
| `frontend/src/styles/global.css` | M1: 新增 4 个 CSS 变量 `--dm-code-inline-bg` / `--dm-code-inline-font-size` / `--dm-code-copy-btn-bg` / `--dm-code-copy-btn-hover-bg` |
| `frontend/docs/UIDESIGN.md` | M1: v0.8→v0.9，§1 新增代码块相关 Design Token 定义 |
| `backend/tests/test_llm.py` | M5: 新增 `reset_llm_singleton` autouse fixture，确保模块级单例在测试间隔离 |
| `backend/tests/test_sse_helpers.py` | R3: `TestBuildSources` 3 个测试 dict 访问 → 属性访问，新增 `chunk_index` 断言 |
| `backend/tests/test_chat_service.py` | M3: `TestGenerateTitle`、`TestExtractCitationIndices` 添加技术债务注释 |
| `frontend/tests/markdown.test.js` | M4: 复制按钮测试不再验证 `navigator.clipboard.writeText` 存在，改为验证不存在 |
| `backend/tests/test_fusion.py` | M7: 删除文件末尾多余空行 |
| `backend/tests/test_prompt_builder.py` | M7: 删除文件末尾多余空行 |

### 修复

| 文件 | 变更 |
|:---|:---|
| — | 本次为审查报告修复批次，无 Bug 修复 |

### 审查来源

- `code-review-report-20260605-1556.md`（报告 A，12 个发现）
- `review_phase3.md`（报告 B，5 个发现）
- 核实后确认修复 10 项（R1-R3 + M1-M7），假阳性 1 项（selectable 端点已注册），延后 3 项（Phase 5 评估）

---

## 2026-06-04 — Phase 3 第 1 轮人工答案评分完成

### 新增

| 文件 | 变更 |
|:---|:---|
| `backend/tests/human_eval_template.md` | 填写全部 10 题评估记录（系统答案 + 4 维度评分 + 评语），汇总表 + 逐题备注 + 总体评价 |

### 修改

| 文件 | 变更 |
|:---|:---|
| `docs/TEST_CASES.md` | v0.41→v0.42；E6 人工评分状态 ⬜→✅，实际值 4.38/5.0；文件头状态更新 |
| `docs/ROADMAP.md` | v0.28→v0.29；Phase 3 §5.5 人工评分状态 ⬜→✅ |
| `docs/TESTING.md` | v0.9→v0.10；§9 人工评分行新增完成状态 + 日期；文件头状态更新 |

### 评估结论

- **平均综合分**：4.38/5.0 ✅ 满足 ≥ 4.0 目标
- **满分题**：Q1（入职手续）、Q5（打印机卡纸）、Q22（离职资产+报销）、Q29（负向测试）
- **最低分题**：Q18（绩效 C 档，3.1/5.0）— 核心问题：过度推断 + 编造细节
- **主要问题模式**：过度推断/编造细节、概念混淆、引用标注不规范、细节扩展失准
- 详见 `backend/tests/human_eval_template.md`

---

## 2026-06-04 — sources 引用过滤：仅发送 LLM 实际引用的 chunk

### 修改

| 文件 | 变更 |
|:---|:---|
| `backend/app/services/chat_service.py` | 新增 `_extract_citation_indices()` 提取 LLM 回答中的 `[来源N]` 编号；`_CITATION_PATTERN` 增加捕获组 `(\d+)`；`_generate_sse_stream` sources 发送逻辑增加引用过滤：仅发送被实际引用的 chunk（保持原始 Prompt 编号不重新编号），零引用时抑制 sources，LLM 失败时回退全量发送 |
| `backend/tests/test_chat_service.py` | 新增 `TestExtractCitationIndices`（5 用例）+ `TestChatCitationFiltering`（4 用例）；修复 2 个已有测试：LLM chunks 增加 `[来源1]` 引用（零引用时 sources 不再发送）；`_mock_chat_pipeline` 已含 `used_chunks` |
| `backend/tests/test_sse_helpers.py` | `TestBuildSources` 3 个测试修复：`_build_sources(reranked_output, ...)` → `_build_sources(reranked_output.results, ...)`（6月4日重构遗漏） |
| `docs/ARCHITECTURE.md` | v0.21→v0.22；§5.1.3 SSE 事件序列 + sources 引用过滤规格（5 条规则）；§5.2 伪代码更新 |
| `backend/docs/API.md` | v0.20→v0.21；§6.1 `event: sources` 重写发送规则（引用过滤 / 未找到抑制 / 零引用抑制 / 检索无结果 / LLM 失败）；字段说明更新 |
| `docs/ROADMAP.md` | v0.27→v0.28；Phase 3 §5.2 新增 sources 引用过滤任务 + §5.5 新增测试任务；决策索引新增 #27；Phase 5 新增 sources 智能预览优化项 |
| `docs/TEST_CASES.md` | v0.40→v0.41；新增 U7.63d（`_extract_citation_indices` + 引用过滤集成 7 用例）；文件头状态更新 |

### 说明

**问题**：LLM 回答中仅引用 `[来源1]` 和 `[来源3]`，但 `event: sources` 将进入 Prompt 的全部 chunk（含不相关的 [来源2]/[来源4]）都发给前端。用户看到 4 个引用来源，但 LLM 只用了 2 个，第一眼看着不相关。

**修复**：LLM 流式结束后从 `assistant_content` 中提取所有 `[来源N]` 编号，`event: sources` 仅发送被实际引用的 chunk。编号保持与 Prompt 一致（不重新编号），确保前端 `[来源N]` 标签与 LLM 回答中的引用精确对应。

**边界处理**：
- LLM 引用全部 chunk → 全量发送（行为不变）
- LLM 零引用 → sources 不发送（与「未找到」抑制互补）
- LLM 失败 → 回退全量发送（无 assistant_content 无法过滤）
- 幻觉编号 → 忽略，仅取有效范围

---

## 2026-06-04 — sources 事件增加 chunk_index 字段 + 前端 [来源N] 标签

### 修改

| 文件 | 变更 |
|:---|:---|
| `backend/app/services/chat_service.py` | `_build_sources` 重构：接受 chunks 列表（替代 `RetrievalOutput`），每条增加 `chunk_index` 字段；两处调用改用 `prompt_result.used_chunks`（与 LLM Prompt 编号一致），LLM 失败时回退 `reranked_output.results` |
| `frontend/src/components/chat/MessageItem.vue` | 来源项增加 `[来源N]` 标签（`source-index`），读取 `src.chunk_index`；新增 `.source-index` CSS |
| `backend/docs/API.md` | §6.1 `event: sources` 文档增加 `chunks[].chunk_index` 字段 + JSON 示例更新 |
| `frontend/docs/FRONTEND.md` | v0.13→v0.14；§4.2/§9.4/§9.5 三处 sources 描述增加 [来源N] 标签说明 |
| `frontend/docs/UIDESIGN.md` | v0.7→v0.8；§4.7 新增 `.source-index` CSS |
| `docs/TEST_CASES.md` | v0.39→v0.40；新增 U7.63b（sources 抑制 4 用例）+ U7.63c（chunk_index） |
| `backend/tests/test_chat_service.py` | mock `build_prompt` 返回值增加 `used_chunks` 字段 |

### 说明

**问题**：LLM 回答中引用 `[来源1]`，但前端来源面板展示的 5 个片段没有编号标签，用户无法将回答中的引用映射到具体的文档片段。

**修复**：三层编号一致性——
- Prompt 层：`_format_chunk_reference` 按 `[来源N]` 格式编号
- SSE 层：`_build_sources` 传入 `prompt_result.used_chunks`，`chunk_index` 与 Prompt 编号一致
- 前端层：`[来源N]` 标签渲染在每条来源项开头

---

## 2026-06-04 — sources 抑制关键词从全文字串匹配改为前缀匹配

### 修复

| 优先级 | 问题 | 根因 | 修复方案 |
|:---|:---|:---|:---|
| P1 | LLM 给出有价值回答+[来源N]引用，但因回答后文提及"未找到相关信息"（如"文档提到X，但未找到相关信息关于Y"），`_NOT_FOUND_KEYWORDS` 全文子串匹配误判为真阴性，错误抑制 sources 事件 | System Prompt 指示 LLM 在真正无法回答时以"知识库中未找到相关信息"**开头**，但 `any(kw in assistant_content)` 匹配了回答任何位置的子串。部分回答场景下 LLM 先给出有信息量的回答，仅在后文对某个子问题声明未找到，此时关键词出现在回答中部/后部，不应抑制 sources | `_NOT_FOUND_KEYWORDS` 匹配范围从全文改为**前 35 字符**（`assistant_content.strip()[:35]`）。真"未找到"回答首句即声明（"知识库中未找到相关信息"=13 字符），35 字符覆盖了"抱歉，知识库中未找到相关信息"（~16 字符）等礼貌前缀，同时排除假阳性（回答开头为"根据文档内容..."等，关键词出现在 ~40 字符后） |

**涉及文件**：
- `backend/app/services/chat_service.py` — `_NOT_FOUND_KEYWORDS` 注释 + `_not_found` 前缀匹配逻辑
- `backend/tests/test_chat_service.py` — 新增 `test_LLM部分回答后文提及未找到时sources仍发送` 防假阳性测试
- `backend/tests/regression_test.py` — 增强诊断输出：`answer_text` + `answer_not_found_count` + 失败题显示 LLM 回答片段

### 诊断过程

回归测试失败题可分为两类：

| 类别 | 数量 | 表现 | 例 |
|:---|:---|:---|:---|
| **假阳性**（本次修复目标） | ~10 题 | LLM 给出含 [来源N] 的有价值回答，但后文提及"未找到" | Q2 "员工请病假需要提交**医院证明**[来源1]...但是，关于提前几天，文档中未找到..." |
| **真阴性**（知识库缺失） | ~4 题 | LLM 首句即"知识库中未找到相关信息" | Q12 "知识库中未找到相关信息。所提供的文档..." |

---

## 2026-06-04 — prompt_builder 移除第二层 sorted(key=len)

### 修复

| 优先级 | 问题 | 根因 | 修复方案 |
|:---|:---|:---|:---|
| P1 | 回归测试仍有 8/30 题缺失 sources 事件（Q12/13/15/17/18/24/26/30，全为 medium/hard 语义复杂题） | `prompt_builder.py:94` 对上游 NoopReranker 输出再次执行 `sorted(key=len)`，将 RRF 相关性排序重新按长度打乱。短但不相关的 chunk 优先占满 token 预算，真正相关的长 chunk 被挤出 → LLM 看不到相关内容 → 输出"未找到" | 移除 `sorted(key=len)`，改为直接使用 `retrieval_output.results`（保持上游 RRF 相关性降序）。软上限跳过逻辑保留，但理由从"尝试下一个更短的"改为"跳过当前尝试下一个能否塞入" |

**涉及文件**：
- `backend/app/rag/prompt_builder.py` — 第 94 行移除 `sorted(key=len)`；模块/docstring/注释同步修正
- `backend/tests/test_prompt_builder.py` — 更新 2 个测试：`test_保持输入排序_不按长度重排` + `test_软上限控制_预算不足时跳过后续chunk`
- `docs/ARCHITECTURE.md` — v0.20→v0.21；§5.1.2 策略描述从"按长度排序择优"改为"相关性优先填充"
- `docs/ROADMAP.md` — v0.26→v0.27；§2 Prompt 组装行 + 决策 #19 同步修正
- `docs/TEST_CASES.md` — v0.38→v0.39；U7.50/U7.52 更新

### 说明

**根因链**：RRF 融合（相关性降序）→ NoopReranker（✅ 第一次修复：保持 RRF 排序）→ **prompt_builder `sorted(key=len)`（❌ 第二次打乱）**→ LLM 拿到不相关短 chunk。

第一次修复（`reranker.py`）是必要但不充分的——prompt_builder 有自己独立的长度排序，注释称"防御性重新排序，消除对上游排序行为的隐式依赖"，在 reranker 按长度排序时两者一致所以未暴露。reranker 改为 RRF 排序后，prompt_builder 的防御排序反而变成了反向破坏。

---

## 2026-06-04 — NoopReranker 策略文档修正

### 修改

| 文件 | 变更 |
|:---|:---|
| `docs/ARCHITECTURE.md` | v0.19→v0.20；§5.1.2 检索后排序行 + §5.2 伪代码注释 + §7.3 整个段落（表、代码块、要点）：NoopReranker 策略从「按 chunk 长度升序排列（短 chunk 优先）」修正为「保持 RRF 融合排序（相关性降序），仅截取 top_k」 |
| `docs/ROADMAP.md` | v0.25→v0.26；§2 NoopReranker 任务行 + §5.5 测试描述 + 决策 #18：同步修正 NoopReranker 策略描述 |
| `docs/TEST_CASES.md` | v0.37→v0.38；§5.5 U7.40-U7.44：用例名/预期行为/用例数/日期同步更新 |
| `backend/app/rag/reranker.py` | 模块 docstring + `NoopReranker` 类 docstring 同步修正 |

### 说明

**根本问题**：ARCHITECTURE.md §7.3 将 NoopReranker 描述为「按 chunk 长度升序排列（短 chunk 优先，信息密度高）」，这是一个错误的启发式策略——在 RAG 场景中，相关性 >> 长度，用长度排序会完全打乱 RRF 融合计算出的相关性排名。

**实际影响**：短 chunk 优先导致语义匹配/跨文档场景下 LLM 拿到不相关短 chunk → 误判「未找到相关信息」→ sources 被抑制 → 回归测试 17/30 失败。

**修复**：代码（`reranker.py`）和文档（4 份）均已修正为「保持 RRF 原始排序，仅截取 top_k」。

---

## 2026-06-04 — Phase 3 评估基础设施：测试集 + 评估脚本 + 回归脚本

### 新增

| 优先级 | 功能 | 实现 |
|:---|:---|:---|
| P1 | 示例知识库文档目录 | `backend/knowledge_samples/` 创建 20 份空 Markdown 文档（11 份来自 TESTING.md 示例 + 9 份补充），覆盖 HR/财务/IT/安全/行政/研发等企业场景 |
| P1 | 共享评估测试集 | `backend/tests/eval_test_set.py` — 30 题测试集（不含项目依赖），供 eval_retrieval.py 和 regression_test.py 共用 |
| P1 | 离线检索评估脚本 | `backend/tests/eval_retrieval.py` — 三路检索对比（向量/BM25/RRF），计算 Recall@5/Recall@10/MRR/Precision@5，输出汇总表 + 逐题明细 + 未召回分析 |
| P1 | 回归测试脚本 | `backend/tests/regression_test.py` — 端到端 SSE 问答验证：答案非空/引用来源有效/SSE 格式正确/无系统错误，每次提交前运行 |

### 修改

| 文件 | 变更 |
|:---|:---|
| `backend/tests/eval_retrieval.py` | 测试集提取到 `eval_test_set.py`，改为 `from tests.eval_test_set import EVAL_TEST_SET` |

### 修复

| 优先级 | 问题 | 根因 | 修复方案 |
|:---|:---|:---|:---|
| P1 | 回归测试 17/30 题缺失 sources 事件 | NoopReranker 按内容长度重排 RRF 结果，LLM 拿到不相关的短 chunk → 误判"未找到"→ sources 被抑制。离线评估直接测 RRF（Recall@5=1.000），但 chat 链路经 NoopReranker 后相关 chunk 被丢弃 | NoopReranker 改为保持 RRF 原始排序（已按相关性降序），仅截取 top_k，不再按长度重排 |

**涉及文件**：
- `backend/app/rag/reranker.py` — `NoopReranker.rerank()` 移除 `sorted(key=len)`，改为直接 `retrieval_output.results[:top_k]`
- `backend/tests/test_reranker.py` — 更新 4 个测试：保持 RRF 排序、截取 top_k、top_k=1、不改变内容

---

## 2026-06-04 — 修复「未找到相关信息」时仍显示不相关引用来源（后端）

### 修复

| 优先级 | 问题 | 根因 | 修复方案 |
|:---|:---|:---|:---|
| P1 | LLM 回答"知识库中未找到相关信息"时，来源面板仍展示不相关的文档片段 | `_generate_sse_stream` 仅检查 `reranked_output.results` 是否非空即发送 sources 事件。即使 LLM 判定所有 chunks 不相关并输出"未找到"，只要检索返回了 top_k chunks（即使相似度为 0），sources 仍被发送 | 在 `chat_service.py` 增加 `_NOT_FOUND_KEYWORDS` 模块级常量，LLM 正常完成后检查回答内容是否包含"未找到相关信息"/"知识库中未找到"，若命中则跳过 sources 事件发送 |

### 修改

| 文件 | 变更 |
|:---|:---|
| `backend/app/services/chat_service.py` | 新增 `_NOT_FOUND_KEYWORDS = ["未找到相关信息", "知识库中未找到"]` 常量；`_generate_sse_stream` 第 198-202 行 sources 发送条件增加 `not _not_found` 检查 |
| `backend/tests/test_chat_service.py` | 新增 `TestChatSourcesSuppression` 类：2 个测试验证 LLM 声明"未找到"时 sources 不发送 + LLM 正常回答时 sources 正常发送 |
| `backend/docs/API.md` | v0.19→v0.20，§6.1 `event: sources` 补充"LLM 声明未找到时不发送"规则 |

---

## 2026-06-03 — Phase 3 前端组件测试全部完成

### 新增

| 优先级 | 功能 | 实现 |
|:---|:---|:---|
| P1 | Phase 3 前端组件测试 | 7 个测试文件共 109 用例：SSE 解析工具(21) + Markdown 渲染工具(14) + ChatInput(19) + MessageList(10) + MessageItem(24) + WelcomeScreen(8) + ChatPage 集成(13)。全部通过，前端总用例数 61→170。 |

### 修改

| 文件 | 变更 |
|:---|:---|
| `frontend/tests/sse.test.js` | 新建：`parseSSEEvent`(11) + `createSSEStream`(10)，Mock fetch + ReadableStream |
| `frontend/tests/markdown.test.js` | 新建：`renderMarkdown`(9) + `wrapCodeBlocks`(5) |
| `frontend/tests/ChatInput.test.js` | 新建：19 用例覆盖渲染/输入/发送/streaming/deepThinking/expose |
| `frontend/tests/MessageList.test.js` | 新建：10 用例覆盖渲染/自动滚动/expose API |
| `frontend/tests/MessageItem.test.js` | 新建：24 用例覆盖布局/Markdown/thinking/sources/状态/操作按钮 |
| `frontend/tests/WelcomeScreen.test.js` | 新建：8 用例覆盖欢迎语/快捷问题卡片渲染与点击 |
| `frontend/tests/ChatPage.test.js` | 新建：13 用例覆盖KB选择器/消息发送/停止/空态切换/快捷问题 |
| `docs/TEST_CASES.md` | v0.34→v0.35，Phase 3 前端测试用例全部标记 ✅，覆盖率表更新 |

---

## 2026-06-03 — 公共KB详情返回按钮修复 + Sidebar 折叠/展开

### 修复

| 优先级 | 问题 | 根因 | 修复方案 |
|:---|:---|:---|:---|
| P1 | 公共知识库详情页返回按钮总是跳转到「我的知识库」 | KnowledgeDetail.vue 两处 `router.push('/knowledge-bases')` 硬编码，且 PublicKnowledgeList 跳转详情时不传来源标识 | KnowledgeDetail 读取 `route.query.from` 参数决定返回目标；PublicKnowledgeList 跳转时附加 `?from=public` |

### 新增

| 优先级 | 功能 | 实现 |
|:---|:---|:---|
| P2 | 侧边栏展开/收起 | Sidebar.vue 新增 `collapsed` ref + 切换按钮；展开态 260px / 收起态 64px；CSS `width` transition 动画（0.2s ease）；收起态仅显示图标（导航项含 `title` tooltip）；移除 Logo 中的「DocMind」文字（标题由 AppLayout header 展示）；副标题「知识库问答平台」字体调大（`--dm-text-sm`） |

### 修改

| 文件 | 变更 |
|:---|:---|
| `frontend/src/views/PublicKnowledgeList.vue` | `goDetail` 跳转附加 `?from=public` 查询参数 |
| `frontend/src/views/KnowledgeDetail.vue` | 新增 `backRoute` computed（读取 `route.query.from`）；返回按钮 + 错误处理使用 `backRoute` 替代硬编码路径 |
| `frontend/src/components/layout/Sidebar.vue` | 新增 `collapsed` ref + `toggleCollapse()`；模板：切换按钮 + 条件渲染（`v-show="!collapsed"`）+ 移除 `.logo-title` + 收起态 `title` tooltip；CSS：`.collapsed` 规则 + 过渡动画 + 收起态居中样式 + `.logo-subtitle` 字体放大 |
| `frontend/tests/KnowledgeDetail.test.js` | `mockRoute` 添加 `query: {}`；新增 2 个返回按钮行为测试（from=public / 无 from） |
| `frontend/docs/UIDESIGN.md` | 新增 `--dm-sidebar-width-collapsed: 64px` 变量；§3.2 补充收起状态规格 |
| `frontend/docs/FRONTEND.md` | §4.1 布局图更新 sidebar 宽度标注；新增 §4.5.5 侧边栏展开/收起行为；§10 移除「可选实现」标注 |
| `docs/CHANGE.md` | 记录本次两个变更 |

---

## 2026-06-03 — 测试体系修复：补齐缺失的服务层测试 + TEST_CASES.md 审计

### 背景

全量审计 499 用例后发现两类问题：
1. **测试分层缺失**：`knowledge_base_service.py` 和 `document_service.py` 仅有 API 层序列化测试（全部用 `patch()` mock），零行业务逻辑被执行。`_fill_real_chunk_count` NameError Bug 因此逃逸。
2. **TEST_CASES.md 覆盖率表不准确**：上述两个模块标记「✅ 100%」，实际覆盖率为 0%（API 序列化测试不计入服务层覆盖率）。

### 修改

| 文件 | 变更 |
|:---|:---|
| `backend/tests/test_kb_service.py` | **新建**。33 用例覆盖 `knowledge_base_service.py` 全部 7 个公开函数（`create_kb`/`get_kb`/`list_kbs`/`list_public_kbs`/`update_kb`/`delete_kb`/`_get_real_chunk_counts`）。含关键回归测试 `test_db_refresh后用实时分块数覆写`——验证 `update_kb` 在 `db.refresh()` 后用 `_get_real_chunk_counts` 修正 chunk_count |
| `backend/tests/test_document_service.py` | **新建**。29 用例覆盖 `document_service.py` 核心函数（`_validate_file`/`_check_kb_ownership`/`list_documents`/`get_document`/`get_document_chunks`/`delete_document`/`reprocess_document`/`upload_document` 权限路径） |
| `backend/app/services/knowledge_base_service.py` | 修复 `update_kb()` 调用不存在的 `_fill_real_chunk_count` → 改为 `_get_real_chunk_counts` |
| `docs/TEST_CASES.md` | v0.31→v0.32：① §8 覆盖率表修正 `services/knowledge_base_service.py` 和 `services/document_service.py` 状态（⬜→✅ 真实服务层测试）；② 修正 `rag/chunker.py`(37→36)、`rag/embedder.py`(26→28)、`rag/bm25.py`(25→24)、`rag/prompt_builder.py`(16→13) 用例数；③ 新增 `rag/fusion.py`/`core/llm.py`/`core/sse.py`/`ingest/tasks.py` Phase 3 模块条目；④ 文件头 497→499 |
| `docs/ROADMAP.md` | v0.22→v0.23：§5.3 全部 11 个前端任务 ⬜→✅ + KB 选择器描述更新为双 `el-select` + §5.4 闲谈 stopgap 说明 |
| `docs/CHANGE.md` | chunk_count 条目移除不存在的 `chunk.py` 修改记录，修正 `update_kb` 描述 |

### 测试结果

- 后端：561/561 全部通过（原 499 + 新增 62 服务层测试，零回归）

### P2 后续：消除测试代码重复

| 文件 | 变更 |
|:---|:---|
| `backend/tests/test_chat_service.py` | 新增 `_mock_chat_pipeline()` 共享上下文管理器（ExitStack + contextmanager），封装 ~10 个 `patch()` 调用的样板代码。10 个测试方法从平均 ~15 行 mock 样板缩减为单行 `with _mock_chat_pipeline(...)` 调用。支持 `with_conversation`/`with_messages` 参数控制是否 mock ORM 构造器 |
| `backend/tests/test_sse_helpers.py` | `TestBuildSources` 3 个测试方法从**复制粘贴生产代码**改为 `from app.services.chat_service import _build_sources` 直接调用。消除源代码逻辑变更时测试不同步的风险 |

**关键收益**：
- `test_chat_service.py` 净减少 ~120 行重复 mock 代码
- `test_sse_helpers.py` `TestBuildSources` 从「测试生产代码的副本」变为「验证生产函数的行为」——源代码变更时测试自动跟踪，不再需要手动同步

---

## 2026-06-03 — KB chunk_count 静态缓存→实时查询（消除僵尸计数）

### 修复

| 优先级 | 问题 | 根因 | 修复方案 |
|:---|:---|:---|:---|
| P1 | 文档物理删除后 KB 前端仍显示旧分块数 | `KnowledgeBase.chunk_count` 是去正规化缓存列，值的更新完全依赖 Celery 异步任务（ingest 递增 / delete 递减）。Celery 未运行、任务崩溃、或直接操作 DB 跳过 Celery 时，KB 计数器永久残留僵尸值 | API 响应的 `chunk_count` 改为从 Chunk 表实时 `COUNT(*) GROUP BY kb_id` 查询，不再读 KB 表的静态缓存列。KB 表 `chunk_count` 列保留给 Celery 内部维护，但对外接口层不再依赖它 |

### 修改

| 文件 | 变更 |
|:---|:---|
| `backend/app/services/knowledge_base_service.py` | ① 新增 `_get_real_chunk_counts(db, kb_ids)` 批量查询函数（单次 `GROUP BY` 避免 N+1）；② `get_kb()` 新增 `fill_chunk_count` 参数（默认 True），从 Chunk 表实时取分块数覆写 `kb.chunk_count`；③ `list_kbs()` / `list_public_kbs()` 在返回响应前批量注入实时分块数；④ `update_kb()` 在 `db.refresh()` 后用 `_get_real_chunk_counts` 修正被 DB 缓存列覆盖的分块数 |
| `backend/docs/DATABASE.md` | `chunk_count` 列描述更新为「冗余缓存列，API 响应使用实时 COUNT」 |
| `backend/docs/API.md` | v0.18→v0.19 |

### 测试结果

- 后端：499/499 全部通过（零回归）

---

## 2026-06-03 — Phase 3 后端修复：公共 KB 文档状态 / 闲谈跳过检索

### 修复

| 优先级 | 问题 | 根因 | 修复方案 |
|:---|:---|:---|:---|
| P0 | 公共知识库「知识库无可用文档」E4001 | **两层根因**：① `_validate_and_prepare` 仅统计 `Document.status == "completed"`，排除 `success_with_warnings` / `partial_failed`；② **更关键**：`get_selectable_kbs` 只过滤 `KnowledgeBase.status == "active"`，不检查是否有可检索文档——KB 的 `doc_count` 是静态计数器（含处理中/失败文档），即使零可检索文档也在下拉框中可选，选中后 chat 端实时查询才报 E4001 | ① 新增 `RETRIEVABLE_STATUSES = ["completed", "success_with_warnings", "partial_failed"]` 常量；② `_validate_and_prepare` 文档计数改用该常量；③ **`get_selectable_kbs` 增加 `EXISTS` 子查询**——仅返回至少有 1 篇可检索文档的 KB，从源头消除「可选中但不可用」 |
| P0 | 输入「你好」「谢谢」等闲谈仍触发检索，并引用无关文档片段 | Phase 3 不含完整意图识别，所有 query 强制走检索链路 → chunks 注入 Prompt → `event: sources` 无条件发送。即使 LLM 回答未引用文档，前端仍展示无关 sources | ① 新增 `_is_casual_chat()` 函数（规则级：问候/致谢/告别/极短输入等 6 类模式）；② 闲谈命中时跳过检索、使用 `CASUAL_SYSTEM_PROMPT` 无文档上下文直接回复；③ `event: sources` 仅在 `reranked_output.results` 非空时发送（正常 + 错误分支均 guard） |

### 修改

| 文件 | 变更 |
|:---|:---|
| `backend/app/services/chat_service.py` | ① 新增 `RETRIEVABLE_STATUSES` 常量（`completed` / `success_with_warnings` / `partial_failed`）；② `CASUAL_SYSTEM_PROMPT` + `_CASUAL_PATTERNS` + `_is_casual_chat()`；③ `_validate_and_prepare`：闲谈跳过检索 + 文档计数用常量；④ `get_selectable_kbs`：`EXISTS` 子查询过滤零可检索文档的 KB；⑤ `event: sources` 两处 guard |
| `backend/docs/API.md` | v0.16→v0.18：① selectable API 过滤逻辑说明 + doc_count 静态计数器局限；② E4001 补充 `partial_failed`；③ §6 闲谈检测 + sources 空结果行为说明 |

### 测试结果

- 后端：499/499 全部通过（零回归）

---

## 2026-06-03 — Phase 3 前端优化：KB 选择器双下拉框 / 分组标签样式 / 移除 Logo

### 修复

| 优先级 | 问题 | 根因 | 修复方案 |
|:---|:---|:---|:---|
| P1 | KB 下拉框分组标题「我的知识库」「公共知识库」与可选项字体样式混淆 | Element Plus 默认 `el-option-group__title` 样式视觉差异不够，用户误以为分组标题是可点击的知识库 | ① 新增 `:deep(.el-select-group__title)` 覆盖样式（小号 + 加粗 + tertiary 色 + 大写 + 字间距），与可选项明显区分（随 D 方案改为双下拉框后此规则自然移除）；② 后续改为双独立下拉框彻底消除此问题 |
| P2 | WelcomeScreen 显示大脑 Logo 冗余 | 空状态页有一颗大 Logo 图标，侧边栏已有独立的 DocMind Logo，多余且占用空间 | 删除 `WelcomeScreen.vue` 中的 `.welcome-logo` 元素及其 CSS 规则块 |

### 修改

| 文件 | 变更 |
|:---|:---|
| `frontend/src/views/ChatPage.vue` | 单一 `el-select` + `el-option-group` 改为双独立 `el-select` 并排——左侧「我的知识库」、右侧「公共知识库」；新增 `selectedMineKBId`/`selectedPublicKBId`/`hasAnyKB` 三个 computed；公共 KB 选项 label 附加 `(username)` 标识所有者；无任何 KB 时显示「暂无可用的知识库」提示；`.kb-selector-inner .el-select` 设 `min-width: 160px` 防止过窄 |
| `frontend/src/components/chat/WelcomeScreen.vue` | 删除 `.welcome-logo` 元素（`<i class="fas fa-brain">`）及对应 CSS |
| `frontend/docs/FRONTEND.md` | v0.11→v0.12：§4.1 布局图 + 知识库选择器描述更新为双下拉框方案 |

### 测试结果

- 前端：59/59 全部通过（零回归）
- 构建：`npm run build` 成功

---

## 2026-06-03 — Phase 3 前端审查修复：Sources 展示 / 布局 / 会话隔离 / 空 KB 提示

### 修复

| 优先级 | 问题 | 根因 | 修复方案 |
|:---|:---|:---|:---|
| P0 | Sources 引用来源：`content` 分块文本未渲染，`score` 误显示为百分比 | `MessageItem.vue` 只渲染 `doc_name`/`page`/`score*100`，后端传来的 200 字截断分块文本 `content` 字段被完全忽略；RRF 排名融合分数乘以 100 显示百分比没有任何语义意义 | 重写 sources-box：① 新增 `.source-content` 区域渲染 `src.content` 分块文本（灰色引用样式）；② 移除误导性的 `score*100 %` 显示；③ 标题改为「引用 X 个文档（共 N 个片段）」，去重文档计数 |
| P0 | 输入框不固定在底部，需要滚动才能看到 | `AppLayout.vue` 的 `.content-scroll` 有 `overflow-y: auto`，ChatPage 内容超出时外层产生滚动条把 ChatInput 推走 | ① `AppLayout.vue`：Chat 路由时 `.content-scroll` 改为 `overflow-y: hidden; padding: 0`，ChatPage 内部独立管理滚动；② ChatPage 去掉负 margin hack；③ MessageList/WelcomeScreen 加 `min-height: 0` 防止 flex 子元素撑开父容器 |
| P0 | 退出登录换账号后还能看到上一个用户的聊天记录 | `authStore.logout()` 只清除 auth 数据，未清空 `chatStore` 的 messages/selectedKBId/selectableKBs；`localStorage.last_kb_id` 跨用户未清理 | ① `chatStore` 新增 `reset()` 方法清空全部状态 + 移除 `last_kb_id`；② `Sidebar.handleLogout` 先调 `chatStore.reset()` 再 `authStore.logout()` |
| P2 | 未选知识库时发送消息静默失败 | `sendUserMessage` throw Error → ChatPage `catch` 仅 `console.error`；WelcomeScreen 快捷问题空 KB 时直接 `return` 无提示 | `handleSend`/`handleQuickQuestion` 显式判断 `selectedKBId`，空时 `ElMessage.warning('请先选择一个知识库')` |
| P2 | Chat 页面标题硬编码「智能问答」 | `AppLayout.vue` 路由标题映射 `Chat: '智能问答'` | 改为 `Chat: 'DocMind'`（产品名；后续 Phase 4 可根据 finish 事件 title 动态更新） |

### 修改

| 文件 | 变更 |
|:---|:---|
| `frontend/src/components/chat/MessageItem.vue` | sources-box 重写：新增 `uniqueDocCount` computed（去重文档计数）；每个 source-item 改为垂直布局，新增 `source-header`（文档名+页码）+ `source-content`（分块文本引用展示）；移除 `source-score` 百分比展示；新增对应 CSS |
| `frontend/src/components/layout/AppLayout.vue` | `content-scroll` Chat 路由时 class 切换 `chat-active`（`overflow-y: hidden; padding: 0`）避免外层滚动；标题映射 `Chat: '智能问答'`→`Chat: 'DocMind'` |
| `frontend/src/views/ChatPage.vue` | 移除负 margin hack；新增 `min-height: 0` 到 flex 子元素；导入 `ElMessage`，`handleSend`/`handleQuickQuestion` 增加空 KB 用户提示 |
| `frontend/src/components/chat/MessageList.vue` | `.message-list` 新增 `min-height: 0` 防止撑开父容器 |
| `frontend/src/components/chat/WelcomeScreen.vue` | `.welcome-screen` 新增 `min-height: 0; overflow-y: auto` 防止撑开父容器 + 小屏内容溢出时可滚动 |
| `frontend/src/stores/chat.js` | 新增 `reset()` 方法：清空 messages/conversationId/streaming/currentStream/selectedKBId/selectableKBs/loadingKBs + `localStorage.removeItem('last_kb_id')` |
| `frontend/src/components/layout/Sidebar.vue` | `handleLogout` 优先调用 `chatStore.reset()` 清空聊天状态 |
| `frontend/tests/AppLayout.test.js` | `Chat 路由显示"智能问答"` → `Chat 路由显示"DocMind"`，断言同步 |

### 测试结果

- 前端：59/59 全部通过（零回归）
- 构建：`npm run build` 成功

### 待后续

| 事项 | 状态 | 说明 |
|:---|:---|:---|
| KB ID 信息泄露（问题 4） | 暂缓 | 涉及后端 selectable 接口数据 + 前端 `last_kb_id` 按用户隔离，需先明确方案 |
| 侧边栏产品名布局调整（问题 5b） | 暂缓 | 新增功能——产品名移到 ChatPage 标题 + 字体调大，需先补充 FRONTEND.md 设计文档 |
| 侧边栏可折叠（问题 6） | 暂缓 | 新增功能，需先补充 FRONTEND.md + UIDESIGN.md |

## 2026-06-03 — Phase 3 前端问答界面：核心组件 + 页面集成

### 新增

| 文件 | 变更 |
|:---|:---|
| `frontend/src/components/chat/ChatInput.vue` | **新建** 输入框组件：textarea 自动高度调整 + ≤2000字实时计数 + Enter发送/Shift+Enter换行 + 深度思考开关（黄色激活态）+ 流式中显示「停止生成」按钮 + 空输入抖动反馈 + `setText()`/`focus()` 暴露方法 |
| `frontend/src/components/chat/MessageItem.vue` | **新建** 单条消息组件：用户消息右对齐黑底白字气泡 / 助手消息左对齐无背景 + 角色头像 + Markdown 实时渲染（markdown-it + highlight.js）+ thinking 黄色折叠面板（默认展开）+ sources 引用来源卡片（默认展开，含文档名/页码/相似度百分比）+ typing 三点跳动动画 + 完成态 hover「重新生成」按钮 + 错误状态提示 + 代码块复制按钮 |
| `frontend/src/components/chat/MessageList.vue` | **新建** 消息列表组件：自动滚动到底部（新消息/流式内容变化时）+ 手动上滚时显示 sticky「新消息」浮动按钮 + 点击按钮平滑滚回底部 |

### 修改

| 文件 | 变更 |
|:---|:---|
| `frontend/src/views/ChatPage.vue` | **重写** 占位页 → 完整问答页面：KB 选择器（el-select + el-option-group）+ WelcomeScreen/MessageList 条件切换 + ChatInput 底部固定 + 快捷问题直接发送 + 切换 KB 自动清空对话 + 覆盖 AppLayout padding 全屏布局 |
| `frontend/src/components/layout/Sidebar.vue` | 新建对话按钮联动 `chatStore.clearMessages()`（已在 /chat 时清空消息；其他页面时跳转）；新对话按钮在 Chat 路由时高亮激活态；新增 `useRoute` + `useChatStore` 导入 |
| `frontend/src/main.js` | 新增 `highlight.js/styles/github-dark.css` 导入（代码块深色主题，对齐 UIDESIGN.md 规范） |

### 文档同步

| 文件 | 版本变更 | 主要变更 |
|:---|:---|:---|
| `frontend/docs/FRONTEND.md` | v0.10→v0.11 | §4.3/§4.4/§4.5 组件行为补充实现状态；§10 模块表组件状态更新；§11 TODO 更新 Phase 3 前端状态 |
| `docs/TEST_CASES.md` | v0.30→v0.31 | §5.13-§5.19 前端组件测试用例补充「代码已实现」备注；§8 覆盖率表补充实现状态 |

## 2026-06-02 — Phase 3 Chat API 与 SSE 审查修复

### 修复

| 文件 | 变更 |
|:---|:---|
| `backend/app/core/sse.py` | **重写** `stream_with_heartbeat()`：移除有 bug 的 `_collect_heartbeat()` 后台收集方案，改用 `asyncio.wait` + timeout 实时发送心跳帧。原方案心跳帧仅在 `while True` 循环的本地 list 中堆积，从未被 yield 给客户端，且 `.cancel()` 后 `.result()` 必抛 `CancelledError` 导致已收集帧丢失 |
| `backend/app/services/chat_service.py` | 检索阶段新增 try/except 包装，检索异常统一包装为 `RetrievalServiceException(E4003)`；会话越权访问改用 `ConversationAccessDeniedException(E3002)` 替代通用 `PermissionDeniedException(E5005)`；**重构** `chat()` 函数：提取 `_validate_and_prepare()`（校验+会话+检索，~70行）和 `_generate_sse_stream()`（SSE 事件生成+LLM 流式+消息持久化，~115行），原 200 行函数缩减至 26 行编排入口 |
| `backend/app/schemas/chat.py` | 新增 `TokenUsage(BaseModel)` Pydantic 模型，`ChatFinishData.token_usage` 类型从 `dict` 改为 `TokenUsage` |
| `backend/app/schemas/__init__.py` | 导出新增的 `TokenUsage` |
| `backend/tests/test_sse_helpers.py` | 新增 2 个心跳行为测试：`test_事件间隙实时发送心跳帧`（验证心跳在事件间隙实时 yield）和 `test_事件流结束后无多余心跳`（验证快速事件流不残留心跳帧） |
| `backend/tests/test_chat_service.py` | `_consume_sse` 初始化 `current_event = None` 并增加 guard；检索失败测试断言改为 `RetrievalServiceException(E4003)`；会话越权测试断言改为 `ConversationAccessDeniedException(E3002)` 并修复 KB 可见性设置使 KB 权限检查先行通过 |

### 修改

| 文件 | 变更 |
|:---|:---|
| `docs/TEST_CASES.md` | v0.29→v0.30：U7.62 预期行为修正（检索失败 → E4003 包装）；U7.78 ⬜→✅，备注 DeepSeek 流式 API 不返回 usage → 估算替代的技术偏差 |

## 2026-06-02 — Phase 3 Chat API 与 SSE 测试

### 新增

| 文件 | 变更 |
|:---|:---|
| `backend/tests/test_chat_schema.py` | ChatRequest Schema 校验测试（6 用例） |
| `backend/tests/test_sse_helpers.py` | SSE 工具模块测试（16 用例） |
| `backend/tests/test_chat_service.py` | Chat Service 单元测试（19 用例） |
| `backend/tests/test_chat_api.py` | Chat SSE API 集成测试（12 用例） |
| `backend/tests/test_kb_selectable_api.py` | KB 选择器 API 测试（6 用例） |

### 修改

| 文件 | 变更 |
|:---|:---|
| `docs/TEST_CASES.md` | v0.28→v0.29：§5.7/§5.9/§5.10/§5.11/§5.12 共 59 用例状态 ⬜→✅ |
| `docs/ROADMAP.md` | §5.5 Phase 3 测试 5 个任务标记 ✅ |

## 2026-06-02 — 修复 DeepSeek thinking 与 reasoning_effort 参数冲突

### 修复

| 文件 | 变更 |
|:---|:---|
| `backend/app/core/llm.py` | 修复 `deep_thinking=false` 时仍传 `reasoning_effort` 导致 `thinking disabled` 与推理强度控制冲突的问题；现在仅 `deep_thinking=true` 时传 `reasoning_effort="high"` |
| `backend/tests/test_llm.py` | 更新 LLM 参数断言：开启 thinking 时校验顶层 `reasoning_effort`，关闭 thinking 时校验不传 `reasoning_effort`；补充非流式关闭 thinking 用例 |

### 修改

| 文件 | 变更 |
|:---|:---|
| `backend/docs/API.md` | v0.15→v0.16：移除请求体中的 `reasoning_effort` 字段示例，明确 Phase 3 仅通过 `deep_thinking` 控制，后端内部在开启 thinking 时固定 high |
| `docs/ARCHITECTURE.md` | v0.18→v0.19：修正 §5.1.3 参数映射，明确 `thinking.disabled` 时禁止同时传 `reasoning_effort` |
| `docs/ROADMAP.md` | v0.21→v0.22：同步决策 #20 与 Phase 3 推迟项说明 |
| `docs/TEST_CASES.md` | v0.27→v0.28：同步 LLM 参数用例预期和 ChatRequest 中 `reasoning_effort` 的 Phase 3 跳过说明 |

## 2026-06-02 — Phase 3 Chat API 与 SSE 流式输出

### 新增

| 文件 | 变更 |
|:---|:---|
| `backend/app/schemas/chat.py` | ChatRequest / ChatSourceChunk / ChatFinishData / SelectableKBItem / SelectableKBResponse Pydantic 模型 |
| `backend/app/core/sse.py` | SSE 工具模块：`format_sse_event()` / `format_sse_heartbeat()` / `stream_with_heartbeat()`（15s 心跳 + asyncio 任务合并） |
| `backend/app/services/chat_service.py` | Chat Service 核心流程：`chat()` 全链路（权限校验→会话创建→多路检索→RRF→Rerank→Prompt→LLM SSE 流式→消息持久化→标题生成）+ `get_selectable_kbs()` KB 选择器 |
| `backend/app/api/chat.py` | Chat Router：`POST /api/chat` SSE 端点 |

### 修改

| 文件 | 变更 |
|:---|:---|
| `backend/app/api/knowledge_base.py` | 新增 `GET /api/knowledge-bases/selectable` 端点（在 `/{kb_id}` 之前注册避免路由冲突） |
| `backend/app/main.py` | 注册 `chat_router`（`prefix="/api"`） |
| `backend/app/schemas/__init__.py` | 导出 chat 模块 Schema |
| `docs/ROADMAP.md` | §5.2 后端 Chat API 与 SSE 9 个任务 ⬜→✅ |

## 2026-06-02 — Phase 3 审查报告修复

### 修改

| 文件 | 变更 |
|:---|:---|
| `docs/ARCHITECTURE.md` | 9 处 `[Planned: Phase 3]` → `[Implemented]`（§1 关键词检索、§3.1 多路检索/Rerank、§5 流程图 5 处、§5.1 标题）；版本 v0.17→v0.18 |
| `docs/ROADMAP.md` | §5.5 LLM 调用测试：移除「重试+指数退避」描述，用例数 16→15；版本 v0.20→v0.21 |
| `docs/TEST_CASES.md` | `prompt_builder.py` 覆盖率 ⬜→✅ 100%（16 用例）；版本 v0.26→v0.27 |
| `backend/app/ingest/tasks.py` | 局部导入 `invalidate_bm25_cache` 提升为顶部导入（消除 L474/L565 两次局部导入） |
| `backend/app/services/document_service.py` | 局部导入 `get_redis` + `invalidate_bm25_cache` 提升为顶部导入 |
| `backend/app/rag/prompt_builder.py` | `build_prompt()` 排序处加注释说明输入已由 NoopReranker 按相同键排序（消除隐式依赖） |
| `backend/tests/test_bm25.py` | `test_正常检索流程` 加固断言（验证 chunk_id + 分数范围）；`test_分数降序排列` 加前置断言消除条件断言静默通过风险 |
| `backend/tests/test_retriever.py` | 删除 `TestParseResults`（6 用例，私有方法 `_parse_results` 禁测） |
| `backend/tests/test_llm.py` | 删除 `TestGetLLMClient`（1 用例，私有函数 `_get_llm_client` 禁测） |
| `backend/tests/test_fusion.py` | 删除 `test_k值为0`（1 用例，未定义行为禁固化为测试）；删除 `TestConstants`（合并到集中文件） |
| `backend/tests/test_reranker.py` | 删除 `TestConstants`（合并到集中文件）；清理 `DEFAULT_RERANK_TOP_K` 导入 |
| `backend/tests/test_prompt_builder.py` | 删除 `TestConstants`（合并到集中文件）；清理常量导入 |

### 新增

| 文件 | 变更 |
|:---|:---|
| `backend/tests/test_constants.py` | **新建** Phase 3 模块常量定位测试，集中管理 5 个常量验证（`DEFAULT_RRF_K`、`DEFAULT_RERANK_TOP_K`、`DEFAULT_MAX_CONTEXT_TOKENS`、`DEFAULT_MAX_CHUNKS`、`SYSTEM_PROMPT_TEMPLATE`） |

## 2026-06-01 — Phase 3 ChromaDB metadata 类型一致性保障

### 修改

| 文件 | 变更 |
|:---|:---|
| `backend/app/ingest/tasks.py` | ChromaDB 入库 metadata 显式 `int()` 转换：`kb_id`、`doc_id`、`chunk_index` 确保 int 类型 |
| `backend/app/rag/retriever.py` | ChromaDB 查询 metadata 显式 `int()` 转换：`doc_id`、`chunk_index` 确保 int 类型 |
| `backend/tests/test_retriever.py` | 新增 `test_metadata字段为int类型` 测试，验证 metadata 字段类型一致性 |
| `docs/ROADMAP.md` | §5.1 ChromaDB metadata 类型一致性状态更新为 ✅ |
| `docs/TEST_CASES.md` | §5.1 U7.8 测试用例状态更新为 ✅（2026-06-01） |

## 2026-06-01 — Phase 3 Prompt 组装与 LLM 调用实现

### 新增

| 文件 | 变更 |
|:---|:---|
| `backend/app/rag/prompt_builder.py` | **新建** Prompt 组装模块，实现 `build_prompt()` 函数：SYSTEM_PROMPT 模板 + 检索结果格式化 + 软上限择优填充（超预算时尝试下一个更短 chunk）+ Token 预算控制 |
| `backend/app/core/llm.py` | **新建** LLM 调用模块，实现 `stream_chat_completion()` 和 `chat_completion()` 函数：DeepSeek API（OpenAI 兼容）流式/非流式调用 + `extra_body` 控制 thinking 开关 + 解析 `content` + `reasoning_content` |
| `backend/tests/test_prompt_builder.py` | **新建** Prompt 组装单元测试，15 个用例覆盖：chunk 格式化、空检索结果、按长度升序排列、软上限控制、最大 chunk 数限制、用户问题保留、system prompt 格式、单 chunk、第一个 chunk 超预算仍加入、返回类型、常量验证 |
| `backend/tests/test_llm.py` | **新建** LLM 调用单元测试，16 个用例覆盖：LLMChunk/LLMResult 数据类、客户端创建、流式输出、deep_thinking 参数、reasoning_effort 参数、限流异常、其他异常、非流式调用、空结果异常 |

### 修改

| 文件 | 变更 |
|:---|:---|
| `docs/ROADMAP.md` | §5.1 Prompt 组装和 LLM 调用状态更新为 ✅；§5.5 Prompt 模板测试和 LLM 调用测试状态更新为 ✅ |
| `docs/TEST_CASES.md` | §5.6 Prompt 模板测试用例状态更新为 ✅（U7.50-U7.55）；§5.8 LLM 调用测试用例状态更新为 ✅（U7.70-U7.76） |

## 2026-06-01 — Phase 3 NoopReranker 占位实现

### 新增

| 文件 | 变更 |
|:---|:---|
| `backend/app/rag/reranker.py` | **新建** Rerank 重排序模块，实现 `NoopReranker` 类：按 chunk 长度升序排列后截取 top_k=5，短 chunk 优先（高信息密度），输入不足 top_k 时返回全部 |
| `backend/tests/test_reranker.py` | **新建** NoopReranker 单元测试，12 个用例覆盖：按长度排序、截取 top_k、输入不足 top_k、空输入、不改变 chunk 内容、默认 top_k、单 chunk、top_k=1、相同长度稳定性、接口一致性 |

### 修改

| 文件 | 变更 |
|:---|:---|
| `docs/ROADMAP.md` | §5.1 NoopReranker 状态更新为 ✅；§5.5 NoopReranker 测试状态更新为 ✅（12 用例） |
| `docs/TEST_CASES.md` | §5.5 NoopReranker 测试用例状态更新为 ✅（U7.40-U7.44）；§8 覆盖率表 `rag/reranker.py` 状态更新为 ✅ |

## 2026-06-01 — Phase 3 RRF 多路融合实现

### 新增

| 文件 | 变更 |
|:---|:---|
| `backend/app/rag/fusion.py` | **新建** RRF 多路融合模块，实现 `rrf_fusion()` 函数：支持多路检索结果融合，k=60 默认平滑常数，单路为空返回另一路，两路均空返回空结果 |
| `backend/tests/test_fusion.py` | **新建** RRF 融合单元测试，14 个用例覆盖：标准合并、单路为空、两路均空、三路融合、排名相同、参数化 k 值、边界情况 |

### 修改

| 文件 | 变更 |
|:---|:---|
| `docs/ROADMAP.md` | §5.1 RRF 多路融合状态更新为 ✅；§5.5 RRF 融合算法测试状态更新为 ✅（14 用例） |
| `docs/TEST_CASES.md` | §5.4 RRF 融合算法测试用例状态更新为 ✅（U7.30-U7.36） |

## 2026-06-01 — Phase 3 代码审查修复：异常捕获 + 类型标注 + 边界防护

### 修复

| 优先级 | 文件 | 变更 |
|:---|:---|:---|
| P0 | `backend/app/rag/embedder.py` | `_call_embed_api` 新增 `json.JSONDecodeError` 捕获（DashScope 服务降级返回 HTML + 200 时不再穿透崩溃，转为重试） |
| P1 | `backend/app/rag/bm25.py` | `_load_and_cache` 返回类型标注修正 `BM25Okapi` → `BM25Okapi \| None`（空 KB 返回 `None`） |
| P2 | `backend/app/rag/embedder.py` | `_parse_embed_response` Token 计数余数分配（`total_tokens=23, text_count=5` → `[5,5,5,4,4]` 替代整除丢弃 `[4,4,4,4,4]`）；新增 embedding 维度一致性校验 |
| P2 | `backend/app/rag/embedder.py` | `embed_chunks` 新增批量上限 guardrail（`len(texts) > EMBED_BATCH_SIZE` 抛出 `ValueError`） |
| P2 | `backend/app/rag/retriever.py` | `_parse_results` 边界防护加固：`documents[0]` 三段式检查 `documents and documents[0]`（防御 ChromaDB 异常数据导致 IndexError） |

### 修改

| 文件 | 变更 |
|:---|:---|
| `backend/tests/test_embedder.py` | `test_token计数_按文本数等比例分配` 期望值更新为余数分配结果 `[5,5,5,4,4]` |

### 重构

| 文件 | 变更 |
|:---|:---|
| `backend/tests/helpers.py` | **新建** 共享测试工厂模块，集中 8 个工厂函数：`make_mock_doc`、`make_mock_chunks`、`make_mock_embed_result`、`setup_mock_db`、`mock_async_session_ctx`、`make_mock_embed_response`、`make_mock_httpx_response`、`make_mock_chroma_results` |
| `backend/tests/test_tasks.py` | 移除 6 个本地工厂函数，改为从 `tests.helpers` 导入 |
| `backend/tests/test_embedder.py` | 移除 `MOCK_DIM` + 2 个本地工厂函数，改为从 `tests.helpers` 导入 |
| `backend/tests/test_retriever.py` | 移除 `MOCK_DIM` + 2 个本地工厂函数，改为从 `tests.helpers` 导入 |

## 2026-05-29 — 测试质量修复：BM25 负分阈值 + 真实分词集成测试 + test_tasks 断言精确化

### 修改

| 文件 | 变更 |
|:---|:---|
| `backend/app/rag/bm25.py` | 新增 `MIN_BM25_SCORE = -5.0` 阈值常量；`search()` 新增 `min_score` 参数，过滤低于阈值的 chunk（极端负分不进入 RRF 融合） |
| `backend/tests/test_bm25.py` | 新增 `TestBM25RetrieverWithRealJieba` 类（7 用例使用真实 jieba 验证中文分词检索质量）；旧 `test_查询无匹配时分数为零` 改为精确验证分数=0.0 行为 |
| `backend/tests/test_tasks.py` | 4 处 `result["status"] in ("completed", "success_with_warnings")` 改为精确断言 `== "completed"`；checkpoint 测试 commit 计数从 `>=3` 改为 `>=4` 并移除未使用的 `expected_batches` 变量 |

### 修复

- **BM25 负分不截断**：原实现因 mock jieba 逐字拆分导致测试发现负分后直接去掉截断逻辑。现恢复阈值策略：`min_score=-5.0` 过滤极端负值，score=0.0（无证据）保留
- **过度 mock**：所有 BM25 测试 mock jieba 为 `list(text)` 逐字拆分，验证的是"算法能处理字符数组"而非"中文检索质量"。现新增 7 个真实 jieba 测试覆盖精确匹配排序、top_k 截取、阈值过滤
- **test_tasks 模糊断言**：`status in ("completed", "success_with_warnings")` 无法区分成功与部分失败。改为精确 `== "completed"`

## 2026-05-28 — Phase 3 BM25 关键词检索器实现

### 新增

| 文件 | 变更 |
|:---|:---|
| `backend/app/rag/bm25.py` | BM25 检索器 `BM25Retriever`：jieba 分词 + Redis 缓存 tokenized corpus（TTL=300s）+ BM25Okapi 评分检索 + `invalidate_bm25_cache()` 缓存失效函数 |
| `backend/tests/test_bm25.py` | BM25 检索器单元测试：18 个用例覆盖分词、缓存命中/未命中、空语料、Redis 降级、top_k 截取、排序、缓存失效 |

### 修改

| 文件 | 变更 |
|:---|:---|
| `backend/app/ingest/tasks.py` | 入库完成 + 文档删除完成后调用 `invalidate_bm25_cache()` 清除 BM25 缓存（对齐 ARCHITECTURE.md §6.2） |
| `backend/app/services/document_service.py` | reprocess 触发时清除 BM25 缓存 |
| `docs/TEST_CASES.md` | U7.10-U7.15 BM25 检索用例 + U7.20-U7.26 缓存用例状态 ⬜→✅，版本 v0.24→v0.25 |
| `docs/ROADMAP.md` | BM25 检索器 + BM25 索引缓存 + 对应测试任务 ⬜→✅ |

## 2026-05-28 — Phase 3 向量检索器实现

### 新增

| 文件 | 变更 |
|:---|:---|
| `backend/app/rag/retriever.py` | 向量检索器 `VectorRetriever`：ChromaDB cosine 相似度检索 + `RetrievalResult` 标准化数据结构 |
| `backend/tests/test_retriever.py` | 向量检索器单元测试：18 个用例覆盖正常检索、空结果、异常处理、参数传递、类型一致性 |

### 修改

| 文件 | 变更 |
|:---|:---|
| `backend/app/rag/embedder.py` | `_build_payload()` / `_call_embed_api()` / `embed_chunks()` 新增 `text_type` 参数，支持 `"query"` 类型向量化（DashScope 区分 query/document 策略） |
| `backend/tests/test_embedder.py` | 新增 `text_type="query"` 参数传递测试 |
| `docs/TEST_CASES.md` | U7.1-U7.8 向量检索用例状态 ⬜→✅，`rag/retriever.py` 覆盖率状态更新 |

## 2026-05-28 — Phase 3 文档补充：SSE 协议行为 + KB 空库行为 + 前端文档对齐

### 修改

| 文件 | 版本变更 | 变更 |
|:---|:---|:---|
| `backend/docs/API.md` | v0.14→v0.15 | ① §6 补充 SSE 中断持久化策略（assistant 仅完整完成后持久化）；② §6 补充 LLM 失败时 sources 仍发送；③ §8.3 错误流程示例补充 sources 事件；④ KB 选择器接口补充空知识库行为说明（允许选择，发问返回 E4001） |
| `frontend/docs/FRONTEND.md` | v0.9→v0.10 | ① §4.1 布局图会话区域标注 Phase 3 空态 + Phase 4 实现历史列表；② §10 模块表 ChatPage Sidebar 修正「新建对话」为 Phase 3（原误标 Phase 4） |

## 2026-05-27 — Phase 3 准入修复：代码缺陷 + DeepSeek 参数对齐 + 文档过期/矛盾清理

### 修复

| 文件 | 变更 |
|:---|:---|
| `backend/app/services/knowledge_base_service.py` | `delete_kb()` 在 `delete_kb_task.delay(kb.id)` 前新增 `await db.commit()`，对齐 CLAUDE.md Celery 分发约束 |

### 修改

| 文件 | 版本变更 | 变更 |
|:---|:---|:---|
| `docs/ARCHITECTURE.md` | v0.15→v0.16 | ① ChromaDB metadata 策略 string→int（3 处）；② §5.1.3 thinking_content 处理新增 `extra_body` 映射 + `reasoning_effort` + 默认值风险说明；③ §5.2 伪代码 LLM 调用补充 `extra_body` 参数传递 |
| `backend/docs/API.md` | v0.13→v0.14 | ① §6 ChatRequest 新增 `reasoning_effort` 字段 + `deep_thinking` 映射说明（extra_body/type:enabled\|disabled）；② thinking 事件补充 DeepSeek API 调用说明；③ §7 会话消息列表示例 thinking_content 改为 null（对齐决策 #25）；④ 问答示例补充 reasoning_effort |
| `docs/ROADMAP.md` | v0.18→v0.20 | ① 决策 #20（LLM）补充 `extra_body` + `reasoning_effort` + 默认 enabled 风险；② 决策 #25（thinking_content）补充 `extra_body` 映射说明；③ §5.1 LLM 调用任务补充 `extra_body` 参数；④ §5.4 推迟项新增 reasoning_effort 前端可控说明；⑤ §6 Phase 4 新增消息状态机任务（`message.status` complete/partial）；⑥ Phase 4 测试新增消息状态机接口测试 |
| `docs/TEST_CASES.md` | v0.21→v0.23 | ① §5.10 ChatRequest 新增 reasoning_effort 默认值/非法值 2 个用例；② U7.72/U7.73 LLM test 补充 `extra_body` 参数说明；③ U7.8 metadata 测试从字符串转换改为 int 类型一致性；④ A4.11 SSE 中断从「消息已保存」改为「前端内存保留，Phase 3 不持久化」对齐设计方案 |
| `docs/TESTING.md` | v0.8→v0.9 | §5 检索评估 + §7 回归测试 TODO 标记从「待实现」改为「Phase 3 实现」，明确非 Phase 3 准入前置项 |
| `docs/DEVELOPMENT.md` | v0.12→v0.13 | §5 `.env` 示例 LLM 配置对齐 `config.py`：`LLM_BASE_URL` 移除 `/v1`，`LLM_MODEL` deepseek-chat→deepseek-v4-pro |
| `frontend/docs/FRONTEND.md` | — | 无需修改（thinking 开关描述保持 deep_thinking bool 抽象层） |
| `README.md` | — | Phase 2/2.5 标记 ✅，Phase 3 标记「进行中」 |

### 决策索引（追加）

| # | 决策 | 位置 |
|:---|:---|:---|
| 27 | DeepSeek thinking：`deep_thinking` bool → `extra_body={"thinking":{"type":"enabled\|disabled"}}` + `reasoning_effort="high"`，关闭时须显式传 disabled（官方默认 enabled） | ARCHITECTURE.md §5.1.3, API.md §6 |
| 28 | SSE 中断不持久化：Phase 3 前端内存保留半条消息（刷新丢失），Phase 4 引入 `message.status` 字段 + 前端 PATCH 保存 | ROADMAP.md §6, TEST_CASES.md A4.11 |

## 2026-05-25 — Phase 3 文档细化：全部设计文档扩充

### 背景

Phase 3（核心问答）开发启动前，对全部 5 份设计文档进行细化：ROADMAP 排期拆分为 4 个子阶段 50+ 任务、TEST_CASES 从 20 个框架用例扩充至 100+ 详细用例、ARCHITECTURE/API/FRONTEND 补充 Phase 3 设计细节。

### 修改

| 文件 | 版本变更 | 变更 |
|:---|:---|:---|
| `docs/ROADMAP.md` | v0.17→v0.18 | Phase 3 从 10 项简略任务拆分为 4 个子阶段 25+ 详细任务（§5.1 后端 RAG 检索管线 8 项 / §5.2 Chat API 与 SSE 9 项 / §5.3 前端问答界面 11 项 / §5.4 暂不做 7 项）；§5.5 测试 22 项；§5.6 关键决策索引 #15-#26；修复编号错误（4.1→5.1, 5.1→6.1, 6.1→7.1） |
| `docs/TEST_CASES.md` | v0.20→v0.21 | §5 从 20 个框架用例扩充至 100+ 详细用例，覆盖 20 个子模块（向量检索 8 + BM25 检索 6 + BM25 缓存 7 + RRF 融合 7 + NoopReranker 5 + Prompt 7 + Chat Service 8 + LLM 9 + SSE 7 + Schema 6 + 问答接口 12 + KB 选择器 6 + SSE 解析 12 + Markdown 6 + ChatInput 10 + MessageList 8 + MessageItem 8 + WelcomeScreen 3 + ChatPage 8 + 专项测试 6）；§8 覆盖率表新增 Phase 3 模块 |
| `docs/ARCHITECTURE.md` | v0.14→v0.15 | §5 拆分为 3 个子节（§5.1.1 多路检索实现含 BM25 生命周期 / §5.1.2 Prompt 组装与 Token 预算含 4 级策略表 / §5.1.3 SSE 事件流与心跳机制）；§5.2 伪代码从注释骨架更新为 Phase 3 实现（含会话自动创建/SSE 心跳/thinking 处理）；§6 检索方案拆分为 3 子节（§6.1 向量 / §6.2 BM25 含生命周期表 / §6.3 RRF）；§7 补充 ChromaDB metadata 类型一致性和 BM25 缓存结构 |
| `backend/docs/API.md` | v0.12→v0.13 | §3 新增 `GET /api/knowledge-bases/selectable` 端点（Phase 3 KB 选择器）；§6 SSE 事件格式中补充 thinking_content 不落库说明、finish 事件 title 生成说明、SSE 实现方式注释（手动 StreamingResponse + 15s 心跳）；§9 权限矩阵新增 selectable 端点 |
| `frontend/docs/FRONTEND.md` | v0.8→v0.9 | §4.1 布局图新增 KB 选择器（el-select + el-option-group）；§4.2 补充会话自动创建/标题生成/thinking 展示/SSE 心跳说明；§4.5.1 新建对话行为细化；§9 SSE 交互重写（fetch + ReadableStream/心跳解析/事件详情表）；§11 TODO 更新 Phase 3 状态 |

## 2026-05-25 — 文档同步修复

### 修改

| 文件 | 变更 |
|:---|:---|
| `frontend/docs/UIDESIGN.md` | §4.1 幽灵按钮 hover 颜色 `#DDD6FE` → `var(--dm-primary-hover-light)` |
| `frontend/docs/FRONTEND.md` | §5.7 `GET /api/knowledge-bases/public` 状态「待实现」→「已实现」 |
| `docs/ARCHITECTURE.md` | 文件头开发进度更新至 Phase 2.5，版本 v0.13→v0.14 |
| `backend/docs/API.md` | §4 POST documents/batch-upload 权限「仅创建者或 admin」→「仅 owner」，对齐 §9 权限表 |

## 2026-05-25 — 修复：上传文档后状态一直停在「解析中」

### 修复

| 文件 | 变更 |
|:---|:---|
| `frontend/src/views/KnowledgeDetail.vue` | `uploadFiles()` 在 `reloadDocList()` 后对非终态文档启动状态轮询，与 `loadPage()` 保持一致 |

### 根因

上传成功后只刷新了文档列表，没有 `startPolling()`，前端不会轮询状态变化。Celery 后台正常处理，但 UI 不更新。

## 2026-05-25 — 修复：知识库 doc_count 上传不递增 + deleting 状态文档无法重新上传

### 修复

| 文件 | 变更 |
|:---|:---|
| `backend/app/services/document_service.py` | ① `upload_document` 创建文档记录后通过 SQL 表达式原子递增 `kb.doc_count = KnowledgeBase.doc_count + 1`（生成 `UPDATE SET doc_count = doc_count + 1`，避免竞态）；② `upload_document` 同名文档状态为 `deleting` 时复用旧记录（清 Chunk + 清 ChromaDB 向量 + 重置状态），不再拒绝上传；③ 新增 `delete` 导入 |

### 根因

1. `doc_count` 只在删除时递减 (`tasks.py:552`)，上传时从未递增
2. `deleting` 状态和其他处理中状态一视同仁地被拒绝上传。但 `deleting` 语义是「用户已要求删除」，应允许立即重新上传。Celery 挂掉时用户会被彻底卡死：前端看不到该文档，后端又拒绝重新上传同名文件

### 复用旧记录方案（deleting → uploaded）

```
同名文档存在 & status=deleting
  → DELETE 旧 Chunk（MySQL），同步递减 kb.chunk_count
  → DELETE 旧向量（ChromaDB），失败仅 logger.warning 不阻塞
  → 重置 doc.status/error_msg/chunk_count/current_stage/last_success_batch
  → 复用旧 doc_id 保存新文件 + 分发 Celery 入库任务
  → doc_count 不递增（复用旧记录，计数不漂移）
```

### 注意事项

`doc_count` 历史数据需通过 SQL 手动修正（见上条记录）。

### 测试结果

- 后端：343/343 全部通过

---

## 2026-05-24 — 修复：KnowledgeDetail 编辑弹窗缺少可见性选项 + 非 owner 访问公开 KB 误报错

### 修复

| 文件 | 变更 |
|:---|:---|
| `frontend/src/views/KnowledgeDetail.vue` | ① 编辑弹窗新增 `visibility` 字段（Radio：私有/公开），对齐 KnowledgeList 的编辑弹窗；② `loadPage` 中 `reloadDocList` 改为仅 owner 调用，避免非 owner 访问公开 KB 时文档列表 API 返回 403 被误判为页面级错误 |

### 根因

1. KnowledgeDetail 编辑弹窗只传了 `name`/`description`，缺少 `visibility`，导致从详情页编辑 KB 时无法修改可见性
2. `loadPage` 无条件调用 `reloadDocList()`，而后端文档列表接口要求 owner/admin 权限。非 owner 访问公开 KB 时文档列表 403 → `catch` 误报「知识库不存在或无权限」→ 跳转回我的知识库，导致公开 KB 详情页对普通 user 不可用

### 设计说明

公开知识库对普通 user 的价值是**知识发现 + 问答入口**（PRD §5.4）：
1. 浏览公共知识库列表 → 找到感兴趣的
2. 进入详情页查看 KB 名称、描述、统计
3. 点击「开始问答」跳转 `/chat?kb_id=xxx` 进行检索问答

文档列表、上传、编辑、删除仅 owner 可见，符合权限矩阵。

### 测试结果

- 前端：59/59 全部通过

### 文档同步

| 文件 | 版本变更 | 主要变更 |
|:---|:---|:---|
| `frontend/docs/FRONTEND.md` | v0.6→v0.7 | §5.4 编辑操作补充可见性字段；§5.5.2 交互流程区分 owner/非 owner 的文档列表加载逻辑 |
| `docs/ROADMAP.md` | v0.16→v0.17 | Phase 5 新增「Admin 访问 KB 详情页权限」任务；Phase 2.5 §4.5 新增推迟理由 |

---

## 2026-05-24 — Phase 2.5 前端实现：知识库可见性前端

### 背景

Phase 2.5 前端实现：在用户界面中支持知识库 `visibility` 字段（`private`/`public`），新增公共知识库浏览页，非 owner 访问 public KB 时只读展示。

### 代码修改

| 文件 | 变更 |
|:---|:---|
| `frontend/src/api/knowledge.js` | 新增 `getPublicKnowledgeBases()` 函数，调用 `GET /api/knowledge-bases/public` |
| `frontend/src/stores/knowledge.js` | 新增 `publicKbList`/`publicKbLoading`/`publicKbTotal` 状态；新增 `fetchPublicKbList()` action |
| `frontend/src/router/index.js` | 新增 `/knowledge-bases/public` 路由（`PublicKnowledgeList`，需登录） |
| `frontend/src/components/layout/Sidebar.vue` | 知识库导航新增「公共知识库」入口（所有用户可见），使用 `fa-globe` 图标 |
| `frontend/src/views/KnowledgeList.vue` | 新建/编辑弹窗新增 visibility 选择（Radio：私有/公开）；卡片新增 visibility 标识标签 |
| `frontend/src/views/PublicKnowledgeList.vue` | **新建文件**。公共知识库浏览页：卡片网格 + 搜索 + owner 用户名展示，无新建/编辑/删除按钮 |
| `frontend/src/views/KnowledgeDetail.vue` | 新增 `isOwner` 计算逻辑；非 owner 访问 public KB 时隐藏上传区/文档表格/编辑删除按钮，显示「开始问答」入口 |

### 测试

| 文件 | 变更 |
|:---|:---|
| `frontend/tests/PublicKnowledgeList.test.js` | **新建文件**。10 个用例覆盖：页面标题/搜索框渲染、无不含新建按钮/卡片、空状态、卡片网格 + username + 公开标识、无操作菜单、卡片点击跳转、生命周期 |
| `frontend/tests/KnowledgeList.test.js` | 新增 `el-radio-group`/`el-radio` stubs（visibility 选择控件） |
| `frontend/tests/KnowledgeDetail.test.js` | 新增 `@/stores/auth` mock（`isOwner` 计算依赖）；mockKb 新增 `user_id: 1`；新增 stubs |

### 测试结果

- 前端：59/59 全部通过（5 个测试文件，含新增 PublicKnowledgeList 10 用例）
- 构建：`npm run build` 成功

### 文档同步

| 文件 | 版本变更 | 主要变更 |
|:---|:---|:---|
| `backend/docs/API.md` | v0.11→v0.12 | §9 权限速查表 `GET /api/knowledge-bases/public` 状态 ⬜→✅（后端已实现） |

---

## 2026-05-24 — Phase 2.5 后端实现：知识库可见性重构

### 背景

Phase 2.5 需求：知识库新增 `visibility` 字段（`private`/`public`），实现「弱混合模式」——`visibility` 控制 READ，`ownership` 控制 WRITE。后端先行：数据库迁移 → ORM → Schema → Service → API。

### 数据库迁移

| 迁移文件 | 版本链 | 变更 |
|:---|:---|:---|
| `8fa3ea12b75e_knowledge_bases新增visibility字段.py` | `687b64790b37` → `8fa3ea12b75e` | `knowledge_bases` 新增 `visibility ENUM('private','public') DEFAULT 'private'` |

### 代码修改

| 文件 | 变更 |
|:---|:---|
| `backend/app/models/knowledge_base.py` | 新增 `visibility` 字段：`Mapped[str]`，`Enum("private", "public")`，`default="private"`，`server_default="'private'"` |
| `backend/app/schemas/knowledge_base.py` | `KnowledgeBaseCreate` 新增 `visibility: str = Field("private", pattern="^(private|public)$")`；`KnowledgeBaseUpdate` 新增 `visibility: str \| None = Field(None, pattern="^(private|public)$")`；`KnowledgeBaseResponse` 新增 `visibility: str` 字段；新增 `PublicKnowledgeBaseResponse`（含 `username`）+ `PublicKnowledgeBaseListResponse` |
| `backend/app/schemas/__init__.py` | 导出 `PublicKnowledgeBaseResponse`、`PublicKnowledgeBaseListResponse` |
| `backend/app/services/knowledge_base_service.py` | `create_kb()` 支持 visibility 参数；`get_kb()` 权限重构：public KB 所有登录用户可读，private KB 仅 owner + admin 可读；新增 `list_public_kbs()` 查询 visibility=public + status=active（JOIN users 获取 owner 用户名）；`update_kb()` 支持 visibility 字段更新（owner 改自己的，admin 改任意 KB） |
| `backend/app/api/knowledge_base.py` | 新增 `GET /api/knowledge-bases/public` 端点（路由在 `/{kb_id}` 之前）；`GET /{kb_id}` 适配 public KB 可见性；`PUT /{kb_id}` 支持 visibility 修改 |

### 测试文档同步

| 文件 | 版本变更 | 主要变更 |
|:---|:---|:---|
| `docs/TEST_CASES.md` | v0.17→v0.18 | 新增 §4 Phase 2.5 测试用例（Schema 校验 8 个 + 权限矩阵接口 6 个 + 公共 KB 列表接口 7 个 + 前端组件 4 个）；A2.4/A2.6/A2.8 更新描述对齐 visibility 模型；§7→§8 覆盖率表新增 `schemas/knowledge_base.py`、`services/knowledge_base_service.py`、`api/knowledge_base.py (public)` 三行；文档版本号更新 |
| `docs/TESTING.md` | v0.4→v0.5 | §9 测试执行计划新增 Phase 2.5 四个测试行（Schema 校验/权限矩阵/公共列表/前端组件）|
| `docs/ROADMAP.md` | — | §4.2 后端实现 5 项标记 ✅（DB迁移/ORM/Schema/Service/API），文档接口权限和问答接口权限标记为后续验证 |

### 测试结果

- 后端：343/343 全部通过（零回归）
- Phase 2.5 新增测试 39 个：
  - Schema 校验 10 个（`TestKnowledgeBaseCreateVisibility` 5 + `TestKnowledgeBaseUpdateVisibility` 4 + `TestKnowledgeBaseResponseVisibility` 1）
  - KB 权限矩阵 6 个（`TestVisibilityPermissionMatrix`）
  - 公共 KB 列表 5 个（`TestPublicKbList`）
  - 文档接口权限 18 个（`TestDocumentPermissionMatrix`：上传 3 + 列表 3 + 详情 3 + 分块 3 + 删除 3 + reprocess 3）

### 文档接口权限更新

| 文件 | 变更 |
|:---|:---|
| `backend/app/services/document_service.py` | `_check_kb_ownership` 新增 `owner_only` 参数：`True` 时仅 owner 可操作（admin 也不允许），用于上传/reprocess；`False`（默认）时 owner + admin 均可操作，用于查看/分块/删除 |
| `backend/tests/test_document_api.py` | 新增 `TestDocumentPermissionMatrix`（18 用例）覆盖全部权限组合；修复 `test_upload_admin_can_access` → `test_upload_admin_denied`（上传仅 owner） |

### 权限模型总结

| 操作 | owner | admin | 其他用户 |
|:---|:---|:---|:---|
| 上传文档 | ✅ | ❌ | ❌ |
| 批量上传 | ✅ | ❌ | ❌ |
| 查看文档列表 | ✅ | ✅ | ❌（public KB 除外） |
| 查看文档详情 | ✅ | ✅ | ❌（public KB 除外） |
| 查看文档分块 | ✅ | ✅ | ❌（public KB 除外） |
| 删除文档 | ✅ | ✅ | ❌ |
| 重新处理 | ✅ | ❌ | ❌ |

---

## 2026-05-22 — 知识库可见性模型：弱混合模式文档体系建立

### 背景

当前权限模型为「仅 owner 能看自己的 KB + admin 全局只读」，与 PRD 描述的跨部门知识共享场景不匹配。采用「弱混合模式」——`visibility` 控制 READ，`ownership` 控制 WRITE——用一个字段解决核心矛盾，不做 ACL/多租户。

### 文档修改

| 文件 | 版本变更 | 主要变更 |
|:---|:---|:---|
| `docs/PRD.md` | v0.3→v0.4 | 新增 §5「知识库可见性模型」：ownership 归属规则、visibility 规则、CRUD 权限矩阵（user/admin × 各操作）、问答检索范围、暂时不做的推迟项说明 |
| `docs/ARCHITECTURE.md` | v0.12→v0.13 | 新增 §7.6「知识库可见性模型（弱混合模式）」设计决策：决策背景、方案、代码约束 |
| `backend/docs/DATABASE.md` | v0.6→v0.7 | §2.2 `knowledge_bases` 表新增 `visibility ENUM('private','public') DEFAULT 'private'` 列 + 字段说明 |
| `backend/docs/API.md` | v0.10→v0.11 | §3 KB 创建/列表/详情/更新接口补充 visibility 字段；新增 `GET /api/knowledge-bases/public` 端点；§9 权限速查表全面更新（public 可读约束 + admin 只读约束 + 文档接口仅 owner 可写） |
| `frontend/docs/FRONTEND.md` | v0.4→v0.5 | §2.1 路由表新增 `/knowledge-bases/public`（PublicKnowledgeList）；§4.5.2 侧边栏新增「公共知识库」入口；新增 §5.7 公共知识库浏览页规格（布局、与我的 KB 差异、卡片行为）；§5.5 KB 详情页增加 public KB 非 owner 只读说明；§11 TODO 更新 |
| `docs/ROADMAP.md` | v0.13→v0.14 | 新增 §4「Phase 2.5：知识库可见性重构」（1-2 天）：业务规则文档、后端实现、前端实现、测试 4 个子任务组；依赖关系图更新（Phase 2→2.5→3） |
| `CLAUDE.md` | — | 关键约定→后端 新增「权限分离原则（visibility / ownership）」约束；文档索引 PRD 描述更新为「需求/验收/权限模型」 |

### 设计决策

| # | 决策 | 文档位置 |
|:---|:---|:---|
| 14 | 弱混合模式：`visibility` 控制 READ，`ownership` 控制 WRITE | PRD.md §5, ARCHITECTURE.md §7.6 |

### 2026-05-23 — Admin 权限修正

**问题**：初始版本将 admin 设为「全局只读管理」，但「管理」天然需要写权限。只能看不能动的 admin 实际什么都做不了（无法删除违规 KB、无法修正不当元数据、无法审计 private KB 内容）。

**修正**：

| 操作 | 修正前 | 修正后 | 理由 |
|:---|:---|:---|:---|
| 查看 KB | 只读（公私皆可） | 含 private KB 审计 | 审计需要 |
| 编辑 KB 元数据 | ❌ | ✅ | 修正不当名称/离职员工 KB 转 public |
| 删除 KB | ✅ | ✅ | 不变 |
| 上传文档 | ❌ | ❌ | 不越权写入（不变） |
| 删除文档 | ❌ | ✅ | 逐文档违规清理，不必整库删除 |
| 查看文档/分块 | ❌ | ✅ | 审计 private KB 内容 |

**涉及文档**：PRD.md §5.1/§5.3/§5.4（权限矩阵）、ARCHITECTURE.md §7.6（设计决策）、API.md §9（权限速查表）、CLAUDE.md（权限分离约束）、ROADMAP.md §4.2（任务描述）、FRONTEND.md §5.6/§7.3（Admin 页面描述）

### 代码变更

本次仅文档，无代码变更。代码实现将在 Phase 2.5 进行（数据库迁移 + API 权限重构 + 前端页面）。

---

## 2026-05-22 — Phase 2.3.3 前端测试：组件测试编写并全部通过

### 新增
- **`frontend/tests/KnowledgeList.test.js`**：KnowledgeList 组件测试（11 用例）— 渲染（搜索框/新建按钮/卡片/空状态/部门图标/无描述占位）、交互（新建弹窗/卡片点击跳转）、生命周期（fetchKbList 调用）
- **`frontend/tests/KnowledgeDetail.test.js`**：KnowledgeDetail 组件测试（12 用例）— 渲染（KB 信息/返回按钮/统计卡片/上传区域/文档表格/空状态/筛选区域/编辑删除按钮）、生命周期（挂载获取数据/卸载清除轮询）

### 修改
- **`frontend/tests/AppLayout.test.js`**：新增 3 个路由标题测试（11→14 用例）— KnowledgeList / KnowledgeDetail / AdminStats
- **`docs/DEVELOPMENT.md` v0.11**：§2 前端测试目录新增 KnowledgeList.test.js + KnowledgeDetail.test.js
- **`docs/TEST_CASES.md` v0.16→v0.17**：§3.5 C2.1-C2.7 更新状态（5 个 ✅ / 1 个 ⬜ C2.4 下拉菜单删除确认 / 1 个 ✅ C2.6 上传区域渲染）；§7 前端组件覆盖率更新为 49 通过

---

## 2026-05-22 — Phase 2.3.3 前端开发：知识库管理 + 文档管理

### 新增
- **`frontend/src/api/knowledge.js`**：知识库 CRUD + 文档管理 + 分块查询 全部 API 封装（getKnowledgeBases / createKnowledgeBase / updateKnowledgeBase / deleteKnowledgeBase / getDocuments / uploadDocument / batchUploadDocuments / reprocessDocument / deleteDocument / getDocumentChunks）
- **`frontend/src/stores/knowledge.js`**：Pinia 知识库状态管理，含 KB CRUD、文档上传/删除/轮询、分块预览、`TERMINAL_STATUSES` 常量、`isTerminal()` 判断、`getDepartmentStyle()` 部门色匹配
- **`frontend/src/views/KnowledgeList.vue`**：知识库列表页（`/knowledge-bases`）— 卡片网格 + 搜索 + 新建/编辑弹窗 + 删除确认 + 部门图标色自动匹配
- **`frontend/src/views/KnowledgeDetail.vue`**：知识库详情页（`/knowledge-bases/:id`）— KB 信息+统计卡片 + 拖拽上传区 + 文档表格（筛选/排序/分页）+ 状态轮询 + 分块预览弹窗 + reprocess 按钮
- **`frontend/src/views/admin/StatsPage.vue`**：Admin 系统概览占位页面（Phase 5 联调）

### 修改
- **`frontend/src/router/index.js`**：新增 `/knowledge-bases`、`/knowledge-bases/:id`、`/admin/stats` 三条路由
- **`frontend/src/components/layout/AppLayout.vue`**：pageTitle 映射增加 KnowledgeList / KnowledgeDetail / AdminStats
- **`frontend/src/components/layout/Sidebar.vue`**：所有用户增加「我的知识库」导航入口（路由高亮适配 KB 详情子路由）
- **`frontend/src/views/admin/KnowledgeList.vue`**：从空占位更新为 Phase 2 规格占位页（统计卡片 + Phase 5 联调提示）
- **`frontend/src/views/admin/DocumentList.vue`**：从空占位更新为 Phase 2 规格占位页

## 2026-05-22 — 文档体系对齐：前后端权限模型 + 路由结构统一

### 修改
- **API.md v0.9→v0.10**：§7 补充 `GET /api/admin/knowledge-bases` 接口规格；所有 admin 接口标注「Phase 5 实现」状态；§9 权限速查表增加实现状态列
- **FRONTEND.md v0.3→v0.4**：§2.1 路由表重构（区分用户视角 `/knowledge-bases/**` 和管理员视角 `/admin/**`）；§4.1 Sidebar 增加「我的知识库」入口；§5 重写为用户 KB 列表 + 新增 §5.5 KB 详情页规格 + §5.6 Admin KB 列表；§6 重写为 KB 内文档管理（上传自动归属 KB）+ §7 管理后台补充完整页面规格；§11 TODO 更新
- **ROADMAP.md v0.10→v0.11**：§3.3 前端任务拆分更新（新增 KnowledgeDetail 页面、Sidebar 导航更新、Admin 占位页）；§6 Phase 5 补充 Admin 后端接口实现 + 前端联调任务
- **问题修复**：解决 #18（文档上传 KB 上下文缺失）、#19（KB 管理页权限不一致）、#20（Admin KB 接口缺失）、#21（KB 详情页缺失）、#22（Sidebar 导航设计错误）、#23（Admin 接口文档有但未标注实现状态）、#24（Admin router 未注册但文档未提及）

---

## 2026-05-22 — UI 配色二轮调整：纯黑白体系 + 加强边界感

### 修改
- **去除蓝色点睛色**（`global.css`）：`--dm-primary` 系列从蓝色 `#2563EB` 切换为黑色 `#1A1A1A`，Logo、激活态、链接全部统一黑白
- **加强层次边界**（`global.css`）：页面底色 `#FAFAFA`→`#F2F2F2`；边框 `#E8E8E8`→`#E0E0E0`；阴影整体加重（sm/md/lg/xl 透明度 +2-3%）
- **Element Plus 主题同步**：`--el-color-primary` 系列从蓝色系切换为灰度系（`#1A1A1A`/`#404040`/`#737373`/...）
- **登录卡片增加边界**（`LoginPage.vue`）：卡片新增 `1px solid` 边框；Tab 切换容器底色 `#E8E8E8` 让白色激活态更跳；激活 Tab 阴影加重
- **底部链接增强**：`toggle-tip` 链接改用 `--dm-weight-semibold` 加粗

### 文档同步
- **`frontend/docs/UIDESIGN.md` v0.5→v0.6**：CSS 变量、Element Plus 覆盖、UnoCSS 配置全部同步纯黑白

## 2026-05-22 — UI 配色体系重构：极简黑白风格

### 修改
- **Design Token 全局重写**（`frontend/src/styles/global.css`）：配色从 Indigo/Slate 体系（`#4F46E5`/`#F8FAFC`）切换为黑白灰极简体系（`#1A1A1A`/`#FAFAFA`），点睛色 `#2563EB`。移除所有渐变（`--dm-primary-gradient`、`--dm-gradient-login`），品牌色阴影改为中性柔和阴影
- **登录页去渐变**（`LoginPage.vue`）：背景从紫色渐变改为纯色 `#FAFAFA`；Logo 图标从渐变改为纯色 `#2563EB`；提交按钮从渐变改为纯黑 `#1A1A1A`
- **侧边栏极简化**（`Sidebar.vue`）：Logo 图标纯色 `#2563EB`；新建对话按钮从填充风格改为白底描边风格；用户头像从渐变改为纯黑
- **布局数值微调**：侧边栏 `260px→260px`（聊天）/`260px→240px`（管理）；顶栏 `64px→56px`；聊天最大宽度 `900px→768px`；圆角统一放大 2px（`6→8px`, `10→12px`, `14→16px`）；阴影整体更柔和
- **Element Plus 主题同步**：`--el-color-primary` 系列从 Indigo 切换为 Blue

### 文档同步
- **`frontend/docs/UIDESIGN.md` v0.4→v0.5**：CSS 变量、组件样式示例、Element Plus 覆盖、UnoCSS 配置全部同步到新配色；消息气泡用户侧改为黑底白字、AI 侧无背景；头像/Logo 改为纯色；移除所有渐变引用

## 2026-05-22 — Windows Celery Worker 启动修复

### 修复
- **Celery Worker 任务接收后卡死**（`celery_app.py`）：移除 `eventlet` 池配置，改用 `solo` 池。eventlet monkey-patch 与 asyncio 事件循环冲突，导致任务收到后静默,另外注意 --pool=solo 一次只处理一个任务，本地开发够用。如果后续需要并发，Windows 上可以起多个 Worker 进程。
- **aiomysql 在 Worker 中静默卡死**（`celery_app.py`）：Windows 平台新增 `asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())`，aiomysql 依赖 Selector 事件循环，Windows 默认 Proactor 不兼容
- **Celery Worker 中 ChromaDB 未初始化**（`chroma_client.py`）：`get_collection()` / `get_client()` 改为懒加载自动初始化，原实现仅依赖 FastAPI lifespan 调用 `init_chroma()`，Worker 独立进程未覆盖
- **Service 层与 Celery 任务命名冲突**（`document_service.py`）：`delete_document` / `ingest_document` 导入加别名 `as _delete_doc_task` / `as _ingest_doc_task`，避免 service 同名函数覆盖 Celery task 导致 `.delay()` 抛出 AttributeError
- **Celery 任务跨事件循环连接池报错**（`tasks.py`）：新增 `_get_worker_loop()` 持久化事件循环，`ingest_document` / `delete_document` / `delete_kb` 三个任务入口复用同一 loop。原每次任务 `new_event_loop()` → `close()` 导致 SQLAlchemy 连接池中连接挂在旧 loop 上，下个任务在新 loop 复用时触发 `attached to a different loop`
- **Celery 任务在 commit 前被消费导致状态不一致**（`document_service.py`）：`upload_document` / `delete_document` / `reprocess_document` / force 覆盖路径 — 所有 `delay()` 分发前加 `await db.commit()`。原仅 `flush()` 后分发，`get_db()` 依赖注入在路由返回后才 commit，Worker 在 commit 前捡到任务时查到的仍是旧状态（如 delete 任务看到 completed 而非 deleting → 跳过删除 → 文档永久卡在 deleting）
- **SQLAlchemy passive_deletes 导致删除文档报 IntegrityError**（`document.py` / `knowledge_base.py`）：`Document.chunks`、`KnowledgeBase.documents`、`KnowledgeBase.chunks` 三处 `relationship()` 添加 `passive_deletes=True`。SQLAlchemy 默认 `passive_deletes=False`，删除父对象前会先加载子对象并 SET FK=NULL 再让数据库 CASCADE 删除，但 chunk 的 `doc_id`/`kb_id` 为 NOT NULL，SET NULL 触发 `(1048, "Column 'doc_id' cannot be null")`。加 `passive_deletes=True` 跳过中间步骤，直接由数据库 FK CASCADE 处理

### 修改
- **批量上传错误信息丢失诊断细节**（`document_service.py`）：batch failed 的 `reason` 增加 `error_detail` 拼接。原仅 `error_code:error_message`（如 `E2011: 文档正在处理中`），用户无法判断是重名拦截还是真的在处理；现追加 detail（如 `（文档 'xxx' 正在处理中（状态：uploaded），请等待处理完成）`）
- **批量上传接口 message 语义不明确**（`api/document.py`）：message 改为含计数格式 `批量上传完成（2 个文件，成功 1 个，失败 1 个）`，前端无需解析 data 就能感知有失败项。HTTP 200 + 部分成功为批量接口设计意图，前端须检查 `data.failed` 数组

### 文档同步
- **`docs/ARCHITECTURE.md` v0.11→v0.12**：§4.4 EMBED_BATCH_SIZE 20→10 并标注 DashScope 上限；§4.6 锁键格式更新为 `doc_lock:{doc_id}`（ingest/delete 共享互斥）；§7.1 ChromaDB 初始化改为懒加载描述（覆盖 FastAPI + Celery Worker 双运行时）；§4.9 Celery 配置示例补充 `autoretry_for` + `retry_backoff` + 持久化事件循环说明；§4.5 删除流程补充 `chunk_count`/`doc_count` 原子递减步骤；§4.1 入库流程图补充 force=true 覆盖分支（终态→异步删旧→建新）；§4.1 补充 reprocess ChromaDB 旧向量清理说明
- **`backend/docs/API.md` v0.8→v0.9**：§4 batch-upload 响应示例更新 message 含计数格式；failed reason 更新为含 detail 诊断信息；新增 message 约定和前端检查 data.failed 的提示
- **`backend/docs/DATABASE.md` v0.5→v0.6**：§4 外键策略补充「SQLAlchemy ORM 行为注意事项」，说明 `passive_deletes=False` 默认行为与 NOT NULL 列的冲突及解决方案；§2.2 `chunk_count`/`doc_count` 字段说明补充删除时原子递减维护要求
- **`docs/DEVELOPMENT.md` v0.10→v0.11**：§3.1 Celery Worker 启动命令区分 Linux/Mac 和 Windows（`--pool=solo`）；新增 Windows 特别注意事项（pool 选型、事件循环策略、solo 并发限制）
- **`CLAUDE.md`**：关键约定新增 Service/Celery 任务命名隔离规则 + `delay()` 分发前必须显式 `commit()` 规则；常用命令 Celery 启动加 `--pool=solo`

## 2026-05-21 — 审查报告 10 项质量修复

### 修复
- **force 覆盖未触发 Celery 删除**（`document_service.py`）：`upload_document` force=true 覆盖终态文档时，新增 `delete_document.delay(existing.id)` 触发异步清理，确保旧文档向量/文件/MySQL 记录被清理
- **delete_document 未递减 KB 统计计数**（`tasks.py`）：`_delete_document_async` 物理删除文档后，原子递减 `KnowledgeBase.chunk_count`/`doc_count`（使用 `func.greatest(0, ...)` 防止负数）
- **KB 删除未触发 Celery 异步清理**（`tasks.py` + `knowledge_base_service.py`）：新增 `_delete_kb_async` / `delete_kb` Celery 任务，遍历 KB 下所有文档清理 ChromaDB + 磁盘 → 物理 DELETE KB；`delete_kb` service 层触发 `delete_kb_task.delay(kb.id)`
- **reprocess 时 ChromaDB 旧向量清理缺失**（`document_service.py`）：`reprocess_document` 在重置状态前显式调用 `collection.delete(where={"doc_id": doc_id})` 清理旧向量
- **Celery max_retries=3 死代码**（`tasks.py`）：移除 `_ingest_document_async` / `_delete_document_async` 外层 catch-all `except Exception`，添加 `autoretry_for=(Exception,)` + `retry_backoff=True`，未捕获异常由 Celery 自动重试
- **vector_storing 恢复吞噬 ChromaDB 清理失败**（`tasks.py`）：ChromaDB 残留向量清理失败时标记 `DocumentStatus.FAILED` 并返回，不再静默继续
- **Embedder 未校验 API 返回向量数**（`embedder.py`）：`_parse_embed_response` 新增 `len(embeddings) != text_count` 校验，不匹配时抛 `ValueError`
- **入库/删除任务无互斥锁**（`lock.py` + `test_idempotent_lock.py`）：锁键格式从 `idempotency_key:{doc_id}:{task_type}` 改为 `doc_lock:{doc_id}`，ingest/delete 对同一 doc_id 共享互斥锁

### 修改
- `docs/ARCHITECTURE.md` — v0.10→v0.11；§1 技术选型 Embedding/智能分块 改为 `[Implemented]`；§2.2 实现图 Chunker/Embedder/Vector Store 改为 ✅；§4.5 异步删除改为 `[Implemented]`
- `docs/TEST_CASES.md` — v0.14→v0.15；U6.7 更新为覆盖 `test_tasks.py`
- `backend/tests/test_tasks.py` — 新增 11 用例：`RESUMABLE_STAGES` 阶段常量(5) + 断点恢复(3) + checkpoint 更新(1) + 幂等锁集成(1) + last_success_batch(1)
- `backend/tests/test_idempotent_lock.py` — 锁键格式更新：`doc_lock:{doc_id}`；shared lock for ingest/delete

### 测试结果
- 后端：304/304 全部通过（零回归，+11 新用例）

## 2026-05-21 — delete_document Celery 异步任务实现

### 修改
- `backend/app/ingest/tasks.py` — `delete_document` 骨架 → 完整实现：
  - 新增 `_delete_document_async()` 异步函数：幂等锁 → ChromaDB 向量清理 → 磁盘文件删除 → MySQL 物理 DELETE（FK CASCADE 清 chunks）
  - 新增 `local_storage` import

### 测试结果
- 现有 293 测试全部通过（API 层 delete 测试已覆盖，Celery 层通过 mock 隔离）

## 2026-05-21 — Phase 2 入库流水线 6 项质量修复

### 修复
- **数据一致性：MySQL-ChromaDB 事务断点恢复**
  - `tasks.py`：新增 `RESUMABLE_STAGES` + 阶段检测，`chunking_done`/`embedding`/`vector_storing` 阶段跳过解析分块
  - `tasks.py`：chunk 插入前 `delete(Chunk).where(doc_id=...)` 幂等去重，避免重试时重复写入
  - `tasks.py`：Embedding 循环从 `doc.last_success_batch` 续传，checkpoint 真正被利用
  - `tasks.py`：`vector_storing` 恢复时先清理 ChromaDB 残留向量
  - 新增 `_load_chunk_rows()` 辅助函数
- **数据一致性：kb.chunk_count 原子更新**
  - `tasks.py`：改为 `update(KB).values(chunk_count=KB.chunk_count + N)` 数据库端原子操作
- **Token 回写防御性改进**
  - `tasks.py`：构建时同步写入 `token_map: dict[int, int]`（chunk_id → token_count），回写时用 map 替代索引隐式假设
- **Embedder 响应格式防御性校验**
  - `embedder.py`：`_parse_embed_response` 逐条检查 `embedding` key，缺失时抛 `ValueError`
- **错误信息单位判断修正**
  - `parser.py`：`ParseResult` 新增 `source_type` 字段
  - `tasks.py`：`_build_error_msg` 改用 `source_type == "docx"` 区分「段/页」
- **代码清理**
  - `embedder.py`：删除未使用的 `embed_chunks_batched`（tasks.py 需逐批写 checkpoint，无法直接复用）
  - `test_embedder.py`：移除 `TestEmbedChunksBatched` 测试类（4 用例）

### 修改
- `docs/TEST_CASES.md` — v0.13→v0.14；全量回归 293 ✅

### 测试结果
- 后端：293/293 全部通过（零回归）

## 2026-05-21 — 文件存储服务测试补全

### 新增
- `backend/tests/test_storage.py` — 文件存储服务单元测试（37 用例）：
  - `TestSanitizeFilename`（16）: 普通文件名 / 路径分隔符 / 空字节 / 控制字符 / 中文保留 / basename 剥离 / 首尾空白点号 / 空文件名→unnamed
  - `TestGenerateStoredFilename`（4）: 8位uuid格式 / 危险字符安全化 / uuid唯一性 / 16进制校验
  - `TestLocalStorage`（17）: save 文件写入+目录创建+seek重置 / read bytes/空文件/不存在抛异常 / delete 幂等+空目录自动清理+多级目录清理+同目录有其他文件保留 / 中文路径 / kb_id隔离

### 修改
- `docs/TEST_CASES.md` — v0.12→v0.13；§3.4 U6.7-U6.11 标记 ✅；§7 覆盖率表新增 `core/storage.py` 行
- `docs/ROADMAP.md` — v0.9→v0.10；§3.5 文件存储服务测试标记 ✅

### 测试结果
- 后端：297/297 全部通过（37 新增 + 260 原有，零回归）

## 2026-05-21 — Phase 2 Embedding 向量化 + ChromaDB 入库完成

### 新增
- `backend/app/rag/embedder.py` — Embedding 向量化模块，DashScope text-embedding-v3 API 调用：
  - `embed_chunks(texts)` — 单批次调用，max_retries=5 指数退避（1s→2s→4s→8s→16s）
  - `embed_chunks_batched(texts, batch_size)` — 分批调用，支持批次级 checkpoint
  - `EmbedResult` dataclass：embeddings(1024 维) + token_counts + total_tokens
  - `_parse_embed_response()` — API 响应解析，按文本数等比例分配 token 计数
- `backend/tests/test_embedder.py` — Embedding 模块单元测试（30 用例）：
  - `TestEmbedResult`（3）: 默认值 / 正常创建 / asdict 序列化
  - `TestBuildEmbedUrl`（2）: URL 格式 / 无连续斜杠
  - `TestBuildPayload`（4）: model + input_texts / text_type=document / 空列表 / 单文本
  - `TestSafetyTruncate`（3）: 短文本 / 超长截断 / 默认 max_len
  - `TestParseEmbedResponse`（5）: 2 条解析 / 等比例分配 / total_tokens=0 / 空列表 / 单文本
  - `TestEmbedChunks`（4）: 空列表 / 正常调用 / 请求体格式 / 1024 维验证
  - `TestEmbedRetry`（5）: 500 重试 / 网络异常重试 / 全部失败抛 RuntimeError / 指数退避延迟 / 4xx 重试
  - `TestEmbedChunksBatched`（4）: 单批 / 自动分批 / 空列表 / 顺序正确

### 修改
- `backend/app/ingest/tasks.py` — 入库流水线完整实现（步骤 7-9）：
  - 步骤 7 Embedding：加载 MySQL chunks → 分批调用 `embed_chunks()` → 每批成功更新 `last_success_batch`
  - 步骤 8 ChromaDB：`collection.add()` 批量写入（batch_size=100），失败时 `collection.delete(where={doc_id})` 全清 + 标记 FAILED
  - 步骤 9 终态判定：token_count 回写（API 实际值覆盖估算值）→ `doc.chunk_count` + `kb.chunk_count` 事务更新 → `completed` / `success_with_warnings`
  - 新增 import：`embed_chunks`、`get_collection`、`KnowledgeBase`、`select`、`update`
- `docs/ROADMAP.md` — v0.8→v0.9；§3.2 标记 Embedding/ChromaDB/chunk_count/状态机为 ✅

### 测试结果
- 后端：260/260 全部通过（30 新增 + 230 原有，零回归）

## 2026-05-21 — 入库流水线代码质量修复（6 项）

### 修复
- `backend/app/rag/parser.py` — `_parse_docx` 改为逐段 try/except 容错（对齐 PDF 逐页容错粒度），每段一个 `ParsedPage`；空白段跳过不计入失败
- `backend/app/rag/chunker.py` — `_resolve_page_number` 改用基于搜索偏移量的定位方式（`text.find(chunk_text, search_start)`），消除 `str.find` 重复片段歧义和 O(chunks×text_len) 性能问题
- `backend/app/rag/chunker.py` — `estimate_tokens` 新增中文字符占比检测（中文 >30% → ratio=1.5，否则 ratio=4.0），修复纯英文/英文为主文档 token 严重低估问题
- `backend/app/ingest/tasks.py` — 合并冗余 DB session，从 5-6 次 `select(Document)` 降至 3 次 `db.get(Document, doc_id)`；每个 DB session 后新增 DELETING 状态检查；新增空文档显式检测（`total_pages==0` 或 `full_text` 为空 → 明确 error_msg）
- `backend/app/ingest/tasks.py` — `asyncio.run()` 替换为 `asyncio.new_event_loop()` + `run_until_complete()` 模式，兼容 gevent/eventlet 等已有事件循环环境
- `backend/app/ingest/tasks.py` — `_build_error_msg` 自动识别「页/段」单位（多段落 docx 显示「段」）

### 测试
- `backend/tests/test_parser.py` — 新增 `test_空白段落被跳过_不影响容错率`、`test_DOCX单段解析异常_跳过继续`、`test_DOCX无段落`、更新 `test_正常DOCX_逐段提取`（total_pages=2）、`test_DOCX全部空白_无有效文本`
- `backend/tests/test_chunker.py` — `TestResolvePageNumber` 适配新签名（`(start_offset, offset_map)`）；`TestEstimateTokens` 新增 `test_中文为主_占比超阈值`，更新英文/混合用例预期值

### 测试结果
- 后端：230/230 全部通过（新增 4 用例，chunker 35→37，parser 32→34，全量无回归）

## 2026-05-20 — 文档进度同步更新

### 修改
- `docs/ROADMAP.md` — v0.7→v0.8；§3.2「智能分块」标记 ✅（chunker.py 已开发完成 + 35 用例全部通过）
- `docs/TEST_CASES.md` — v0.9→v0.10；§7 覆盖率表新增 `rag/chunker.py` 行（35 用例 ✅）
- `docs/DEVELOPMENT.md` — v0.7→v0.8；§5 依赖列表同步：`passlib[bcrypt]`→`bcrypt==4.0.*`（与 requirements.txt 一致）、补充 `rank-bm25==0.2.*`

## 2026-05-20 — Phase 2 3.2 智能分块开发

### 新增
- `backend/app/rag/chunker.py` — 智能分块模块，使用 `RecursiveCharacterTextSplitter`（分隔符 `["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""]`，`keep_separator=True`，`chunk_size=1000`，`chunk_overlap=150`），支持页码回溯（`_build_page_offset_map` + `_resolve_page_number`）和字符数 token 估算（`int(len(content) / 1.5)`）
- `backend/tests/test_chunker.py` — U6.6 分块逻辑单元测试（35 用例全部通过，6 个测试类）
  - `TestChunkResult`（3）: 字段默认值、page_number 可空、estimated_tokens 类型
  - `TestChunkingResult`（2）: 默认空结果、含分块聚合结果
  - `TestEstimateTokens`（5）: 中文/英文/混合/短文本/空文本字符估算
  - `TestBuildPageOffsetMap`（4）: 正常偏移构建、跳过失败页/空页、空列表
  - `TestResolvePageNumber`（5）: 首页/中间页/末页定位、空映射、找不到
  - `TestChunkDocument`（16）: 单块/空文本、段落/句号/换行分隔符优先级、keep_separator、chunk_size 范围、overlap 重叠、页码追踪、token 估算、中英混合文本

### 修改
- `backend/app/ingest/tasks.py` — 集成 chunker 到 Celery 流水线：解析通过容错判定后 → 状态置 `CHUNKING` → 调用 `chunk_document()` → 批量写入 MySQL `chunks` 表（含 `chroma_id`、`metadata` 页码）→ `current_stage = "chunking_done"`；空 chunk 结果标记 `FAILED`
- `docs/ARCHITECTURE.md` — v0.8→v0.9；§4.2 分块策略分隔符从 `["\n\n", "\n", "。！？", ".!?", " ", ""]` 展开为独立字符 `["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""]`，补充注释说明 `RecursiveCharacterTextSplitter.separators` 是精确字符串匹配（非正则）。新增 `keep_separator=True` 配置（中文场景保留语义完整性）。

## 2026-05-20 — 跨文档一致性修复（4 处）

### 修复
- `docs/ROADMAP.md` — v0.6→v0.7；§3.2 删除 "Unstructured + "（实际代码仅使用 PyPDF2 + python-docx，无 unstructured 依赖）
- `docs/ARCHITECTURE.md` — v0.7→v0.8；修复重复的 §4.6 编号：
  - `§4.6 chunk_count 事务更新` → `§4.7`
  - `§4.7 文档解析容错` → `§4.8`
  - `§4.8 Celery 配置要点` → `§4.9`
- `docs/TEST_CASES.md` — v0.7→v0.8；§7 覆盖率表新增 `ingest/lock.py`（16 用例 ✅）和 `rag/parser.py`（32 用例 ✅）两行
- `docs/PRD.md` — v0.2→v0.3；§5 验收标准从 TODO 补全为量化指标表（Recall@5≥0.85 / P50≤3s / 综合分≥4.0 等 9 项），与 ROADMAP §7.1 / TESTING.md §5-§8 对齐

## 2026-05-20 — 架构文档实现状态标记重构

### 修改
- `docs/ARCHITECTURE.md` — v0.6→v0.7；修复 13 处跨文档不一致：
  - 新增「当前实现状态说明」章节，定义 `[Implemented]`/`[Planned: Phase X]`/`[Target Architecture]` 三种标记
  - §1 技术选型表新增「状态」列，标注每项技术当前实现阶段
  - §2 拆分为 2.1 目标架构 [Target Architecture] + 2.2 当前实现 [Phase 2] 双图
  - §3.1 模块总览表新增「状态」列
  - §4.2 分块策略补全分隔符优先级、token_count 回写说明，结构感知分块标记 [Planned: Phase 3]
  - §4.5 新增 KB/文档异步删除章节，标注实现程度
  - §5 问答流程标记 [Target Architecture]，新增 §5.1 Phase 3 实际流程 + §5.2 伪代码含阶段标注及 history 变量说明
  - §7.3 Rerank 策略修正 NoopReranker 阶段（Phase 1-2 → Phase 3）
  - §8 会话记忆策略标记 [Planned: Phase 4]
- `backend/docs/DATABASE.md` — v0.4→v0.5；修正 reprocess 触发条件描述（"任一终态"→"仅 partial_failed / failed"）

## 2026-05-19 — Phase 2 3.2 文档解析开发

### 新增
- `backend/app/rag/parser.py` — 文档解析器，支持 PDF（PyPDF2 逐页）、DOCX（python-docx）、MD/TXT 格式解析，含 `ParsedPage`/`ParseResult` 数据结构，部分容错机制（单页失败跳过）
- `backend/app/ingest/tasks.py` — Celery 入库流水线任务：
  - `ingest_document(doc_id)` — 主入库任务，幂等锁获取 → 状态机流转 → 解析阶段调用 → 容错判定（<20% 继续 / 20-50% partial_failed / >50% failed）
  - `delete_document(doc_id)` — 异步删除任务骨架（待后续实现）
- `backend/tests/test_parser.py` — 解析器单元测试（32 用例），覆盖 ParsedPage/ParseResult 数据类、TXT/MD 解析、PDF 逐页解析（Mock）、DOCX 段落提取（Mock）、容错阈值判定、parse_document 入口分发

### 修改
- `backend/app/ingest/celery_app.py` — 末尾导入 `app.ingest.tasks` 注册 Celery 任务
- `backend/app/services/document_service.py` — `upload_document()`/`reprocess_document()`/`delete_document()` 注入 Celery 任务调度（替换 TODO 占位符），修复 delete_document 函数内导入为文件顶部导入
- `docs/DEVELOPMENT.md` — v0.6→v0.7；补充 `test_parser.py` 到项目结构树

### 测试结果
- 后端：191/191 全部通过（32 新增 + 159 原有，无回归）

## 2026-05-19 — Phase 3.2 Celery 幂等锁开发

### 新增
- `backend/app/core/redis_client.py` — Redis 客户端懒加载单例（`get_redis()`），供锁/缓存/会话等模块复用
- `backend/app/ingest/lock.py` — Celery 幂等锁模块，基于 Redis `SET NX EX 600` 实现：
  - `acquire_idempotency_lock()` — 获取锁（原子操作，已锁定返回 False → E2011）
  - `release_idempotency_lock()` — 释放锁（幂等，DELETE 不存在 key 无异常）
  - `check_idempotency_lock()` — 检查锁状态
  - Key 格式：`idempotency_key:{doc_id}:{task_type}`（如 `123:ingest`）
- `backend/app/ingest/celery_app.py` — Celery 应用配置（broker/backend 从 settings 读取，json 序列化，soft_time_limit=600s，time_limit=900s）
- `backend/tests/test_idempotent_lock.py` — 幂等锁单元测试（16 用例，Mock Redis），覆盖 key 格式/获取成功/重复拒绝/自定义 TTL/释放/检查/完整生命周期

### 修改
- `docs/DEVELOPMENT.md` — v0.5→v0.6；结构树补充 `core/redis_client.py`、`ingest/lock.py`、`tests/test_idempotent_lock.py`
- `docs/TEST_CASES.md` — v0.5→v0.6；U6.1/U6.2 标记 ✅（2026-05-19），被测模块更正为 `lock.py`
- `docs/ROADMAP.md` — §3.2 Celery 幂等锁标记 ✅

### 测试结果
- 后端：159/159 全部通过（16 新增 + 143 原有，无回归）

## 2026-05-18 — DocumentStatus ENUM 映射修复

### 修复
- `backend/app/models/document.py` — `status` 列的 `Enum(DocumentStatus)` 新增 `values_callable=lambda obj: [e.value for e in obj]`，修复 SQLAlchemy 默认使用枚举**成员名**（`UPLOADED` 大写）而 MySQL ENUM 列实际存储**成员值**（`'uploaded'` 小写）的映射错误
- 根因：`alembic/versions/42097bdbd61a` 通过 raw SQL `ALTER TABLE ... ENUM('uploaded','parsing',...)` 创建了小写值，但 SQLAlchemy ORM 层 `Enum(DocumentStatus)` 默认按成员名（大写）校验，导致 `LookupError: 'uploaded' is not among the defined enum values`

### 修改
- `docs/ROADMAP.md` — v0.6；§3.1 文档上传/批量上传/重新处理/列表详情/删除/文件存储标记 ✅（API 层全部完成，Celery 异步管道在 §3.2 待实现）

## 2026-05-18 — Phase 2 文档 API 接口测试

### 新增
- `backend/tests/test_document_api.py` — 47 个文档 API 接口测试（7 个 TestClass），覆盖全部 7 个端点：
  - 上传（11 用例）：正常/重复文件名/force 覆盖/force 冲突/处理中冲突/不支持格式/超大文件/知识库不存在/越权/未认证/admin 权限
  - 批量上传（4 用例）：全部成功/部分失败/知识库不存在/未认证
  - 列表（11 用例）：正常/状态筛选/文件名搜索/排序/分页/空列表/知识库不存在/越权/未认证/page_size=0/page_size>100
  - 详情（5 用例）：正常/文档不存在/知识库不存在/越权/未认证
  - 分块（5 用例）：正常/空数据/分页/文档不存在/未认证
  - 重新处理（5 用例）：正常/无效状态(E2010)/文档不存在/越权/未认证
  - 删除（5 用例）：正常(202)/已在删除中/文档不存在/越权/未认证

### 修改
- `docs/TEST_CASES.md` — v0.4→v0.5；§3.3 更新：A3.1-A3.19 全部标记 ✅ + 补充 A3.11-A3.19 扩展用例；§7 覆盖率表新增 `api/document.py` 行
- `docs/ROADMAP.md` — Phase 2 测试节：文档上传/删除 API 接口测试标记 ✅

### 测试结果
- 后端：143/143 全部通过（无回归，新增 47 用例）

## 2026-05-18 — Phase 2 文档上传 API 开发

### 新增
- `backend/app/api/document.py` — 7 个文档 API 端点：上传（POST multipart + force 覆盖）、批量上传（POST batch-upload 部分成功返回）、列表（GET 支持 status/filename 筛选 + sort_by/order 排序 + 分页）、详情（GET）、分块列表（GET 分页 + 预览截断）、删除（DELETE 标记 deleting → 202）、重新处理（POST 仅 partial_failed/failed 允许）
- `backend/app/services/document_service.py` — 文档业务服务完整实现：文件类型/大小校验、KB 所有权校验、同名文档检查（含 force 覆盖逻辑：终态允许覆盖 → 标记旧文档 deleting、处理中拒绝 E2011/E2012）、批量上传部分成功模式、Chunk metadata_ 属性名适配、Celery 任务分发入口预留 TODO
- `backend/app/core/storage.py` — 文件存储服务：`StorageBackend` 抽象基类（save/read/delete）+ `LocalStorage` 本地磁盘实现，目录结构 `uploads/{kb_id}/{doc_id}/{uuid}_{sanitized_filename}`，含安全文件名处理（移除路径分隔符/空字节/控制字符）

### 测试结果
- 后端：96/96 全部通过（无回归）

## 2026-05-18 — BM25 方案切换为 rank-bm25

### 修改
- `docs/ARCHITECTURE.md` — v0.4→v0.5；§1 技术选型关键词检索方案从「自定义 BM25」更新为 `rank-bm25 (BM25Okapi)`；§6 对比表同步更新；§7.2 完整重写选型理由：自定义 BM25 → rank-bm25，说明 tokenizer 参数支持中文分词及向量化性能优势；§9.3 风险描述从「IDF 计算偏差」更新为「IDF 静默衰减」
- `docs/ROADMAP.md` — Phase 2 BM25 关键词检索说明更新为 `rank-bm25 (BM25Okapi) + jieba 分词`
- `docs/DEVELOPMENT.md` — §5 注脚同步更新
- `backend/requirements.txt` — 加回 `rank-bm25==0.2.*`（此前于 2026-05-15 移除）

### 决策说明
- 此前认为 `rank-bm25`「基于空格分词，中文无分词能力」的判断不成立：库构造函数接受 `tokenizer` 参数，传入 `jieba.lcut` 后内部以多进程对语料分词，中文分词问题不存在
- 库仅 260 行单文件 + numpy 依赖，小且稳定；BM25 核心公式几十年未变，2022 年停止更新不构成弃用理由
- 自定义实现需重新处理 NumPy 向量化、IDF 负值 floor、batch_scores 等细节，造轮子性价比低

## 2026-05-17 — 代码审查问题修复 + 权限标注修正

### 修复
- `services/knowledge_base_service.py` — `get_kb` 新增可选 `user_id`/`role` 参数，传入时校验所有权（非 owner 且非 admin 拒绝访问，E5005）
- `api/knowledge_base.py` — `GET /{kb_id}` 传入 `current_user` 至 `get_kb`，修复详情接口缺少 owner 校验的安全漏洞
- `tests/test_kb_api.py` — 新增 `test_get_permission_denied` 用例，补齐 A2.8 越权访问测试
- `docs/ARCHITECTURE.md` — §7.2 移除 `rank-bm25` 过期待办描述（依赖已于 2026-05-15 移除）

### 修改
- `docs/ARCHITECTURE.md` — 文档元信息 v0.3→v0.4，日期 2026-05-14→2026-05-17
- `backend/docs/API.md` — v0.4→v0.7；§3 + §9 GET `/{id}` 权限修正为「所有者/admin」；§3 + §9 5 个文档子资源接口权限从 `user` 修正为 `user（所有者/admin）`（POST upload/batch-upload、GET documents 列表/详情、DELETE document）
- `backend/docs/DATABASE.md` — 文档元信息 v0.3→v0.4，日期 2026-05-14→2026-05-17
- `docs/TEST_CASES.md` — Phase 2 说明更新：标注 §3.1/§3.2 已补充详细用例并全部通过

### 测试结果
- 后端：96/96 全部通过（新增 1 个越权测试，无回归）

---

## 2026-05-17 — Phase 1 模型测试补齐（U4.1-U4.3）

### 新增
- `backend/tests/test_models.py` — 用户模型测试（U4.1 默认 role / U4.2 username 唯一约束 / U4.3 FK 关联验证），含 `dispose_engine_after` autouse fixture 解决 Windows pool 清理
- `backend/tests/conftest.py` — 新增 `db_session` fixture

### 修改
- `backend/pytest.ini` — 新增 `asyncio_default_fixture_loop_scope = session`，避免 Windows ProactorEventLoop 提前关闭导致连接池残留异常
- `docs/TESTING.md` v0.3→v0.4 — §3.1 修正：API 接口测试用 Mock session，模型层测试可直接连开发库 MySQL
- `docs/TEST_CASES.md` v0.3→v0.4 — U4.1-U4.3 状态 ⏭️→✅，models/ 覆盖率 ✅ 已覆盖
- `docs/DEVELOPMENT.md` v0.4→v0.5 — 项目结构 tests/ 节新增 `test_models.py`
- `CLAUDE.md` — 通用约束新增：新建文件须汇报用户、变更记录只能写入 `docs/CHANGE.md`

### 测试结果
- 后端：95/95 全部通过（新增 3 个模型测试，无回归）

---

## 2026-05-17 — Phase 2 文档状态枚举

### 新增
- `schemas/document.py` — 文档 Pydantic Schema（`DocumentResponse`、`DocumentUploadResponse`、`DocumentListResponse`、`DocumentDeleteResponse`、`DocumentReprocessResponse`、`DocumentBatchUploadResponse`、`DocumentChunkResponse`、`DocumentChunkListResponse`），status 字段统一使用 `DocumentStatus` 枚举
- `tests/test_schemas.py` — 新增 `DocumentStatus` 枚举（10 状态 + `TERMINAL_STATUSES` + `is_terminal()`）和 `DocumentResponse` Schema 校验测试（18 个用例）

### 修改
- `schemas/knowledge_base.py` — `KnowledgeBaseListData` → `KnowledgeBaseListResponse`，`KnowledgeBaseDeleteData` → `KnowledgeBaseDeleteResponse`，统一命名风格
- `schemas/__init__.py` — 导出全部文档 Schema
- `tests/test_knowledge_base.py` → `tests/test_kb_api.py` — 重命名对齐 DEVELOPMENT.md
- ROADMAP.md — 标记「文档状态枚举」+ 对应测试任务完成
- TEST_CASES.md — 新增文档状态枚举测试用例（U5.1-U5.12），Phase 2-3 用例 ID 全部顺延

### 测试结果
- 后端：92/92 全部通过（新增 18 个 Schema 测试，无回归）

---

## 2026-05-17 — Phase 2 KB CRUD 代码审查 + 修复

### 审查结论
- **审查范围**：`api/knowledge_base.py`, `models/knowledge_base.py`, `schemas/knowledge_base.py`, `services/knowledge_base_service.py`, 迁移脚本
- **原始问题**：2 项严重 + 3 项规范，18 项合规检查全部通过
- **已修复**：见下方「修复」节

### 修复
- `api/knowledge_base.py:50` 内联 `from app.schemas...` 移至模块顶部
- `API.md` §3 GET list 响应 items 示例补上 `user_id` 字段
- 编写 `tests/test_knowledge_base.py`（28 个用例）覆盖 KB CRUD 全部端点 + 错误码（E1001/E1002/E5005）+ 未认证 401 + 参数校验 422

### 新增 fixture
- `conftest.py`: `auth_headers` / `admin_auth_headers` / `other_user_auth_headers` 三个 fixture

### 测试结果
- 后端：72/72 全部通过（新增 28 个 KB CRUD 测试，无回归）
- 覆盖率：测试覆盖了所有 5 个 KB 端点（POST/GET/PUT/DELETE）的 7 类场景

---

## 2026-05-16 — Phase 2 知识库 CRUD 实现

### 新增
- 知识库 CRUD 接口（POST/GET/PUT/DELETE `/api/knowledge-bases`）
- `idx_user_name` 唯一索引（user_id, name），保证用户级知识库名称唯一
- `KnowledgeBaseCreate/Update/Response/ListData/DeleteData` Pydantic Schema
- `create_kb/get_kb/list_kbs/update_kb/delete_kb/check_kb_active` 服务层函数
- 同名冲突捕获 IntegrityError → E1002
- DELETE 仅标记 status=deleting + 返回 202，不做物理删除/ChromaDB 清理
- 列表分页返回 `{total, page, page_size, items}`
- 所有响应 data 中均包含 status 字段
- 权限校验：非 owner 且非 admin 拒绝修改/删除（E5005）
- `check_kb_active()` 供后续上传/检索/reprocess 调用

### 数据库迁移
| 迁移文件 | 版本链 | 变更 |
|:---|:---|:---|
| `687b64790b37_添加idx_user_name唯一索引.py` | `04b3e0425da8` → `687b64790b37` | `knowledge_bases` 添加 `idx_user_name (user_id, name)` 唯一索引 |

### 测试结果
- 后端：44/44 全部通过（无回归）
- API 手工验证：创建/列表/详情/更新/删除/同名冲突/权限拒绝 全部通过

---

## 2026-05-16 — 文档规范修复 + 代码合规修复

### 背景

对照 CLAUDE.md 强制约定和 API.md/UIdesign.md 规范，发现多处代码与文档不一致：模型字段缺少 `server_default`、前端组件硬编码颜色、LoginRequest 缺少最小长度校验、auth 响应 `code` 为整数而非字符串。同时修复了文档集自身的 19 项矛盾/缺失。

### 文档修改

| 文件 | 版本变更 | 主要变更 |
|:---|:---|:---|
| `backend/docs/API.md` | v0.3 → v0.4 | §1.2 成功响应 code 统一为字符串 `"0"`，删除过期注释；§1.3 E1xxx/E2xxx 间补空行；§3/§5/§7 补充 PUT KB、DELETE 会话、GET admin/documents 响应示例；§6 新增 SSE vs HTTP JSON 错误流程区分说明；§8.2 错误响应从旧嵌套格式改为扁平 `{code, message, detail}`；§9 删除分页/API 版本 TODO |
| `docs/ROADMAP.md` | v0.3 → v0.4 | 文件头版本/日期更新；§2.1 Phase 1 测试全部标记为 ✅ |
| `docs/TEST_CASES.md` | v0.1 → v0.2 | A3.x 文档 API 路径补全为 `/api/knowledge-bases/{kb_id}/documents/*`；A3.1 状态码 202→201；U3.5/A1.9 更新为 LoginRequest 有 min_length 的预期行为 |
| `docs/TESTING.md` | v0.2 → v0.3 | §5 子节编号 2.1/2.2 → 5.1/5.2 |
| `docs/DEVELOPMENT.md` | v0.3 → v0.4 | §5 移除 `rank-bm25==0.2.*`，替换为 `jieba==0.42.*`；§3.1 移除 `cp .env.example` 步骤 |
| `docs/CHANGE.md` | — | 错误码数量描述 20→31，子类计数同步更新 |
| `frontend/docs/UIDESIGN.md` | v0.3 → v0.4 | §4.6/§4.8 硬编码颜色全部替换为 `--dm-*` 变量；§1 新增 `--dm-primary-hover-light`、`--dm-logo-shadow` Token |
| `frontend/docs/FRONTEND.md` | v0.2 → v0.3 | §2.1 路由表补充 `/ → /chat` 重定向条目 |
| `README.md` | — | 末尾静态日期改为「见各文档元信息」 |

### 代码修改

| 文件 | 修改 |
|:---|:---|
| `backend/app/models/user.py` | `role` 字段新增 `server_default=text("'user'")` |
| `backend/app/models/document.py` | `status` 字段新增 `server_default=text("'uploaded'")` |
| `backend/app/models/conversation.py` | `title` 字段新增 `server_default=text("'新对话'")` |
| `backend/app/schemas/auth.py` | `LoginRequest` username 新增 `min_length=2`，password 新增 `min_length=6`，与 `RegisterRequest` 和 `FRONTEND.md §3.3` 对齐 |
| `backend/app/api/auth.py` | 注册/登录接口 `"code": 0` → `"code": "0"`，与 `API.md §1.2` 字符串格式统一 |
| `backend/requirements.txt` | 新增 `jieba==0.42.*` |
| `frontend/src/styles/global.css` | 新增 `--dm-primary-hover-light` 和 `--dm-logo-shadow` Design Token |
| `frontend/src/components/layout/Sidebar.vue` | L160 `#DDD6FE` → `var(--dm-primary-hover-light)` |
| `frontend/src/views/LoginPage.vue` | L167 硬编码 `box-shadow` → `var(--dm-logo-shadow)` |

### 数据库迁移

| 迁移文件 | 版本链 | 变更 |
|:---|:---|:---|
| `04b3e0425da8_补充user_role_document_status_.py` | `42097bdbd61a` → `04b3e0425da8` | `users.role` SET DEFAULT `'user'`；`documents.status` SET DEFAULT `'uploaded'`（幂等）；`conversations.title` SET DEFAULT `'新对话'` |

### 测试修改

| 文件 | 修改 |
|:---|:---|
| `backend/tests/test_schemas.py` | `test_empty_username_accepted` → `test_empty_username_rejected`，预期 `ValidationError` |
| `backend/tests/test_auth_api.py` | 空用户名测试预期 422 + E9003；错误密码测试改为 ≥6 字符；`code == 0` → `code == "0"` |

### 测试结果

- 后端：44/44 全部通过 ✅
- 前端：2 文件 23 测试全部通过 ✅

---

## 2026-05-15 — 测试体系补全：测试策略增强 + Phase 1 测试用例

### 背景

项目有 TESTING.md 但无实际测试文件。Phase 1 已完成但零测试覆盖，Phase 2 即将启动前补齐测试基础设施。

### 文档修改

| 文件 | 版本变更 | 主要变更 |
|:---|:---|:---|
| `docs/ROADMAP.md` | v0.3 → v0.4 | 每个 Phase 增加测试子章节 + Phase 1 待补测试项；§7 增加测试准入规则；关联 TEST_CASES.md |
| `docs/TESTING.md` | v0.1 → v0.2 | 测试体系从 4 层扩充为 6 层（新增单元测试、接口测试、前端组件测试）；§9 执行计划从 Phase 1 起始 |
| `docs/DEVELOPMENT.md` | v0.2 → v0.3 | §2 项目树加入 `backend/tests/` 和 `frontend/tests/` 完整目录结构；§5 加入 test 依赖；§7 加入测试命令 |
| `docs/TEST_CASES.md` | **新文件** | 测试用例跟踪文档：Phase 1-5 全部用例 ID + 状态 + 覆盖率目标，对应 6 层体系 |

### 代码新增

#### 后端测试 (`backend/tests/`)

| 文件 | 说明 |
|:---|:---|
| `__init__.py` | 包初始化 |
| `conftest.py` | pytest fixtures：`mock_db`（AsyncMock DB session）、`async_client`（FastAPI async HTTP client）+ ChromaDB init 全局 Mock |
| `test_security.py` | JWT & 密码哈希：10 个测试（hash/verify/token create/decode/edge cases） |
| `test_auth_service.py` | 认证 Service：7 个测试（注册正常/重复/强密码 + 登录正常/密码错/用户不存在/Token 非空格式） |
| `test_auth_api.py` | 认证 API：14 个测试（注册 6 + 登录 4 + 中间件 4），Mock service 层 |
| `test_schemas.py` | Pydantic Schema：10 个测试（RegisterRequest 5 + LoginRequest 3 + TokenResponse 3） |
| `pytest.ini` | pytest 配置（asyncio_mode=auto） |

#### 前端测试 (`frontend/tests/`)

| 文件 | 说明 |
|:---|:---|
| `setup.js` | 全局 Mock：Element Plus（ElMessage 等）、Font Awesome |
| `LoginPage.test.js` | 登录页：12 个测试（渲染 4 + 交互 2 + 校验 3 + 提交 3） |
| `AppLayout.test.js` | 布局：11 个测试（渲染 5 + 页面标题 5 + slot 1） |
| `vitest.config.js` | vitest 配置（jsdom + @ alias + vue 插件） |

#### 依赖更新

| 文件 | 变更 |
|:---|:---|
| `backend/requirements.txt` | 新增 `pytest==8.*`、`pytest-asyncio==0.24.*`、`pytest-cov==5.*` |
| `frontend/package.json` | 新增 devDeps：`vitest`、`@vue/test-utils`、`jsdom`；scripts 新增 `test`/`test:ui`/`test:watch` |

### 测试执行结果（2026-05-15）

| 套件 | 结果 | 说明 |
|:---|:---|:---|
| 后端 `pytest tests/ -v` | **44/44 通过** | 安全模块 10 + Schema 校验 10 + Service 7 + API 接口 14 + 中间件 3 |
| 前端 `vitest run` | **23/23 通过** | LoginPage 12 + AppLayout 11 |

### 统计

| 类别 | 数量 |
|:---|:---|
| 新增文档 | 1（TEST_CASES.md） |
| 修改文档 | 3（ROADMAP / TESTING / DEVELOPMENT） |
| 新增测试文件（后端） | 6 |
| 新增测试文件（前端） | 4 |
| 测试用例总数（Phase 1） | 67（后端 44 + 前端 23） |

---

## 2026-05-15 — 测试修复：Mock 适配 & Pydantic V2 兼容

### 背景

首轮测试 13 个失败，经三轮修复后全部通过。

### 发现与修复

| # | 问题 | 根因 | 修复方式 |
|:---|:---|:---|:---|
| 1 | Schema 校验 `min_length`/`max_length` 断言不匹配 | Pydantic V2 错误类型为 `string_too_short` / `string_too_long` | `test_schemas.py` 断言改为匹配 V2 类型名 |
| 2 | `LoginRequest(username="")` 预期抛异常但未抛 | `LoginRequest` 无 `min_length` 约束，空字符串合法 | 改为 `test_empty_username_accepted` |
| 3 | Service 测试 `'coroutine' object has no attribute 'password_hash'` | `_make_mock_result` 使用 `AsyncMock`，`scalar_one_or_none()` 返回协程而非值 | 改用 `MagicMock` 构造非异步返回值 |
| 4 | `UserResponse.model_validate(user)` 校验失败（id/role/created_at 为 None） | `mock_db.refresh` 未回填 DB 生成字段 | Mock `refresh.side_effect` 设置默认值 |
| 5 | `r1.access_token != r2.access_token` 断言失败 | 两次 `create_access_token` 调用间隔 < 1s，`exp` 相同导致 JWT 完全一致 | 改为 `test_login_token_not_empty`（验证 token 非空 + JWT 格式） |
| 6 | API 测试 `test_login_empty_username` 未 mock service | `LoginRequest` 允许空用户名，请求直达真实 service | 添加 `patch("app.api.auth.login")` mock |
| 7 | `test_options_preflight_skipped` 返回 404 | OPTIONS `/api/knowledge-bases` 路由不存在（仅骨架） | 预期状态码放宽为 `200/404/405` |
| 8 | 前端 `AppLayout` 全部 10 个失败：`useRoute.mockReturnValue is not a function` | `vi.mock` 工厂函数中 `useRoute` 不是 `vi.fn()`，无法动态改返回值 | 用 `vi.hoisted()` 包裹 `mockUseRoute = vi.fn()`，再传入 mock 工厂 |

### 修改文件

| 文件 | 说明 |
|:---|:---|
| `test_schemas.py` | 适配 Pydantic V2 错误类型；LoginRequest 测试用例调整 |
| `test_auth_service.py` | `_make_mock_result` 改用 `MagicMock`；`mock_db.refresh` 回填字段；移除 Token 不同断言 |
| `test_auth_api.py` | `test_login_empty_username` 补 mock；`test_options_preflight_skipped` 放宽预期；`test_public_route_skips_middleware` 改用 `/api/auth/login` |
| `test_cases.md` | 用例 U2.6 改为 `test_login_token_not_empty` |

---

## 2026-05-15 — 设计修正：KB/文档删除流程统一为物理删除（方案 B）

### 背景

审查发现 KB 删除流程存在设计矛盾：API.md §3 的 Celery 流程写了「批量删除 chunks / documents / kb 记录」，但紧接着标记 `status=deleted`——物理删除后行已不存在，无法 UPDATE。同时 `knowledge_bases.status` ENUM 包含 `'deleted'`，若行永不物理删除，`ON DELETE CASCADE` 外键将成为死代码。

### 决策：方案 B — Celery 异步物理删除 + FK CASCADE 兜底

**核心流程**（KB 级）：
```
DELETE /api/knowledge-bases/{id}
↓ kb.status = deleting → 返回 202
↓ Celery Worker:
  1. collection.delete(where={"kb_id": kb_id})   — ChromaDB
  2. 删除 uploads/{kb_id}/                           — 磁盘文件
  3. DELETE FROM knowledge_bases WHERE id=?          — MySQL 物理删除
     └─ FK CASCADE → documents → chunks（兜底）
```
**文档级同理**：`status = deleting` → Celery 清理 ChromaDB + 磁盘 → `DELETE FROM documents` → FK CASCADE 清 chunks。

### 修改的文件

| 文件 | 变更内容 |
|:---|:---|
| `API.md` | 移除 E1003 错误码；§3 KB 异步清理流程改为物理 DELETE + FK CASCADE；§4.0 DocumentStatus 移除 `DELETED`，TERMINAL_STATUSES 移除 `'deleted'`；§4 文档异步清理流程同步修正 |
| `DATABASE.md` | §2.2 `knowledge_bases.status` ENUM 移除 `'deleted'`；§2.3 `documents.status` ENUM 移除 `'deleted'`；DocumentStatus 枚举移除 `DELETED`；§4 外键说明改为物理删除为主、FK CASCADE 兜底 |
| `ARCHITECTURE.md` | §4.0 TERMINAL_STATUSES 移除 `deleted`；§7.1 KB 删除流程描述更新 |
| `FRONTEND.md` | §6.4 TERMINAL_STATUSES 常量移除 `'deleted'`；§6.5 状态标签映射移除 `deleted` 行 |
| `UIDESIGN.md` | §4.8 移除 `.status-tag.deleted` CSS 类；图标配对表移除 `deleted` 行 |
| `CHANGE.md` | 本文档 |

### 代码层面执行（2026-05-15 当天完成）

| # | 位置 | 修改内容 | 状态 |
|:---|:---|:---|:---|
| 1 | `requirements.txt` | 删除 `passlib[bcrypt]==1.7.*` + `rank-bm25==0.2.*` | ✅ |
| 2 | `config.py` | 新增 `CHROMA_BATCH_SIZE=100`、`EMBED_BATCH_SIZE=20`、`DEBUG_CHUNK_FULL=False` | ✅ |
| 3 | `core/exceptions.py` | 移除 `KnowledgeBaseDeleteFailedException(E1003)`；新增 E2006-E2013 共 8 个异常类 | ✅ |
| 4 | `models/enums.py` | **新文件**：`DocumentStatus(str, Enum)` 10 值 + `TERMINAL_STATUSES` + `is_terminal()` | ✅ |
| 5 | `models/document.py` | status ENUM 从 8 值改为 10 值（`uploading→uploaded`、`indexing→vector_storing`，新增 `success_with_warnings`/`partial_failed`/`deleting`，移除 `deleted`）；新增 `file_path`/`current_stage`/`last_success_batch` 字段；新增 `idx_kb_filename` 复合索引 | ✅ |
| 6 | `models/knowledge_base.py` | 新增 `status` 字段 `Enum('active','deleting')` | ✅ |
| 7 | `models/__init__.py` | 导出 `DocumentStatus`、`TERMINAL_STATUSES`、`is_terminal` | ✅ |
| 8 | `api/knowledge_base.py` | 路由骨架（`prefix="/api/knowledge-bases"`） | ✅ |
| 9 | `api/document.py` | 路由骨架（`prefix="/api/knowledge-bases"`） | ✅ |
| 10 | `main.py` | 注册 `kb_router` + `doc_router` | ✅ |
| 11 | `alembic/versions/42097bdbd61a` | 新迁移：documents ENUM 值重命名 + 新增值（含旧数据 UPDATE 适配）+ knowledge_bases.status 新增；已执行 `upgrade head` | ✅ |

### 代码层面仍待处理（Phase 2 实施时）

| # | 位置 | 修改内容 | 优先级 |
|:---|:---|:---|:---|
| 12 | `schemas/` | 创建/更新 Pydantic schema 对齐新枚举和字段 | P1 |
| 13 | `services/` | 实现 KB/文档 CRUD service，使用新的 `DocumentStatus` 枚举 | P1 |
| 14 | `api/knowledge_base.py` | 实现具体端点 | P1 |
| 15 | `api/document.py` | 实现具体端点 | P1 |
| 16 | `ingest/celery_tasks.py` | KB/文档删除任务末尾物理 DELETE（非 UPDATE status） | P0 |
| 17 | `frontend/` | TERMINAL_STATUSES 常量 + 状态标签映射同步 | P1 |

### 关键决策索引（追加）

| # | 决策 | 文档位置 |
|:---|:---|:---|
| 12 | KB/文档删除采用物理删除 + FK CASCADE 兜底，不保留软删除状态 | API.md §3, DATABASE.md §4 |

---

## 2026-05-15 — 响应格式补全：所有成功响应统一 `{code, message, data}`

### 背景

API.md §1.2 已约定「所有成功响应必须包含 `code`、`message`、`data` 三个字段。当前部分接口仅返回 `{code, data}`，Phase 2 起统一补齐 `message` 字段」。经审查发现 7 处接口的成功响应缺少 `message`，本次统一补齐。

### 文档修改（API.md）

| # | 接口 | 补全值 |
|:---|:---|:---|
| 1 | POST `/api/auth/register` | `"message": "注册成功"` |
| 2 | POST `/api/auth/login` | `"message": "登录成功"` |
| 3 | POST `/api/knowledge-bases` | `"message": "知识库创建成功"` |
| 4 | GET `/api/knowledge-bases` | `"message": "ok"` |
| 5 | GET `/api/knowledge-bases/{id}` | 继承创建响应结构（自动补全） |
| 6 | POST `/api/conversations` | `"message": "会话创建成功"` |
| 7 | GET `/api/conversations/{id}` | `"message": "ok"` |
| 8 | GET `/api/admin/stats` | `"message": "ok"` |

### 代码修改（Phase 1 已实现接口）

| 文件 | 变更 |
|:---|:---|
| `api/auth.py` | `register` 返回中加入 `"message": "注册成功"`；`login` 返回中加入 `"message": "登录成功"` |

> 其余接口代码尚未实现，Phase 2 实现时按文档直接输出三字段格式。

---

## 2026-05-14 — Phase 2 前置准备：文档全面补全

### 背景

Phase 1 代码骨架完成，Phase 2 启动前对齐全部设计决策，补全所有文档中遗漏的技术细节。

### 修改的文件

| 文件 | 版本变更 | 主要补全内容 |
|:---|:---|:---|
| `API.md` | v0.2 → v0.3 | E2006-E2013 错误码、文档状态枚举(11值)、reprocess/batch-upload 接口、force 覆盖流程、DELETE KB 异步清理、chunks 分页、Refresh Token Phase 5 TODO |
| `DATABASE.md` | v0.2 → v0.3 | `documents.status` 枚举改为 11 值 + `DocumentStatus(str,Enum)` 定义、新增 `file_path`/`current_stage`/`last_success_batch` 字段、`knowledge_bases` 新增 `status` 字段、`idx_kb_filename` 复合索引 |
| `ARCHITECTURE.md` | v0.2 → v0.3 | §4 文档入库流程完整重写（状态机、幂等锁、批量写入、批次 checkpoint、解析容错分级、chunk_count 事务更新）、§7.1 KB 删除 metadata filter 流程、§7.2 标注 rank-bm25 移除、§7.5 文件路径更新 |
| `ROADMAP.md` | v0.2 → v0.3 | §3 Phase 2 拆分为 3 个子阶段（后端CRUD 7 项 / Celery流水线 7 项 / 前端 5 项）+ 明确不做的 5 项推迟、§6 Refresh Token 细化 |
| `FRONTEND.md` | v0.1 → v0.2 | §6 文档管理页扩写（上传交互、同名冲突、轮询策略、11 状态标签映射、上传进度、空状态、分块预览）、§11 已知 TODO 更新为 Phase 分阶段 |
| `UIDESIGN.md` | v0.2 → v0.3 | §4.8 状态标签从 4 种扩展至 11 种 + 图标配对表 |
| `CHANGE.md` | — | 本文档 |

### 关键决策索引

| # | 决策 | 文档位置 |
|:---|:---|:---|
| 1 | 文档状态机：11 状态 + `TERMINAL_STATUSES` + `is_terminal()` | API.md §4.0, DATABASE.md §2.3 |
| 2 | Celery 幂等键：`{doc_id}:{task_type}` + Redis 分布式锁 TTL=600s | ARCHITECTURE.md §4.5 |
| 3 | ChromaDB batch 写入失败清理策略 | ARCHITECTURE.md §4.3 |
| 4 | 文档唯一性：`(kb_id, filename)` 检查 + `force=true` 覆盖 | API.md §4, ARCHITECTURE.md §4.1 |
| 5 | 分块策略：RecursiveCharacterTextSplitter（800-1200 chars） | ARCHITECTURE.md §4.2 |
| 6 | 文件路径：`uploads/{kb_id}/{doc_id}/{uuid}_{sanitized_filename}` | ARCHITECTURE.md §7.5, DATABASE.md §2.3 |
| 7 | KB 删除：单 Collection metadata filter 异步批量清理 | API.md §3, ARCHITECTURE.md §7.1 |
| 8 | 解析容错分级：<20% warning / 20-50% partial / >50% failed | ARCHITECTURE.md §4.7 |
| 9 | 状态轮询：2s 间隔 / 终态停止 / 5 分钟超时 | FRONTEND.md §6.4 |
| 10 | Embedding 批量：batch_size=20 + 5 次指数退避重试 + 批次 checkpoint | ARCHITECTURE.md §4.4 |
| 11 | 不支持 .doc 格式 | ROADMAP.md §3.4 |

### 未改动代码

本次仅修正文档，不涉及代码变更。已知待修 Bug（migration `server_default` 字符串字面量、`rank-bm25` 残留依赖）在 Phase 2 实现时一并修复。

---

## 2026-05-13 — Phase 1 交互补漏：登录/退出反馈 + 用户栏行为修正

### 文档补充（FRONTEND.md）

| 位置 | 补充内容 |
|:---|:---|
| §3.2 登录流程 | 成功步骤增加 `ElMessage.success('登录成功')` 反馈 |
| §4.1 页面布局 | Sidebar 底部区域描述细化：头像点击→个人资料（预留）、退出按钮→提示+跳转 |
| §4.5.1 用户栏行为（新增） | 用户栏交互行为表：头像预留 / 退出图标 → toast + 跳转 |
| §8.2 表单反馈 | 新增「退出登录」「登录成功」两行交互规范 |

### 修复

| 问题 | 修复前 | 修复后 |
|:---|:---|:---|
| 点击头像区域也退出登录 | `@click="handleLogout"` 挂在 `.user-bar` 容器上 | 仅退出图标按钮绑定 `@click.stop`，头像/用户名区域无操作（预留个人资料入口） |
| 退出登录无反馈 | 静默跳转 `/login` | `ElMessage.success('已退出登录')` → 跳转 |
| 登录成功无反馈 | 静默跳转 `/chat` | `ElMessage.success('登录成功')` → 跳转 |

### 修改文件

| 文件 | 说明 |
|:---|:---|
| `frontend/src/components/layout/Sidebar.vue` | 移除 `.user-bar` 退出点击，仅退出图标触发；新增 `ElMessage` 退出反馈 |
| `frontend/src/views/LoginPage.vue` | 新增 `ElMessage.success('登录成功')` |

---

## 2026-05-13 — Phase 1 收尾：前端布局框架（AppLayout + Sidebar）

### 新增

| 文件 | 说明 |
|:---|:---|
| `frontend/src/components/layout/Sidebar.vue` | 侧边栏组件：Logo + 新建对话按钮 + 会话列表空态 + 管理导航（admin可见）+ 用户信息栏 + 退出登录 |
| `frontend/src/components/layout/AppLayout.vue` | 布局容器：左侧 Sidebar + 右侧主内容区（顶部 header + `<slot />`） |

### 修改

| 文件 | 说明 |
|:---|:---|
| `frontend/src/App.vue` | 路由感知布局切换：公开页面（login）独立渲染，认证页面包裹 AppLayout |

### 组件结构

```
App.vue
├── /login → LoginPage（独立渲染，全屏渐变背景）
└── 其他路由 → AppLayout
                ├── Sidebar（280px）
                │   ├── 顶部：Logo（DocMind）+ 新建对话按钮
                │   ├── 中间：会话列表空态 + 管理导航（admin）
                │   └── 底部：用户头像/用户名/角色 + 退出按钮
                └── 主内容区
                    ├── Top Header（页面标题）
                    └── <slot />（router-view 页面内容）
```

### Phase 1 完成状态

| 任务 | 状态 |
|:---|:---|
| 项目初始化 | ✅ |
| 前端环境搭建 | ✅ |
| Git 初始化 | ✅ |
| MySQL 表建好 | ✅ |
| ChromaDB 连接 | ✅ |
| JWT 认证 | ✅ |
| 前端登录页 | ✅ |
| 前端布局框架 | ✅ |

Phase 1 骨架搭建全部完成，可进入 Phase 2 文档入库开发。

---

## 2026-05-13 — 错误响应格式统一（AppException 去嵌套）

### 修复

`AppException` 继承 `HTTPException`，FastAPI 默认 handler 会将其 `detail` dict 再包一层 `{"detail": {...}}`，而 `AuthMiddleware` 直接构造 `JSONResponse` 返回扁平格式 `{code, message, detail}`，导致前后端错误响应格式不统一。

- **`backend/app/main.py`** — 新增 `@app.exception_handler(AppException)`，直接返回 `JSONResponse` 扁平格式，与中间件响应一致
- **`frontend/src/views/LoginPage.vue`** — 错误处理从双路径兼容（`data.detail.message` / `data.message`）简化为单一路径 `data?.message`

### 影响

此后所有 `AppException` 子类（31 个错误码）抛出的错误响应均为扁平格式 `{"code":"Exxxx","message":"...","detail":"..."}`，与 `AuthMiddleware`、`RequestValidationError` handler、通用 `Exception` handler 保持一致。

---

## 2026-05-13 — Phase 1: 前端登录页交互修复

### 修复

根据 FRONTEND.md §3.2 交互流程、§3.3 表单校验规则及 §8.2 表单反馈规范，修正 LoginPage.vue 三处问题：

| 问题 | 修复前 | 修复后 |
|:---|:---|:---|
| Tab 切换不清空表单 | `switchMode` 仅重置 `errorMsg` | 同时清空 `username`、`password`、`errorMsg` |
| 用户名长度校验缺失 | 仅校验非空 | 新增 `length ≥ 2` 校验，提示「用户名至少 2 个字符」 |
| 注册成功无反馈 | 静默切换至登录模式 | `ElMessage.success('注册成功，请登录')` |

### 修改

- **`frontend/src/views/LoginPage.vue`** — 上述 3 处修复，并新增 `import { ElMessage } from 'element-plus'`

---

## 2026-05-13 — Phase 1: 前端登录页 + 路由 + 全局样式

### 新增

| 文件 | 说明 |
|:---|:---|
| `frontend/src/styles/global.css` | 全局 CSS 变量（Design Token）+ 重置样式 + 组件基础样式，严格对齐 UIDESIGN.md §1-2 |
| `frontend/src/views/LoginPage.vue` | 登录/注册页，含渐变背景、Logo、Tab 切换、表单验证、错误提示，样式对齐 UIDESIGN.md |
| `frontend/src/router/index.js` | Vue Router 配置，含路由守卫（公开/认证/管理员三级权限），懒加载页面 |
| `frontend/src/stores/auth.js` | Pinia 认证状态管理（login/register/logout），JWT 解析 + localStorage 持久化 |
| `frontend/src/api/index.js` | Axios 实例 + 请求拦截器（Bearer Token）+ 响应拦截器（401 跳转登录页） |
| `frontend/src/api/auth.js` | 认证 API 封装（register/login） |

### 修改

| 文件 | 说明 |
|:---|:---|
| `frontend/index.html` | 添加 Font Awesome 6.5.1 CDN 链接 |
| `frontend/src/main.js` | 导入 `global.css` |
| `frontend/vite.config.js` | 添加 `@` 路径别名（→ `./src`） |
| `frontend/src/views/admin/*.vue` | 填充占位 `<template>`，修复空文件导致构建失败 |
| `frontend/src/views/ChatPage.vue` | 同上，填充占位内容 |

### 路由设计

| 路径 | 页面 | 权限 |
|:---|:---|:---|
| `/login` | LoginPage | 公开（已登录自动跳转 `/chat`） |
| `/chat` | ChatPage | 需登录 |
| `/admin/documents` | DocumentList | 需管理员 |
| `/admin/conversations` | ConversationList | 需管理员 |
| `/admin/knowledge` | KnowledgeList | 需管理员 |
| `/` | — | 重定向 `/chat` |

### 数据流

```
LoginPage → authStore.login() → api/auth.js POST /api/auth/login
           → 解析 JWT payload → localStorage 持久化 → router.push('/chat')

LoginPage → authStore.register() → api/auth.js POST /api/auth/register
           → 注册成功 → 切换至登录模式
```

---

## 2026-05-12 — Phase 1 代码规范修正 & 模型外键补齐

### 修改

- **相对导入 → 绝对导入** — `core/database.py`、`core/chroma_client.py`、`main.py`、`models/__init__.py` 全部改为 `from app.xxx` 绝对路径
- **`core/security.py`** — `datetime.utcnow()` → `datetime.now(timezone.utc)`，避免弃用 API
- **`middleware/auth_middleware.py`** — `int(payload.get("sub"))` 增加 `KeyError/ValueError/TypeError` 异常防护，返回 401 而非 500
- **`middleware/auth_middleware.py`** — 移除 `_PUBLIC_PATHS` 中 `/docs`、`/openapi.json` 的重复 `startswith` 判断（`in` 集合 + `startswith` 提取为 `_is_public()` 函数）
- **`main.py`** — 注册全局异常处理器：`RequestValidationError`（422 → E9003）+ `Exception`（500 → E9001），统一响应格式 `{code, message, detail}`

### 新增

- **6 张模型表补充 `sa.ForeignKey(...)`** — 对齐 DATABASE.md §4 外键策略，全部 7 条外键约束：
  | 字段 | 引用 | ondelete |
  |:---|:---|:---|
  | `knowledge_bases.user_id` | `users.id` | RESTRICT |
  | `documents.kb_id` | `knowledge_bases.id` | CASCADE |
  | `chunks.doc_id` | `documents.id` | CASCADE |
  | `chunks.kb_id` | `knowledge_bases.id` | CASCADE |
  | `conversations.user_id` | `users.id` | CASCADE |
  | `conversations.kb_id` | `knowledge_bases.id` | SET NULL |
  | `messages.conversation_id` | `conversations.id` | CASCADE |

- **6 张模型表补充 `relationship`** — User ↔ KB ↔ Document ↔ Chunk / User ↔ Conversation ↔ Message 双向关联
- **`server_default=sa.text('0')`** — `chunk_count`（KB/Document）、`doc_count`（KB）、`token_count`（Chunk/Message）、`message_count`（Conversation）添加 DB 层默认值

### 数据库迁移

- **`252a79df66dd`** — 添加 7 条外键约束 + 6 列 server_default 修改，已执行 `alembic upgrade head`

---

## 2026-05-12 — Phase 1: JWT 认证（注册/登录 + 中间件 + 异常类）

### 新增

- **`core/exceptions.py`** — 统一异常类体系，覆盖 API.md §1.3 全部 31 个错误码
  - E1xxx 知识库（2）、E2xxx 文档（13）、E3xxx 会话（2）、E4xxx 问答（5）、E5xxx 认证（5）、E9xxx 系统（4）
  - 基类 `AppException(HTTPException)` 携带统一响应格式 `{code, error: {code, message, detail}}`
- **`core/security.py`** — JWT + 密码哈希（bcrypt 直调，未使用 passlib 以避免兼容性问题）
  - `hash_password` / `verify_password` / `create_access_token` / `decode_access_token`
- **`schemas/auth.py`** — RegisterRequest / LoginRequest / UserResponse / TokenResponse
- **`services/auth_service.py`** — register（查重+创建） / login（验证+签发 token）
- **`api/auth.py`** — POST /api/auth/register + POST /api/auth/login
- **`middleware/auth_middleware.py`** — 纯 ASGI 中间件，从 Authorization Bearer 提取 JWT，验证后写入 request.state；OPTIONS 放行；公开路由白名单
- **`dependencies.py`** — 新增 `get_current_user(request)` 从 request.state 读取已认证用户
- **`main.py`** — 注册 AuthMiddleware + auth_router

### 修改

- **`requirements.txt`** — 新增 `bcrypt==4.0.*`（pin 版本兼容 passlib 替代方案）

### 验证

| 场景 | 结果 |
|:---|:---|
| 注册 | 201 Created，返回用户信息 |
| 登录 | 200 OK，返回 access_token（HS256，24h）+ expires_in |
| 重复注册 | 409 Conflict，E5001「用户名已存在」 |
| 密码错误 | 401 Unauthorized，E5002「用户名或密码错误」 |
| 无 Token | 401 Unauthorized，E5004「Token 无效或格式错误」 |
| 有效 Token | 中间件放行，进入路由（返回 404 因路由未实现） |

### 修复

- **错误响应格式** — 外层 `"code": 0` 改为实际错误码（如 `"code": "E5001"`），去掉嵌套的 `error` 包裹层
  - `API.md` §1.2 — 错误响应示例从 `{code: 0, error: {code: "E1001", ...}}` 改为 `{code: "E1001", message: "...", detail: "..."}`
  - `core/exceptions.py` — `AppException` 响应体同步改为扁平结构
  - `middleware/auth_middleware.py` — 两处 `JSONResponse` 同步修正

---

## 2026-05-12 — Phase 1: ChromaDB 连接 & collection 创建

### 新增

- **`core/chroma_client.py`** — ChromaDB PersistentClient 连接管理
  - `init_chroma()` — 初始化 PersistentClient，获取或创建 `docmind` collection
  - `get_collection()` / `get_client()` — 获取全局单例
  - Collection 使用 `hnsw:space=cosine` 余弦相似度
  - 持久化目录：`CHROMA_PERSIST_DIR`（.env 配置，默认 `./chroma_data`）
- **`main.py`** — lifespan 启动时调用 `init_chroma()` 初始化 ChromaDB

### 验证

- Collection `docmind` 创建成功，count = 0
- `chroma.sqlite3` 持久化文件生成在 `backend/chroma_data/`
- FastAPI 启动正常，`/api/health` 返回 200

---

## 2026-05-11 — 设计文档更新: Embedding 方案切换为 DashScope

### 修改

- **CLAUDE.md** — 技术栈行: `text-embedding-3-small` → `DashScope text-embedding-v3`，LLM 标注为 DeepSeek
- **DESIGN.md §2** — 技术选型表 Embedding 行: `OpenAI text-embedding-3-small / 1536维` → `DashScope text-embedding-v3 / 1024维，中文优化`
- **DESIGN.md §9** — .env 模板 Embedding 段: URL 改为 `dashscope.aliyuncs.com/api/v1`，MODEL 改为 `text-embedding-v3`

---

## 2026-05-11 — Phase 1: 数据库连接 & ORM 模型 & Alembic 迁移

### 操作概述

按照 `DESIGN.md` §4 表结构和 §6 项目结构，完成 MySQL 数据库连接配置、全部 6 张表的 SQLAlchemy 模型、Alembic 异步迁移环境和首次迁移脚本。

### 环境变量配置

- **`.env`** — 从项目根目录移至 `backend/.env`，pydantic-settings 自动从 CWD 读取
- **`config.py`** — `Settings(BaseSettings)` 声明全部字段，`.env` 变量自动映射覆盖默认值，提供 `mysql_url` 计算属性拼接异步连接串

### 数据库连接 (`core/database.py`)

- `engine` — `create_async_engine(settings.mysql_url, pool_size=10, max_overflow=20)`
- `async_session` — `async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)`
- `Base` — `DeclarativeBase` 所有 ORM 模型基类

### SQLAlchemy 模型（6 张表，对齐 DESIGN.md §4.2）

| 模型 | 表名 | 关键字段 |
|---|---|---|
| `User` | `users` | id, username(unique), password_hash, role(Enum: user/admin), created_at, updated_at |
| `KnowledgeBase` | `knowledge_bases` | id, name, description, user_id, chunk_count, doc_count, created_at, updated_at |
| `Document` | `documents` | id, kb_id(索引), filename, file_type, file_size, status(Enum: uploading→failed), chunk_count, error_msg, created_at, updated_at |
| `Chunk` | `chunks` | id, doc_id(索引), kb_id(索引), chroma_id, content, chunk_index, token_count, metadata(JSON), created_at |
| `Conversation` | `conversations` | id, user_id(索引), kb_id, title, message_count, created_at, updated_at |
| `Message` | `messages` | id, conversation_id(索引), role(Enum: user/assistant/system), content, thinking_content, token_count, feedback(Enum: like/dislike), created_at |

- 全部使用 SQLAlchemy 2.0 Mapped 类型注解写法
- Enum 使用 SQL 原生 ENUM 类型
- `created_at` 使用 `server_default=func.current_timestamp()`
- `updated_at` 额外设置 `onupdate=func.current_timestamp()`
- `models/__init__.py` 导入全部模型供 Alembic 发现

### 依赖注入 (`dependencies.py`)

- `get_db()` — `AsyncGenerator[AsyncSession]`，每次请求获取独立 session，成功自动 commit，异常自动 rollback

### Alembic 异步迁移环境

- **`alembic.ini`** — 基本配置（URL 由 env.py 运行时从 config.py 读取，避免硬编码）
- **`alembic/env.py`** — 异步引擎 + 自动发现模型，支持 offline（生成 SQL）和 online（直连 DB）两种模式
- **首次迁移** — `alembic/versions/7588fa83e017_初始化建表.py`，包含全部 6 张表的 DDL（用户手动执行 `alembic upgrade head` 成功）
- 注意：`alembic revision --autogenerate` 因 aiomysql 连接在事件循环关闭后清理报错（`RuntimeError: Event loop is closed`），迁移脚本已生成但需手动执行 upgrade

### FastAPI 入口 (`main.py`)

- `lifespan` 上下文管理器（当前为空，后续注册资源初始化）
- CORS 中间件（开发阶段允许 localhost:5173）
- `/api/health` 健康检查路由

### 版本修正

- **`requirements.txt`** — 版本号对齐 DESIGN.md §10（fastapi 0.115, uvicorn 0.32, aiomysql 0.2, python-jose 3.3, celery 5.4, alembic 1.14 等）

### 修复

- **`dependencies.py`** — 导入路径 `from core.database` → `from app.core.database`（绝对导入）
- **`main.py`** — 导入路径 `from config` → `from app.config`（绝对导入）

### 验证

- `.env` 配置正确加载（DeepSeek + DashScope 凭证）
- 6 个模型全部导入成功，表结构打印验证通过
- Alembic `--autogenerate` 检测到 6 张表 + 4 个索引，生成迁移脚本后由用户手动 `alembic upgrade head` 完成建表

### 统计

| 操作 | 数量 |
|:---|:---|
| 新增/重写文件 | 13 |
| 模型 | 6 张表 |
| 迁移脚本 | 1 |

### 后续步骤（按 DESIGN.md Phase 1）

- [x] MySQL 表建好（SQLAlchemy models） ✅
- [ ] ChromaDB 连接 & collection 管理
- [ ] JWT 认证（注册/登录）
- [ ] 前端登录页 + 路由骨架

---

## 2026-05-10 — Phase 1: 脚手架提交 & 分支拆分

### 操作概述

提交全部脚手架文件到 main，并创建前后端独立开发分支。

### 操作记录

```
git add .gitignore CHANGE.md DESIGN.md backend/ frontend/
git commit -m "feat: project scaffold — FastAPI backend + Vue3 frontend"
git push origin main

git branch dev-backend
git branch dev-frontend
git push origin dev-backend dev-frontend
```

### 提交详情

- Commit: `90993f7`
- 文件数: 83 files changed
- 内容: 后端 50 + 前端 26 + 根目录 7 个文件

### 分支策略

```
main          ← 稳定主分支（受保护）
├── dev-backend   ← 后端开发分支
└── dev-frontend  ← 前端开发分支
```

### 后续步骤（按 DESIGN.md Phase 1）

- [ ] MySQL 表建好（SQLAlchemy models）
- [ ] ChromaDB 连接 & collection 管理
- [ ] JWT 认证（注册/登录）
- [ ] 前端登录页 + 路由骨架

---

## 2026-05-10 — Phase 1: 前端环境搭建

### 操作概述

根据用户确认的技术选型补充 DESIGN.md 前端章节，随后搭建前端运行环境并验证。

### DESIGN.md 更新

**§2 技术选型** — 前端行拆分为明细条目：
- 前端框架 → Vue 3 + Vite
- UI 组件库 → Element Plus
- 状态管理 → Pinia
- 路由 → Vue Router 4
- HTTP 客户端 → Axios
- Markdown 渲染 → markdown-it
- 包管理器 → npm
- 前端语言 → JavaScript（非 TypeScript）

**§6 项目结构** — 所有 `.ts` 扩展名改为 `.js`

**§10.1** — 新增前端 npm 依赖清单

### 文件变更

**重命名（12 个）：**
- `src/api/*.ts` → `src/api/*.js`（5 个文件）
- `src/stores/*.ts` → `src/stores/*.js`（3 个文件）
- `src/router/index.ts` → `src/router/index.js`
- `src/utils/*.ts` → `src/utils/*.js`（2 个文件）
- `vite.config.ts` → `vite.config.js`

**新创建（3 个）：**
- `package.json` — npm 依赖声明（vue 3.5, element-plus 2.9, pinia 2.3, vue-router 4.5, axios 1.7, markdown-it 14.1, vite 6, @vitejs/plugin-vue 5.2）
- `vite.config.js` — Vite 配置（Vue 插件 + `/api` 代理到 localhost:8000）
- `index.html` — 入口 HTML（zh-CN, 挂载 #app）

**新增 bootstrap 文件（2 个，环境必需）：**
- `src/main.js` — Vue 应用入口（createApp + Pinia + Router + ElementPlus）
- `src/App.vue` — 根组件（仅 `<router-view />`）

### npm 依赖安装

```
npm install → 89 packages added
```

已安装核心包：vue, vue-router, pinia, element-plus, axios, markdown-it, @vitejs/plugin-vue, vite

### 验证

- Vite 开发服务器正常启动（端口 5173）
- HTTP 200 响应正常

### 统计

| 操作 | 数量 |
|:---|:---|
| DESIGN.md 更新 | 3 处（§2, §6, §10.1） |
| 文件重命名 | 12 |
| 新创建文件 | 5 |
| npm 包安装 | 89 |

### 后续步骤（按 DESIGN.md Phase 1）

- [ ] MySQL 表建好（SQLAlchemy models）
- [ ] ChromaDB 连接 & collection 管理
- [ ] JWT 认证（注册/登录）
- [ ] 前端登录页 + 路由骨架

---

## 2026-05-10 — Phase 1: Git 版本控制初始化

### 操作概述

建立 Git 仓库并推送至 GitHub 远程仓库。

### 操作记录

```
echo "# docmind" > README.md        # 创建项目 README
git init                            # 初始化 Git 仓库
git add README.md                   # 暂存 README
git commit -m "first commit"        # 首次提交（仅 README.md）
git branch -M main                  # 默认分支 master → main
git remote add origin \
  https://github.com/zhenyu-39/docmind.git
git push -u origin main             # 推送至远程
```

### .gitignore 补充

在 Git 初始化前，根据前端环境（Vite + Vue）补充了 `.gitignore` 规则：
- `*.local` — Vite 本地环境变量文件
- `.vite/` — Vite 开发服务器缓存
- `frontend/dist/` — 生产构建产物

### 当前状态

- 远程仓库: `https://github.com/zhenyu-39/docmind.git`
- 默认分支: `main`
- 首次提交: `568de74` (仅 README.md)
- 待提交: `.gitignore`, `DESIGN.md`, `CHANGE.md`, `backend/`, `frontend/`（脚手架文件）

---

## 2026-05-10 — Phase 1: 项目初始化（目录脚手架）

### 操作概述

严格按照 `DESIGN.md` §6 项目结构定义，创建完整的目录脚手架和空占位文件。**所有文件均为空占位文件，未写入任何实现代码。**

### 后端目录 (`backend/`)

**目录创建：**
- `backend/app/` — FastAPI 应用根目录
- `backend/app/api/` — API 路由层（7 个占位文件）
- `backend/app/models/` — SQLAlchemy 数据模型（7 个占位文件）
- `backend/app/schemas/` — Pydantic 请求/响应模型（6 个占位文件）
- `backend/app/services/` — 业务逻辑层（6 个占位文件）
- `backend/app/rag/` — RAG 核心模块（8 个占位文件）
- `backend/app/ingest/` — 文档入库任务模块（3 个占位文件）
- `backend/app/core/` — 基础设施层（7 个占位文件）
- `backend/app/middleware/` — 中间件（2 个占位文件）
- `backend/knowledge_samples/` — 示例知识库文档目录（空）
- `backend/alembic/` — 数据库迁移目录（空）

**根级文件：**
- `backend/requirements.txt` — 依赖清单（空）
- `backend/alembic.ini` — Alembic 配置（空）

### 前端目录 (`frontend/`)

**目录创建：**
- `frontend/src/views/` — 页面组件（3 个占位文件）
- `frontend/src/views/admin/` — 管理后台页面（3 个占位文件）
- `frontend/src/components/chat/` — 聊天相关组件（4 个占位文件）
- `frontend/src/components/layout/` — 布局组件（2 个占位文件）
- `frontend/src/stores/` — Pinia 状态管理（3 个占位文件）
- `frontend/src/api/` — HTTP 请求封装（5 个占位文件）
- `frontend/src/router/` — 路由配置（1 个占位文件）
- `frontend/src/utils/` — 工具函数（2 个占位文件）

**根级文件：**
- `frontend/index.html` — 入口 HTML（空）
- `frontend/package.json` — 依赖清单（空）
- `frontend/vite.config.ts` — Vite 配置（空）

### 项目根目录

- `.gitignore` — Git 忽略规则（已配置 Python / Node / IDE / 环境变量等规则）

### 统计

| 类别 | 数量 |
|:---|:---|
| 后端目录 | 10 |
| 后端占位文件 | 50 |
| 前端目录 | 9 |
| 前端占位文件 | 26 |
| 根目录文件 | 1 (.gitignore) |
| **总计新增** | **96 项** |

### 后续步骤（按 DESIGN.md Phase 1）

- [ ] MySQL 表建好（SQLAlchemy models）
- [ ] ChromaDB 连接 & collection 管理
- [ ] JWT 认证（注册/登录）
- [ ] 前端登录页 + 路由骨架
