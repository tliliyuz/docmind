# ROADMAP — 开发排期

| 属性 | 值          |
|:---|:-----------|
| 文档版本 | v1.1 |
| 最后更新 | 2026-06-23 |

> **编号规范**
>
> 本章子节编号格式为 `{章节号}.{序号}`，全部两级，序号连续。每个 Phase 内按「功能 → 测试 → 🚫 推迟项 → 索引」固定顺序排列。
>
> 每个子节标题标注 `[角色]` 标签，角色包括：后端 / 前端 / 数据库 / 测试 / 文档 / 运维 / 体验完善 / 管理后台 / 基础设施 / 高级功能。
>
> 🚫 推迟项统一编号，放在 `[测试]` 之后、`[索引]` 之前。


---

## 1. 总体时间线

**预计总工期**：4-6 周（120-180 小时）

```
Phase 1          Phase 2          Phase 3          Phase 4              Phase 5      Phase 5.5           Phase 6
骨架搭建         文档入库          核心问答          会话 & 记忆           打磨上线     知识库质量治理       迭代优化
3-4天            3-4天            3-4天            + 基础设施加固         3-4天       1-2天              不设时限
                  ▲                ▲               4-5天
  ├────────────────┼────────────────┼────────────────┼──────────────────┼──────┼────┤
Week 1            Week 2           Week 2-3         Week 3-5           Week 5-6  W6   Week 6+
[✅]              [✅]             [✅]             [✅]                [✅]   [✅]  [—]
```

---

## 2. Phase 1：骨架搭建（3-4 天）

**目标**：可运行的全栈骨架，前后端联通，数据库表就绪。

| 状态 | 任务 | 说明 |
|:---|:---|:---|
| ✅ | 项目初始化 | FastAPI + Vue3 脚手架 |
| ✅ | 前端环境搭建 | npm 依赖与 Vite 配置 |
| ✅ | Git 初始化 | .gitignore + 分支策略 |
| ✅ | MySQL 表建好 | 6 张表 SQLAlchemy 模型 + Alembic 迁移 |
| ✅ | ChromaDB 连接 | collection 创建与管理（已被 ADR-018 BaseVectorStore 抽象层覆盖） |
| ✅ | JWT 认证 | 注册/登录接口 + 中间件 |
| ✅ | 前端登录页 | LoginPage.vue + 路由骨架 |
| ✅ | 前端布局框架 | AppLayout + Sidebar 空壳 |

### 2.1 [测试] Phase 1 测试

> Phase 1 测试已完成，全部通过。

| 状态 | 任务 | 测试类型 | 说明 |
|:---|:---|:---|:---|
| ✅ | 密码哈希 & JWT 单元测试 | 单元测试 | `hash_password` / `verify_password` / `create_access_token` / `decode_access_token` |
| ✅ | 认证 Service 单元测试 | 单元测试 | `register`（用户名重复/正常注册）/ `login`（密码错误/正常登录） |
| ✅ | 认证 API 接口测试 | 接口测试 | POST `/api/auth/register` + `/api/auth/login` 请求/响应格式 + 错误码 |
| ✅ | Pydantic Schema 校验测试 | 单元测试 | `RegisterRequest` / `LoginRequest` 字段校验（用户名长度/密码长度） |
| ✅ | 用户模型测试 | 单元测试 | `User` ORM 字段默认值、`relationship` 关联 |
| ✅ | 前端 LoginPage 组件测试 | 组件测试 | 表单渲染、提交按钮、错误提示 |
| ✅ | 前端 AppLayout 组件测试 | 组件测试 | 布局渲染、Sidebar 存在性 |
| ✅ | 前端路由守卫测试 | 组件测试 | 未登录重定向到 `/login` |

---

## 3. Phase 2：文档入库（3-4 天）

**目标**：用户可以创建知识库、上传文档，系统异步完成解析 → 分块 → 向量化 → 入库。

### 3.1 [后端] 知识库 CRUD + 文档管理

| 状态 | 任务 | 说明 | 依赖决策 |
|:---|:---|:---|:---|
| ✅ | 知识库 CRUD 接口 | POST/GET/PUT/DELETE `/api/knowledge-bases`，名称用户级唯一 `(user_id, name)`，DELETE 当前阶段仅标记 `status=deleting` + 返回 202（Celery 异步物理删除后续实现） | KB 级异步批量清理 |
| ✅ | 文档状态枚举 | `DocumentStatus(str, Enum)` — 10 状态 + `TERMINAL_STATUSES` + `is_terminal()`，ORM/Schema/API 统一使用；前端 `TERMINAL_STATUSES` 去重修复 | 约束一 |
| ✅ | 文档上传 API | POST `/documents`（multipart + force 参数），唯一性检查 `(kb_id, filename)` | 约束二、约束四 |
| ✅ | 批量上传 API | POST `/documents/batch-upload`（多文件，部分成功返回） | 决策 #13 |
| ✅ | 重新处理 API | POST `/documents/{id}/reprocess`（仅 `partial_failed`/`failed` 允许） | 决策 #12 |
| ✅ | 文档列表/详情 API | GET 文档支持 status/filename 筛选 + sort_by/order，分块接口分页（仅 owner/admin） | 决策 #14、#18、#19 |
| ✅ | 文档删除 API | DELETE 异步清理（标记 deleting → Celery 清理向量+文件 → 物理 DELETE，FK CASCADE 清 chunks） | 决策 #10、#11 |
| ✅ | 文件存储 | `uploads/{kb_id}/{doc_id}/{uuid}_{sanitized_filename}` 目录结构 | 决策 #5 |

### 3.2 [后端] Celery 异步入库流水线

| 状态 | 任务 | 说明 | 依赖决策 |
|:---|:---|:---|:---|
| ✅ | Celery 幂等锁 | Redis `SET idempotency_key:{doc_id}:{task_type} EX 600 NX`，处理中拒绝重复入队 | 约束二 |
| ✅ | 文档解析 | PyPDF2 + python-docx，部分容错（<20% warning / 20-50% partial / >50% failed） | 决策 #8 |
| ✅ | 智能分块 | `RecursiveCharacterTextSplitter`（800-1200 chars，分隔符优先级 `\n\n`→`\n`→`。！？`），字符估算 token | 决策 #1、#2 |
| ✅ | Embedding 向量化 | DashScope text-embedding-v3，batch_size=20，max_retries=5 指数退避，批次级 checkpoint + token 回写 | 决策 #7 |
| ✅ | ChromaDB 批量写入 | batch_size=100，禁止单条循环；失败时 `vector_store.delete(where={doc_id})` 全清 + 标记 FAILED | 决策 #3 |
| ✅ | chunk_count 事务更新 | 全部 batch 成功后一次性事务更新 `documents.chunk_count` + `kb.chunk_count`，token_count 回写覆盖估算值 | 决策 #4 |
| ✅ | 阶段化状态机 | `uploaded → parsing → chunking → embedding → vector_storing → completed`，每阶段更新 `current_stage` + `last_success_batch` | 决策 #9 |

### 3.3 [前端] 知识库管理 + 文档管理

> **权限模型对齐**：用户视角（管理自己的 KB）和管理员视角（跨用户管理）使用不同路由，详见 FRONTEND.md §2.1。

| 状态 | 任务 | 说明 | 依赖决策 |
|:---|:---|:---|:---|
| ✅ | 知识库管理页（`/knowledge-bases`） | 我的知识库列表：网格布局 + 新建/编辑弹窗 + 删除确认 | UIDESIGN.md §4 |
| ✅ | 知识库详情页（`/knowledge-bases/:id`） | **新增页面**：KB 信息+统计 + 文档上传区 + 文档表格 + 状态轮询 + 分块预览 | FRONTEND.md §5.5 |
| ✅ | 文档管理（KB 详情页内嵌） | 表格 + 筛选（status/filename）+ 分页 + 上传（拖拽 + force 覆盖选项）+ reprocess | 决策 #15、#19、#20 |
| ✅ | 文档状态轮询 | 非终态 2s 间隔轮询，终态停止，5 分钟超时 | 决策 #16 |
| ✅ | 上传进度反馈 | axios `onUploadProgress`（百分比 + 速度 + 剩余时间） | 决策 #15 |
| ✅ | 状态标签样式 | 10 种状态对应不同颜色/图标（详见 UIDESIGN.md §4.8） | 约束一 |
| ✅ | Sidebar 导航更新 | 增加「我的知识库」入口（所有用户可见）+ 管理后台保留 admin 可见 | FRONTEND.md §4.5 |
| ✅ | Admin 管理页前端（占位） | `/admin/knowledge`、`/admin/documents`、`/admin/stats` 前端页面（后端接口 Phase 5） | — |

### 3.4 🚫 本阶段不做的

| 推迟项 | 排期 | 原因 |
|:---|:---|:---|
| 结构感知分块（Markdown 标题层级） | Phase 3 | Phase 2 先跑通固定大小，后续优化 |
| `.doc` 格式支持 | 不做 | 维护成本极高，前端提示「请先转换为 .docx」 |
| WebSocket 实时状态推送 | Phase 5 | 轮询已满足需求 |
| Resumable 分片上传 | Phase 5+ | 50MB 以内 multipart 足够 |
| 内容去重 | Phase 5+ | Phase 2 仅做文件名唯一性检查 |

### 3.5 [测试] Phase 2 测试

> Phase 2 功能完成后立即执行，不推迟到后续阶段。

