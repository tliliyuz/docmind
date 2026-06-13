# DocMind

> 企业内部知识库智能问答平台 —— 你不必知道文档在哪、叫什么名字、关键词是什么，问就行。

DocMind 是面向中型企业的知识库问答系统。员工用自然语言提问，系统从上传的 PDF、Word、Markdown 等文档中进行语义检索，由大语言模型生成可溯源的答案，并附带引用来源和证据高亮。

---

## 核心特性

**文档入库**：支持 PDF / DOCX / Markdown / TXT 四种格式上传，Celery 异步流水线完成解析、智能分块（RecursiveCharacterTextSplitter）、DashScope Embedding 向量化、ChromaDB 入库，前端实时展示入库进度和状态。

**多路检索与融合**：向量语义检索（ChromaDB）与 BM25 关键词检索（rank-bm25 + jieba 中文分词）双路并行，通过 RRF（Reciprocal Rank Fusion）算法融合排序，兼顾语义理解和精确关键词匹配，离线评估 Recall@5 达到 1.000。

**智能问答链路**：意图识别（知识查询 / 闲聊 / 元问题三分类）→ 问题重写（多轮上下文补全）→ 多路检索 → RRF 融合 → Evidence Highlight（句级 BM25 定位证据句）→ Prompt 组装 → DeepSeek LLM 流式生成，SSE 实时推送答案。

**多轮对话与记忆**：支持完整的多轮对话上下文管理，Token 预算四池子分拆独立截断（History / Retrieval / System / User），滑动窗口保留最近对话，问题重写自动消解代词指代和省略主语。

**知识库管理**：支持 public / private 两种可见性模式，private 知识库仅创建者可见，public 知识库全组织可检索。管理员可查看、审计、管理所有知识库和文档。

**管理后台**：系统统计（ECharts 可视化：问答趋势 / 延迟分布 / Token 用量）、Trace 链路追踪（问答全链路各阶段耗时记录与 JSON 详情）、知识库管理、文档管理、用户管理（角色 / 状态 / 密码重置）。

**可溯源引用**：每个答案附带引用来源卡片，展示文档名称、页码、证据句高亮，用户可以一键展开查看原始分块内容。

---

## 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│                    前端 (Vue 3 + Element Plus)                │
│  ChatPage │ LoginPage │ AdminPages │ Sidebar │ SSE 解析      │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTP + SSE
┌──────────────────────────▼───────────────────────────────────┐
│                    FastAPI 后端 (异步)                         │
│                                                              │
│  api/auth   api/kb   api/doc   api/chat   api/admin          │
│     │          │        │         │          │               │
│  services/  services/ services/ services/ services/          │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │                RAG 核心（问答链路）                     │    │
│  │  Intent → Rewrite → Retriever → RRF → Rerank → LLM  │    │
│  └────────────────────────┬─────────────────────────────┘    │
│                           │                                   │
│  ┌──────────┬─────────────┼──────────────┬────────────────┐  │
│  │ ChromaDB │   MySQL     │    Redis     │  File Storage  │  │
│  │ (向量库)  │  (业务数据)  │  (缓存/队列) │  (文档文件)    │  │
│  └──────────┴─────────────┴──────────────┴────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │           Celery Worker（文档异步入库）                  │    │
│  │  Parser → Chunker → Embedder → ChromaDB + MySQL      │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

---

## 技术栈

| 层面 | 技术 | 说明 |
|:---|:---|:---|
| 后端框架 | FastAPI | 异步 Python Web 框架，原生支持 SSE 流式输出 |
| AI 编排 | LangChain | RAG 链路编排，不依赖高级封装 |
| LLM | DeepSeek | OpenAI 兼容接口，支持深度思考模式（reasoning_content） |
| Embedding | DashScope text-embedding-v3 | 1024 维向量，中文优化 |
| 向量数据库 | ChromaDB | 嵌入式运行，零配置，单 collection + metadata 隔离 |
| 关键词检索 | rank-bm25 + jieba | BM25Okapi + 中文分词，三级缓存（进程内 → Redis → 懒加载） |
| 关系数据库 | MySQL 8.0 | SQLAlchemy 2.0 async ORM + Alembic 迁移 |
| 缓存/队列 | Redis 7.0 + Celery | 异步任务队列 + 分布式锁 + BM25 索引缓存 |
| 前端框架 | Vue 3 + Vite | Composition API + `<script setup>` |
| UI 组件库 | Element Plus | 企业级 Vue 3 组件库 |
| 状态管理 | Pinia | Vue 3 官方推荐状态管理 |
| Markdown | markdown-it + highlight.js | 问答内容渲染 + 代码块高亮 |
| 图表 | ECharts 5 | 管理后台统计可视化 |
| 部署 | Docker Compose + Nginx | 5 服务编排（MySQL / Redis / Backend / Celery / Nginx） |

