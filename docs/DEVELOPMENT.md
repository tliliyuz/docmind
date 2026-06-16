# DEVELOPMENT — 开发指南

| 属性 | 值 |
|:---|:---|
| 文档版本 | v1.0 |
| 最后更新 | 2026-06-14 |

---

## 1. 环境要求

| 工具 | 最低版本 | 说明 |
|:---|:---|:---|
| Python | 3.11+ | 后端运行环境 |
| Node.js | 18+ | 前端构建环境 |
| MySQL | 8.0+ | 业务数据库，**必须配置 `time_zone='+00:00'`**（连接串已通过 `init_command` 强制执行会话级 UTC），详见 §7 |
| Redis | 7.0+ | 缓存 + Celery broker |

### 1.1 Redis 客户端说明

| 环境 | 实现方案 | 说明 |
|:---|:---|:---|
| **开发（Windows）** | `redis.Redis` 同步客户端 + `asyncio.to_thread()` 线程池包装 | `redis.asyncio` 在 Windows 下存在连接超时和稳定性问题，线程池包装保持异步接口同时避免阻塞事件循环 |
| **生产（Linux）** | 原生 `redis.asyncio.Redis` + `ConnectionPool` | 连接池复用、预热、健康检查，性能最优 |

| 模块 | 客户端 | 说明 |
|:---|:---|:---|
| FastAPI / BM25 | `get_async_redis()` | 异步接口（开发环境是线程池包装，生产环境是原生 async） |
| Celery Worker | `get_redis()` | 同步接口（Celery 本身是同步多进程架构） |

---

## 2. 项目结构

> 最后更新：2026-06-15（同步自实际文件清单）