| 状态 | 任务 | 测试类型 | 说明 |
|:---|:---|:---|:---|
| ✅ | 知识库 CRUD API 接口测试 | 接口测试 | POST/GET/PUT/DELETE `/api/knowledge-bases` 正常流程 + 错误码（E1001/E1002/E5005）+ 未认证 401 + 参数校验 422（28 个用例）|
| ✅ | 文档上传 API 接口测试 | 接口测试 | POST `/api/documents` multipart 上传 + force 覆盖 + 唯一性冲突（47 用例全部通过）|
| ✅ | 文档删除 API 接口测试 | 接口测试 | DELETE 异步清理流程 + 状态流转（含批量上传/分块/reprocess）|
| ✅ | 文档状态枚举与状态机测试 | 单元测试 | `DocumentStatus` 10 状态 + `TERMINAL_STATUSES` + `is_terminal()` |
| ✅ | Celery 入库流水线单元测试 | 单元测试 | 幂等锁(16) / 解析容错(34) / 分块逻辑(37) / Embedding(30) — 全量 260 通过 ✅ |
| ✅ | Embedding 模块测试 | 单元测试 | `embedder.py` API 调用 / 重试 / 批量处理 / 响应解析（30 用例） |
| ✅ | 文件存储服务测试 | 单元测试 | `storage.py` 本地存储 save/read/delete + 空目录清理 + sanitize_filename 安全处理（37 用例） |
| ✅ | 前端知识库管理页组件测试 | 组件测试 | KnowledgeList.test.js — 11 用例全部通过（渲染/交互/生命周期） |
| ✅ | 前端文档管理页组件测试 | 组件测试 | KnowledgeDetail.test.js — 12 用例全部通过（表格/上传区域/筛选/空状态） |
| ✅ | 前端文档状态轮询测试 | 组件测试 | 挂载获取数据 + 卸载清除轮询验证 |

---

## 4. Phase 2.5：知识库可见性重构（1-2 天）

**目标**：采用「弱混合模式」，新增 `visibility` 字段实现 public/private KB 分离，支持跨部门知识共享。

> **设计原则**：`visibility` 控制 READ，`ownership` 控制 WRITE。详见 PRD.md §5。

### 4.1 [文档] 业务规则文档

| 状态 | 任务 | 说明 |
|:---|:---|:---|
| ✅ | PRD.md §5 可见性模型 | ownership/visibility 规则 + CRUD 权限矩阵 + 检索范围 |
| ✅ | ARCHITECTURE.md §7.7 | 弱混合模式设计决策 |
| ✅ | DATABASE.md §2.2 | `visibility` 列定义 |
| ✅ | API.md §3/§9 | 接口权限速查表更新 + public KB 列表端点 |
| ✅ | FRONTEND.md §2.1/§4.5/§5.7 | 路由 + 侧边栏 + 公共 KB 浏览页 |
| ✅ | CLAUDE.md | 权限分离约束 |
| ✅ | CHANGELOG.md + ADR | 变更日志 + 架构决策记录 |

### 4.2 [后端] 后端实现

| 状态 | 任务 | 说明 |
|:---|:---|:---|
| ✅ | 数据库迁移 | `knowledge_bases` 表新增 `visibility ENUM('private','public') DEFAULT 'private'`（迁移 `8fa3ea12b75e`） |
| ✅ | ORM 模型更新 | `KnowledgeBase` 模型新增 `visibility` 字段 |
| ✅ | Pydantic Schema 更新 | `KnowledgeBaseCreate` 新增 `visibility` 可选字段（默认 `private`）；`KnowledgeBaseUpdate` 新增 `visibility` 可选字段；`KnowledgeBaseResponse` 新增 `visibility` 字段；新增 `PublicKnowledgeBaseResponse`（含 `username`）和 `PublicKnowledgeBaseListResponse` |
| ✅ | KB Service 权限重构 | `get_kb()` 增加 visibility 判断：public KB 允许非 owner 读取；`list_kbs()` 仅返回用户自己的 KB（不变）；新增 `list_public_kbs()` 返回所有 public+active KB（JOIN users 含 username） |
| ✅ | API 端点更新 | `POST /api/knowledge-bases` 支持 visibility 参数；`GET /api/knowledge-bases/{id}` public KB 对非 owner 放行；`PUT /api/knowledge-bases/{id}` owner + admin 可修改含 visibility；新增 `GET /api/knowledge-bases/public` 端点 |
| ✅ | 文档接口权限更新 | `require_kb_owner` / `require_kb_writable` 替代旧 `_check_kb_ownership`（委托 `permissions.py` 共享函数）：上传/reprocess 仅 owner；查看/分块/删除 owner + admin；`TestDocumentPermissionMatrix` 18 用例覆盖全部权限组合 |

### 4.3 [前端] 前端实现

| 状态 | 任务 | 说明 |
|:---|:---|:---|
| ✅ | 创建 KB 弹窗增加 visibility 选择 | 新建/编辑知识库弹窗增加 `private`/`public` 切换（Radio 或 Switch） |
| ✅ | KB 卡片增加 visibility 标识 | 卡片上显示 public/private 标签或图标 |
| ✅ | 公共知识库页面 | `PublicKnowledgeList.vue`（`/knowledge-bases/public`）：卡片网格 + 搜索 + owner 用户名展示，无新建/编辑/删除按钮 |
| ✅ | Sidebar 导航更新 | 新增「公共知识库」入口（所有用户可见），位于「我的知识库」下方 |
| ✅ | 路由更新 | 新增 `/knowledge-bases/public` 路由 |
| ✅ | KB 详情页适配 | 非 owner 访问 public KB 时：隐藏文档上传区、文档表格、编辑/删除按钮；显示「开始问答」入口 |
| ✅ | Pinia Store 更新 | `knowledge.js` 新增 `fetchPublicKbList()` action |

### 4.4 [测试] Phase 2.5 测试

| 状态 | 任务 | 测试类型 | 说明 |
|:---|:---|:---|:---|
| ✅ | visibility 字段校验测试 | 单元测试 | `TestKnowledgeBaseCreateVisibility`（5 用例）+ `TestKnowledgeBaseUpdateVisibility`（4 用例）+ `TestKnowledgeBaseResponseVisibility`（1 用例） |
| ✅ | KB 权限矩阵接口测试 | 接口测试 | `TestVisibilityPermissionMatrix`（6 用例）：public KB 非 owner 可读/不可写；private KB 非 owner 拒绝；admin 全局读写 |
| ✅ | 公共 KB 列表接口测试 | 接口测试 | `TestPublicKbList`（5 用例）：分页 + 仅返回 public+active + username + 未认证拒绝 |
| ✅ | 前端公共 KB 页组件测试 | 组件测试 | PublicKnowledgeList 渲染 + 无编辑/删除/新建按钮（10 用例） |

### 4.5 🚫 本阶段不做的

| 推迟项 | 排期 | 原因 |
|:---|:---|:---|
| shared（指定用户共享） | Phase 5+ | 需要 ACL 表 + 邀请机制，复杂度爆炸 |
| 部门管理员 / 角色扩展 | Phase 5+ | 当前无真实需求 |
| 协作编辑、版本控制 | 不做 | 那是 Notion，不是知识库问答平台 |

---

## 5. Phase 3：核心问答（3-4 天）

**目标**：单轮问答全链路跑通，SSE 流式输出，前端展示答案及引用来源。

### 5.1 [后端] RAG 检索管线

> KnowledgePipeline（`app/rag/knowledge_pipeline.py`）封装了检索+上下文构建管线：查询重写→双路检索→RRF→Rerank→句子匹配→Prompt 构建。

| 状态 | 任务 | 说明 | 依赖决策 |
|:---|:---|:---|:---|
| ✅ | 向量检索器 | `BaseVectorStore.search()` 语义检索，`kb_id` 路由到 `kb_{kb_id}` collection，返回 top_k=10 | 决策 #15、#21 |
| ✅ | BM25 关键词检索器 | `rank-bm25` (BM25Okapi) + `jieba.lcut` 分词，每个 KB 独立索引 | 决策 #16 |
| ✅ | BM25 索引缓存 | Redis `bm25_tokens:{kb_id}` 存储 `tokenized_corpus` + `doc_ids` + `section_info`（JSON），TTL=300s；文档终态后 Celery 触发重建；查询时未命中则懒加载重建；`BM25_LOCAL_CACHE_MAX_CHUNKS=5000`（大 KB 跳过进程内缓存，ADR-023 重构） | 决策 #16 |
| ✅ | BM25 超大 KB 保护 | `BM25_MAX_CHUNKS=10000` 硬限制：三层检查点（COUNT 先于 SELECT / Redis skipped+chunk_count 校验 / 进程内 len(doc_ids) 超限清除），超大 KB 完全跳过 BM25 检索仅依赖向量检索，512MB 容器不再 OOM | ADR-023 |
| ✅ | RRF 多路融合 | `score(d) = Σ 1/(k+rank_i(d))`，k=60，单路为空时仅返回另一路结果 | 决策 #17 |
| ❌ | NoopReranker | ~~占位实现：保持 RRF 融合排序（相关性降序），截取 top_k=5。~~ 已于 Phase 5.5 被 DashScopeReranker 完全替代，类已删除 | 决策 #18 |
| ✅ | Prompt 组装 | 检索结果拼接 + 用户问题，软上限预算控制（超预算时跳过当前 chunk 尝试下一个），保持 RRF 相关性排序（相关性降序） | 决策 #19 |
| ✅ | LLM 调用 | DeepSeek API（OpenAI 兼容），流式 `chat/completions`，`extra_body={"thinking":{"type":"enabled/disabled"}}` 控制思考开关；仅 `deep_thinking=true` 时传 `reasoning_effort="high"`，解析 `content` + `reasoning_content` | 决策 #20 |
| ✅ | ChromaDB metadata 类型一致性 | metadata 保持数值型，入库/查询两端统一使用 int 类型 `kb_id/doc_id/chunk_index`，显式 `int()` 转换保障（由 BaseVectorStore 层处理） | 决策 #21 |

