# Changelog

DocMind 项目所有重要变更。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/)。

设计决策详见 [`docs/decisions/`](docs/decisions/)。

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