```
docmind/
├── CLAUDE.md                          # Claude Code 项目指引
├── README.md                          # 项目入口导航
├── .gitignore
│
├── docs/                              # 公用设计文档
│   ├── PRD.md                         # 产品需求文档
│   ├── ARCHITECTURE.md                # 架构设计文档
│   ├── ROADMAP.md                     # 开发排期
│   ├── DEVELOPMENT.md                 # 开发指南（本文件）
│   ├── tests/                         # 测试文档
│   │   ├── TESTING.md                 # 测试策略
│   │   └── TEST_CASES.md              # 测试用例跟踪
│   ├── CHANGELOG.md                   # 变更日志
│   └── decisions/                     # 架构决策记录（ADR）
│
├── backend/
│   ├── .env                           # 环境变量（在 backend/ 下，不在根目录！）
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── alembic.ini
│   ├── alembic/                       # 数据库迁移
│   │   ├── env.py
│   │   └── versions/
│   │
│   ├── docs/                          # 后端设计文档
│   │   ├── API.md                     # 接口文档
│   │   ├── DATABASE.md                # 数据库设计文档
│   │   └── RAG_PIPELINE.md            # RAG 管线详细设计
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI 入口
│   │   ├── config.py                  # 配置管理（读取 .env）
│   │   ├── dependencies.py            # 依赖注入（DB session, current_user）
│   │   │
│   │   ├── api/                       # API 路由层
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                # 认证接口（注册/登录/refresh）
│   │   │   ├── knowledge_base.py      # 知识库 CRUD + 选择器
│   │   │   ├── document.py            # 文档上传 & 管理
│   │   │   ├── conversation.py        # 会话管理
│   │   │   ├── chat.py                # 问答接口（SSE 流式输出）
│   │   │   └── admin.py               # 管理后台（统计/知识库/文档/链路/用户）
│   │   │
│   │   ├── models/                    # SQLAlchemy ORM 模型
│   │   │   ├── __init__.py            # 导出全部模型 + DocumentStatus
│   │   │   ├── _types.py              # UTCDateTime TypeDecorator（UTC 时区处理）
│   │   │   ├── user.py                # 用户表
│   │   │   ├── knowledge_base.py      # 知识库表
│   │   │   ├── document.py            # 文档表
│   │   │   ├── chunk.py               # 分块表
│   │   │   ├── conversation.py        # 会话表
│   │   │   ├── message.py             # 消息表
│   │   │   ├── refresh_token.py       # Refresh Token 表
│   │   │   ├── trace.py               # 链路追踪表
│   │   │   └── enums.py               # DocumentStatus 枚举定义
│   │   │
│   │   ├── schemas/                   # Pydantic 请求/响应模型
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                # RegisterRequest / LoginRequest / TokenResponse
│   │   │   ├── knowledge_base.py      # KnowledgeBaseCreate / KnowledgeBaseResponse
│   │   │   ├── document.py            # DocumentUploadResponse / DocumentListResponse 等
│   │   │   ├── conversation.py        # ConversationCreate / ConversationResponse
│   │   │   ├── chat.py                # ChatRequest / ChatSSEEvent / SelectableKB*
│   │   │   ├── admin.py               # Admin 统计/列表/用户管理 Schema
│   │   │   └── trace.py               # Trace 查询响应 Schema
│   │   │
│   │   ├── services/                  # 业务逻辑层
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py        # 注册/登录/refresh token 逻辑
│   │   │   ├── knowledge_base_service.py  # 知识库 CRUD + 删除（共享权限函数 require_kb_*）
│   │   │   ├── document_service.py    # 文档上传/列表/详情/删除/reprocess
│   │   │   ├── conversation_service.py # 会话 CRUD + 标题生成
│   │   │   ├── chat_service.py        # 问答入口（chat/get_selectable_kbs）+ 校验准备，re-export 兼容层
│   │   │   ├── chat_helpers.py        # 问答辅助函数（历史加载/标题生成/引用提取/sources 构建）
│   │   │   ├── sse_stream.py          # SSE 流生成器 + 固定响应（meta/reject）+ 消息持久化
│   │   │   ├── admin_service.py       # Admin 统计/知识库/文档/用户管理
│   │   │   └── trace_service.py       # 链路追踪查询/详情
│   │   │
│   │   ├── rag/                       # RAG 核心模块
│   │   │   ├── __init__.py
│   │   │   ├── _types.py              # RAG 管线共享类型（Source, IntentResult 等）
│   │   │   ├── parser.py              # 文档解析器（PDF/DOCX/MD/TXT）
│   │   │   ├── chunker.py             # 文本分块策略（512 token / 50 重叠）
│   │   │   ├── embedder.py            # Embedding 封装（DashScope text-embedding-v3）
│   │   │   ├── vector_store.py        # 向量存储抽象层（BaseVectorStore ABC + ChromaVectorStore，ADR-018）
│   │   │   ├── retriever.py           # 向量检索器（依赖 BaseVectorStore 抽象，ADR-018）
│   │   │   ├── bm25.py                # BM25 关键词检索 + Redis 缓存
│   │   │   ├── fusion.py              # RRF 多路融合算法
│   │   │   ├── reranker.py            # DashScope Rerank API 语义精排
│   │   │   ├── knowledge_pipeline.py  # 知识管线：查询重写→双路检索→RRF→Rerank→句级修辞过滤→句子匹配→Prompt 构建
│   │   │   ├── prompt_builder.py      # Prompt 模板组装（宽松策略 + System/History/Retrieval/Question）
│   │   │   ├── intent.py              # 意图识别（Meta/Chitchat/RAG 三路分发）
│   │   │   ├── query_rewriter.py      # 多轮对话问题重写
│   │   │   ├── sentence_matcher.py    # 句级修辞过滤（陈述/引用角色判断）+ Evidence Highlight 句子匹配
│   │   │   ├── evidence_auditor.py    # 三层证据审计（引用存在性 + 来源一致性 + 句级证据回溯）
│   │   │   └── trace_recorder.py      # RAG 链路追踪记录器
│   │   │
│   │   ├── ingest/                    # 入库任务模块
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py          # Celery 配置（DB/Redis 集成）
│   │   │   ├── lock.py                # Celery 幂等锁（Redis SET NX, ingest/delete 共享互斥）
│   │   │   ├── tasks.py               # 入库 Celery 任务（文档解析→分块→嵌入→存储）
│   │   │   └── delete_tasks.py        # 文档/知识库异步删除 Celery 任务
│   │   │
│   │   ├── core/                      # 基础设施
│   │   │   ├── __init__.py
│   │   │   ├── database.py            # 数据库连接 & async session
│   │   │   ├── chroma_client.py       # ChromaDB 连接 + get_vector_store() 工厂函数
│   │   │   ├── permissions.py         # KB 访问权限共享函数（require_kb_readable/writable/owner）
│   │   │   ├── redis_client.py        # Redis 客户端（懒加载单例，Win/Linux 双模式）
│   │   │   ├── security.py            # JWT & 密码哈希
│   │   │   ├── sse.py                 # SSE 发送工具
│   │   │   ├── storage.py             # 文件存储抽象（当前本地，后续 OSS）
│   │   │   ├── exceptions.py          # 自定义异常（AppException 基类 + 全局处理器）
│   │   │   ├── llm.py                 # LLM 调用封装（DashScope/OpenAI 兼容）
│   │   │   ├── logging_config.py      # 日志配置
│   │   │   └── uuid_helpers.py        # UUID 工具函数
│   │   │
│   │   └── middleware/
│   │       ├── __init__.py
│   │       ├── auth_middleware.py      # JWT 验证中间件
│   │       ├── rate_limit_middleware.py # 限流中间件
│   │       └── request_id_middleware.py # 请求 ID 追踪中间件
│   │
│   ├── tests/                         # 后端测试（pytest + httpx）
│   │   ├── __init__.py
│   │   ├── conftest.py                # 顶层共享 fixtures（mock DB, auth headers, async client）
│   │   ├── helpers.py                 # 共享测试工厂函数
│   │   │
│   │   ├── unit/                      # 单元测试（快速、模拟，自动标记 @unit）
│   │   │   ├── __init__.py
│   │   │   ├── conftest.py            # 自动添加 pytest.mark.unit
│   │   │   ├── api/                   # API 层测试（10 文件）
│   │   │   │   ├── test_auth_api.py
│   │   │   │   ├── test_kb_api.py
│   │   │   │   ├── test_document_api.py
│   │   │   │   ├── test_conversation_api.py
│   │   │   │   ├── test_chat_api.py
│   │   │   │   ├── test_admin_api.py
│   │   │   │   ├── test_admin_user_api.py
│   │   │   │   ├── test_trace_api.py
│   │   │   │   ├── test_kb_selectable_api.py
│   │   │   │   └── test_uuid_api.py
│   │   │   ├── core/                  # 核心模块测试（10 文件）
│   │   │   ├── ingest/                # 入库流水线测试（2 文件）
│   │   │   ├── rag/                   # RAG 管线测试（16 文件）
│   │   │   ├── schemas/               # Pydantic Schema 测试（3 文件）
│   │   │   └── services/             # Service 层测试（10 文件）
│   │   │
│   │   ├── integration/               # 集成测试（自动标记 @integration）
│   │   │   ├── __init__.py
│   │   │   ├── conftest.py            # 自动添加 pytest.mark.integration
│   │   │   └── test_chat_trace_integration.py
│   │   │
│   │   ├── eval/                      # 评估脚本
│   │   │   ├── __init__.py
│   │   │   ├── eval_retrieval.py      # 离线检索评估
│   │   │   ├── eval_test_set.py       # 30 题固定测试集
│   │   │   ├── eval_multi_turn_test_set.py  # 多轮对话测试集
│   │   │   └── human_eval_template.md       # 人工评分记录模板
│   │   │
│   │   ├── regression/                # 回归测试（端到端）
│   │   │   ├── __init__.py
│   │   │   ├── regression_test.py
│   │   │   └── regression_multi_turn_test.py
│   │   │
│   │   └── performance/               # 性能/压力测试
│   │       ├── __init__.py
│   │       ├── locustfile.py
│   │       ├── run_stress_test.bat
│   │       └── run_stress_test.sh
│   │
│   ├── chroma_data/                   # ChromaDB 持久化目录
│   └── uploads/                       # 上传文件存储目录
│
├── frontend/
│   ├── docs/                          # 前端设计文档
│   │   ├── FRONTEND.md                # 前端交互文档
│   │   └── UIDESIGN.md                # UI 设计规范
│   │
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   ├── vite.config.js
│   ├── vitest.config.js
│   │
│   ├── src/
│   │   ├── App.vue                    # 根组件（路由感知布局切换）
│   │   ├── main.js                    # Vue 应用入口
│   │   │
│   │   ├── views/                     # 页面
│   │   │   ├── ChatPage.vue           # 问答页（核心）
│   │   │   ├── LoginPage.vue          # 登录页
│   │   │   ├── KnowledgeList.vue      # 我的知识库列表
│   │   │   ├── KnowledgeDetail.vue    # 知识库详情（文档列表+上传）
│   │   │   ├── PublicKnowledgeList.vue # 公开知识库广场
│   │   │   └── admin/
│   │   │       ├── StatsPage.vue      # 系统统计（ECharts 可视化）
│   │   │       ├── KnowledgeList.vue  # 知识库管理
│   │   │       ├── DocumentList.vue   # 文档管理
│   │   │       ├── TraceList.vue      # 链路追踪列表
│   │   │       ├── TraceDetail.vue    # 单次链路详情
│   │   │       ├── AdminUserList.vue  # 用户管理
│   │   │       ├── AdminUserDetail.vue # 用户详情
│   │   │       └── ConversationList.vue # 会话管理（占位）
│   │   │
│   │   ├── components/
│   │   │   ├── chat/
│   │   │   │   ├── ChatInput.vue      # 输入框 + 发送 + 停止
│   │   │   │   ├── MessageList.vue    # 消息列表容器
│   │   │   │   ├── MessageItem.vue    # 单条消息气泡（含 Evidence Highlight）
│   │   │   │   └── WelcomeScreen.vue  # 空状态欢迎页
│   │   │   ├── layout/
│   │   │   │   ├── AppLayout.vue      # 布局容器（Sidebar + 主内容）
│   │   │   │   ├── Sidebar.vue        # 侧边栏（会话列表 + 管理导航）
│   │   │   │   └── AdminLayout.vue    # Admin 布局（侧边导航 + 内容区）
│   │   │   └── charts/
│   │   │       ├── LatencyChart.vue   # 延迟分布图
│   │   │       ├── TokenChart.vue     # Token 消耗图
│   │   │       └── TrendChart.vue     # 请求趋势图
│   │   │
│   │   ├── stores/                    # Pinia 状态管理
│   │   │   ├── auth.js                # 认证状态（token/用户/login/logout）
│   │   │   ├── chat.js                # 聊天状态（messages/streaming/send/abort）
│   │   │   ├── conversation.js        # 会话列表状态
│   │   │   └── knowledge.js           # 知识库状态（kbList/currentKb/docList）
│   │   │
│   │   ├── api/                       # HTTP 请求封装
│   │   │   ├── index.js               # Axios 实例 + 拦截器
│   │   │   ├── auth.js                # register / login / refresh
│   │   │   ├── knowledge.js           # 知识库/文档相关 API
│   │   │   ├── conversation.js        # 会话相关 API
│   │   │   ├── chat.js                # 问答 SSE 请求 + KB 选择器
│   │   │   ├── admin.js               # Admin 统计/管理 API
│   │   │   └── trace.js               # 链路追踪 API
│   │   │
│   │   ├── router/
│   │   │   └── index.js               # Vue Router + 路由守卫（认证/Admin）
│   │   │
│   │   ├── composables/
│   │   │   └── useECharts.js          # ECharts 动态加载 composable
│   │   │
│   │   ├── constants/
│   │   │   └── charts.js              # ECharts 图表颜色常量
│   │   │
│   │   ├── styles/
│   │   │   └── global.css             # 全局样式（Design Token --dm-* 变量）
│   │   │
│   │   └── utils/
│   │       ├── sse.js                 # SSE 事件解析
│   │       ├── markdown.js            # Markdown 渲染
│   │       └── format.js              # 共享格式化工具（formatDateTime/formatFileSize/formatRelativeTime）
│   │
│   └── tests/                         # 前端测试（vitest + @vue/test-utils）
│       ├── setup.js                   # 全局 Mock & 配置
│       ├── LoginPage.test.js
│       ├── ChatPage.test.js
│       ├── ChatInput.test.js
│       ├── MessageList.test.js
│       ├── MessageItem.test.js
│       ├── WelcomeScreen.test.js
│       ├── markdown.test.js
│       ├── sse.test.js
│       ├── AppLayout.test.js
│       ├── AdminLayout.test.js
│       ├── Sidebar.test.js
│       ├── KnowledgeList.test.js
│       ├── KnowledgeDetail.test.js
│       ├── PublicKnowledgeList.test.js
│       ├── KnowledgeListAdmin.test.js
│       ├── DocumentListAdmin.test.js
│       ├── StatsPage.test.js
│       ├── TraceList.test.js
│       ├── TraceDetail.test.js
│       ├── AdminUserList.test.js
│       ├── AdminUserDetail.test.js
│       ├── admin.test.js
│       ├── ConversationList.test.js
│       ├── Charts.test.js
│       ├── useECharts.test.js
│       ├── tokenRefresh.test.js
│       ├── UuidAdaptation.test.js
│       ├── authStore.test.js          # Auth Store 测试（JWT 解析/刷新/并发守卫）
│       ├── chatStore.test.js          # Chat Store 测试（SSE 状态机/消息管理）
│       ├── conversationStore.test.js  # Conversation Store 测试（分页/时间分组/CRUD）
│       └── knowledgeStore.test.js     # Knowledge Store 测试（KB/Document CRUD/轮询）
│
├── Dockerfile.backend
├── Dockerfile.frontend
├── docker-compose.yml
└── nginx.conf
```