### 5.2 [后端] Chat API + SSE + 会话生命周期

| 状态 | 任务 | 说明 | 依赖决策 |
|:---|:---|:---|:---|
| ✅ | ChatRequest Schema | Pydantic model：`conversation_id: int\|None`、`kb_id: int`、`question: str`（≤2000字符）、`deep_thinking: bool=False` | — |
| ✅ | Chat Service 核心流程 | `chat_service.chat()` — 委托 KnowledgePipeline 检索+构建，LLM SSE 流式，阶段化错误处理（检索失败 E4003 / LLM失败 E4002） | — |
| ✅ | 问答检索权限 | `POST /api/chat` 校验 kb_id：使用 `require_kb_readable`（权限集中化，private KB 仅 owner + admin 可检索，public KB 所有用户可检索） | — |
| ✅ | Chat Router 注册 | `main.py` 注册 `chat_router`（`prefix="/api"`） | — |
| ✅ | SSE 流式输出 | 手动 `StreamingResponse`（不用 sse-starlette），事件类型：meta → thinking → message → sources → finish → error，15s 心跳注释帧 | 决策 #22 |
| ✅ | 会话自动创建 | `conversation_id=null` 时自动创建会话（`kb_id` 记录问答目标 KB），不注入历史消息（`history=[]`），数据结构兼容 Phase 4 | 决策 #23 |
| ✅ | 标题自动生成 | 截取用户问题前 12 字（`question[:12]`），去除标点。首轮问答后 `event: finish` 返回 title；后续轮次不更新标题 | 决策 #24 |
| ✅ | thinking_content 传输 | `deep_thinking=true` 时解析 DeepSeek `reasoning_content` → `event: thinking` 流式推送。**不落库**，仅前端实时展示 | 决策 #25 |
| ✅ | sources 引用过滤 | LLM 流式结束后从 `assistant_content` 提取 `[来源N]` 编号，仅发送被实际引用的 chunk；LLM 失败时回退全量发送 | 决策 #27 |
| ✅ | KB 选择器接口 | `GET /api/knowledge-bases/selectable` 返回 `{"mine": [...], "public": [...]}`（mine=用户全部 KB，public=他人 public KB） | 决策 #26 |

### 5.3 [前端] 问答界面

| 状态 | 任务 | 说明 | 依赖决策 |
|:---|:---|:---|:---|
| ✅ | KB 选择器 | ChatPage 顶部双独立 `el-select` 并排（左侧「我的知识库」/ 右侧「公共知识库」），公共 KB 选项附加 `(username)` 标识所有者，数据来源 `GET /api/knowledge-bases/selectable`，默认选中最近使用的 KB | 决策 #26 |
| ✅ | ChatInput 组件 | 输入框（≤2000字符计数字）+ Enter 发送 / Shift+Enter 换行 + 深度思考开关（黄色激活态）+ 发送中切换为「停止生成」按钮 + 空输入抖动反馈 | FRONTEND.md §4.3 |
| ✅ | MessageList 组件 | 消息列表：用户气泡（右对齐黑底白字）+ AI 气泡（左对齐无背景）+ Markdown 实时渲染 + thinking 黄色折叠面板 + sources 引用卡片（文档计数去重）；自动滚动到底部，手动上滚时显示 sticky「新消息」浮动按钮 | FRONTEND.md §4.4 |
| ✅ | MessageItem 组件 | 单条消息渲染：角色头像 + 内容区（markdown-it + highlight.js）+ thinking 黄色折叠面板（默认展开）+ sources 引用来源卡片（含分块文本内容预览）+ typing 三点动画 + 完成态 hover「重新生成」+ 错误状态提示 + 代码块复制按钮 | — |
| ✅ | WelcomeScreen 组件 | 空消息列表时展示：欢迎语 + 快捷问题卡片（点击自动填入输入框并发送）。已移除产品 Logo（侧边栏已有独立 Logo） | FRONTEND.md §4.6 |
| ✅ | SSE 解析工具 `sse.js` | `fetch` + `ReadableStream` 解析 SSE 事件流（`event:` 行 + `data:` 行），支持 6 种事件类型 + 格式异常容错 + 心跳帧忽略 | 决策 #22 |
| ✅ | Markdown 渲染工具 `markdown.js` | `markdown-it` 封装 + `highlight.js` 代码块高亮（github-dark 主题）+ 一键复制 + 安全过滤（XSS 防护） | — |
| ✅ | ChatStore (Pinia) | 消息列表状态 + `sendMessage()` SSE 流式消费 + `abort()` 中断 + `conversation_id` 管理 + `reset()` 方法（退出登录时清空全部状态 + 移除 `last_kb_id`） | — |
| ✅ | Chat API 封装 `api/chat.js` | `sendMessage(params, onEvent, onError)` — fetch SSE 流，回调式事件分发 | — |
| ✅ | 来源引用展示 | `event: sources` 事件在消息底部渲染引用文档卡片（doc_name + 分块文本预览 + page），去重文档计数（「引用 X 个文档，共 N 个片段」） | — |
| ✅ | Sidebar 会话入口适配 | 会话区域展示空态（Phase 4 实现 CRUD），「新建对话」按钮清空消息列表 + conversation_id=null，Chat 路由时高亮激活态 | — |

### 5.4 🚫 本阶段不做的

| 推迟项 | 排期 | 原因 |
|:---|:---|:---|
| 结构感知分块（Markdown 标题层级） | Phase 5+ | Phase 3 继续用固定大小分块，检索质量已够用 |
| 意图识别（知识查询/闲聊分类） | Phase 5 | Phase 3 已加轻量规则级 stopgap（`_is_casual_chat()`：问候/致谢/告别等 6 类正则），跳过检索直接回复。完整意图识别（含问题类型判别）仍排 Phase 5 |
| 问题重写（多轮上下文补全） | Phase 4 | Phase 3 仅单轮，不注入历史 |
| 会话 CRUD（列表/重命名/删除） | Phase 4 | Phase 3 仅自动创建 + 标题生成 |
| DashScope Rerank API | Phase 5.5 | 语义精排，已完全替代 NoopReranker |
| 对话历史注入 Prompt | Phase 4 | Phase 3 `history=[]`，数据结构兼容 Phase 4 |
| thinking_content 持久化 | Phase 5+ | Phase 3 仅流式展示不落库；SSE 中断半条消息持久化见 Phase 4 消息状态机 |
| reasoning_effort 前端可控 | Phase 5+ | Phase 3 后端在 `deep_thinking=true` 时固定 `"high"`，前端仅 deep_thinking 开关 |

### 5.5 [测试] Phase 3 测试

> Phase 3 功能完成后立即执行，不推迟到后续阶段。

| 状态 | 任务 | 测试类型 | 说明 |
|:---|:---|:---|:---|
| ✅ | 向量检索器单元测试 | 单元测试 | ChromaDB `query()` Mock：返回 top_k 结果 + `where` kb_id 过滤 + 空结果处理（18 用例） |
| ✅ | BM25 检索器单元测试 | 单元测试 | BM25Okapi 初始化 + `get_scores()` 排序 + jieba 分词 + 空语料处理（12 用例） |
| ✅ | BM25 索引缓存测试 | 单元测试 | Redis 缓存命中/未命中懒加载/Celery 触发重建/缓存失效（8 用例） |
| ✅ | RRF 融合算法测试 | 单元测试 | k=60 标准合并 / 单路为空 / 两路均空 / 排名相同处理（14 用例） |
| ❌ | NoopReranker 测试 | ~~单元测试~~ | ~~保持 RRF 排序 + top_k 截取 + 输入不足 top_k（11 用例）~~ 随 NoopReranker 类一并移除 |
| ✅ | Prompt 模板测试 | 单元测试 | 检索结果拼接 / 软上限预算控制 / chunk 择优填充 / 空检索结果处理（15 用例） |
| ✅ | Chat Service 单元测试 | 单元测试 | 检索→RRF→Rerank→Prompt→LLM 全链路 Mock（19 用例） |
| ✅ | sources 引用过滤测试 | 单元测试 | `_extract_citation_indices` 提取/去重/无效编号；SSE sources 仅含被引用 chunk / 全引用 / 零引用 / LLM 失败回退（9 用例全部通过） |
| ✅ | LLM 调用与 thinking 解析测试 | 单元测试 | DeepSeek API 流式响应 Mock / `reasoning_content` 解析 / `content` 解析（15 用例） |
| ✅ | SSE 流式输出测试 | 单元测试 | `StreamingResponse` 事件序列 / 心跳帧 / 中途错误 / sources/finish 数据结构（16 用例） |
| ✅ | 问答 SSE 接口测试 | 接口测试 | POST `/api/chat` SSE 事件序列 + 错误码 + 权限校验 + deep_thinking 开关 + 心跳帧（12 用例） |
| ✅ | KB 选择器接口测试 | 接口测试 | GET `/knowledge-bases/selectable` 返回 mine+public 分组 + 不重复 + 仅返回 active KB（6 用例） |
| ✅ | ChatRequest Schema 校验测试 | 单元测试 | question 空/超长 + kb_id 缺失 + conversation_id 类型 + deep_thinking 默认值（6 用例） |
| ✅ | 前端 SSE 解析工具测试 | 单元测试 | `sse.js` 各 event 类型解析 + 异常格式容错 + 心跳帧忽略 + 多行 data 拼接（21 用例） |
| ✅ | 前端 Markdown 渲染工具测试 | 单元测试 | markdown-it 渲染 + 代码块高亮 + XSS 过滤 + 链接处理（14 用例） |
| ✅ | 前端 ChatInput 组件测试 | 组件测试 | 输入/发送/停止/Enter/Shift+Enter/字数计数/空内容拒绝/deep_thinking 开关（19 用例） |
| ✅ | 前端 MessageList 组件测试 | 组件测试 | 消息气泡排列 / 自动滚动 / 手动上滚「新消息」按钮 / 空状态（10 用例） |
| ✅ | 前端 MessageItem 组件测试 | 组件测试 | Markdown 渲染 / thinking 折叠面板 / sources 引用卡片 / 重新生成按钮 / 来源抑制（26 用例） |
| ✅ | 前端 WelcomeScreen 组件测试 | 组件测试 | 欢迎语渲染 + 快捷问题卡片点击填入输入框（8 用例） |
| ✅ | 前端 ChatPage 集成测试 | 组件测试 | 完整问答流程：选择KB→输入问题→SSE流式渲染→sources展示→停止按钮（13 用例） |
| ✅ | 人工答案评分（第 1 轮） | 人工评估 | 10 题 × 4 维度评分表，平均综合分 4.38/5.0 ✅ 满足目标（见 `backend/tests/eval/human_eval_template.md`） |
| ✅ | 离线检索评估 | 检索评估 | RRF 融合 Recall@5=1.000（28/28 完全召回），修复向量和 BM25 各自盲区。脚本：`tests/eval/eval_retrieval.py` |
| ✅ | 回归测试集初版建立 | 回归测试 | 30 题固定测试集（`tests/eval/eval_test_set.py`）+ 回归脚本（`tests/regression/regression_test.py`） |

