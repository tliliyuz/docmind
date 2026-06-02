# ROADMAP — 开发排期

| 属性 | 值 |
|:---|:---|
| 文档版本 | v0.22 |
| 最后更新 | 2026-06-02 |
| 作者 | yuz |
| 状态 | 进行中 |

---

## 1. 总体时间线

**预计总工期**：3-4 周（80-120 小时）

```
Phase 1          Phase 2          Phase 3          Phase 4        Phase 5
骨架搭建         文档入库          核心问答          会话 & 记忆     打磨上线
3-4天            3-4天            3-4天            2-3天          2-3天
  ├────────────────┼────────────────┼────────────────┼──────────────┤
Week 1            Week 2           Week 2-3         Week 3         Week 3-4
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
| ✅ | ChromaDB 连接 | collection 创建与管理 |
| ✅ | JWT 认证 | 注册/登录接口 + 中间件 |
| ✅ | 前端登录页 | LoginPage.vue + 路由骨架 |
| ✅ | 前端布局框架 | AppLayout + Sidebar 空壳 |

### 2.1 Phase 1 测试

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

### 3.1 后端：知识库 CRUD + 文档管理

| 状态 | 任务 | 说明 | 依赖决策 |
|:---|:---|:---|:---|
| ✅ | 知识库 CRUD 接口 | POST/GET/PUT/DELETE `/api/knowledge-bases`，名称用户级唯一 `(user_id, name)`，DELETE 当前阶段仅标记 `status=deleting` + 返回 202（Celery 异步物理删除后续实现） | KB 级异步批量清理 |
| ✅ | 文档状态枚举 | `DocumentStatus(str, Enum)` — 10 状态 + `TERMINAL_STATUSES` + `is_terminal()`，ORM/Schema/API 统一使用 | 约束一 |
| ✅ | 文档上传 API | POST `/documents`（multipart + force 参数），唯一性检查 `(kb_id, filename)` | 约束二、约束四 |
| ✅ | 批量上传 API | POST `/documents/batch-upload`（多文件，部分成功返回） | 决策 #13 |
| ✅ | 重新处理 API | POST `/documents/{id}/reprocess`（仅 `partial_failed`/`failed` 允许） | 决策 #12 |
| ✅ | 文档列表/详情 API | GET 文档支持 status/filename 筛选 + sort_by/order，分块接口分页（仅 owner/admin） | 决策 #14、#18、#19 |
| ✅ | 文档删除 API | DELETE 异步清理（标记 deleting → Celery 清理向量+文件 → 物理 DELETE，FK CASCADE 清 chunks） | 决策 #10、#11 |
| ✅ | 文件存储 | `uploads/{kb_id}/{doc_id}/{uuid}_{sanitized_filename}` 目录结构 | 决策 #5 |

### 3.2 后端：Celery 异步入库流水线

| 状态 | 任务 | 说明 | 依赖决策 |
|:---|:---|:---|:---|
| ✅ | Celery 幂等锁 | Redis `SET idempotency_key:{doc_id}:{task_type} EX 600 NX`，处理中拒绝重复入队 | 约束二 |
| ✅ | 文档解析 | PyPDF2 + python-docx，部分容错（<20% warning / 20-50% partial / >50% failed） | 决策 #8 |
| ✅ | 智能分块 | `RecursiveCharacterTextSplitter`（800-1200 chars，分隔符优先级 `\n\n`→`\n`→`。！？`），字符估算 token | 决策 #1、#2 |
| ✅ | Embedding 向量化 | DashScope text-embedding-v3，batch_size=20，max_retries=5 指数退避，批次级 checkpoint + token 回写 | 决策 #7 |
| ✅ | ChromaDB 批量写入 | batch_size=100，禁止单条循环；失败时 `collection.delete(where={doc_id})` 全清 + 标记 FAILED | 决策 #3 |
| ✅ | chunk_count 事务更新 | 全部 batch 成功后一次性事务更新 `documents.chunk_count` + `kb.chunk_count`，token_count 回写覆盖估算值 | 决策 #4 |
| ✅ | 阶段化状态机 | `uploaded → parsing → chunking → embedding → vector_storing → completed`，每阶段更新 `current_stage` + `last_success_batch` | 决策 #9 |

### 3.3 前端

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

### 3.4 本阶段不做的

| 推迟项 | 排期 | 原因 |
|:---|:---|:---|
| 结构感知分块（Markdown 标题层级） | Phase 3 | Phase 2 先跑通固定大小，后续优化 |
| `.doc` 格式支持 | 不做 | 维护成本极高，前端提示「请先转换为 .docx」 |
| WebSocket 实时状态推送 | Phase 5 | 轮询已满足需求 |
| Resumable 分片上传 | Phase 5+ | 50MB 以内 multipart 足够 |
| 内容去重 | Phase 5+ | Phase 2 仅做文件名唯一性检查 |

### 3.5 Phase 2 测试

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

### 4.1 业务规则文档

| 状态 | 任务 | 说明 |
|:---|:---|:---|
| ✅ | PRD.md §5 可见性模型 | ownership/visibility 规则 + CRUD 权限矩阵 + 检索范围 |
| ✅ | ARCHITECTURE.md §7.6 | 弱混合模式设计决策 |
| ✅ | DATABASE.md §2.2 | `visibility` 列定义 |
| ✅ | API.md §3/§9 | 接口权限速查表更新 + public KB 列表端点 |
| ✅ | FRONTEND.md §2.1/§4.5/§5.7 | 路由 + 侧边栏 + 公共 KB 浏览页 |
| ✅ | CLAUDE.md | 权限分离约束 |
| ✅ | CHANGE.md | 文档变更记录 |

### 4.2 后端实现

| 状态 | 任务 | 说明 |
|:---|:---|:---|
| ✅ | 数据库迁移 | `knowledge_bases` 表新增 `visibility ENUM('private','public') DEFAULT 'private'`（迁移 `8fa3ea12b75e`） |
| ✅ | ORM 模型更新 | `KnowledgeBase` 模型新增 `visibility` 字段 |
| ✅ | Pydantic Schema 更新 | `KnowledgeBaseCreate` 新增 `visibility` 可选字段（默认 `private`）；`KnowledgeBaseUpdate` 新增 `visibility` 可选字段；`KnowledgeBaseResponse` 新增 `visibility` 字段；新增 `PublicKnowledgeBaseResponse`（含 `username`）和 `PublicKnowledgeBaseListResponse` |
| ✅ | KB Service 权限重构 | `get_kb()` 增加 visibility 判断：public KB 允许非 owner 读取；`list_kbs()` 仅返回用户自己的 KB（不变）；新增 `list_public_kbs()` 返回所有 public+active KB（JOIN users 含 username） |
| ✅ | API 端点更新 | `POST /api/knowledge-bases` 支持 visibility 参数；`GET /api/knowledge-bases/{id}` public KB 对非 owner 放行；`PUT /api/knowledge-bases/{id}` owner + admin 可修改含 visibility；新增 `GET /api/knowledge-bases/public` 端点 |
| ✅ | 文档接口权限更新 | `_check_kb_ownership` 新增 `owner_only` 参数：上传/reprocess 仅 owner；查看/分块/删除 owner + admin；`TestDocumentPermissionMatrix` 18 用例覆盖全部权限组合 |

### 4.3 前端实现

| 状态 | 任务 | 说明 |
|:---|:---|:---|
| ✅ | 创建 KB 弹窗增加 visibility 选择 | 新建/编辑知识库弹窗增加 `private`/`public` 切换（Radio 或 Switch） |
| ✅ | KB 卡片增加 visibility 标识 | 卡片上显示 public/private 标签或图标 |
| ✅ | 公共知识库页面 | `PublicKnowledgeList.vue`（`/knowledge-bases/public`）：卡片网格 + 搜索 + owner 用户名展示，无新建/编辑/删除按钮 |
| ✅ | Sidebar 导航更新 | 新增「公共知识库」入口（所有用户可见），位于「我的知识库」下方 |
| ✅ | 路由更新 | 新增 `/knowledge-bases/public` 路由 |
| ✅ | KB 详情页适配 | 非 owner 访问 public KB 时：隐藏文档上传区、文档表格、编辑/删除按钮；显示「开始问答」入口 |
| ✅ | Pinia Store 更新 | `knowledge.js` 新增 `fetchPublicKbList()` action |

### 4.4 测试

| 状态 | 任务 | 测试类型 | 说明 |
|:---|:---|:---|:---|
| ✅ | visibility 字段校验测试 | 单元测试 | `TestKnowledgeBaseCreateVisibility`（5 用例）+ `TestKnowledgeBaseUpdateVisibility`（4 用例）+ `TestKnowledgeBaseResponseVisibility`（1 用例） |
| ✅ | KB 权限矩阵接口测试 | 接口测试 | `TestVisibilityPermissionMatrix`（6 用例）：public KB 非 owner 可读/不可写；private KB 非 owner 拒绝；admin 全局读写 |
| ✅ | 公共 KB 列表接口测试 | 接口测试 | `TestPublicKbList`（5 用例）：分页 + 仅返回 public+active + username + 未认证拒绝 |
| ✅ | 前端公共 KB 页组件测试 | 组件测试 | PublicKnowledgeList 渲染 + 无编辑/删除/新建按钮（10 用例） |

### 4.5 本阶段不做的

| 推迟项 | 原因 |
|:---|:---|
| shared（指定用户共享） | 需要 ACL 表 + 邀请机制，复杂度爆炸 |
| 部门管理员 / 角色扩展 | 当前无真实需求 |
| 协作编辑、版本控制 | 那是 Notion，不是知识库问答平台 |
| Admin 在 KB 详情页的管理权限（查看文档列表/编辑/删除） | 延后到 Phase 5，随 Admin 后端接口一并实现。当前 `KnowledgeDetail.vue` 仅按 `user_id` 判断 owner，admin 访问他人 KB 时暂为只读 |

---

## 5. Phase 3：核心问答（3-4 天）

**目标**：单轮问答全链路跑通，SSE 流式输出，前端展示答案及引用来源。

### 5.1 后端：RAG 检索管线

| 状态 | 任务 | 说明 | 依赖决策 |
|:---|:---|:---|:---|
| ✅ | 向量检索器 | ChromaDB `collection.query()` 语义检索，`where={"kb_id": kb_id}` 过滤，返回 top_k=10 | 决策 #15、#21 |
| ✅ | BM25 关键词检索器 | `rank-bm25` (BM25Okapi) + `jieba.lcut` 分词，每个 KB 独立索引 | 决策 #16 |
| ✅ | BM25 索引缓存 | Redis `bm25_tokens:{kb_id}` 存储 `tokenized_corpus` + `doc_ids`（JSON），TTL=300s；文档终态后 Celery 触发重建；查询时未命中则懒加载重建 | 决策 #16 |
| ✅ | RRF 多路融合 | `score(d) = Σ 1/(k+rank_i(d))`，k=60，单路为空时仅返回另一路结果 | 决策 #17 |
| ✅ | NoopReranker | 占位实现：按 chunk 长度升序排列后截取 top_k=5，保证短 chunk（高信息密度）优先 | 决策 #18 |
| ✅ | Prompt 组装 | 检索结果拼接 + 用户问题，软上限预算控制（超预算时尝试下一个更短 chunk 而非 break），按 chunk 长度升序择优填充 | 决策 #19 |
| ✅ | LLM 调用 | DeepSeek API（OpenAI 兼容），流式 `chat/completions`，`extra_body={"thinking":{"type":"enabled/disabled"}}` 控制思考开关；仅 `deep_thinking=true` 时传 `reasoning_effort="high"`，解析 `content` + `reasoning_content` | 决策 #20 |
| ✅ | ChromaDB metadata 类型一致性 | metadata 保持数值型，入库/查询两端统一使用 int 类型 `kb_id/doc_id/chunk_index`，显式 `int()` 转换保障 | 决策 #21 |

### 5.2 后端：Chat API 与 SSE

| 状态 | 任务 | 说明 | 依赖决策 |
|:---|:---|:---|:---|
| ✅ | ChatRequest Schema | Pydantic model：`conversation_id: int\|None`、`kb_id: int`、`question: str`（≤2000字符）、`deep_thinking: bool=False` | — |
| ✅ | Chat Service 核心流程 | `chat_service.chat()` — 检索 → RRF → Rerank → Prompt → LLM SSE 流式，阶段化错误处理（检索失败 E4003 / LLM失败 E4002） | — |
| ✅ | SSE 流式输出 | 手动 `StreamingResponse`（不用 sse-starlette），事件类型：meta → thinking → message → sources → finish → error，15s 心跳注释帧 `: ping\n\n` | 决策 #22 |
| ✅ | 会话自动创建 | `conversation_id=null` 时自动创建会话（`kb_id` 记录问答目标 KB），不注入历史消息（`history=[]`），数据结构兼容 Phase 4 | 决策 #23 |
| ✅ | 标题自动生成 | 截取用户问题前 12 字（`question[:12]`），去除标点。首轮问答后 `event: finish` 返回 title；后续轮次不更新标题 | 决策 #24 |
| ✅ | thinking_content 传输 | `deep_thinking=true` 时解析 DeepSeek `reasoning_content` → `event: thinking` 流式推送。**不落库**（`messages.thinking_content=null`），仅前端实时展示 | 决策 #25 |
| ✅ | 问答检索权限 | `POST /api/chat` 校验 kb_id：private KB 仅 owner + admin 可检索，public KB 所有用户可检索 | — |
| ✅ | KB 选择器接口 | `GET /api/knowledge-bases/selectable` 返回 `{"mine": [...], "public": [...]}`（mine=用户全部 KB，public=他人 public KB），前端直接渲染 `<el-option-group>` | 决策 #26 |
| ✅ | Chat Router 注册 | `main.py` 注册 `chat_router`（`prefix="/api"`） | — |

### 5.3 前端：问答界面

| 状态 | 任务 | 说明 | 依赖决策 |
|:---|:---|:---|:---|
| ⬜ | KB 选择器 | ChatPage 顶部 `<el-select>` + `<el-option-group>`（「我的知识库」/「公共知识库」），数据来源 `GET /api/knowledge-bases/selectable`，默认选中最近使用的 KB | 决策 #26 |
| ⬜ | ChatInput 组件 | 输入框（≤2000字符计数字）+ Enter 发送 / Shift+Enter 换行 + 深度思考开关 + 发送中切换为「停止生成」按钮 | FRONTEND.md §4.3 |
| ⬜ | MessageList 组件 | 消息列表：用户气泡 + AI 气泡（Markdown 实时渲染）+ thinking 折叠面板 + sources 引用卡片；自动滚动到底部，手动上滚时显示「新消息」浮动按钮 | FRONTEND.md §4.4 |
| ⬜ | MessageItem 组件 | 单条消息渲染：角色头像 + 内容区（markdown-it 渲染）+ thinking 黄色折叠面板 + sources 文档链接（点击预览分块内容） | — |
| ⬜ | WelcomeScreen 组件 | 空消息列表时展示：Logo + 欢迎语 + 快捷问题卡片（点击自动填入输入框并发送） | FRONTEND.md §4.6 |
| ⬜ | SSE 解析工具 `sse.js` | `fetch` + `ReadableStream` 解析 SSE 事件流（`event:` 行 + `data:` 行），支持 6 种事件类型 + 格式异常容错 + 心跳帧忽略 | 决策 #22 |
| ⬜ | Markdown 渲染工具 `markdown.js` | `markdown-it` 封装，代码块高亮 + 一键复制 + 安全过滤（XSS 防护） | — |
| ⬜ | ChatStore (Pinia) | 消息列表状态 + `sendMessage()` SSE 流式消费 + `abort()` 中断 + `conversation_id` 管理 | — |
| ⬜ | Chat API 封装 `api/chat.js` | `sendMessage(params, onEvent, onError)` — fetch SSE 流，回调式事件分发 | — |
| ⬜ | 来源引用展示 | `event: sources` 事件在消息底部渲染引用文档卡片（doc_name + score + page），点击展开分块预览弹窗 | — |
| ⬜ | Sidebar 会话入口适配 | 会话区域先展示空态（Phase 4 实现 CRUD），「新建对话」按钮清空消息列表 + conversation_id=null | — |

### 5.4 本阶段不做的

| 推迟项 | 排期 | 原因 |
|:---|:---|:---|
| 结构感知分块（Markdown 标题层级） | Phase 5+ | Phase 3 继续用固定大小分块，检索质量已够用 |
| 意图识别（知识查询/闲聊分类） | Phase 5 | 单轮问答先跑通核心链路 |
| 问题重写（多轮上下文补全） | Phase 4 | Phase 3 仅单轮，不注入历史 |
| 会话 CRUD（列表/重命名/删除） | Phase 4 | Phase 3 仅自动创建 + 标题生成 |
| DashScope Rerank API | Phase 3+ | 先用 NoopReranker 占位跑通链路 |
| 对话历史注入 Prompt | Phase 4 | Phase 3 `history=[]`，数据结构兼容 Phase 4 |
| thinking_content 持久化 | Phase 5+ | Phase 3 仅流式展示不落库；SSE 中断半条消息持久化见 Phase 4 消息状态机 |
| reasoning_effort 前端可控 | Phase 5+ | Phase 3 后端在 `deep_thinking=true` 时固定 `"high"`，前端仅 deep_thinking 开关 |

### 5.5 Phase 3 测试

> Phase 3 功能完成后立即执行，不推迟到后续阶段。

| 状态 | 任务 | 测试类型 | 说明 |
|:---|:---|:---|:---|
| ✅ | 向量检索器单元测试 | 单元测试 | ChromaDB `query()` Mock：返回 top_k 结果 + `where` kb_id 过滤 + 空结果处理（18 用例） |
| ✅ | BM25 检索器单元测试 | 单元测试 | BM25Okapi 初始化 + `get_scores()` 排序 + jieba 分词 + 空语料处理（12 用例） |
| ✅ | BM25 索引缓存测试 | 单元测试 | Redis 缓存命中/未命中懒加载/Celery 触发重建/缓存失效（8 用例） |
| ✅ | RRF 融合算法测试 | 单元测试 | k=60 标准合并 / 单路为空 / 两路均空 / 排名相同处理（14 用例） |
| ✅ | NoopReranker 测试 | 单元测试 | 按长度排序 + top_k 截取 + 输入不足 top_k（12 用例） |
| ✅ | Prompt 模板测试 | 单元测试 | 检索结果拼接 / 软上限预算控制 / chunk 择优填充 / 空检索结果处理（15 用例） |
| ⬜ | Chat Service 单元测试 | 单元测试 | 检索→RRF→Rerank→Prompt→LLM 全链路 Mock（8 用例） |
| ✅ | LLM 调用与 thinking 解析测试 | 单元测试 | DeepSeek API 流式响应 Mock / `reasoning_content` 解析 / `content` 解析（15 用例） |
| ⬜ | SSE 流式输出测试 | 单元测试 | `StreamingResponse` 事件序列 / 心跳帧 / 中途错误 / 客户端断开（8 用例） |
| ⬜ | 问答 SSE 接口测试 | 接口测试 | POST `/api/chat` SSE 事件序列（meta→message→sources→finish）+ 错误码（E4001/E4005/E1001）+ kb_id 可见性校验（private KB 非 owner 拒绝）+ deep_thinking 开关（13 用例） |
| ⬜ | KB 选择器接口测试 | 接口测试 | GET `/knowledge-bases/selectable` 返回 mine+public 分组 + 不重复 + 仅返回 active KB（6 用例） |
| ⬜ | ChatRequest Schema 校验测试 | 单元测试 | question 空/超长 + kb_id 缺失 + conversation_id 类型 + deep_thinking 默认值（6 用例） |
| ⬜ | 前端 SSE 解析工具测试 | 单元测试 | `sse.js` 各 event 类型解析 + 异常格式容错 + 心跳帧忽略 + 多行 data 拼接（12 用例） |
| ⬜ | 前端 Markdown 渲染工具测试 | 单元测试 | markdown-it 渲染 + 代码块高亮 + XSS 过滤 + 链接处理（6 用例） |
| ⬜ | 前端 ChatInput 组件测试 | 组件测试 | 输入/发送/停止/Enter/Shift+Enter/字数计数/空内容拒绝/deep_thinking 开关（10 用例） |
| ⬜ | 前端 MessageList 组件测试 | 组件测试 | 消息气泡排列 / 自动滚动 / 手动上滚「新消息」按钮 / 空状态（8 用例） |
| ⬜ | 前端 MessageItem 组件测试 | 组件测试 | Markdown 渲染 / thinking 折叠面板 / sources 引用卡片 / 重新生成按钮（8 用例） |
| ⬜ | 前端 WelcomeScreen 组件测试 | 组件测试 | 欢迎语渲染 + 快捷问题卡片点击填入输入框（5 用例） |
| ⬜ | 前端 ChatPage 集成测试 | 组件测试 | 完整问答流程：选择KB→输入问题→SSE流式渲染→sources展示→停止按钮（8 用例） |
| ⬜ | 人工答案评分（第 1 轮） | 人工评估 | 10 题 × 4 维度评分表（见 TESTING.md §6） |
| ⬜ | 离线检索评估 | 检索评估 | BM25 vs 向量 vs RRF 的 Recall@5/MRR 对比报告（见 TESTING.md §5） |
| ⬜ | 回归测试集初版建立 | 回归测试 | 25-30 个固定问题 + 期望文档标注（见 TESTING.md §7） |

### 5.6 关键决策索引

| # | 决策 | 文档位置 |
|:---|:---|:---|
| 15 | 向量检索：ChromaDB `query()` + `where={"kb_id": kb_id}` metadata 过滤，top_k=10 | ARCHITECTURE.md §5.1.1 |
| 16 | BM25 索引生命周期：终态后 Celery 触发重建 + Redis 缓存 `tokenized_corpus` + 查询时懒加载 BM25Okapi 实例化 | ARCHITECTURE.md §5.1.1, §6.2 |
| 17 | RRF 融合：k=60，单路为空时仅返回另一路 | ARCHITECTURE.md §6.3 |
| 18 | NoopReranker：按 chunk 长度升序排列后截取 top_k=5 | ARCHITECTURE.md §7.3 |
| 19 | Prompt 预算：软上限 + 按长度择优填充，chunking 阶段固定 chunk_size 不二次裁剪 | ARCHITECTURE.md §5.1.2 |
| 20 | LLM：DeepSeek API（OpenAI 兼容），流式 `chat/completions`，通过 `extra_body={"thinking":{"type":"enabled/disabled"}}` 控制思考开关；仅开启 thinking 时传 `reasoning_effort="high"` 控制强度。**注意**：DeepSeek 默认 thinking=enabled，关闭时须显式传 disabled 且不传 reasoning_effort | ARCHITECTURE.md §5.1.3 |
| 21 | ChromaDB metadata 类型一致：保持 int 类型，入库/查询两端统一 | ARCHITECTURE.md §7.1 |
| 22 | SSE：手动 `StreamingResponse`，6 事件类型 + 15s 心跳注释帧 `: ping\n\n` | ARCHITECTURE.md §5.1.3, API.md §6 |
| 23 | 会话：Phase 3 自动创建（conversation_id=null），不注入历史（history=[]），数据结构兼容 Phase 4 | ARCHITECTURE.md §5.1 |
| 24 | 标题：截取用户问题前 12 字，首轮 `event: finish` 返回 | ARCHITECTURE.md §5.1 |
| 25 | thinking_content：`event: thinking` 流式推送，不落库（`messages.thinking_content=null`），仅前端实时展示。`deep_thinking` 通过 `extra_body` 映射到 DeepSeek `thinking` 参数 | API.md §6.1, ARCHITECTURE.md §5.1.3 |
| 26 | KB 选择器：`GET /knowledge-bases/selectable` 返回 `{mine, public}` 分组，前端 `<el-option-group>` 渲染 | API.md §3, FRONTEND.md §4.1 |

---

## 6. Phase 4：会话 & 记忆（2-3 天）

**目标**：多轮对话能力，会话管理，滑动窗口记忆。

| 状态 | 任务 | 说明 |
|:---|:---|:---|
| ⬜ | 会话 CRUD | 创建/列表/详情/重命名/删除 |
| ⬜ | 多轮对话上下文 | service 层获取历史消息注入 context |
| ⬜ | 滑动窗口记忆 | 保留最近 10 轮，超出 LLM 摘要压缩 |
| ⬜ | 问题重写 | LLM 结合对话历史补全指代和上下文 |
| ⬜ | 消息状态机 | `messages.status` 字段（`complete`/`partial`），SSE 中断时前端 PATCH 保存已接收内容 |
| ⬜ | 前端会话列表 | Sidebar 展示会话列表 + 切换 |

### 6.1 Phase 4 测试

| 状态 | 任务 | 测试类型 | 说明 |
|:---|:---|:---|:---|
| ⬜ | 会话 CRUD API 接口测试 | 接口测试 | POST/GET/PUT/DELETE 会话正常流程 + 错误码（E3001/E3002） |
| ⬜ | 消息状态机接口测试 | 接口测试 | SSE 中断时前端 PATCH 保存 partial 消息 / 重连后加载历史含 partial 标记 |
| ⬜ | 滑动窗口记忆测试 | 单元测试 | 保留最近 10 轮、超出 LLM 摘要压缩 |
| ⬜ | 问题重写测试 | 单元测试 | LLM 结合对话历史补全指代 |
| ⬜ | 前端会话列表组件测试 | 组件测试 | Sidebar 会话列表渲染、切换、重命名、删除 |
| ⬜ | 人工答案评分（第 2 轮） | 人工评估 | 对比第 1 轮，验证记忆和重写提升效果 |

---

## 7. Phase 5：打磨上线（2-3 天）

**目标**：体验完善，管理后台，错误处理，部署就绪。

| 状态 | 任务 | 说明 |
|:---|:---|:---|
| ⬜ | 意图识别 | LLM 分类：知识查询 / 闲聊，闲聊直接回复不检索 |
| ⬜ | Admin 后端接口实现 | `GET /api/admin/knowledge-bases`（全部知识库）+ `GET /api/admin/documents`（全部文档）+ `GET /api/admin/stats`（概览统计）+ admin router 注册 |
| ⬜ | Admin 前端联调 | `/admin/knowledge`、`/admin/documents`、`/admin/stats` 对接后端接口 |
| ⬜ | Admin 访问 KB 详情页权限 | `KnowledgeDetail.vue` `isOwner` 逻辑扩展为 `isOwner \|\| isAdmin`：admin 访问他人 KB 时可查看文档列表、编辑 KB 元数据（含 visibility）、删除 KB/文档，但不可上传文档（PRD §5.4） |
| ⬜ | 错误处理 | 全局异常处理 + 统一错误码 |
| ⬜ | Refresh Token 机制 | access_token（15-30min）+ refresh_token（7天，存 MySQL/Redis），支持 Rotation（刷新后旧 token 失效）、主动吊销（改密/强制下线） |
| ⬜ | 限流 | 简单 IP/用户级频率限制 |
| ⬜ | 日志 | 结构化日志 + 关键节点埋点 |
| ⬜ | README + 部署文档 | 项目说明 + Docker Compose 部署方案 |
| ⬜ | 简历描述文案 | 项目亮点提炼，技术选型理由 |

### 7.1 Phase 5 测试

| 状态 | 任务 | 测试类型 | 说明 |
|:---|:---|:---|:---|
| ⬜ | 全量回归测试 | 回归测试 | 运行 `regression_test.py` 遍历完整测试集，检查召回/非空/来源/SSE/错误率 |
| ⬜ | 压测 | 性能测试 | Locust 4 场景（基准/日常/峰值/极限），P50≤3s / P99≤10s |
| ⬜ | 最终人工评分 | 人工评估 | 最终 10 题 × 4 维度评分，平均综合分 ≥ 4.0 |
| ⬜ | 限流测试 | 接口测试 | IP/用户级频率限制生效验证 |
| ⬜ | Refresh Token 测试 | 接口测试 | Token 刷新 / Rotation（旧 token 失效）/ 主动吊销 |

---

## 8. 依赖关系

```
Phase 1 ──→ Phase 2 ──→ Phase 2.5 ──→ Phase 3 ──→ Phase 4 ──→ Phase 5
  │            │            │              │            │            │
  └─ 测试 ──→  └─ 测试 ──→  └─ 测试 ────→ └─ 测试 ──→  └─ 测试 ──→  └─ 测试
     (已测)      (含离线评估)  (权限测试)     (含人工评分1) (含人工评分2)  (全量+压测)
```

- Phase 2.5 在 Phase 2 完成后立即执行，Phase 3 问答实现前完成——检索范围必须早于问答接口确定
- Phase 3 和 Phase 4 可部分并行：核心问答的单轮链路可与会话 CRUD 同时开发
- Phase 4 的问题重写依赖 Phase 3 的 LLM 调用能力
- Phase 5 在所有功能就绪后进行

### 8.1 测试准入规则

**每个 Phase 的测试必须在该 Phase 功能完成后立即执行，作为下一 Phase 的准入条件：**

- Phase N 功能完成 → 执行 Phase N 测试 → 全部通过 → 方可进入 Phase N+1
- 回归测试集随 Phase 迭代持续扩充，每次提交运行全量回归

---

## 9. 相关文档

- [产品需求文档](PRD.md)
- [架构设计文档](ARCHITECTURE.md)
- [开发指南](DEVELOPMENT.md)
- [测试策略](TESTING.md)
- [测试用例跟踪](TEST_CASES.md)
- [UI 设计规范](../frontend/docs/UIDESIGN.md)