---

## 3. 快速开始

### 3.1 后端

```bash
# 1. 创建虚拟环境
cd backend
python -m venv venv
source venv/bin/activate    # Linux/Mac
# venv\Scripts\activate     # Windows

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 .env
# 在 backend/ 目录下创建 .env 文件，参考下方 §4 环境变量章节填入凭证

# 4. 执行数据库迁移
alembic upgrade head

# 5. 启动开发服务器
uvicorn app.main:app --reload --port 8000

# 6. 启动 Celery Worker（另一个终端）
# Linux/Mac:
celery -A app.ingest.celery_app worker --loglevel=info
# Windows（必须加 --pool=solo，eventlet 与 asyncio 不兼容）:
celery -A app.ingest.celery_app worker --loglevel=info --pool=solo
```

> **注意**：Celery task 中禁止直接使用 `asyncio.run()`，若 Worker 使用 gevent/eventlet pool 会触发 `RuntimeError`。正确模式：`asyncio.new_event_loop()` + `run_until_complete()`，见 `app/ingest/tasks.py`。
> 
> **Windows 特别注意**：
> - Celery Worker 必须使用 `--pool=solo`（单进程池），`eventlet` / `gevent` pool 的 monkey-patch 与 asyncio 事件循环冲突，会导致任务收到后静默卡死
> - `aiomysql` 依赖 `SelectorEventLoop`，Windows 默认使用 `ProactorEventLoop`。`celery_app.py` 启动时已自动设置 `WindowsSelectorEventLoopPolicy()`，无需手动干预
> - `solo` 池一次只处理一个任务，本地开发够用；生产环境 Windows 上可起多个 Worker 进程实现并发&#8203;