### 5.6 [索引] 关键决策索引

| # | 决策 | 文档位置 |
|:---|:---|:---|
| 15 | 向量检索：`BaseVectorStore.search()` + `kb_id` 路由到 Per-KB collection `kb_{kb_id}`，top_k=10 | RAG_PIPELINE.md §2.1 |
| 16 | BM25 索引生命周期：终态后 Celery 触发重建 + Redis 缓存 `tokenized_corpus` + 查询时懒加载 BM25Okapi 实例化 | RAG_PIPELINE.md §2.2, ARCHITECTURE.md §6.2 |
| 17 | RRF 融合：k=60，单路为空时仅返<br/>回另一路 | ARCHITECTURE.md §6.3 |
| 18 | NoopReranker：保持 RRF 融合排序（相关性降序），截取 top_k=5 | ARCHITECTURE.md §7.3 |
| 19 | Prompt 预算：软上限 + 相关性优先填充（保持 RRF 排序），超预算时跳过当前 chunk；chunking 阶段固定 chunk_size 不二次裁剪 | RAG_PIPELINE.md §3 |
| 20 | LLM：DeepSeek API（OpenAI 兼容），流式 `chat/completions`，通过 `extra_body={"thinking":{"type":"enabled/disabled"}}` 控制思考开关；仅开启 thinking 时传 `reasoning_effort="high"` 控制强度。**注意**：DeepSeek 默认 thinking=enabled，关闭时须显式传 disabled 且不传 reasoning_effort | RAG_PIPELINE.md §5 |
| 21 | ChromaDB metadata 类型一致：保持 int 类型，入库/查询两端统一（由 BaseVectorStore 层处理） | ARCHITECTURE.md §7.1 |
| 22 | SSE：手动 `StreamingResponse`，6 事件类型 + 15s 心跳注释帧 `: ping\n\n` | RAG_PIPELINE.md §5, API.md §6 |
| 23 | 会话：Phase 3 自动创建（conversation_id=null），不注入历史（history=[]），数据结构兼容 Phase 4 | ARCHITECTURE.md §5, RAG_PIPELINE.md §1 |
| 24 | 标题：截取用户问题前 12 字，首轮 `event: finish` 返回 | ARCHITECTURE.md §5 |
| 25 | thinking_content：`event: thinking` 流式推送，不落库（`messages.thinking_content=null`），仅前端实时展示。`deep_thinking` 通过 `extra_body` 映射到 DeepSeek `thinking` 参数 | API.md §6.1, RAG_PIPELINE.md §5 |
| 26 | KB 选择器：`GET /knowledge-bases/selectable` 返回 `{mine, public}` 分组，前端 `<el-option-group>` 渲染 | API.md §3, FRONTEND.md §4.1 |
| 27 | sources 引用过滤：LLM 流式结束后从 `assistant_content` 提取 `[来源N]` 编号，仅发送被实际引用的 chunk；LLM 失败时回退全量发送；零引用时不发送 sources | RAG_PIPELINE.md §5, API.md §6.1 |

---

## 6. Phase 4：会话 & 记忆 + 基础设施加固 ✅

**目标**：多轮对话能力 + 会话管理 + 三项独立基础设施（错误处理 / Refresh Token / 结构化日志），为 Phase 5 减负。

> Phase 4 已全部完成（18 项任务）。

### 6.1 [后端] 会话管理 + 多轮上下文

| 状态 | 任务 | 说明 | 依赖决策 |
|:---|:---|:---|:---|
| ✅ | 会话 CRUD | 列表（按 `updated_at DESC`，仅当前用户）/ 详情（含 messages）/ 重命名 / 硬删除 | 决策 #28 |
| ✅ | 多轮对话上下文 | service 层 `_load_history()` 获取历史消息注入 context，Token 预算四池子分拆独立截断（详见 ARCHITECTURE.md §8） | 决策 #28 |
| ✅ | 会话标题 LLM 生成 | 替换当前「前 12 字截断」方案，更准确的自然语言标题；SSE finish 先返回截断标题，流结束后异步 LLM 更新 | — |
| ✅ | 问题重写 | 轻量歧义检测 `needs_rewrite()` → LLM 指代/省略补全（~30 行）。仅在有歧义时触发（无历史/独立问题跳过），降级回原始 query。详见 RAG_PIPELINE.md §4 | 决策 #32 |

### 6.2 [后端] 基础设施加固 + 数据库准备（从 Phase 5 提前）

| 状态 | 任务 | 说明 |
|:---|:---|:---|
| ✅ | 错误处理 | 全局异常处理 + 统一错误码。已有 `AppException` 体系和 31 个异常类，本阶段补充遗漏的异常映射 + 未知异常兜底策略（生产环境屏蔽堆栈） |
| ✅ | Refresh Token 机制 | access_token（15min）+ refresh_token（7天，存 MySQL/Redis），支持 Rotation（刷新后旧 token 失效）、主动吊销（改密/强制下线） |
| ✅ | 结构化日志 | 关键节点埋点（请求入口/检索耗时/LLM 调用/异常），统一日志格式（request_id + user_id + 阶段 + 耗时），便于上线后定位问题 |
| ✅ | `messages` 表新增 `metadata` 列 | `metadata JSON NULL DEFAULT NULL`，alembic revision `9a1b2c3d4e5f`。Phase 4 不使用，为 Phase 5+ 预留 |
| ✅ | `conversations` 新增索引 | `(user_id, updated_at)` 复合索引，alembic revision `9a1b2c3d4e5f` |

> **限流留在 Phase 5**：限流阈值依赖真实流量特征和压测数据，开发阶段随意设值（如 10/min）要么太严误伤用户，要么太松形同虚设。压测完成后再定策略更合理。

### 6.3 [前端] 会话列表 + 路由

| 状态 | 任务 | 说明 |
|:---|:---|:---|
| ✅ | Sidebar 会话列表 | 展示当前用户会话列表 + 切换加载 + 高亮当前会话 |
| ✅ | Token 自动刷新（Axios 拦截器） | 响应拦截器捕获 401+E5003 → 调 `POST /api/auth/refresh` → 重放原请求（最多 1 次）；并发请求防抖（`isRefreshing` 标志位）；刷新失败 → 清除 token → 跳转 `/login`；`scheduleRefresh` 定时器（access_token 到期前 1 分钟自动刷新） |
| ✅ | ChatPage 会话路由 | `onMounted` 读取 `route.query.conversation_id` → 加载历史消息；新建对话 → URL 回到 `/chat` |
| ✅ | 修改密码弹窗 | Sidebar 用户栏头像/用户名 `@click` → `el-dialog`（420px）→ 表单（旧密码 + 新密码 + 确认新密码，含一致性校验）→ `PUT /api/auth/password`。成功后 `ElMessage.success('密码修改成功，请重新登录')` → 注销 + 跳转 `/login` |

### 6.4 🚫 本阶段不做的

| 推迟项 | 排期 | 原因 |
|:---|:---|:---|
| 滑动窗口摘要压缩 | Phase 6 | 额外 LLM 调用开销大，Token 截断先够用 |
| 消息状态机（partial/complete + PATCH） | Phase 6 | 投入产出比低——SSE 中断重问一遍即可，partial 持久化增加 SSE 流中异步写库复杂度 |
| 前端 Conversation 独立管理页 | Phase 6 | Sidebar 内联管理已满足需求 |
| 限流 | Phase 5 | 依赖压测数据定策略，开发阶段无法设定合理阈值 |
| Retrieval-aware Rewrite（检索质量触发改写） | Phase 5 | 当前 v2 信号词策略存在纯省略主语盲区（如「审批流程需要多长时间？」），但覆盖率 95.7% 已足够。检索先行 + 结果差时二次改写是更优的触发机制 |

