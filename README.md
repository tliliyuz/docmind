# DocMind

**DocMind是什么？**

这是一个企业内部知识库智能问答平台 —— 你不必知道文档在哪、叫什么名字、关键词是什么，问就行。

多路检索：向量语义检索与 BM25 关键词检索双路并行，RRF 融合后再由 DashScope Rerank 语义精排，兼顾精准与召回。

意图识别：知识查询 / 闲聊 / 元问题三分类，规则快速通道 + Flash 模型兜底，可扩展模型、提示词、topK 等核心参数。

文档入库：PDF / DOCX / Markdown / TXT 四格式上传，Celery 异步流水线完成解析、分块、Embedding 向量化、ChromaDB 入库。

多轮记忆：Token 预算四池子分拆独立截断，滑动窗口保留最近对话，问题重写自动消解代词指代与省略主语。

证据治理：句级修辞过滤 + Evidence Highlight 句级定位 + 三层证据审计，输出 high / medium / low 置信度。

可溯源引用：每个答案附带来源卡片，展示文档名称、页码、证据句高亮，可一键展开查看原始分块内容。

……
![预览图](resources/diagrams/预览.png)

---

## 目录

| 序号 | 主题 | 描述 |
|:---|:---|:---|
| 1 | [核心特性](#核心特性) | 文档入库、多路检索融合、智能问答链路、多轮记忆、知识库管理、管理后台、可溯源引用、质量治理 |
| 2 | [系统架构](#系统架构) | 前端、FastAPI 后端、KnowledgePipeline 检索管线、Celery 异步入库的分层与数据流 |
| 3 | [技术栈](#技术栈) | 后端、AI、检索、存储、前端、部署各层技术选型一览 |
| 4 | [规模量化](#规模量化) | 代码、测试、文档、ADR、测试用例的实测规模数据 |
| 5 | [核心链路](#核心链路) | 入库与问答两条主链路的端到端流程图 |
| 6 | [界面预览](#界面预览) | 登录、知识问答、知识库管理、管理后台页面截图 |
| 7 | [快速开始](#快速开始) | Docker Compose 部署与本地开发环境指引 |
| 8 | [项目结构](#项目结构) | 后端分层、RAG 核心模块、前端结构、测试金字塔目录树 |
| 9 | [质量保障](#质量保障) | 检索召回、答案评分、回归通过率、多轮保活性指标 |
| 10 | [设计文档](#设计文档) | PRD / 架构 / 数据库 / API / RAG / 前端 / UI / ADR 文档索引 |
| 11 | [常见问题](#常见问题) | 文档格式、LLM、检索协同、上下文管理、置信度评估问答 |
| 12 | [License](#license) | 开源协议 |

---

## 核心特性

**文档入库**：支持 PDF / DOCX / Markdown / TXT 四种格式上传，Celery 异步流水线完成解析、智能分块（RecursiveCharacterTextSplitter）、DashScope Embedding 向量化、ChromaDB 入库，前端实时展示入库进度和状态。

**多路检索与融合**：向量语义检索（ChromaDB）与 BM25 关键词检索（rank-bm25 + jieba 中文分词）双路并行，通过 RRF（Reciprocal Rank Fusion）算法融合排序后，经向量相似度粗排过滤低分候选，再由 DashScope Rerank（qwen3-rerank）做语义精排，兼顾语义理解和精确关键词匹配。BM25 支持章节号检测与加权，用户提问包含章节号时自动提升对应章节的检索权重。离线评估 Recall@5 达到 1.000。

**智能问答链路**：意图识别（知识查询 / 闲聊 / 元问题三分类，规则快速通道 + Flash 模型兜底）→ 问题重写（多轮上下文补全）→ 多路检索 → RRF 融合 → 粗排（向量相似度过滤 + top_k 截断，ADR-024）→ DashScope Rerank 语义精排 → 句级修辞过滤 → Evidence Highlight（句级 BM25 定位证据句）→ Prompt 组装 → DeepSeek LLM 流式生成 → 三层证据审计 → SSE 实时推送答案（含置信度评分）。检索与上下文构建由独立的 KnowledgePipeline 管线封装，与 ChatService 职责分离。

**多轮对话与记忆**：支持完整的多轮对话上下文管理，Token 预算四池子分拆独立截断（History / Retrieval / System / User），滑动窗口保留最近对话，问题重写自动消解代词指代和省略主语。

**知识库管理**：支持 public / private 两种可见性模式，private 知识库仅创建者可见，public 知识库全组织可检索。管理员可查看、审计、管理所有知识库和文档。

**管理后台**：系统统计（ECharts 可视化：问答趋势 / 延迟分布 / Token 用量）、Trace 链路追踪（问答全链路各阶段耗时记录与 JSON 详情）、知识库管理、文档管理、用户管理（角色 / 状态 / 密码重置）。

**可溯源引用**：每个答案附带引用来源卡片，展示文档名称、页码、证据句高亮，用户可以一键展开查看原始分块内容。

**知识库质量治理**：句级修辞过滤自动剔除引用性文本（示例、说明等），三层证据审计（引用存在性 → 来源一致性 → 句级证据回溯）对答案进行后验质量检查，输出 high / medium / low 三级置信度，前端实时展示置信度警告。Ragas 自动化评估框架（Faithfulness 0.8436 / Answer Relevancy 0.9210 / Context Precision 0.8556 / Context Recall 0.9702，四项均 ≥ 0.80 达标）持续监控生成质量，与人工评分形成互补。DashScope Rerank（qwen3-rerank）对检索结果做语义精排，Chunk 元数据增强支持章节标题/路径感知，BM25 章节号加权进一步提升结构化文档的检索精度。

---

## 系统架构
---

![系统架构](resources/diagrams/系统架构.png)

---

## 技术栈

| 层面 | 技术 | 说明 |
|:---|:---|:---|
| 后端框架 | FastAPI | 异步 Python Web 框架，原生支持 SSE 流式输出 |
| AI 编排 | LangChain | RAG 链路编排，不依赖高级封装 |
| LLM | DeepSeek | OpenAI 兼容接口，支持深度思考模式（reasoning_content） |
| Embedding | DashScope text-embedding-v3 | 1024 维向量，中文优化 |
| Rerank | DashScope qwen3-rerank | RRF 融合后语义精排，API 异常降级为 RRF 排序 |
| 向量数据库 | ChromaDB | 嵌入式运行，零配置，BaseVectorStore 抽象层支持替换 |
| 关键词检索 | rank-bm25 + jieba | BM25Okapi + 中文分词，三级缓存（进程内 → Redis → 懒加载） |
| 评估框架 | Ragas + datasets | RAG 生成质量自动化评估（Faithfulness / Answer Relevancy / Context Precision / Context Recall） |
| 关系数据库 | MySQL 8.0 | SQLAlchemy 2.0 async ORM + Alembic 迁移 |
| 缓存/队列 | Redis 7.0 + Celery | 异步任务队列 + 分布式锁 + BM25 索引缓存 |
| 前端框架 | Vue 3 + Vite | Composition API + `<script setup>` |
| UI 组件库 | Element Plus | 企业级 Vue 3 组件库 |
| 状态管理 | Pinia | Vue 3 官方推荐状态管理 |
| Markdown | markdown-it + highlight.js | 问答内容渲染 + 代码块高亮 |
| 图表 | ECharts 5 | 管理后台统计可视化 |
| 部署 | Docker Compose + Nginx | 5 服务编排（MySQL / Redis / Backend / Celery / Nginx） |

---

## 规模量化

| 维度 | 数量 | 说明 |
|:---|:---|:---|
| 后端应用代码 | 12,173 行 Python | `backend/app/` |
| 后端测试代码 | 24,567 行 | 测试 ≈ 应用代码 ×2.0 |
| 前端代码 | 11,945 行 | Vue SFC + JS |
| 设计文档 | 12,577 行 | 含 24 份 ADR |
| 架构决策记录 | 24 份 ADR | `ADR-001` ~ `ADR-024` |
| 后端测试文件 | 59 个 | 覆盖 api / core / ingest / rag / schemas / services 全层 |
| 前端测试文件 | 30 个 | 覆盖全部 view / store / util |
| 测试用例总数 | ~1,285 后端 + 513 前端 | 100% 通过 |

---

## 核心链路

![核心链路](resources/diagrams/核心链路.png)

---

## 界面预览

### 登录
DocMind 的入口，支持普通用户和管理员角色登录。

| 页面 | 截图 |
|:---|:---|
| 登录 | ![登录页](resources/prototypes/login.png) |

### 知识问答
核心交互界面：用户用自然语言提问，系统流式返回带来源引用的答案。

| 页面 | 截图 |
|:---|:---|
| 问答首页 | ![主页](resources/prototypes/chat_home.png) |
| 问答对话 | ![聊天页](resources/prototypes/chat_1.png) |

### 知识库管理
管理文档资产：创建知识库、上传文档、查看处理状态和已有分块。

| 页面 | 截图 |
|:---|:---|
| 知识库列表 | ![知识库列表](resources/prototypes/kb_list.png) |
| 知识库详情 | ![知识库详情](resources/prototypes/kb_detail.png) |

### 管理后台
面向管理员的运维审计面板：系统统计、问答全链路追踪、用户管理。

| 页面 | 截图 |
|:---|:---|
| 系统统计 | ![系统统计](resources/prototypes/admin_stus_1.png) |
| 链路追踪 | ![链路追踪列表](resources/prototypes/admin_trace_list.png) |
| 用户管理 | ![用户列表](resources/prototypes/admin_user_list.png) |

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
├── docs/                        # 公用设计文档（PRD / 架构 / 排期 / 变更日志 / 开发指南）
│   ├── tests/                   # 测试文档（测试策略 / 用例跟踪 / 评估集）
│   └── decisions/               # 架构决策记录（ADR，24 篇，ADR-001 ~ ADR-024）
├── backend/
│   ├── alembic/                 # 数据库迁移脚本
│   ├── docs/                    # 后端设计文档（API / 数据库 / RAG 管线）
│   ├── app/
│   │   ├── api/                 # 路由层（仅参数校验 + 调 service）
│   │   │   └── auth / knowledge_base / document / chat / conversation / admin
│   │   ├── models/              # SQLAlchemy ORM 模型（User / KB / Document / Chunk / Conversation / Message / RefreshToken / Trace + UTCDateTime）
│   │   ├── schemas/             # Pydantic 请求/响应模型（含 admin / trace Schema）
│   │   ├── services/            # 业务逻辑层
│   │   │   ├── chat_service.py / chat_helpers.py / sse_stream.py   # 问答三模块（ADR-022，chat 委托 KnowledgePipeline）
│   │   │   └── auth / conversation / document / knowledge_base / admin / trace
│   │   ├── rag/                 # RAG 核心（19 个模块，管线各阶段独立可测）
│   │   │   ├── knowledge_pipeline.py  # 知识管线协调者：重写→检索→RRF→粗排→Rerank→修辞过滤→句子匹配→Prompt
│   │   │   ├── vector_store.py        # 向量存储抽象（BaseVectorStore ABC + ChromaVectorStore，Per-KB Collection）
│   │   │   ├── evidence_auditor.py    # 三层证据审计（引用存在性 / 来源一致性 / 句级证据回溯）
│   │   │   ├── evidence_reviewer.py   # Evidence Review 门控
│   │   │   ├── retriever.py / bm25.py / fusion.py / coarse_ranker.py / reranker.py  # 检索链路（双路检索 + RRF + 粗排 + qwen3-rerank）
│   │   │   ├── intent.py / query_rewriter.py / sentence_matcher.py  # 意图 / 重写 / 修辞过滤 + 证据定位
│   │   │   └── trace_recorder.py / prompt_builder.py / chunker.py / embedder.py / parser.py
│   │   ├── ingest/              # Celery 异步入库（tasks / delete_tasks / lock / celery_app）
│   │   ├── core/                # 基础设施（database / redis_client / chroma_client / security / llm / storage / sse / permissions / uuid_helpers / logging_config / exceptions / utils）
│   │   └── middleware/          # 中间件（JWT 认证 / 限流 / Request ID）
│   └── tests/                   # 后端测试（pytest，53 个文件 / ~1,240 用例）
│       ├── unit/                # 单元测试（api / core / ingest / rag / schemas / services）
│       ├── integration/         # 集成测试（chat_trace）
│       ├── regression/          # 回归测试（单轮 + 多轮 RAG 保活）
│       ├── eval/                # 检索评估 + Ragas 生成质量评估（阶段评估集 + 多轮评估集 + Ragas 自动化评估脚本）
│       └── performance/         # 性能测试（locustfile + 压测报告 + run 脚本）
├── frontend/
│   ├── docs/                    # 前端设计文档（交互规范 / UI 设计规范）
│   ├── src/
│   │   ├── views/               # 页面（ChatPage / LoginPage / KnowledgeList / KnowledgeDetail / PublicKnowledgeList）
│   │   │   └── admin/           # 后台管理（Stats / TraceList / TraceDetail / KnowledgeList / DocumentList / UserList / UserDetail）
│   │   ├── components/          # 组件（chat / layout / charts）
│   │   │   ├── chat/            # ChatInput / MessageItem / MessageList / WelcomeScreen
│   │   │   ├── layout/          # AppLayout / AdminLayout / Sidebar
│   │   │   └── charts/          # LatencyChart / TokenChart / TrendChart（ECharts 封装）
│   │   ├── stores/              # Pinia 状态管理（auth / chat / knowledge / conversation）
│   │   ├── api/                 # HTTP 请求封装（Axios + Token 自动刷新拦截器 + Trace API）
│   │   ├── router/              # Vue Router + 路由守卫（含 Admin 子路由 meta 遍历）
│   │   ├── composables/         # 组合式函数（useECharts）
│   │   ├── constants/           # 常量定义
│   │   ├── styles/              # 全局样式（Design Token --dm-* 变量）
│   │   └── utils/               # 工具函数（SSE 解析 / Markdown 渲染 / 格式化）
│   └── tests/                   # 前端测试（vitest，30 个文件 / 513 用例）
├── docker-compose.yml           # 5 服务编排（MySQL / Redis / Backend / Celery / Nginx）
├── Dockerfile.backend           # FastAPI + Celery Worker 镜像
├── Dockerfile.frontend          # Nginx + Vite 构建产物镜像
├── nginx.server.conf            # 反向代理 + SSE 支持 + SPA fallback
```

---

## 质量保障

| 指标 | 目标 | 当前                                   |
|:---|:---|:-------------------------------------|
| 检索 Recall@5 | ≥ 0.85 | **1.000**（28/28 完全召回）                |
| 答案综合评分 | ≥ 4.0/5.0 | **4.71/5.0**（最终评分） |
| 回归测试通过率 | 100% | **100%**（后端 800+ / 前端 230+）          |
| 多轮 RAG 保活性 | 无退化 | **5.0/5.0** 满分（23 轮均有 sources）       |
| Ragas 生成质量 | 四项均 ≥ 0.80 | **Faithfulness 0.8436 / AR 0.9210 / CP 0.8556 / CR 0.9702**（全部达标） |

测试覆盖 6 个层次：单元测试、接口测试、前端组件测试、离线检索评估、人工答案评分、回归测试。完整的测试策略和评分标准见 [测试策略文档](docs/tests/TESTING.md)。

---

## 设计文档

| 文档 | 说明 |
|:---|:---|
| [PRD.md](docs/PRD.md) | 产品需求文档 — 业务场景、用户痛点、权限模型、验收标准 |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构设计文档 — 技术选型、系统架构、入库/问答流程、关键设计决策 |
| [DATABASE.md](backend/docs/DATABASE.md) | 数据库设计文档 — ER 关系、表 DDL、索引策略 |
| [API.md](backend/docs/API.md) | 接口文档 — REST 接口定义、SSE 事件格式、错误码、权限矩阵 |
| [RAG_PIPELINE.md](backend/docs/RAG_PIPELINE.md) | RAG 管线详细设计 — 多路检索、Prompt 组装、问题重写、意图识别、修辞过滤、Evidence Highlight、三层证据审计、Trace 链路追踪 |
| [DEVELOPMENT.md](docs/DEVELOPMENT.md) | 开发指南 — 环境配置、依赖清单、本地启动、Docker 部署 |
| [ROADMAP.md](docs/ROADMAP.md) | 开发排期 — Phase 1-6（含 5.5）任务分解、时间线、依赖关系 |
| [TESTING.md](docs/tests/TESTING.md) | 测试策略 — 检索评估指标、人工评分标准、压测指标 |
| [TEST_CASES.md](docs/tests/TEST_CASES.md) | 测试用例跟踪 — 各 Phase 测试用例清单与执行状态 |
| [UIDESIGN.md](frontend/docs/UIDESIGN.md) | UI 设计规范 — Design Token（CSS 变量）、组件样式规范 |
| [FRONTEND.md](frontend/docs/FRONTEND.md) | 前端交互文档 — 页面布局、交互流程、组件行为规范 |
| [CHANGELOG.md](docs/CHANGELOG.md) | 变更日志 — 遵循 Keep a Changelog 格式 |
| [decisions/](docs/decisions/) | 架构决策记录（ADR）— 24 篇关键设计决策的详细记录与背景分析（ADR-001 ~ ADR-024） |

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

**Q: 答案的置信度是如何评估的？**
系统在 LLM 生成答案后执行三层证据审计：第一层检查答案中是否包含引用标注（`[来源N]`），第二层评估引用来源是否集中在少数文档，第三层通过句级关键词匹配验证证据是否真实存在。三层结果综合输出 high / medium / low 置信度，前端在 medium/low 时展示警告提示，帮助用户判断是否需要核实原始文档。

---

## License

本项目基于 [MIT License](LICENSE) 开源。