### 3.2 前端

```bash
# 1. 安装依赖
cd frontend
npm install

# 2. 启动开发服务器
npm run dev

# Vite 会在 http://localhost:5173 启动，
# /api 请求自动代理到后端 http://localhost:8000
```

---

## 4. 环境变量

`.env` 文件位于 `backend/` 目录下（**不在项目根目录**）。

```env
# .env
APP_NAME=DocMind
DEBUG=true

# MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=docmind

# ChromaDB
CHROMA_PERSIST_DIR=./chroma_data

# LLM (OpenAI 兼容 — DeepSeek)
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=sk-xxx
LLM_MODEL=deepseek-v4-pro

# Embedding (DashScope)
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/api/v1
EMBEDDING_API_KEY=sk-xxx
EMBEDDING_MODEL=text-embedding-v3

# Rerank (可选，Phase 3 启用)
RERANK_API_KEY=sk-xxx

# JWT
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# Redis
REDIS_URL=redis://localhost:6379/0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# 文件存储
UPLOAD_DIR=./uploads
# 后续扩展 OSS:
# STORAGE_BACKEND=oss
# OSS_ENDPOINT=...
# OSS_BUCKET=docmind-files
```

**注意事项**：
- `config.py` 通过 `pydantic-settings` 自动从 CWD 读取 `.env`，因此运行 uvicorn 时需在 `backend/` 目录下执行
- 所有字段在 `config.py` 的 `Settings` 类中有默认值声明，`.env` 中的同名变量会自动覆盖
- 不要将 `.env` 提交到 Git（已在 `.gitignore` 中排除）