### 6.5 [测试] Phase 4 测试

| 状态 | 任务 | 测试类型 | 说明 |
|:---|:---|:---|:---|
| ✅ | 会话 CRUD API 接口测试 | 接口测试 | POST/GET/PUT/DELETE 会话正常流程 + 错误码（E3001/E3002）+ 权限拒绝。20 用例，全部通过 |
| ✅ | 滑动窗口记忆测试 | 单元测试 | Token 截断（U8.1）/ 条数硬上限（U8.4）/ 空历史（U8.5）/ [来源N] 去除（U8.6）/ system 消息过滤 + 各池子独立截断不互侵。9 用例全部通过。Retrieval 超限截断（U8.2）和双池同时超限（U8.3）已排入 Phase 5（依赖 Rerank 排序完整性） |
| ✅ | 会话标题 LLM 生成测试 | 单元测试 | LLM 正常生成 / 引号去除 / 失败回退 / 空内容回退 / 过长截断 / 回退一致性。6 用例全部通过 |
| ✅ | 多轮 RAG 回归测试 | 接口测试 | 5 Session × 23 轮全部通过。验证：历史记忆正常 + 每轮检索正常 + 每轮引用正常 + RAG 未退化（所有轮次均有 sources）。**单轮测试全部通过 ≠ 多轮没问题** |
| ✅ | 前端会话列表组件测试 | 组件测试 | Sidebar 会话列表渲染（21 用例）：时间分组 / 高亮 / 点击切换 / 重命名 / 删除 / 折叠展开。全部通过 |
| ✅ | Refresh Token 测试 | 接口测试 | Token 刷新 / Rotation（旧 token 失效）/ 主动吊销。20 用例全部通过 |
| ✅ | 前端 Token 刷新测试 | 组件测试 | Axios 拦截器请求/响应 / authStore Token 管理 / conversationStore CRUD（20 用例）。全部通过 |
| ✅ | 错误处理测试 | 单元测试 | 各异常类 → HTTP 状态码映射 / 生产环境堆栈屏蔽 / 未知异常兜底。7 用例全部通过 |
| ✅ | 结构化日志测试 | 单元测试 | JSONFormatter 输出 / RequestIDFilter 注入 / setup_logging 配置。12 用例全部通过 |
| ✅ | 人工答案评分（第 2 轮） | 人工评估 | 5 Session 修正后平均综合分 4.76/5.0 ✅ 远超 ≥ 4.0 目标，较第 1 轮（4.38/5.0）显著提升。详见 `backend/tests/eval/human_eval_template.md` |

### 6.6 [索引] 关键决策索引

| # | 决策 | 文档位置 |
|:---|:---|:---|
| 28 | 会话记忆：Token 预算四池子分拆 + `[来源N]` 去除 + `updated_at` 自动更新 + 硬删除 + metadata 预留 | ARCHITECTURE.md §8 |
| 29 | 前端路由：Query param `/chat?conversation_id=123`，与现有 `?kb_id=` 一致 | FRONTEND.md |
| 30 | 基础设施提前：错误处理 / Refresh Token / 结构化日志从 Phase 5 移至 Phase 4，减轻上线前压力 | 本文件 §6.2 |
| 31 | 限流留 Phase 5：阈值依赖压测数据，开发阶段不设固定值 | 本文件 §6.2 |
| 32 | 问题重写提前至 Phase 4：多轮 RAG 回归测试证实检索阶段需要历史感知 query，不能仅依赖 LLM Prompt 侧 history 注入。轻量触发（仅歧义时）+ 最近 2 轮 history + 降级原始 query | RAG_PIPELINE.md §4 |

---

## 7. Phase 5：打磨上线

**目标**：体验完善 + 简易管理后台 + 限流 + 部署就绪，可以上线。

> **设计文档**：意图识别详见 RAG_PIPELINE.md §6，Admin 接口详见 API.md §7，限流/部署/监控详见 ARCHITECTURE.md §12。

### 7.1 [体验完善] 体验完善

| 状态 | 任务 | 说明 |
|:---|:---|:---|
| ✅ | `intent.py` 实现 | LLM 分类器（3 分类：KNOWLEDGE/CASUAL/META）+ Prompt + 降级回退 `_is_casual_chat()` |
| ✅ | `chat_service.py` 集成 | `_validate_and_prepare()` 中插入分类→路由逻辑；META 直接返回固定响应；CASUAL 委托 `KnowledgePipeline.execute_casual()` 跳过检索 |
| ✅ | 移除 `_is_casual_chat()` 主逻辑 | 降级为 fallback 保留，分类正常时不再作为主分类逻辑 |
| ✅ | 后端定位逻辑（v1 — LLM 引用定位） | `_locate_preview()` / `_fallback_preview()` 实现；`_build_sources()` 新增 `preview_text` / `preview_range` 字段 |
| ✅ | 前端预览渲染 | `MessageItem.vue` 被引段落高亮渲染（`<mark>` 标签包裹 `preview_range` 范围） |
| ✅ | Evidence Highlight 重构（v2 — 句级 BM25 定位） | 定位前移到检索时：新建 `sentence_matcher.py`，删除旧 5 个函数，净代码 -150 行 |
| ✅ | `_is_meta_question()` regex | META 意图规则分类（「你能做什么」「支持什么」等模式） |
| ✅ | CASUAL regex 迁入 intent.py | `_CASUAL_PATTERNS` + `_is_casual_chat()` 从 `chat_service.py` 搬到 `intent.py`；`CASUAL_SYSTEM_PROMPT` 从 `chat_service.py` 迁入 `knowledge_pipeline.py` |
| ✅ | `classify_intent()` 重构 | 规则优先 → `_llm_classify()` 兜底（`deepseek-v4-flash`） |
| ✅ | `config.py` 新增 `LLM_FLASH_MODEL` | 默认 `deepseek-v4-flash`，同 base_url/api_key |
| ✅ | `llm.py` 新增 `model` 参数 | `chat_completion()` 支持指定模型，默认改为 `settings.LLM_FLASH_MODEL`（非流式场景统一用 Flash） |
| ✅ | `chat_service.py` 适配 | `_generate_title_llm()` 自动受益于 Flash 模型默认值 |
| ✅ | `query_rewriter.py` 验证 | `rewrite_query()` 自动受益于 `chat_completion()` 默认值 |
| ✅ | `redis_client.py` 新增 `get_async_redis()` | 保留同步客户端（Celery）+ `ThreadedRedisClient`（Windows 兼容） |
| ✅ | `bm25.py` async Redis | `self._redis.get()` → `await self._async_redis.get()`，修复事件循环阻塞 |
| ✅ | `bm25.py` 进程内缓存 | `dict[kb_id] → (BM25Okapi, doc_ids, contents, expire_at)`，TTL=60s |
| ✅ | `bm25.py` async `invalidate_bm25_cache()` | 清除 Redis + 进程内缓存，提供同步/异步两个版本 |
| ✅ | 调用方适配 | `chat_service.py` → 委托 `knowledge_pipeline.py`；`document_service.py` await 调用 / `tasks.py` 保持同步 |
| ✅ | Windows 兼容性优化 | `redis.asyncio` Windows 超时问题改用 `ThreadedRedisClient` 包装 |

**预期效果**：

| 场景 | 当前 | P0-1 优化后 | P0-2 优化后 |
|:---|:---|:---|:---|
| META "你能做什么" | ~5s pro | <1ms regex | — |
| CASUAL "你好" | ~5s pro | <1ms regex | — |
| 模糊问题（意图分类） | ~5s pro | ~1-2s flash | — |
| 问题改写 | ~3-5s pro | ~1-2s flash | — |
| 标题生成 | ~3-5s pro | ~1-2s flash | — |
| BM25 cache hit | ~2.8s（同步阻塞） | — | ~5ms（进程内缓存） |

### 7.2 [管理后台] 管理后台（简易版）

| 状态 | 任务 | 说明 |
|:---|:---|:---|
| ✅ | Admin Pydantic Schema | `backend/app/schemas/admin.py` — `AdminStatsResponse` / `AdminKBItem` / `AdminKBListResponse` / `AdminDocItem` / `AdminDocListResponse` |
| ✅ | Admin Service | `backend/app/services/admin_service.py` — `get_stats()`（7 统计维度）/ `list_all_kbs()`（5 筛选维度 + 分页）/ `list_all_documents()`（5 筛选维度 + 5 排序字段 + 分页） |
| ✅ | Admin API 端点 | `backend/app/api/admin.py` — GET `/stats` / `/knowledge-bases` / `/documents` + `require_admin` 依赖注入 |
| ✅ | Admin API 封装 | `frontend/src/api/admin.js` — 3 个接口函数 |
| ✅ | AdminKnowledgeList 对接 | 表格 + 筛选（visibility/status/search）+ 分页 + 删除 loading 反馈 |
| ✅ | AdminDocumentList 对接 | 表格 + 筛选（status/kb_id/filename）+ 分页 + 删除操作 |
| ✅ | AdminStatsPage 对接 | 统计卡片真实数据 + 存储量格式化 |
| ✅ | Admin 独立布局 | `AdminLayout.vue` — 独立侧边栏 + 主内容区；Admin 路由嵌套 |
| ✅ | Sidebar 重构 | 移除 admin 导航区，用户菜单新增「管理后台」选项（仅 isAdmin 可见） |
| ✅ | KnowledgeDetail 权限扩展 | `isOwner \|\| isAdmin` 判断（使用 `permissions.py` 共享权限函数 `require_kb_readable`）；admin 可查看文档列表 |
| ✅ | Admin 删除违规内容 | 详情页内 admin 可删除文档（复用已有 DELETE 接口） |

