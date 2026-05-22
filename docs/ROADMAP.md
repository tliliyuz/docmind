# ROADMAP — 开发排期

| 属性 | 值 |
|:---|:---|
| 文档版本 | v0.13 |
| 最后更新 | 2026-05-22 |
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

### 3.6 Phase 2 专项测试

| 状态 | 任务 | 测试类型 | 说明 |
|:---|:---|:---|:---|
| ⬜ | 离线检索评估 | 检索评估 | BM25 vs 向量 vs RRF 的 Recall@5/MRR 对比报告（见 TESTING.md §2） |
| ⬜ | 回归测试集初版建立 | 回归测试 | 25-30 个固定问题 + 期望文档标注（见 TESTING.md §4） |

---

## 4. Phase 3：核心问答（3-4 天）

**目标**：单轮问答全链路跑通，SSE 流式输出，前端展示答案及引用来源。

| 状态 | 任务 | 说明 |
|:---|:---|:---|
| ⬜ | 向量检索 | ChromaDB 语义检索 |
| ⬜ | BM25 关键词检索 | rank-bm25 (BM25Okapi) + jieba 分词 |
| ⬜ | RRF 多路融合 | k=60 合并两路结果 |
| ⬜ | NoopReranker | 占位实现，截取 top_k |
| ⬜ | Prompt 组装 | 拼接检索结果 + 用户问题 |
| ⬜ | LLM 调用 | DeepSeek API，含 thinking_content |
| ⬜ | SSE 流式输出 | sse-starlette，event 类型 meta/thinking/message/sources/finish/error |
| ⬜ | 前端问答界面 | ChatPage + MessageList + ChatInput + SSE 解析 |
| ⬜ | 来源引用展示 | 答案末尾展示引用文档名 |

### 4.1 Phase 3 测试

| 状态 | 任务 | 测试类型 | 说明 |
|:---|:---|:---|:---|
| ⬜ | 检索器单元测试 | 单元测试 | 向量检索 / BM25 检索各自返回正确数量 + metadata 过滤 |
| ⬜ | RRF 融合算法测试 | 单元测试 | k=60 合并两路结果的排序正确性 |
| ⬜ | 问答 SSE 接口测试 | 接口测试 | POST `/api/chat` SSE 事件序列（meta→message→sources→finish）+ 错误码（E4001/E4005） |
| ⬜ | Prompt 模板测试 | 单元测试 | 检索结果拼接、token 预算控制 |
| ⬜ | NoopReranker 测试 | 单元测试 | 截取 top_k 行为正确 |
| ⬜ | 前端 ChatPage 组件测试 | 组件测试 | 消息发送、SSE 流式渲染、停止按钮 |
| ⬜ | 前端 SSE 解析工具测试 | 单元测试 | `sse.js` 事件解析（各 event 类型 + 异常格式） |
| ⬜ | 前端来源引用展示测试 | 组件测试 | MessageItem 中来源文档链接渲染 |
| ⬜ | 人工答案评分（第 1 轮） | 人工评估 | 10 题 × 4 维度评分表（见 TESTING.md §3） |

---

## 5. Phase 4：会话 & 记忆（2-3 天）

**目标**：多轮对话能力，会话管理，滑动窗口记忆。

| 状态 | 任务 | 说明 |
|:---|:---|:---|
| ⬜ | 会话 CRUD | 创建/列表/详情/重命名/删除 |
| ⬜ | 多轮对话上下文 | service 层获取历史消息注入 context |
| ⬜ | 滑动窗口记忆 | 保留最近 10 轮，超出 LLM 摘要压缩 |
| ⬜ | 问题重写 | LLM 结合对话历史补全指代和上下文 |
| ⬜ | 前端会话列表 | Sidebar 展示会话列表 + 切换 |

### 5.1 Phase 4 测试