---

## 界面预览

| 页面 | 截图 |
|:---|:---|
| 登录 | ![登录页](resources/img/login.png) |
| 问答首页 | ![主页](resources/img/chat_home.png) |
| 问答对话 | ![聊天页](resources/img/chat_1.png) |
| 知识库列表 | ![知识库列表](resources/img/kb_list.png) |
| 知识库详情 | ![知识库详情](resources/img/kb_detail.png) |
| 系统统计 | ![系统统计](resources/img/admin_stus_1.png) |
| 链路追踪 | ![链路追踪列表](resources/img/admin_trace_list.png) |
| 用户管理 | ![用户列表](resources/img/admin_user_list.png) |

---

## 快速开始

### Docker Compose 部署（推荐）

前置要求：Docker 20.10+ 和 Docker Compose 2.0+。

```bash
# 1. 配置环境变量
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入 LLM API Key、Embedding API Key、JWT 密钥等

# 2. 构建并启动全部服务（MySQL + Redis + Backend + Celery + Nginx）
docker-compose up -d --build

# 3. 执行数据库迁移
docker-compose exec backend alembic upgrade head

# 4. 访问
#    前端页面：http://localhost
#    后端 API：http://localhost/api
```

生产环境务必修改 `.env` 中的 `JWT_SECRET_KEY`（64 字符随机字符串）、`MYSQL_PASSWORD`、`LLM_API_KEY` 等敏感配置，并确认 `DEBUG=false`。

### 本地开发

前置要求：Python 3.11+、Node.js 18+、MySQL 8.0+、Redis 7.0+。

**后端**：

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 在 backend/ 下创建 .env，填入实际凭证（参考 DEVELOPMENT.md §4）

alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 另开终端启动 Celery Worker
# Linux/Mac:
celery -A app.ingest.celery_app worker --loglevel=info
# Windows（必须加 --pool=solo）:
celery -A app.ingest.celery_app worker --loglevel=info --pool=solo
```

**前端**：

```bash
cd frontend
npm install
npm run dev     # http://localhost:5173，/api 自动代理到后端 8000 端口
```

详细的环境变量说明、依赖清单、编码约定参见 [开发指南](docs/DEVELOPMENT.md)。

---

## 项目结构

```
docmind/
├── docs/                        # 公用设计文档（PRD / 架构 / 排期 / 测试策略 / 变更日志）
├── backend/
│   ├── alembic/                 # 数据库迁移脚本
│   ├── docs/                    # 后端设计文档（API / 数据库）
│   ├── app/
│   │   ├── api/                 # 路由层（auth / kb / document / chat / conversation / admin）
│   │   ├── models/              # SQLAlchemy ORM 模型（6 张业务表）
│   │   ├── schemas/             # Pydantic 请求/响应模型
│   │   ├── services/            # 业务逻辑层
│   │   ├── rag/                 # RAG 核心（检索器 / 分块器 / Embedding / 意图识别 / 问题重写）
│   │   ├── ingest/              # Celery 异步入库任务
│   │   ├── core/                # 基础设施（DB / Redis / ChromaDB / JWT / 文件存储 / SSE）
│   │   └── middleware/          # 中间件（JWT 认证 / 限流）
│   └── tests/                   # 后端测试（pytest，649+ 用例）
├── frontend/
│   ├── docs/                    # 前端设计文档（交互规范 / UI 设计规范）
│   ├── src/
│   │   ├── views/               # 页面（ChatPage / LoginPage / Admin 页面组）
│   │   ├── components/          # 组件（chat / layout / admin）
│   │   ├── stores/              # Pinia 状态管理（auth / chat / knowledge / conversation）
│   │   ├── api/                 # HTTP 请求封装（Axios + Token 自动刷新拦截器）
│   │   ├── router/              # Vue Router + 路由守卫
│   │   ├── styles/              # 全局样式（Design Token --dm-* 变量）
│   │   └── utils/               # 工具函数（SSE 解析 / Markdown 渲染）
│   └── tests/                   # 前端测试（vitest，220+ 用例）
├── docker-compose.yml           # 5 服务编排
├── Dockerfile.backend           # FastAPI + Celery Worker 镜像
├── Dockerfile.frontend          # Nginx + Vite 构建产物镜像
└── nginx.conf                   # 反向代理 + SSE 支持 + SPA fallback
```

---

## 开发进度

项目采用分阶段迭代开发，每个阶段完成后立即编写测试并全量回归，作为下一阶段的准入条件。

| 阶段 | 内容 | 状态 |
|:---|:---|:---|
| Phase 1 | 骨架搭建：FastAPI + Vue 3 脚手架、MySQL 6 表、ChromaDB、JWT 认证、前端登录页与路由 | ✅ 已完成 |
| Phase 2 | 文档入库：知识库 CRUD、文档上传、Celery 异步流水线（解析 → 分块 → 向量化 → 入库） | ✅ 已完成 |
| Phase 2.5 | 知识库可见性：public / private 分离、公共知识库浏览页 | ✅ 已完成 |
| Phase 3 | 核心问答：多路检索、RRF 融合、SSE 流式输出、前端问答界面、引用来源展示 | ✅ 已完成 |
| Phase 4 | 会话与记忆：多轮对话、会话 CRUD、问题重写、Refresh Token、结构化日志 | ✅ 已完成 |
| Phase 5 | 打磨上线：意图识别、Evidence Highlight、管理后台、限流、Trace 链路追踪、Docker 部署 | ⏳ 进行中（外部资源 UUID 化待完成） |
| Phase 6 | 迭代优化：DashScope Rerank、结构感知分块、LLM 摘要压缩等高级功能 | 规划中 |

详细的任务分解和依赖关系见 [开发排期](docs/ROADMAP.md)。

---

## 质量保障

| 指标 | 目标 | 当前 |
|:---|:---|:---|
| 检索 Recall@5 | ≥ 0.85 | **1.000**（28/28 完全召回） |
| 答案综合评分 | ≥ 4.0/5.0 | **4.76/5.0**（第 2 轮人工评分） |
| 回归测试通过率 | 100% | **100%**（后端 649 + 前端 220） |
| 多轮 RAG 保活性 | 无退化 | **5.0/5.0** 满分（23 轮均有 sources） |

测试覆盖 6 个层次：单元测试、接口测试、前端组件测试、离线检索评估、人工答案评分、回归测试。完整的测试策略和评分标准见 [测试策略文档](docs/TESTING.md)。

---

## 设计文档

项目采用文档驱动开发，所有代码实现严格遵循对应的设计文档。

| 文档 | 说明 |
|:---|:---|
| [PRD.md](docs/PRD.md) | 产品需求文档 — 业务场景、用户痛点、权限模型、验收标准 |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构设计文档 — 技术选型、系统架构、入库/问答流程、关键设计决策 |
| [DATABASE.md](backend/docs/DATABASE.md) | 数据库设计文档 — ER 关系、6 张表 DDL、索引策略 |
| [API.md](backend/docs/API.md) | 接口文档 — REST 接口定义、SSE 事件格式、错误码、权限矩阵 |
| [DEVELOPMENT.md](docs/DEVELOPMENT.md) | 开发指南 — 环境配置、依赖清单、本地启动、Docker 部署 |
| [ROADMAP.md](docs/ROADMAP.md) | 开发排期 — Phase 1-6 任务分解、时间线、依赖关系 |
| [TESTING.md](docs/TESTING.md) | 测试策略 — 检索评估指标、人工评分标准、压测指标 |
| [UIDESIGN.md](frontend/docs/UIDESIGN.md) | UI 设计规范 — Design Token（CSS 变量）、组件样式规范 |
| [FRONTEND.md](frontend/docs/FRONTEND.md) | 前端交互文档 — 页面布局、交互流程、组件行为规范 |
| [CHANGE.md](docs/CHANGE.md) | 变更日志 — 每次代码变更的详细记录 |

---

## 常见问题

**Q: 支持哪些文档格式？**
PDF、DOCX、Markdown、TXT 四种格式。不支持旧版 `.doc` 格式，上传时前端会提示「请先转换为 .docx」。单文件大小限制 50MB。

**Q: 问答支持哪些 LLM？**
后端通过 OpenAI 兼容接口调用 LLM，当前使用 DeepSeek，可替换为通义千问、OpenAI 等任何兼容接口。Embedding 使用 DashScope text-embedding-v3（1024 维），可在配置中切换。

**Q: 向量检索和关键词检索如何协同？**
两路独立检索后通过 RRF（Reciprocal Rank Fusion，k=60）算法融合排序。向量检索擅长语义匹配（搜「墨盒怎么换」能找到「打印机耗材更换步骤」），BM25 擅长精确关键词匹配，融合后兼顾两者优势。

**Q: 多轮对话的上下文如何管理？**
采用 Token 预算四池子分拆（History / Retrieval / System / User），各池独立截断互不侵蚀。问题重写模块在检索前自动消解代词指代（如「它需要几个人」→「代码评审需要几个人」），确保检索质量不受多轮影响。

---

## License

本项目为内部使用项目。