### 7.3 [基础设施] 基础设施

| 状态 | 任务 | 说明 |
|:---|:---|:---|
| ✅ | `rate_limit_middleware.py` 中间件 | 固定窗口计数器 + Redis 原子操作（`INCR` + `EXPIRE`），纯 ASGI 中间件，Lua 脚本原子性，降级放行策略 |
| ✅ | 限流配置项 | `config.py` 新增 6 个限流配置字段（`RATE_LIMIT_ENABLED` + 4 接口组阈值 + `RATE_LIMIT_WINDOW_SECONDS`） |
| ✅ | 限流中间件注册 | `main.py` 注册 `RateLimitMiddleware`（放在 `RequestIDMiddleware` 之后） |
| ✅ | README.md 部署章节 | 项目简介 + 快速开始（Docker Compose）+ 文档索引 |
| ✅ | Dockerfile × 2 | `Dockerfile.backend`（FastAPI + Celery Worker）+ `Dockerfile.frontend`（Nginx + 静态资源） |
| ✅ | docker-compose.yml | 5 服务编排（MySQL + Redis + Backend + Celery + Nginx）+ ChromaDB 挂卷 |
| ✅ | nginx.conf | 反向代理 + SSE buffering 关闭 + 静态资源 SPA fallback + client_max_body_size 50m |

### 7.4 [高级功能] Trace 链路追踪

> Trace 不承担审计职责，仅承担性能观测。完整对话内容通过 `conversation_id` JOIN 查询获取。

| 状态 | 任务 | 说明 |
|:---|:---|:---|
| ✅ | Trace 模型 + Alembic 迁移 | `traces` 表含 trace_id / user_id / conversation_id / kb_id / question / status / intent_type / intent_method / response_mode / total_duration_ms / 各阶段 JSON / error_message / created_at。6 个索引 |
| ✅ | `trace.record()` 上下文管理器 | TraceRecorder 数据收集器：各阶段 record_* + finish 写入，写入失败不阻塞主流程 |
| ✅ | `chat_service.py` 各阶段埋点 | 检索阶段埋点已移至 `knowledge_pipeline.py`；复用已有 `time.perf_counter()` 计时点，整合为 TraceRecorder 结构化写入 |
| ✅ | `core/llm.py` 流式调用埋点 | 记录 `ttft_ms` + `total_ms` + `model` + `finish_reason` |
| ✅ | Trace API（列表 + 详情） | GET `/api/admin/traces`（分页+筛选）+ GET `/api/admin/traces/{trace_id}` |
| ✅ | 统计增强接口 | GET `/api/admin/stats/traces`（days/group_by 参数，返回 trend/latency/tokens 等） |
| ✅ | TraceList.vue | 列表页：概览卡片 + 搜索 + 筛选 + 表格 + 分页。点击行→详情页 |
| ✅ | TraceDetail.vue | 详情页：基本信息卡片 + 5 阶段概览卡片 + JSON 展开面板 |
| ✅ | `api/trace.js` | 接口封装（getTraceList + getTraceDetail） |
| ✅ | AdminLayout 导航更新 | 添加「链路追踪」菜单项 |

> **v2 迭代**：Trace 详情瀑布图 / BM25 细粒度高亮

### 7.5 [高级功能] 系统统计 ECharts

| 状态 | 任务 | 说明 |
|:---|:---|:---|
| ✅ | 增强 `/api/admin/stats` 接口 | 响应新增 `charts` 字段：trend / latency（P50/P95/P99）/ tokens，从 `traces` 表聚合 |
| ✅ | P50/P95/P99 分位数计算 | 按天/小时聚合 `total_duration_ms` |
| ✅ | 引入 ECharts 5 | 封装 `useECharts` 组合式函数（ResizeObserver + 自动 dispose） |
| ✅ | StatsPage 图表组件 | 问答量趋势（折线图）/ 响应时间分布（折线图）/ Token 使用统计（堆叠柱状图） |
| ✅ | 图表配置常量文件 | `frontend/src/constants/charts.js` — 颜色/样式/tooltip 配置（对齐 Design Token） |

> **v2 迭代**：意图分类饼图 / 响应模式饼图 / 用户活跃度折线图

### 7.6 [高级功能] 用户管理

| 状态 | 任务 | 说明 |
|:---|:---|:---|
| ✅ | 用户管理 API | GET `/api/admin/users`（分页+筛选：role/status/search）+ GET `/api/admin/users/{user_id}`（含统计） |
| ✅ | 用户操作 API | PUT `.../status`（禁用/启用）+ POST `.../reset-password`（重置密码） |
| ✅ | 用户统计聚合 | 从 traces 表聚合 total_input_tokens / total_output_tokens / last_active_at |
| ✅ | 权限控制 | admin 专属，非 admin 返回 403（E5005）；禁用用户三端拦截（E5010）；KB 权限通过 `permissions.py` 共享函数统一执行 |
| ✅ | AdminUserList.vue | 用户列表：搜索 + 角色/状态筛选 + 表格 + 分页 + 操作菜单 |
| ✅ | AdminUserDetail.vue | 用户详情：信息卡片 + 统计卡片 + 快捷操作（禁用/重置密码） |
| ✅ | `api/admin.js` 新增函数 | getAdminUsers / getAdminUserDetail / changeUserStatus / resetUserPassword |
| ✅ | AdminLayout 导航更新 | 添加「用户管理」菜单项 |

> **v2 迭代**：`user_operations` 审计日志表 / 操作日志 API / 前端操作日志展示

### 7.7 [基础设施] 外部资源 UUID 化

> 双字段方案：内部保留 `id BIGINT AUTO_INCREMENT`（FK/JOIN 性能），新增 `uuid CHAR(36) UNIQUE` 作为外部标识。API 边界做 UUID↔ID 转换。改造范围：knowledge_bases / documents / conversations 三张表。

| 状态 | 任务 | 说明 |
|:---|:---|:---|
| ✅ | Alembic 迁移 | 三表新增 `uuid CHAR(36) NOT NULL` + `UNIQUE INDEX`，存量回填 `uuid()`，默认 `gen_random_uuid()` |
| ✅ | ORM 模型更新 | 三表新增 `uuid` 字段 + `default=uuid4` |
| ✅ | Pydantic Schema 更新 | 响应 `id` → `uuid`，`kb_id` → `kb_uuid`，请求 `kb_id: int` → `kb_uuid: str` |
| ✅ | Service 层 UUID↔ID 转换 | `resolve_uuid_to_id()` / `get_by_uuid()`，内部继续用 int id |
| ✅ | API 路径参数更新 | 所有 `{kb_id}` / `{doc_id}` → `{kb_uuid}` / `{doc_uuid}` |
| ✅ | Chat API 适配 | `kb_id: int` → `kb_uuid: str`，SSE meta 输出 UUID |
| ✅ | Trace 响应清理 | 移除自增 `id` 字段（保留 `trace_id` UUID） |
| ✅ | KB 选择器适配 | 返回 `uuid` 替代 `id` |
| ✅ | ChromaDB metadata 兼容 | `kb_id` / `doc_id` 仍为 int，仅在 API 边界转换，`get_vector_store()` 内部处理 |
| ✅ | 前端 API 接口适配 | `api/*.js` 参数 `kb_id` → `kb_uuid`，`conversation_id` → UUID 字符串 |
| ✅ | 前端路由参数适配 | `/knowledge-bases/:id` → `/:uuid`，`?conversation_id=` 改为 UUID |
| ✅ | Pinia Store 适配 | id 相关字段改为 uuid |
| ✅ | 前端组件适配 | KnowledgeDetail / ChatPage / Sidebar 等 id 引用改为 uuid |
| ✅ | Admin 页面适配 | Trace 列表/详情移除自增 id 展示 |
| ✅ | 前端组件回归（组件测试） | 路由跳转 + API 调用 + 页面渲染 |

### 7.8 [测试] Phase 5 测试