| 状态 | 任务 | 测试类型 | 说明 |
|:---|:---|:---|:---|
| ⬜ | 会话 CRUD API 接口测试 | 接口测试 | POST/GET/PUT/DELETE 会话正常流程 + 错误码（E3001/E3002） |
| ⬜ | 滑动窗口记忆测试 | 单元测试 | 保留最近 10 轮、超出 LLM 摘要压缩 |
| ⬜ | 问题重写测试 | 单元测试 | LLM 结合对话历史补全指代 |
| ⬜ | 前端会话列表组件测试 | 组件测试 | Sidebar 会话列表渲染、切换、重命名、删除 |
| ⬜ | 人工答案评分（第 2 轮） | 人工评估 | 对比第 1 轮，验证记忆和重写提升效果 |

---

## 6. Phase 5：打磨上线（2-3 天）

**目标**：体验完善，管理后台，错误处理，部署就绪。

| 状态 | 任务 | 说明 |
|:---|:---|:---|
| ⬜ | 意图识别 | LLM 分类：知识查询 / 闲聊，闲聊直接回复不检索 |
| ⬜ | Admin 后端接口实现 | `GET /api/admin/knowledge-bases`（全部知识库）+ `GET /api/admin/documents`（全部文档）+ `GET /api/admin/stats`（概览统计）+ admin router 注册 |
| ⬜ | Admin 前端联调 | `/admin/knowledge`、`/admin/documents`、`/admin/stats` 对接后端接口 |
| ⬜ | 错误处理 | 全局异常处理 + 统一错误码 |
| ⬜ | Refresh Token 机制 | access_token（15-30min）+ refresh_token（7天，存 MySQL/Redis），支持 Rotation（刷新后旧 token 失效）、主动吊销（改密/强制下线） |
| ⬜ | 限流 | 简单 IP/用户级频率限制 |
| ⬜ | 日志 | 结构化日志 + 关键节点埋点 |
| ⬜ | README + 部署文档 | 项目说明 + Docker Compose 部署方案 |
| ⬜ | 简历描述文案 | 项目亮点提炼，技术选型理由 |

### 6.1 Phase 5 测试

| 状态 | 任务 | 测试类型 | 说明 |
|:---|:---|:---|:---|
| ⬜ | 全量回归测试 | 回归测试 | 运行 `regression_test.py` 遍历完整测试集，检查召回/非空/来源/SSE/错误率 |
| ⬜ | 压测 | 性能测试 | Locust 4 场景（基准/日常/峰值/极限），P50≤3s / P99≤10s |
| ⬜ | 最终人工评分 | 人工评估 | 最终 10 题 × 4 维度评分，平均综合分 ≥ 4.0 |
| ⬜ | 限流测试 | 接口测试 | IP/用户级频率限制生效验证 |
| ⬜ | Refresh Token 测试 | 接口测试 | Token 刷新 / Rotation（旧 token 失效）/ 主动吊销 |

---

## 7. 依赖关系

```
Phase 1 ──→ Phase 2 ──→ Phase 3 ──→ Phase 4 ──→ Phase 5
  │            │            │            │            │
  └─ 测试 ──→  └─ 测试 ──→  └─ 测试 ──→  └─ 测试 ──→  └─ 测试
     (待补)      (含离线评估)  (含人工评分1) (含人工评分2)  (全量+压测)
```

- Phase 3 和 Phase 4 可部分并行：核心问答的单轮链路可与会话 CRUD 同时开发
- Phase 4 的问题重写依赖 Phase 3 的 LLM 调用能力
- Phase 5 在所有功能就绪后进行

### 7.1 测试准入规则

**每个 Phase 的测试必须在该 Phase 功能完成后立即执行，作为下一 Phase 的准入条件：**

- Phase N 功能完成 → 执行 Phase N 测试 → 全部通过 → 方可进入 Phase N+1
- Phase 1 的测试需在 Phase 2 正式开始前补齐
- 回归测试集随 Phase 迭代持续扩充，每次提交运行全量回归

---

## 8. 相关文档

- [产品需求文档](PRD.md)
- [架构设计文档](ARCHITECTURE.md)
- [开发指南](DEVELOPMENT.md)
- [测试策略](TESTING.md)
- [测试用例跟踪](TEST_CASES.md)
- [UI 设计规范](../frontend/docs/UIDESIGN.md)
