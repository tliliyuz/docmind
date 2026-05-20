# DEVELOPMENT — 开发指南

| 属性 | 值 |
|:---|:---|
| 文档版本 | v0.7 |
| 最后更新 | 2026-05-19 |
| 作者 | yuz |
| 状态 | 草稿 |

---

## 1. 环境要求

| 工具 | 最低版本 | 说明 |
|:---|:---|:---|
| Python | 3.11+ | 后端运行环境 |
| Node.js | 18+ | 前端构建环境 |
| MySQL | 8.0+ | 业务数据库 |
| Redis | 7.0+ | 缓存 + Celery broker |

---

## 2. 项目结构

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
│   ├── TESTING.md                     # 测试策略
│   └── CHANGE.md                      # 变更日志
│
├── backend/
│   ├── .env                           # 环境变量（在 backend/ 下，不在根目录！）
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/                       # 数据库迁移
│   │
│   ├── docs/                          # 后端设计文档
│   │   ├── API.md                     # 接口文档
│   │   └── DATABASE.md                # 数据库设计文档
│   │
│   ├── app/
│   │   ├── main.py                    # FastAPI 入口
│   │   ├── config.py                  # 配置管理（读取 .env）
│   │   ├── dependencies.py            # 依赖注入（DB session, current_user）
│   │   │
│   │   ├── api/                       # API 路由层
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                # 认证接口（注册/登录）
│   │   │   ├── knowledge_base.py      # 知识库 CRUD
│   │   │   ├── document.py            # 文档上传 & 管理
│   │   │   ├── conversation.py        # 会话管理
│   │   │   ├── chat.py                # 问答接口（SSE）
│   │   │   └── admin.py               # 管理后台
│   │   │
│   │   ├── models/                    # SQLAlchemy ORM 模型
│   │   │   ├── __init__.py            # 导出全部模型 + DocumentStatus
│   │   │   ├── user.py                # 用户表
│   │   │   ├── knowledge_base.py      # 知识库表
│   │   │   ├── document.py            # 文档表
│   │   │   ├── chunk.py               # 分块表
│   │   │   ├── conversation.py        # 会话表
│   │   │   ├── message.py             # 消息表
│   │   │   └── enums.py               # DocumentStatus 枚举定义
│   │   │
│   │   ├── schemas/                   # Pydantic 请求/响应模型
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                # RegisterRequest / LoginRequest / TokenResponse
│   │   │   ├── knowledge_base.py      # KnowledgeBaseCreate / KnowledgeBaseResponse
│   │   │   ├── document.py            # DocumentResponse / DocumentListResponse
│   │   │   ├── conversation.py        # ConversationCreate / ConversationResponse
│   │   │   └── chat.py                # ChatRequest / ChatSSEEvent
│   │   │
│   │   ├── services/                  # 业务逻辑层
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py         # 注册/登录逻辑
│   │   │   ├── knowledge_base_service.py  # 知识库 CRUD
│   │   │   ├── document_service.py     # 文档上传/状态管理
│   │   │   ├── conversation_service.py # 会话管理
│   │   │   └── chat_service.py        # 问答核心流程
│   │   │
│   │   ├── rag/                       # RAG 核心模块
│   │   │   ├── __init__.py
│   │   │   ├── parser.py              # 文档解析器
│   │   │   ├── chunker.py             # 文本分块策略
│   │   │   ├── embedder.py            # Embedding 封装
│   │   │   ├── retriever.py           # 检索器（向量 + BM25）
│   │   │   ├── reranker.py            # 重排序（NoopReranker / DashScopeReranker）
│   │   │   ├── prompt_builder.py      # Prompt 模板
│   │   │   └── intent.py              # 意图识别 + 问题重写
│   │   │
│   │   ├── ingest/                    # 入库任务模块
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py          # Celery 配置
│   │   │   ├── lock.py                # Celery 幂等锁（Redis SET NX）
│   │   │   └── tasks.py               # 入库任务（ingest_document）
│   │   │
│   │   ├── core/                      # 基础设施
│   │   │   ├── __init__.py
│   │   │   ├── database.py            # 数据库连接 & session
│   │   │   ├── chroma_client.py       # ChromaDB 连接
│   │   │   ├── redis_client.py        # Redis 客户端（懒加载单例）
│   │   │   ├── security.py            # JWT & 密码哈希
│   │   │   ├── sse.py                 # SSE 发送工具
│   │   │   ├── storage.py             # 文件存储抽象（当前本地，后续 OSS）
│   │   │   └── exceptions.py          # 自定义异常
│   │   │
│   │   └── middleware/
│   │       ├── __init__.py
│   │       └── auth_middleware.py      # JWT 验证中间件
│   │
│   ├── chroma_data/                   # ChromaDB 持久化目录（chroma.sqlite3）
│   ├── knowledge_samples/             # 示例知识库文档
│   │
│   ├── tests/                         # 后端测试（pytest + httpx）
│   │   ├── __init__.py
│   │   ├── conftest.py                # pytest fixtures（async client, test DB session）
│   │   ├── test_security.py           # JWT & 密码哈希单元测试
│   │   ├── test_storage.py            # 文件存储服务单元测试（本地存储 put/get/delete + 路径生成）
│   │   ├── test_auth_service.py       # 认证业务逻辑单元测试
│   │   ├── test_auth_api.py           # 认证接口集成测试
│   │   ├── test_schemas.py            # Pydantic Schema 校验测试
│   │   ├── test_models.py             # ORM 模型测试（约束/默认值/关联）
│   │   ├── test_kb_api.py             # 知识库 CRUD 接口测试
│   │   ├── test_document_api.py       # 文档上传/删除接口测试
│   │   ├── test_idempotent_lock.py    # Celery 幂等锁单元测试
│   │   ├── test_ingest_tasks.py        # Celery 入库流水线集成测试（阶段状态机/batch checkpoint/容错判定）
│   │   ├── test_parser.py             # 文档解析器单元测试（PDF/DOCX/MD/TXT + 容错阈值）
│   │   ├── test_chunker.py            # 文本分块策略单元测试
│   │   ├── test_embedder.py           # Embedding 向量化单元测试（批次级 checkpoint）
│   │   ├── test_retriever.py          # 检索器单元测试（向量+BM25）
│   │   ├── test_rrf.py                # RRF 融合算法测试
│   │   ├── test_chat_api.py           # 问答 SSE 接口测试
│   │   ├── eval_retrieval.py          # 离线检索评估脚本
│   │   ├── regression_test.py         # 回归测试脚本
│   │   └── locustfile.py              # 压测脚本（Locust）
│   │
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
│   │
│   └── src/
│       ├── App.vue                    # 根组件（路由感知布局切换）
│       ├── main.js                    # Vue 应用入口
│       │
│       ├── views/                     # 页面
│       │   ├── ChatPage.vue           # 问答页（核心）
│       │   ├── LoginPage.vue          # 登录页
│       │   └── admin/
│       │       ├── KnowledgeList.vue  # 知识库管理
│       │       ├── DocumentList.vue   # 文档管理
│       │       └── ConversationList.vue # 会话管理
│       │
│       ├── components/
│       │   ├── chat/
│       │   │   ├── ChatInput.vue      # 输入框 + 发送 + 停止
│       │   │   ├── MessageList.vue    # 消息列表容器
│       │   │   ├── MessageItem.vue    # 单条消息气泡
│       │   │   └── WelcomeScreen.vue  # 空状态欢迎页
│       │   └── layout/
│       │       ├── AppLayout.vue      # 布局容器（Sidebar + 主内容）
│       │       └── Sidebar.vue        # 侧边栏（会话列表 + 管理导航）
│       │
│       ├── stores/                    # Pinia 状态管理
│       │   ├── auth.js                # 认证状态（token/用户/login/logout）
│       │   ├── chat.js                # 聊天状态（messages/streaming/send/abort）
│       │   └── knowledge.js           # 知识库状态（kbList/currentKb/docList）
│       │
│       ├── api/                       # HTTP 请求封装
│       │   ├── index.js               # Axios 实例 + 拦截器
│       │   ├── auth.js                # register / login
│       │   ├── knowledge.js           # 知识库/文档相关 API
│       │   ├── conversation.js        # 会话相关 API
│       │   └── chat.js                # 问答 SSE 请求
│       │
│       ├── router/
│       │   └── index.js               # Vue Router + 三级路由守卫
│       │
│       ├── utils/
│       │   ├── sse.js                 # SSE 事件解析
│       │   └── markdown.js            # Markdown 渲染
│       │
│       └── tests/                     # 前端测试（vitest + @vue/test-utils）
│           ├── setup.js               # 全局 Mock & 配置
│           ├── LoginPage.test.js      # 登录页组件测试
│           ├── AppLayout.test.js      # 布局组件测试
│           ├── ChatPage.test.js       # 问答页组件测试
│           ├── KnowledgeList.test.js  # 知识库管理页组件测试
│           ├── DocumentList.test.js   # 文档管理页组件测试
│           └── sse.test.js            # SSE 解析工具测试
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
celery -A app.ingest.celery_app worker --loglevel=info
```

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
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=sk-xxx
LLM_MODEL=deepseek-chat

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
passlib[bcrypt]==1.7.*
python-multipart==0.0.*
chromadb==0.5.*
langchain==0.3.*
langchain-community==0.3.*
langchain-openai==0.2.*
jieba==0.42.*
unstructured==0.16.*
PyPDF2==3.0.*
python-docx==1.1.*
markdown-it-py==3.0.*
redis==5.2.*
celery==5.4.*
httpx==0.28.*
sse-starlette==2.1.*
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

## 7. 常用命令速查

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
pytest tests/test_auth_api.py -v              # 运行单个测试文件

# === 前端 ===
cd frontend
npm run dev        # 开发服务器（localhost:5173）
npm run build      # 生产构建（输出到 dist/）
npm run preview    # 预览生产构建
npm run test       # 运行 vitest 测试
npm run test:ui    # vitest UI 模式
```

---

## 8. 编码约定

详见项目根目录 [CLAUDE.md](../CLAUDE.md) 的「关键约定」章节。核心要点：

- 所有注释、变量名、提交信息用中文
- 后端异步优先，路由只做校验 + 调用 service
- 前端 Composition API + `<script setup>`，请求走 api/ 封装
- 导入使用 `from app.xxx` 绝对路径

---

## 9. 相关文档

- [架构设计文档](ARCHITECTURE.md)
- [数据库设计文档](../backend/docs/DATABASE.md)
- [接口文档](../backend/docs/API.md)
- [开发排期](ROADMAP.md)
- [测试策略](TESTING.md)
- [UI 设计规范](../frontend/docs/UIDESIGN.md)