| 状态 | 任务 | 测试类型 | 说明 |
|:---|:---|:---|:---|
| ✅ | 意图识别测试 | 单元测试 | 分类正确性 6 + 路由 2 + 降级 2 = 10 用例（`test_intent.py`），全部通过 |
| ✅ | sources Evidence 预览测试 | 单元测试 | Evidence 定位集成 3 + 降级 3 + 短 chunk 2 + 格式 3 + 边界 5 + Schema 5 = 21 用例（`test_sources_preview.py`）+ 句级定位 14 用例（`test_sentence_matcher.py`）= 35 用例，全部通过；前端零改动 |
| ✅ | Admin 接口测试 | 接口+单元 | Service 层 21 用例（`test_admin_service.py`）+ API 层 27 用例（`test_admin_api.py`，含权限矩阵参数化），全部通过 |
| ✅ | 限流测试 | 接口+单元 | 限流中间件 22 用例（`test_rate_limit.py`）：IP 提取 4 + 路由规则 6 + 阈值获取 3 + A8.1-A8.5 集成测试 5 + OPTIONS/health/WebSocket/Lua 参数 4，全部通过 |
| ✅ | 性能埋点验证 | 单元测试 | 日志格式校验 1 用例（U12.4，独立于 Trace）。chat_service 全链路集成埋点测试 5 用例（§6.14.4，U13.10-U13.14）— 验证 KNOWLEDGE/CASUAL/META/错误/retrieve 细粒度各路径 Trace 数据收集正确性。细粒度检索阶段断言（vector/bm25/fusion/match_sentence 各自 duration_ms）已移至 `test_knowledge_pipeline.py`。原检索/LLM 耗时埋点（U12.1-U12.3）已合并入 Trace 测试（§6.14，✅） |
| ✅ | Trace 接口测试 | 接口+单元 | Service 层 23 用例（`test_trace_service.py`）+ API 层 17 用例（`test_trace_api.py`）= 40 用例，全部通过。覆盖 U13.1-U13.5, A9.1-A9.15 |
| ✅ | Trace 前端组件测试 | 前端组件 | TraceList 23 用例（C9.1-C9.7）+ TraceDetail 25 用例（C9.8-C9.12）= 48 用例，全部通过。覆盖渲染/空状态/搜索防抖/筛选/分页/行跳转/剪贴板复制/阶段卡片/JSON 展开折叠/返回导航 |
| ✅ | ECharts 图表组件测试 | 前端组件 | TrendChart + LatencyChart + TokenChart = 21 用例（C7.4-C7.7），全部通过。含空数据边界（ResizeObserver mock + ECharts mock） |
| ✅ | ECharts 统计接口测试 | 单元测试 | trend 聚合 2 + latency 分位数 3 + tokens 聚合 2 = 7 用例（test_admin_api.py TestAdminStatsChartsAPI），全部通过 |
| ✅ | 用户管理接口测试 | 接口+单元 | 用户列表 3 + 详情 3 + 禁用启用 3 + 重置密码 3 + 权限矩阵 8 = 20 用例（`test_admin_api.py`），全部通过 |
| ✅ | 用户管理前端组件测试 | 前端组件 | AdminUserList 15 用例（C8.1-C8.9）+ AdminUserDetail 16 用例（C8.10-C8.14）= 31 用例，全部通过。覆盖渲染/空状态/筛选/分页/行点击/操作菜单/错误处理/加载状态/导航/禁用启用 |
| ✅ | U8.2 Retrieval 超限截断测试 | 单元测试 | 3 用例（`test_history_memory.py` TestRetrievalBudgetTruncation）：超预算从低分丢弃 / 软上限跳过超大保留小 / score 降序验证。**P0 Bug 防御** |
| ✅ | U8.3 History + Retrieval 同时超限测试 | 单元测试 | 3 用例（`test_history_memory.py` TestHistoryRetrievalDualBudget）：双池独立截断 / 历史不侵蚀检索（P0防御） / 检索不侵蚀历史。**P0 Bug 防御** |
| ✅ | 全量回归测试 | 回归测试 | 运行 `regression_test.py` + `regression_multi_turn_test.py` 遍历完整测试集 |
| ✅ | 压测 | 性能测试 | Locust 4 场景（基准/日常/峰值/极限），P50≤3s / P99≤10s。**压测完成后据此设定限流阈值** |
| ✅ | 最终人工评分 | 人工评估 | 第 3 轮 10 题 × 4 维度评分，平均综合分 **4.71/5.0** ✅ 满足 ≥ 4.0 目标，较第 1 轮（4.38）↑+0.33，较第 2 轮（4.62）↑+0.09。Phase 5.5 治理效果验证通过。详见 `backend/tests/eval/human_eval_template.md` |

### 7.9 🚫 本阶段不做的

| 推迟项 | 排期 | 原因 |
|:---|:---|:---|
| Retrieval-aware Rewrite | Phase 6 | 当前 v2 信号词策略覆盖率 95.7%，盲区仅 1 个已知案例。方案 E 需要设计检索质量判据 + 实验调参闭环，Phase 5 目标是上线，不应引入新检索链路变量 |
| 细粒度问题类型分类 | Phase 6 | 3 类粗分类已覆盖核心场景 |
| Loki + Grafana 部署 | Phase 6（可选） | 结构化日志已就绪，`jq` 命令行可做基本聚合分析。生产环境可视需要部署 |
| Trace 瀑布图 | v2 | v1 先用 JSON 面板展示详情，后续迭代时间轴可视化 |
| 意图分类/响应模式饼图 | v2 | ECharts v1 先做趋势/延迟/Token 三个核心图表 |
| 用户审计日志 | v2 | `user_operations` 表 + 操作日志 API，v1 先做 CRUD + 角色管理 |
| User/Message/Chunk UUID 化 | 不做 | User 为 Admin 内部管理 + JWT 保护，暴露风险低；Message 仅通过 SSE 传输 + 高频写入，UUID 开销不值得；Chunk 为内部结构，不暴露给 API |
| 向量存储 metadata 改用 UUID | 不做 | 向量库中 `kb_id`/`doc_id` 保持 int 类型，UUID 仅在 API 边界转换，避免影响检索性能和现有数据迁移成本 |

---

## 8. Phase 5.5：知识库质量治理

**目标**：系统性治理知识库污染问题——RAG 系统将示例/测试/接口说明等引用性文本误认为事实答案返回。通过句级修辞过滤 + 三层证据审计 + DashScope Rerank 精排 + Chunk 元数据增强 + Evidence Review 门控，预计消除 85%+ 的污染问题。

> **架构决策**：详见 [ADR-019](decisions/ADR-019-句级修辞过滤.md) / [ADR-020](decisions/ADR-020-三层证据审计.md) / [ADR-021](decisions/ADR-021-EvidenceReview门控.md) / [ADR-024](decisions/ADR-024-粗排层.md)。

### 8.1 [后端] Prompt 陈述知识 vs 引用知识原则 ❌ 已移除

| 状态 | 任务 | 说明 |
|:---|:---|:---|
| ❌ | `SYSTEM_PROMPT_TEMPLATE` 升级 | ~~从简单的「请仅基于文档回答」升级为完整的陈述知识/引用知识判断框架。~~ 实验结果表明严格 Prompt 导致 Recall 显著下降（单轮 19/30 vs 旧版 30/30），已回退为旧版宽松 Prompt。「陈述 vs 引用」思想保留在证据审计后验检查中，不做生成前强约束 |

### 8.2 [后端] 句级修辞过滤

| 状态 | 任务 | 说明 |
|:---|:---|:---|
| ✅ | `detect_sentence_role()` | 基于 `_REFERENTIAL_PATTERNS` 规则层（显式标记 + 结构层 JSON/代码块检测）判断单个句子的修辞角色（assertive / referential） |
| ✅ | `filter_chunk_sentences()` | 对 chunk 内容做句级修辞过滤，仅保留陈述句。过滤后为空时回退到原始内容（宁可放过不可错杀） |
| ✅ | `knowledge_pipeline.py` 集成 | 在 `match_sentences()` 前插入 `filter_chunk_sentences()` 过滤步骤，解决 Chunk 内部混合陈述句和引用句的污染问题 |

### 8.3 [后端] 程序级三层证据审计

| 状态 | 任务 | 说明 |
|:---|:---|:---|
| ✅ | `evidence_auditor.py` 新模块 | 三层审计：引用存在性检查（第一层，`[来源N]` 标注检测）、来源一致性检查（第二层，文档集中度评估）、句级证据回溯（第三层，jieba 关键词匹配验证） |
| ✅ | `EvidenceAuditResult` 数据类 | 综合审计结果：`has_citation` / `consistency_status` / `evidence_status` / `confidence_level` / `confidence_note` |
| ✅ | `_compute_confidence()` 置信度计算 | 综合三层审计结果计算 high/medium/low 三级置信度。≥2 问题或 unsupported → low；1 问题 → medium；无问题 → high |
| ✅ | `chat_service.py` 集成 | LLM 流完成后、sources 事件构建阶段执行审计，审计失败不阻断主流程（降级跳过）。sources SSE 事件新增 `confidence` / `confidence_note` 字段 |

### 8.4 [前端] 置信度展示

| 状态 | 任务 | 说明 |
|:---|:---|:---|
| ✅ | `chat.js` store 适配 | sources SSE 事件中提取 `confidence` / `confidence_note` 字段，挂载到消息对象 |
| ✅ | `MessageItem.vue` 置信度警告组件 | 当证据审计发现 medium/low 置信度时展示黄色警告提示（low：「以下答案可能存在偏差，建议核实原始文档」；medium：「以下答案部分内容可能不准确，请注意核实」）+ 详细说明 |

### 8.5 [测试] Phase 5.5 测试

