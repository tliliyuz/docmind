# DocMind

企业内部知识库智能问答平台。员工用自然语言提问，系统从文档中语义检索，由 LLM 生成可溯源的答案。

> 详细设计见 DESIGN.md

---

## 技术栈

**后端**：Python / FastAPI / LangChain / ChromaDB / MySQL / Redis / Celery
**前端**：Vue 3 / Vite / Element Plus / Pinia / Axios
**AI**：OpenAI 兼容接口 / text-embedding-3-small / SSE 流式输出

---

## 目录结构
docmind/
├── backend/app/
│   ├── api/          # 路由层
│   ├── models/       # SQLAlchemy 模型
│   ├── schemas/      # Pydantic 模型
│   ├── services/     # 业务逻辑
│   ├── rag/          # RAG 核心（parser/chunker/embedder/retriever/reranker）
│   ├── ingest/       # Celery 异步入库任务
│   └── core/         # 基础设施（db/chroma/jwt/sse/storage）
├── frontend/src/
│   ├── views/        # 页面（ChatPage / LoginPage / admin）
│   ├── components/   # chat 组件 + layout
│   ├── stores/       # Pinia 状态
│   └── api/          # HTTP 请求封装
└── backend/knowledge_samples/  # 示例知识库文档

---

## 核心链路

**入库**：上传 → 解析 → 分块(512token/50重叠) → Embedding → ChromaDB
**问答**：意图识别 → 问题重写 → 向量+BM25双路检索 → RRF融合 → Rerank(当前NoopReranker) → LLM SSE流式输出

**ChromaDB**：单 collection `docmind`，metadata `kb_id` 隔离各知识库
**会话记忆**：滑动窗口保留最近10轮，超出部分 LLM 摘要压缩

---

## 当前进度

- [x] Phase 1 骨架（FastAPI + Vue3 + Git）
- [ ] Phase 2 文档入库
- [ ] Phase 3 核心问答
- [ ] Phase 4 会话记忆
- [ ] Phase 5 打磨上线

---

## 编码约束

**通用**
- 所有注释、变量名、提交信息统一用中文
- 不提前过度设计，当前阶段够用即可

**后端**
- 异步优先：所有 IO 操作用 async/await
- 路由只做参数校验和调用 service，业务逻辑全部在 services/
- 环境变量统一从 config.py 读取，禁止硬编码
- 新接口必须加 Pydantic schema，不裸用 dict

**前端**
- 组件用 Composition API + `<script setup>` 写法
- 所有请求走 api/ 目录封装，不在组件里直接调 axios
- 状态提升到 Pinia，不用组件内 props 透传超过两层

---

## 变更记录规范

详细变更记录写入 `CHANGE.md`，格式：

```markdown
## [日期] vX.X
### 新增
### 修改  
### 修复
```