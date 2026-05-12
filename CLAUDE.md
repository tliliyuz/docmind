# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 常用命令

```bash
# 后端
cd backend && uvicorn app.main:app --reload --port 8000   # 启动 FastAPI 开发服务器
cd backend && alembic upgrade head                          # 执行数据库迁移
cd backend && alembic revision --autogenerate -m "描述"     # 生成迁移脚本（注意：aiomysql 连接关闭时会报 Event loop is closed，脚本已生成但需手动 upgrade）

# 前端
cd frontend && npm run dev                                  # 启动 Vite 开发服务器（端口 5173）
cd frontend && npm run build                                # 生产构建

# Celery Worker（文档异步入库）
cd backend && celery -A app.ingest.celery_app worker --loglevel=info
```

---

## 技术栈

**后端**：Python / FastAPI / LangChain / ChromaDB / MySQL / Redis / Celery
**前端**：Vue 3 / Vite / Element Plus / Pinia / Axios / Vue Router / Font Awesome 6
**AI**：DeepSeek (OpenAI 兼容) / DashScope text-embedding-v3 / SSE 流式输出

---

## 目录结构

```
docmind/
├── backend/
│   ├── .env                    # 环境变量（在 backend/ 下，不是项目根目录！）
│   ├── app/
│   │   ├── main.py             # FastAPI 入口 + CORS + /api/health
│   │   ├── config.py           # pydantic-settings 读取 .env，提供 mysql_url 计算属性
│   │   ├── dependencies.py     # get_db() 异步 session 生成器
│   │   ├── api/                # 路由层（仅参数校验 + 调用 service）
│   │   ├── models/             # SQLAlchemy 2.0 Mapped 模型
│   │   ├── schemas/            # Pydantic 请求/响应模型
│   │   ├── services/           # 业务逻辑
│   │   ├── rag/                # RAG 核心（parser/chunker/embedder/retriever/reranker/intent）
│   │   ├── ingest/             # Celery 异步入库任务
│   │   ├── core/               # 基础设施（database/chroma/security/sse/storage/exceptions）
│   │   └── middleware/         # JWT 验证中间件
│   ├── alembic/                # 数据库迁移（异步引擎，URL 从 config.py 运行时读取）
│   ├── chroma_data/            # ChromaDB 持久化目录（chroma.sqlite3，启动时自动创建）
│   └── knowledge_samples/      # 示例知识库文档
├── frontend/src/
│   ├── views/                  # 页面（ChatPage / LoginPage / admin）
│   ├── components/             # chat 组件 + layout
│   ├── stores/                 # Pinia 状态
│   ├── api/                    # HTTP 请求封装
│   ├── router/                 # Vue Router 配置
│   └── utils/                  # SSE 解析、Markdown 渲染
└── README.md                   # 项目入口 + 文档索引导航
```

---

## 设计文档速查

根目录下有 8 份设计文档，按需查阅：

| 文档 | 何时读取 |
|:---|:---|
| [README.md](./README.md) | 项目入口，了解整体定位和文档索引 |
| [PRD.md](./PRD.md) | 理解业务需求、判断功能优先级时 |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 新增模块、调整链路、做技术决策时 — 含系统架构图、检索/RAG 流程、已知局限 |
| [API.md](./API.md) | 写接口、SSE 事件、错误处理时 — 含完整错误码表、权限矩阵、SSE 格式 |
| [DATABASE.md](./DATABASE.md) | 改表结构、加索引、写迁移时 |
| [DEVELOPMENT.md](./DEVELOPMENT.md) | 搭环境、装依赖、查命令时 |
| [ROADMAP.md](./ROADMAP.md) | 排期、确认当前 Phase 待办时 |
| [TESTING.md](./TESTING.md) | 设计测试、评估检索效果、做压测时 |

---

## 核心链路

**入库**：上传 → 解析 → 分块(512token/50重叠) → Embedding → ChromaDB
**问答**：意图识别 → 问题重写 → 向量+BM25双路检索 → RRF融合 → Rerank(当前NoopReranker) → LLM SSE流式输出

**ChromaDB**：单 collection `docmind`，metadata `kb_id` 隔离各知识库
**会话记忆**：滑动窗口保留最近10轮，超出部分 LLM 摘要压缩

---

## 关键约定

### 后端

- **导入方式**：所有模块内导入使用 `from app.xxx` 绝对路径（如 `from app.core.database import async_session`），禁止用 `from ..core` 相对导入
- **路由 = 薄壳**：api/ 只做参数校验和调用 service，业务逻辑全部在 services/
- **异步优先**：所有 IO 操作用 async/await，DB session 通过 `get_db()` 依赖注入获取
- **配置**：环境变量统一从 `config.py` 的 `settings` 单例读取，禁止硬编码。`.env` 在 `backend/` 目录下，不在项目根目录
- **Schema**：新接口必须定义 Pydantic schema，不裸用 dict

### 前端

- 组件用 Composition API + `<script setup>` 写法
- 所有请求走 `api/` 目录封装，不在组件里直接调 axios
- 状态提升到 Pinia，不用组件内 props 透传超过两层

### 通用

- 所有注释、变量名、提交信息统一用中文
- 不提前过度设计，当前阶段够用即可
- 每次代码变更后必须将操作记录写入 `CHANGE.md`，格式见下方「变更记录规范」

---

## 当前进度

- [x] Phase 1 — SQLAlchemy 模型 + Alembic 迁移 + DB 连接 + FastAPI 入口 + 前端环境
- [x] Phase 1 — ChromaDB 连接 & collection 创建
- [x] Phase 1 — JWT 认证（注册/登录 + 中间件 + 异常类全覆盖）
- [ ] Phase 1 剩余 — 前端登录页 + 路由
- [ ] Phase 2 — 文档入库
- [ ] Phase 3 — 核心问答
- [ ] Phase 4 — 会话记忆
- [ ] Phase 5 — 打磨上线

### 已实现文件

| 文件 | 说明 |
|:---|:---|
| `config.py` | Settings 单例，pydantic-settings 自动从 `backend/.env` 加载 |
| `core/database.py` | `create_async_engine` + `async_sessionmaker` + `Base` 基类 |
| `core/chroma_client.py` | ChromaDB PersistentClient + `docmind` collection（hnsw:space=cosine） |
| `core/security.py` | JWT 令牌（python-jose）+ bcrypt 密码哈希 |
| `core/exceptions.py` | 统一异常类，覆盖 API.md §1.3 全部 20 个错误码 |
| `dependencies.py` | `get_db()` / `get_current_user()` — FastAPI 依赖注入 |
| `models/*.py` | 6 张表：User / KnowledgeBase / Document / Chunk / Conversation / Message |
| `schemas/auth.py` | RegisterRequest / LoginRequest / UserResponse / TokenResponse |
| `services/auth_service.py` | 注册（查重+哈希+入库）、登录（验证+签发 JWT） |
| `api/auth.py` | POST /api/auth/register + POST /api/auth/login |
| `middleware/auth_middleware.py` | 纯 ASGI JWT 验证中间件，公开路由白名单 + OPTIONS 放行 |
| `main.py` | FastAPI app + CORS + AuthMiddleware + auth_router + `/api/health` |
| `frontend/` | Vite + Vue 3 环境搭好，`main.js` + `App.vue` 可运行，其余文件均为空占位 |

---

## 变更记录规范

```markdown
## [日期] vX.X
### 新增
### 修改
### 修复
```