| 状态 | 任务 | 测试类型 | 说明 |
|:---|:---|:---|:---|
| ✅ | 修辞角色判断测试 | 单元测试 | `detect_sentence_role()` 12 用例（`TestDetectSentenceRole`）：陈述知识 2 + 引用知识标记 7 + JSON 结构 1 + 空/空白 2。覆盖示例/例如/测试用例/用户提问/系统返回/TODO/JSON 开头等模式 |
| ✅ | 句级修辞过滤测试 | 单元测试 | `filter_chunk_sentences()` 6 用例（`TestFilterChunkSentences`）：全陈述保留 / 混合过滤 / 全引用回退 / API 文档示例过滤 / 空内容 / 无句末标点 |
| ✅ | 三层证据审计测试 | 单元测试 | `test_evidence_auditor.py` 19 用例：引用存在性 5（`TestCitationExists`）+ 来源一致性 5（`TestSourceConsistency`）+ 句级证据回溯 7（`TestSentenceEvidence`）+ 置信度计算 4（`TestComputeConfidence`）+ 集成 4（`TestAuditEvidenceIntegration`） |
| ✅ | 污染问题回归测试 | 回归测试 | 使用已知失败案例（SSE 示例/测试用例/PRD 背景引用等）验证治理效果 | 2026-06-16 |
| ✅ | CoarseRanker 单元测试 | 单元测试 | 正常过滤/阈值边界/全通过/全拒绝/空候选/候选不足/降级（21 用例全部通过） | 2026-06-23 |
| ⬜ | CoarseRanker 集成测试 | 集成测试 | RRF→Coarse→Rerank 串联/粗排后不足 rerank_top_k/粗排失败降级 | 2026-06-23 |
| ✅ | Ragas 评估回归（粗排后新基线） | 评估 | 28 题全量跑通：Faithfulness 0.8436 / AR 0.9210 / CPragas 0.8556 / CtxRecall 0.9702，四项主指标全部达标（≥ 0.80）。CPdoc 从 0.52 升至 0.60（粗排效果验证）。报告：`backend/ragas_eval.md`。阈值已同步至 TESTING.md §5a.5 | 2026-06-23 |

### 8.6 [后端] 多阶段排序（CoarseRank + DashScope Rerank）

| 状态 | 任务 | 说明 |
|:---|:---|:---|
| ✅ | `coarse_ranker.py` 实现 | CoarseRanker 类：复用 query embedding 与候选 chunk embedding 做余弦相似度粗排，阈值过滤 + top_k 截断。零额外 API 成本，<1ms 延迟。详见 [ADR-024](decisions/ADR-024-粗排层.md) |
| ✅ | `config.py` 新增配置 | `COARSE_RANK_ENABLED` / `COARSE_RANK_THRESHOLD` / `COARSE_TOP_K` |
| ✅ | `knowledge_pipeline.py` 集成 | RRF 融合后、Rerank 前插入 `self._coarse_ranker.rank()` 步骤，粗排异常或候选不足时降级 |
| ✅ | `DashScopeReranker(BaseReranker)` 实现 | 调用 DashScope Rerank API，对粗排后结果做语义精排。支持指数退避重试（默认 3 次）、API 异常时内部降级为 RRF 排序截取。`config.py` 新增 `RERANK_BASE_URL`/`RERANK_MODEL`/`RERANK_MAX_RETRIES`/`RERANK_TIMEOUT` 配置项 |
| ✅ | `knowledge_pipeline.py` 固化 | `DashScopeReranker()` 为唯一 Reranker，已移除 `NoopReranker` 类及诊断开关 |
| ✅ | Reranker 测试 | 单元测试：API 响应解析（8 用例）+ 集成测试（12 用例）+ 配置测试（2 用例）+ 接口测试（2 用例）= 24 用例全部通过 |

### 8.7 [后端] Chunk 元数据增强（section_title / section_path）

> 章节元数据帮助 LLM 在判断修辞角色时有更多上下文。

| 状态 | 任务 | 说明 |
|:---|:---|:---|
| ✅ | `chunker.py` 标题层级感知 | Markdown 通过 `#`/`##`/`###` 正则提取标题；Word/PDF 通过 `parser.py` 解析标题样式。提取结果写入 `Chunk.metadata_` JSON 字段（`{"page": N}` → `{"page": N, "section_title": "...", "section_path": "..."}`） |
| ✅ | `tasks.py` `metas_batch` 扩展 | ChromaDB metadata 从 3 字段（`kb_id/doc_id/chunk_index`）扩展到 5 字段（+`section_title`/`section_path`） |
| ✅ | `retriever.py` `_parse_results()` 回填 | 从 ChromaDB metadata 提取 `section_title`/`section_path` 写入 `RetrievalResult`；`fusion.py` RRF 融合保留章节字段 |
| ✅ | `_format_chunk_reference()` 章节信息 | Prompt 中来源格式化从 `[来源1]（文档: API.md）` 升级为 `[来源1] 文档: API.md \| 章节: §6.1 SSE 事件完整格式` |

### 8.8 [后端] 章节号 BM25 增强

> 检测用户提问中的章节号，对 BM25 检索做加权 boost。

| 状态 | 任务 | 说明 |
|:---|:---|:---|
| ✅ | 章节号检测正则 | 检测用户提问中的章节号模式（「4.7」「8.2.1」「第四章」「§3.2」），支持 § 符号/中文章节/显式节编号/裸数字章节号四种模式 |
| ✅ | BM25 boost 逻辑 | 匹配到章节号时，对 `section_title`/`section_path` 匹配的 chunk 做 BM25 分数加权（正分 ×2.0，负分 ÷2.0）；缓存结构扩展 `section_info`，向后兼容旧缓存 |
| ✅ | BM25 缓存重构（ADR-023） | Redis/进程内缓存剔除 `contents` 字段（仅存 `tokens` + `doc_ids` + `section_info`）；新增 `_fetch_chunk_contents()` 按需批量取原文；`BM25_LOCAL_CACHE_MAX_CHUNKS=5000` 大 KB 跳过进程内缓存；新增 psutil 内存监控日志 |
| ✅ | BM25_MAX_CHUNKS 硬限制 | `BM25_MAX_CHUNKS=10000`：三层检查点（COUNT 先于 SELECT + Redis skipped/chunk_count 校验 + 进程内超限清除），超大 KB 完全跳过 BM25 检索仅依赖向量检索，512MB 容器不再 OOM |

### 8.9 🚫 本阶段不做的

| 推迟项 | 排期 | 原因 |
|:---|:---|:---|
| LLM 辅助修辞判断 | Phase 6 | 规则层覆盖高频场景，LLM 判断引入额外延迟和不确定性，ROI 待评估 |
| 审计结果持久化 | Phase 6 | 当前审计结果仅通过 SSE 实时推送，不入库。如需历史审计分析需新增 `evidence_audits` 表 |
| 自适应 `_REFERENTIAL_PATTERNS` | Phase 6 | 当前规则为手工维护的正则列表，后续可从审计日志中自动挖掘新模式 |
| 层级检索（Section 表 + 三阶段检索管道） | Phase 6 | 架构级改造，需新增 `sections` 表 + DB 迁移 + `chunker.py` 结构感知分块重构，工程量较大。Phase 5.5 先做元数据增强（§8.7）作为过渡方案 |

---

## 9. Phase 6：迭代优化

**目标**：高级功能、架构级改造、持续优化。不阻塞上线，按需求优先级逐个实现。不设时间线。

### 9.1 [高级功能] 高级功能（按优先级排序）

| 优先级 | 任务 | 来源 | 说明 |
|:---|:---|:---|:---|
| P0 | 层级检索（Section 表 + 三阶段检索管道） | Phase 6 | 扁平 `KB→Documents→Chunks` 升级为 `KB→Documents→Sections→Chunks`。新增 `sections` 表（`id, doc_id, kb_id, title, path, level, start_chunk_index, end_chunk_index`），`Chunk` 表新增 `section_id` 外键。`chunker.py` 替换为结构感知分块器。检索管道从 `VectorRetriever.search(kb_id)` 单步改为 `DocumentRetriever → SectionRetriever → ChunkRetriever` 三步漏斗 |
| P1 | 结构感知分块 | Phase 2/3 推迟 | Markdown 标题层级感知分块，提升长文档检索质量（层级检索的前置依赖） |
| P1 | LLM 摘要压缩 | Phase 4 推迟 | 超窗口消息 LLM 摘要，避免长对话 Token 溢出 |
| P2 | WebSocket 实时状态推送 | Phase 2 推迟 | 替换文档入库轮询，降低前端请求频率 |
| P2 | thinking_content 持久化 | Phase 3 推迟 | `messages.thinking_content` 落库 + 历史回看 |
| P2 | 消息状态机 | Phase 4 推迟 | partial/complete + PATCH 持久化，SSE 中断后可恢复半条消息 |
| P3 | reasoning_effort 前端可控 | Phase 3 推迟 | 前端选择思考深度（low/medium/high） |
| P3 | Resumable 分片上传 | Phase 2 推迟 | 大文件（>50MB）分片上传 + 断点续传 |
| P3 | 内容去重 | Phase 2 推迟 | 文档级去重，避免重复知识占用向量空间 |

---

## 10. 依赖关系

```
Phase 1 ──→ Phase 2 ──→ Phase 2.5 ──→ Phase 3 ──→ Phase 4 ──→ Phase 5 ──→ Phase 5.5 ──→ Phase 6
  │            │            │              │            │            │            │              │
  └─ 测试 ──→  └─ 测试 ──→  └─ 测试 ────→ └─ 测试 ──→  └─ 测试 ──→  └─ 测试 ──→  └─ 测试
     (已测)      (已测)  (权限测试)     (含人工评分1) (含人工评分2)  (全量+压测)  (污染回归)    (不设时限)
```





### 10.1 [规范] 测试准入规则

**每个 Phase 的测试必须在该 Phase 功能完成后立即执行，作为下一 Phase 的准入条件：**

- Phase N 功能完成 → 执行 Phase N 测试 → 全部通过 → 方可进入 Phase N+1
- 回归测试集随 Phase 迭代持续扩充，每次提交运行全量回归

---

## 11. 相关文档

- [产品需求文档](PRD.md)
- [架构设计文档](ARCHITECTURE.md)
- [开发指南](DEVELOPMENT.md)
- [测试策略](tests/TESTING.md)
- [测试用例跟踪](tests/TEST_CASES.md)

- [UI 设计规范](../frontend/docs/UIDESIGN.md)