---

## 5. 后端依赖

```
# backend/requirements.txt
fastapi==0.115.*
uvicorn[standard]==0.32.*
sqlalchemy[asyncio]==2.0.*
aiomysql==0.2.*
pydantic==2.*
pydantic-settings==2.*
python-jose[cryptography]==3.3.*
bcrypt==4.0.*
python-multipart==0.0.*
chromadb==0.5.*
langchain==0.3.*
langchain-community==0.3.*
langchain-openai==0.2.*
jieba==0.42.*
rank-bm25==0.2.*
PyPDF2==3.0.*
python-docx==1.1.*
markdown-it-py==3.0.*
redis==5.2.*
celery==5.4.*
httpx==0.28.*
alembic==1.14.*

# 测试
pytest==8.*
pytest-asyncio==0.24.*
pytest-cov==5.*
httpx==0.28.*
```

> 注：BM25 关键词检索使用 `rank-bm25` (BM25Okapi) + `jieba` 中文分词（见 [ARCHITECTURE.md §7.2](ARCHITECTURE.md#72-bm25-实现方案)）。

---

## 6. 前端依赖

```json
{
  "dependencies": {
    "axios": "^1.7.0",
    "element-plus": "^2.9.0",
    "markdown-it": "^14.1.0",
    "pinia": "^2.3.0",
    "vue": "^3.5.0",
    "vue-router": "^4.5.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.2.0",
    "vite": "^6.0.0",
    "vitest": "^2.1.0",
    "@vue/test-utils": "^2.4.0",
    "jsdom": "^25.0.0"
  }
}
```

---

## 7. MySQL 时区配置

> **所有 DATETIME 列均存储 UTC 时间**，对齐 [ARCHITECTURE.md §11](ARCHITECTURE.md#11-时区策略)。

### 7.1 连接级强制（已内置）

`config.py` 的 `mysql_url` 属性已附加 `init_command=SET time_zone='%2B00:00'`，每个连接建立后自动执行。**新部署无需额外配置**。

### 7.2 服务器级设置（推荐）

```sql
-- 查看当前时区
SELECT @@global.time_zone, @@session.time_zone;

-- 设置全局默认时区为 UTC（需 SUPER 权限）
SET GLOBAL time_zone = '+00:00';
```

或在 MySQL 配置文件 `my.cnf` 中：

```ini
[mysqld]
default_time_zone = '+00:00'
```

> **注意**：若无法修改全局配置，仅靠连接串 `init_command` 即可保证正确性，但 MySQL 重启前全局非 UTC 会影响 `SHOW VARIABLES` 等管理命令的显示值（不影响数据）。

### 7.3 验证

```sql
-- 连接后执行，应返回 +00:00
SELECT @@session.time_zone;
```

---

## 8. 常用命令速查

```bash
# === 后端 ===
cd backend

# 启动开发服务器
uvicorn app.main:app --reload --port 8000

# 数据库迁移
alembic upgrade head                          # 执行迁移
alembic revision --autogenerate -m "描述"     # 生成迁移脚本

# Celery Worker
celery -A app.ingest.celery_app worker --loglevel=info

# 测试
pytest tests/ -v                              # 运行全部测试
pytest tests/ -v --cov=app --cov-report=html  # 含覆盖率报告
pytest tests/unit/ -v                          # 仅单元测试（快速）
pytest tests/unit/api/ -v                      # 仅 API 层单元测试
pytest tests/unit/rag/ -v                      # 仅 RAG 管线单元测试
pytest tests/integration/ -v                   # 仅集成测试
pytest tests/regression/ -v                    # 仅回归测试
pytest tests/unit/api/test_auth_api.py -v      # 运行单个测试文件

# === 前端 ===
cd frontend
npm run dev        # 开发服务器（localhost:5173）
npm run build      # 生产构建（输出到 dist/）
npm run preview    # 预览生产构建
npm run test       # 运行 vitest 测试
npm run test:ui    # vitest UI 模式
```

---

## 9. Docker 部署（Phase 5）

### 9.1 前置条件

| 工具 | 最低版本 | 说明 |
|:---|:---|:---|
| Docker | 20.10+ | 容器运行时 |
| Docker Compose | 2.0+ | 服务编排 |

### 9.2 快速启动

```bash
# 1. 配置环境变量
# 复制模板并填入实际凭证
cp backend/.env.example backend/.env
# 编辑 backend/.env，确保 JWT_SECRET_KEY 和 LLM_API_KEY 等已配置

# 2. 构建镜像并启动所有服务
docker-compose up -d --build

# 3. 查看服务状态
docker-compose ps

# 4. 查看日志
docker-compose logs -f backend      # 后端日志
docker-compose logs -f celery       # Celery Worker 日志
docker-compose logs -f nginx      # Nginx 日志
docker-compose logs -f              # 所有服务日志

# 5. 执行数据库迁移
docker-compose exec backend alembic upgrade head

# 6. 停止服务
docker-compose down

# 7. 停止并清理数据卷（⚠️ 删除所有持久化数据）
docker-compose down -v
```

### 9.3 服务访问

| 服务 | 地址 | 说明 |
|:---|:---|:---|
| 前端页面 | `http://localhost` | Nginx 托管 Vite 构建产物，端口 80 |
| 后端 API | `http://localhost/api` | 通过 Nginx 反向代理到 backend:8000 |
| API 文档 | `http://localhost:8000/docs` | Swagger UI（开发环境可直连后端端口） |
| MySQL | `localhost:3306` | 数据库（本地调试时可连接） |
| Redis | `localhost:6379` | 缓存（本地调试时可连接） |

### 9.4 常用运维命令

```bash
# 进入容器调试
docker-compose exec backend bash
docker-compose exec mysql mysql -u root -p docmind

# 查看后端实时日志（含结构化 JSON）
docker-compose logs -f backend | jq '.'

# 重启单个服务
docker-compose restart backend
docker-compose restart celery

# 重新构建单个服务
docker-compose up -d --build backend

# 扩展 Celery Worker（Linux 生产环境，Windows 不支持 fork）
docker-compose up -d --scale celery=3

# 查看资源使用
docker stats
```

### 9.5 环境变量注入

`docker-compose.yml` 通过 `env_file: backend/.env` 统一注入环境变量。以下变量**必须**在生产环境修改：

| 变量 | .env.example 默认值 | 生产环境要求 |
|:---|:---|:---|
| `JWT_SECRET_KEY` | `change-me` | 更换为 64 字符随机字符串 |
| `LLM_API_KEY` | `sk-xxx` | 填入真实 API Key |
| `EMBEDDING_API_KEY` | `sk-xxx` | 填入真实 API Key |
| `MYSQL_PASSWORD` | `your_strong_password` | 更换为强密码 |
| `DEBUG` | `false` | 确认保持 `false` |
| `CORS_ORIGINS` | `http://localhost` | 设为实际前端域名 |

### 9.6 Windows 注意事项

- Docker Desktop 使用 WSL2 后端，Celery Worker 以 Linux 容器运行，无需 `--pool=solo`（Windows 限制仅影响原生运行）
- `docker-compose.yml` 中 Celery command 不加 `--pool=solo`，使用默认 prefork pool
- 持久化数据使用 Docker 命名卷（`mysql_data` / `redis_data` / `chroma_data` / `upload_data`），由 Docker 引擎管理生命周期，`docker-compose down -v` 会删除所有卷数据

> 部署架构图、服务清单、Nginx 配置、部署约束见 [ARCHITECTURE.md §12.1](ARCHITECTURE.md#121-部署架构)。

---

## 10. 编码约定

详见项目根目录 [CLAUDE.md](../CLAUDE.md) 的「关键约定」章节。核心要点：

- 所有注释、变量名、提交信息用中文
- 后端异步优先，路由只做校验 + 调用 service
- 前端 Composition API + `<script setup>`，请求走 api/ 封装
- 导入使用 `from app.xxx` 绝对路径

---

## 11. 相关文档

- [架构设计文档](ARCHITECTURE.md)
- [数据库设计文档](../backend/docs/DATABASE.md)
- [接口文档](../backend/docs/API.md)
- [开发排期](ROADMAP.md)
- [测试策略](tests/TESTING.md)
- [UI 设计规范](../frontend/docs/UIDESIGN.md)
- [ADR-018：向量存储抽象层](decisions/ADR-018-向量存储抽象层.md)
