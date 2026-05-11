# DocMind 需求设计文档

## 1. 业务场景与项目概述

### 1.1 业务背景

**场景：中型互联网公司的"信息孤岛"问题**

某公司有 300+ 员工，分布在技术、产品、运营、人事、财务等 6 个部门。公司日常运转依赖大量制度文档和业务规范，但这些文档散落在各个角落：

- **HR 侧**：入职指南、薪资福利政策、报销流程、请假制度、招聘 SOP
- **IT 侧**：VPN 配置教程、打印机使用说明、系统权限申请流程、常见故障排查
- **行政侧**：会议室预约规则、访客登记流程、办公用品申领
- **业务侧**：各产品线的接口文档、数据安全规范、合规检查清单

**真实痛点**：

1. **新人入职成本高**：新员工面对海量 Wiki 页面不知道从哪看起，一个简单问题（"报销打车费要填什么表"）需要翻 5-10 分钟文档或反复问 HR
2. **文档检索效率低**：公司 Confluence/语雀上的全文搜索只能做关键词匹配。搜"墨盒怎么换"匹配不到"打印机耗材更换步骤"，搜"加班调休"漏掉"弹性工作制与补休规则"
3. **跨部门知识获取困难**：技术想了解报销规则要翻财务文档，运营想查数据安全规范要翻合规文档，找不到或者找到的版本已经过时
4. **重复问答消耗人力**：HR 和 IT 支持人员每天回答大量重复问题，而这些答案明明写在文档里

### 1.2 解决方案

**DocMind —— 企业内部知识库智能问答平台**

将公司所有制度文档、操作手册、规范文件统一入库，员工用**自然语言提问**，系统**理解语义**后从文档中检索相关内容，由 LLM 汇总生成**准确、可溯源**的答案。

核心价值：**你不必知道文档在哪、叫什么名字、关键词是什么，问就行。**

### 1.3 典型使用场景

| 角色 | 场景 | 传统方式 | DocMind |
|:---|:---|:---|:---|
| 新入职员工 | "报销差旅费需要提交哪些材料？" | 翻 Wiki 10 分钟，或问 HR 等回复 | 输入问题，5 秒得到答案并附源文档 |
| 技术开发 | "生产环境数据库密码怎么申请？" | 不知道找哪个文档，问了一圈人 | 检索 IT 规范文档，直接定位申请流程 |
| HR | "2025 年的年假政策相比去年有什么变化？" | 翻历史版本文档对比 | 自动检索相关段落并对比 |
| 运维 | "服务器安全基线检查有哪些项目？" | 翻安全规范 PDF 逐条看 | 自然语言提问，按检查项返回 |

### 1.4 对标参考

设计思路对齐 **Ragent AI**（Java 企业级 RAG 平台），本项目用 Python 生态重新实现核心设计，适配校招简历的技术栈。

---

## 2. 技术选型

| 层面 | 技术 | 说明 |
|:---|:---|:---|
| 后端框架 | FastAPI | 异步 Python Web 框架 |
| AI 编排 | LangChain | RAG 链路编排，但不依赖其高级封装 |
| LLM | OpenAI API 兼容接口 | 支持 OpenAI / 通义千问 / DeepSeek 等 |
| Embedding | OpenAI text-embedding-3-small | 1536 维向量 |
| 向量数据库 | ChromaDB | 嵌入式运行，零配置 |
| 关系数据库 | MySQL + aiomysql | 业务数据持久化 |
| 异步 ORM | SQLAlchemy 2.0 async | 异步数据库操作 |
| 缓存 | Redis | 会话缓存 |
| 异步入库 | Redis + Celery | 文档入库异步任务队列 |
| 文档解析 | Unstructured + PyPDF2 + python-docx | 多格式文档解析 |
| 文件存储 | 本地磁盘（可扩展至 OSS） | 当前本地存储，预留 S3 兼容接口 |
| LLM 缓存 | LangChain Cache (可选) | 减少重复 LLM 调用 |
| 前端框架 | Vue 3 + Vite | Composition API + SFC |
| UI 组件库 | Element Plus | 企业级 Vue 3 组件库 |
| 状态管理 | Pinia | Vue 3 官方推荐状态管理 |
| 路由 | Vue Router 4 | SPA 路由 |
| HTTP 客户端 | Axios | 请求拦截、响应处理 |
| Markdown 渲染 | markdown-it | 问答内容 Markdown 渲染 |
| 包管理器 | npm | Node.js 默认 |
| 前端语言 | JavaScript | SFC + JS（非 TypeScript） |
| 流式输出 | SSE (Server-Sent Events) | 实时推送 LLM 生成内容 |

### 2.1 知识库示例数据

系统预置一个模拟企业内部的知识库目录，用于开发测试和演示：

```
知识库 "公司内部知识库"
├── 📁 HR 人事
│   ├── 📄 入职指南.md          — 新员工入职流程、账号开通、设备申领
│   ├── 📄 薪资与福利政策.md     — 薪资结构、社保公积金、年度体检
│   ├── 📄 招聘流程SOP.md       — 岗位发布、简历筛选、面试安排
│   ├── 📄 报销制度.md          — 差旅报销、日常费用、审批流程
│   └── 📄 请假与考勤制度.md     — 年假/事假/病假规则、打卡异常处理
├── 📁 IT 支持
│   ├── 📄 VPN配置指南.md       — 各平台 VPN 客户端安装与连接
│   ├── 📄 打印机使用说明.md     — 驱动安装、墨盒更换、常见故障
│   ├── 📄 系统权限申请流程.md   — 数据库/服务器/管理后台权限
│   └── 📄 信息安全规范.md       — 密码策略、数据分类、外发管控
├── 📁 行政服务
│   ├── 📄 会议室预约规则.md     — 预约流程、设备使用、超时释放
│   └── 📄 访客登记流程.md       — 访客预约、门禁、接待规范
├── 📁 业务规范
│   ├── 📄 数据安全规范.md       — 用户数据处理、脱敏规则、合规检查
│   ├── 📄 接口文档编写规范.md   — OpenAPI 规范、命名约定、示例
│   └── 📄 代码评审标准.md       — 评审流程、检查清单、通过标准
└── 📁 财务制度
    ├── 📄 开票信息与流程.md     — 开票资质、税号、申请步骤
    └── 📄 采购审批制度.md       — 采购额度、审批链、合同归档
```

这些文档直接放在 `backend/knowledge_samples/` 目录下，开发阶段可一键导入测试。

---

## 3. 核心功能模块

### 3.1 模块总览：业务痛点 → 技术方案

| 业务痛点 | 对应模块 | 技术方案 | 效果 |
|:---|:---|:---|:---|
| 文档格式五花八门（PDF/Word/MD） | **文档解析** | Apache Tika 思路 → Python `unstructured` + PyPDF2 | 统一提取纯文本 |
| 完整文档太长，无法直接检索 | **智能分块** | 固定大小 + 结构感知分块，重叠窗口保留上下文 | 检索粒度精准，不丢上下文 |
| 关键词搜索"墨盒怎么换"找不到"打印机耗材更换" | **多路检索** | 向量检索（语义）+ BM25（关键词）+ RRF 融合 | 召回率大幅提升 |
| 搜出来的结果排序不准 | **Rerank 重排序**（Phase 3） | DashScope Rerank 模型精排 | 相关文档排在前面 |
| 用户连续提问"怎么申请"，系统不知道在问什么 | **问题重写** | LLM 结合对话历史补全指代和上下文 | 多轮对话不丢失意图 |
| 用户问"今天天气"走知识库检索是浪费 | **意图识别** | LLM 分类：知识查询 / 闲聊 / 工具调用 | 路由到正确处理分支 |
| 200 页制度文档的检索结果塞给 LLM，Token 爆炸 | **Rerank 截断** | 检索 top-10 → 融合 → Rerank 后取 top-3 | 精准上下文，控制 Token |
| 长对话 30 轮后 Token 超限 | **会话记忆** | 滑动窗口 + 旧消息 LLM 摘要压缩 | 记忆不丢，Token 受控 |
| 大文件（100页PDF）上传后同步处理，用户等很久 | **异步入库** | Redis + Celery 异步任务 | 上传即返回，后台处理 |

### 3.2 功能模块树

```
DocMind
├── 文档入库模块（Ingestion）
│   ├── 文档上传 & 格式解析
│   ├── 文本分块策略
│   ├── Embedding 向量化
│   └── 向量入库（ChromaDB）
├── 智能问答模块（Chat）
│   ├── 单路检索（向量检索）
│   ├── 多路检索（向量 + BM25）
│   ├── 结果融合排序（RRF）
│   ├── Rerank 重排序
│   ├── Prompt 组装 & LLM 调用
│   └── SSE 流式输出
├── 会话管理模块（Session）
│   ├── 多轮对话上下文
│   ├── 滑动窗口记忆
│   └── 会话 CRUD
├── 知识库管理模块（Knowledge Base）
│   ├── 知识库 CRUD
│   ├── 文档列表 & 状态
│   └── 分块可视化
└── 意图识别模块（Intent）
    ├── 意图分类（知识查询 / 闲聊 / 工具调用）
    └── 问题重写（多轮上下文补全）
```

### 3.3 文档入库流程（对标 Ragent Ingestion Pipeline）

```
用户上传文档
    ↓
[Parser] 解析文档 → 提取纯文本 + 元数据（页数、段落、表格）
    ↓
[Chunker] 智能分块 → 按段落/固定大小切分，保留上下文重叠
    ↓
[Embedder] 向量化 → 调用 Embedding API 生成向量
    ↓
[Indexer] 写入 ChromaDB → 分块文本 + 向量 + 元数据
    ↓
更新 MySQL 中的文档状态 → 入库完成
```

**分块策略**：
- 固定大小：512 tokens / chunk，重叠 50 tokens（适合通用文档）
- 结构感知：按 Markdown 标题层级切分（适合结构化文档）

### 3.4 问答流程（对标 Ragent Chat Chain）

```
用户提问
    ↓
[Intent] 意图识别 → 判断类型（查知识库 / 闲聊）
    ↓ （如果是查知识库）
[Rewrite] 问题重写 → 结合对话历史补全上下文
    ↓
[Retrieval] 多路检索 → 向量检索 + BM25 关键词检索
    ↓
[Fusion] RRF 融合排序 → 合并两路结果
    ↓
[Rerank] 重排序 → 当前跳过，Phase 3 接入 DashScope Rerank API
    ↓
[Prompt] 组装 Prompt → 拼接检索结果 + 对话历史 + 用户问题
    ↓
[LLM] 调用 LLM → SSE 流式返回答案
```

### 3.5 多路检索设计

| 通道 | 技术 | 优势 | 劣势 |
|:---|:---|:---|:---|
| 向量检索 | Embedding + ChromaDB | 语义理解强 | 精确匹配弱（如订单号） |
| BM25 关键词 | rank-bm25 | 精确匹配强 | 不理解语义 |

融合策略：**RRF (Reciprocal Rank Fusion)**
```
score(doc) = Σ 1 / (k + rank_i(doc))   # k=60
```

### 3.6 会话记忆策略

- **滑动窗口**：保留最近 N 轮对话（默认 10 轮）
- **摘要压缩**：超过窗口的旧消息用 LLM 生成摘要
- **Token 控制**：总上下文 Token 数不超过模型上限的 80%

### 3.7 ChromaDB Collection 策略

| 阶段 | 方案 | 说明 |
|:---|:---|:---|
| 当前（2周内） | **共用 Collection + Metadata 隔离** | 所有知识库共用一个 `docmind` collection，通过 metadata 中的 `kb_id` 字段在查询时做 WHERE 过滤，快速迭代 |
| 2周后评估 | 评估是否需要独立 Collection | 当知识库数量增多或业务隔离需求明显时，考虑迁移 |
| 生产标准 | 3 个以上完全独立的业务线 → 独立 Collection；否则共用 | 独立 Collection 的优点是物理隔离、可单独配置索引参数；代价是内存占用增加 |

**当前实现要点**：
- ChromaDB 只有一个 collection：`docmind`
- 每个 chunk 写入时带 metadata：`{"kb_id": 1, "doc_id": 5, "chunk_index": 3, "page": 2}`
- 检索时加 where 条件过滤 kb_id：
```python
collection.query(
    query_embeddings=[query_vector],
    n_results=10,
    where={"kb_id": kb_id}
)
```

### 3.8 Rerank 策略

| 阶段 | 方案 | 说明 |
|:---|:---|:---|
| 当前（Phase 1-2） | **跳过** | 先跑通核心链路，仅用 RRF 融合排序。省略 Rerank 对初期效果影响不大 |
| Phase 3 后续 | **DashScope Rerank API** | 中文场景首选，阿里通义千问的 Rerank 模型对中文长文本效果最好，且有免费额度 |
| 代码设计 | **预留接口** | `reranker.py` 中先实现 `NoopReranker`（透传不做重排），后续替换为 `DashScopeReranker`，业务代码不动 |

```python
# rag/reranker.py - 接口设计
from abc import ABC, abstractmethod

class BaseReranker(ABC):
    @abstractmethod
    async def rerank(self, query: str, documents: list, top_k: int) -> list:
        ...

class NoopReranker(BaseReranker):
    """占位实现，直接截取 top_k"""
    async def rerank(self, query, documents, top_k):
        return documents[:top_k]

class DashScopeReranker(BaseReranker):
    """后续实现：调用 DashScope Rerank API"""
    async def rerank(self, query, documents, top_k):
        # TODO: Phase 3 实现
        ...
```

### 3.9 文件存储策略

| 阶段 | 方案 | 说明 |
|:---|:---|:---|
| 当前 | **本地磁盘存储** | 文件保存在 `backend/uploads/` 目录，路径格式 `uploads/{kb_id}/{doc_id}_{filename}` |
| 扩展 | **S3 兼容对象存储（OSS/MinIO）** | 抽象 `StorageBackend` 接口，本地实现和 OSS 实现可互换 |

```python
# 当前：本地存储
UPLOAD_DIR = Path("uploads")
file_path = UPLOAD_DIR / str(kb_id) / f"{doc_id}_{filename}"
file_path.parent.mkdir(parents=True, exist_ok=True)

# 后续扩展：通过 StorageBackend 接口替换
class StorageBackend(ABC):
    async def save(self, file) -> str: ...
    async def read(self, path: str) -> bytes: ...
    async def delete(self, path: str) -> None: ...

class LocalStorage(StorageBackend): ...    # 当前使用
class OSSStorage(StorageBackend): ...      # 后续扩展
```

### 3.10 异步入库方案

**方案：Redis + Celery**

```
用户上传文档
    ↓
FastAPI 接收文件 → 保存本地 → 创建 document 记录(status=uploading)
    ↓
dispatch Celery Task: ingest_document(doc_id, kb_id, file_path)
    ↓
立即返回 {"doc_id": 123, "status": "uploading"} 给前端
    ↓
Celery Worker 异步执行入库流水线:
   Parser → Chunker → Embedder → Indexer
    ↓
更新 document.status = 'completed' / 'failed'
```

**为什么 Celery 而不是 BackgroundTasks**：
- FastAPI 的 BackgroundTasks 随进程退出而丢失任务
- Celery 有持久化机制（任务存 Redis），Worker 重启后能继续
- Celery 天然支持重试、超时控制、任务监控

**Celery 配置要点**：
```python
# broker: Redis
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/1"

# 入库任务（耗时较长，放宽超时）
@app.task(bind=True, max_retries=3, soft_time_limit=600)
def ingest_document(self, doc_id, kb_id, file_path):
    ...
```

---

## 4. 数据库设计（MySQL）

### 4.1 ER 图概要

```
users (用户表)
  │
  ├── knowledge_bases (知识库表)
  │     └── documents (文档表)
  │           └── chunks (分块表)
  │
  └── conversations (会话表)
        └── messages (消息表)
```

### 4.2 表结构

```sql
-- 用户表
CREATE TABLE users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    role ENUM('user', 'admin') DEFAULT 'user',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 知识库表
CREATE TABLE knowledge_bases (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(128) NOT NULL,
    description TEXT,
    user_id BIGINT NOT NULL,
    chunk_count INT DEFAULT 0,
    doc_count INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 文档表
CREATE TABLE documents (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    kb_id BIGINT NOT NULL,
    filename VARCHAR(256) NOT NULL,
    file_type VARCHAR(32) NOT NULL COMMENT 'pdf/docx/md/txt',
    file_size BIGINT COMMENT 'bytes',
    status ENUM('uploading','parsing','chunking','embedding','indexing','completed','failed') DEFAULT 'uploading',
    chunk_count INT DEFAULT 0,
    error_msg TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_kb_id (kb_id)
);

-- 分块表（存储分块文本和 ChromaDB 中的引用）
CREATE TABLE chunks (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    doc_id BIGINT NOT NULL,
    kb_id BIGINT NOT NULL,
    chroma_id VARCHAR(256) NOT NULL COMMENT 'ChromaDB中的chunk id',
    content TEXT NOT NULL,
    chunk_index INT NOT NULL COMMENT '在原文档中的顺序',
    token_count INT DEFAULT 0,
    metadata JSON COMMENT '页码、段落标题等',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_doc_id (doc_id),
    INDEX idx_kb_id (kb_id)
);

-- 会话表
CREATE TABLE conversations (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    kb_id BIGINT COMMENT '关联的知识库',
    title VARCHAR(256) DEFAULT '新对话',
    message_count INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id)
);

-- 消息表
CREATE TABLE messages (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    conversation_id BIGINT NOT NULL,
    role ENUM('user', 'assistant', 'system') NOT NULL,
    content TEXT NOT NULL,
    thinking_content TEXT COMMENT '深度思考内容',
    token_count INT DEFAULT 0,
    feedback ENUM('like', 'dislike') NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_conversation_id (conversation_id)
);
```

---

## 5. API 设计

### 5.1 认证相关

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/login` | 登录，返回 JWT Token |

### 5.2 知识库

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| POST | `/api/knowledge-bases` | 创建知识库 |
| GET | `/api/knowledge-bases` | 知识库列表 |
| GET | `/api/knowledge-bases/{id}` | 知识库详情 |
| PUT | `/api/knowledge-bases/{id}` | 更新知识库 |
| DELETE | `/api/knowledge-bases/{id}` | 删除知识库（含向量数据） |

### 5.3 文档管理

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| POST | `/api/knowledge-bases/{kb_id}/documents` | 上传文档（multipart） |
| GET | `/api/knowledge-bases/{kb_id}/documents` | 文档列表 |
| GET | `/api/knowledge-bases/{kb_id}/documents/{id}` | 文档详情 |
| DELETE | `/api/knowledge-bases/{kb_id}/documents/{id}` | 删除文档 |
| GET | `/api/knowledge-bases/{kb_id}/documents/{id}/chunks` | 查看文档分块 |

### 5.4 对话

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| POST | `/api/conversations` | 创建新对话 |
| GET | `/api/conversations` | 对话列表 |
| GET | `/api/conversations/{id}` | 对话详情（含消息） |
| PUT | `/api/conversations/{id}` | 重命名 |
| DELETE | `/api/conversations/{id}` | 删除对话 |

### 5.5 问答（核心）

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| POST | `/api/chat` | 发送消息（SSE 流式返回） |

**请求参数**：
```json
{
  "conversation_id": "可选，新对话不传",
  "kb_id": 1,
  "question": "报销流程是怎样的？",
  "deep_thinking": false
}
```

**SSE 事件类型**：
```
event: meta           → {"conversation_id": 1, "task_id": "uuid"}
event: thinking       → {"delta": "思考内容片段..."}
event: message        → {"delta": "回答内容片段..."}
event: sources        → {"chunks": [{"content": "...", "doc": "xxx.pdf", "score": 0.92}]}
event: finish         → {"message_id": 1, "title": "关于报销流程"}
event: error          → {"message": "错误信息"}
```

### 5.6 管理后台

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| GET | `/api/admin/stats` | 概览统计数据 |
| GET | `/api/admin/documents` | 全部文档列表 |

---

## 6. 后端项目结构

```
docmind/
├── .env                              # 环境变量配置（不上传 Git）
├── .gitignore
├── DESIGN.md                         # 本文件
│
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI 入口
│   │   ├── config.py                  # 配置管理（读取 .env）
│   │   ├── dependencies.py            # 依赖注入（DB session, current_user）
│   │   │
│   │   ├── api/                       # API 路由层
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                # 认证接口
│   │   │   ├── knowledge_base.py      # 知识库 CRUD
│   │   │   ├── document.py            # 文档上传 & 管理
│   │   │   ├── conversation.py        # 会话管理
│   │   │   ├── chat.py                # 问答接口（SSE）
│   │   │   └── admin.py               # 管理后台
│   │   │
│   │   ├── models/                    # SQLAlchemy 模型
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── knowledge_base.py
│   │   │   ├── document.py
│   │   │   ├── chunk.py
│   │   │   ├── conversation.py
│   │   │   └── message.py
│   │   │
│   │   ├── schemas/                   # Pydantic 请求/响应模型
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── knowledge_base.py
│   │   │   ├── document.py
│   │   │   ├── conversation.py
│   │   │   └── chat.py
│   │   │
│   │   ├── services/                  # 业务逻辑层
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py
│   │   │   ├── knowledge_base_service.py
│   │   │   ├── document_service.py
│   │   │   ├── conversation_service.py
│   │   │   └── chat_service.py        # 核心问答编排
│   │   │
│   │   ├── rag/                       # RAG 核心模块
│   │   │   ├── __init__.py
│   │   │   ├── parser.py              # 文档解析器
│   │   │   ├── chunker.py             # 文本分块策略
│   │   │   ├── embedder.py            # Embedding 封装
│   │   │   ├── retriever.py           # 检索器（向量 + BM25）
│   │   │   ├── reranker.py            # 重排序（NoopReranker 占位，后续 DashScope）
│   │   │   ├── prompt_builder.py      # Prompt 模板
│   │   │   └── intent.py              # 意图识别 + 问题重写
│   │   │
│   │   ├── ingest/                     # 入库任务模块
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py          # Celery 配置
│   │   │   └── tasks.py               # 入库任务（ingest_document）
│   │   │
│   │   ├── core/                      # 基础设施
│   │   │   ├── __init__.py
│   │   │   ├── database.py            # 数据库连接 & session
│   │   │   ├── chroma_client.py       # ChromaDB 连接
│   │   │   ├── security.py            # JWT & 密码哈希
│   │   │   ├── sse.py                 # SSE 发送工具
│   │   │   ├── storage.py             # 文件存储抽象（当前本地，后续 OSS）
│   │   │   └── exceptions.py          # 自定义异常
│   │   │
│   │   └── middleware/
│   │       ├── __init__.py
│   │       └── auth_middleware.py      # JWT 验证中间件
│   │
│   ├── requirements.txt
│   ├── knowledge_samples/              # 示例知识库文档（Section 2.1）
│   ├── alembic/                       # 数据库迁移
│   └── alembic.ini
│
├── frontend/                          # Vue 3 + Element Plus
│   ├── src/
│   │   ├── views/                     # 页面
│   │   │   ├── ChatPage.vue           # 问答页（核心）
│   │   │   ├── LoginPage.vue          # 登录页
│   │   │   └── admin/                 # 管理后台
│   │   │       ├── KnowledgeList.vue  # 知识库列表
│   │   │       ├── DocumentList.vue   # 文档管理
│   │   │       └── ConversationList.vue # 对话记录
│   │   ├── components/                # 组件
│   │   │   ├── chat/
│   │   │   │   ├── ChatInput.vue      # 输入框
│   │   │   │   ├── MessageList.vue    # 消息列表
│   │   │   │   ├── MessageItem.vue    # 单条消息（Markdown 渲染）
│   │   │   │   └── WelcomeScreen.vue  # 欢迎页（示例问题）
│   │   │   └── layout/
│   │   │       ├── Sidebar.vue        # 侧边栏（会话列表）
│   │   │       └── AppLayout.vue      # 整体布局
│   │   ├── stores/                    # Pinia 状态管理
│   │   │   ├── auth.js
│   │   │   ├── chat.js
│   │   │   └── knowledge.js
│   │   ├── api/                       # HTTP 请求封装
│   │   │   ├── index.js
│   │   │   ├── auth.js
│   │   │   ├── knowledge.js
│   │   │   ├── chat.js
│   │   │   └── conversation.js
│   │   ├── router/
│   │   │   └── index.js
│   │   └── utils/
│   │       ├── sse.js                 # SSE 事件解析
│   │       └── markdown.js            # Markdown 渲染配置
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
```

---

## 7. 核心接口设计细节

### 7.1 文档上传处理流程

```
POST /api/knowledge-bases/{kb_id}/documents
Content-Type: multipart/form-data

1. 接收文件 → 保存到本地 uploads/{kb_id}/{doc_id}_{filename}
2. 创建 document 记录，status = 'uploading'
3. dispatch Celery Task: ingest_document(doc_id, kb_id, file_path)
4. 立即返回 {"doc_id": 123, "status": "uploading"} 给前端
5. Celery Worker 异步执行入库流水线：
   a. Parser: 解析文档 → 纯文本
   b. Chunker: 分块 → List[chunk_text]
   c. Embedder: 向量化 → List[vector]
   d. Indexer: 写入 ChromaDB（共用 collection，带 kb_id metadata）+ MySQL chunks 表
6. 更新 document.status = 'completed'
7. 前端轮询或 WebSocket 通知状态变更
```

### 7.2 问答接口核心逻辑

```python
# chat_service.py 核心伪代码
async def chat(question, conversation_id, kb_id, deep_thinking):
    # 1. 意图识别
    intent = await intent_classifier.classify(question)

    # 2. 问题重写（多轮对话上下文补全）
    if conversation_id:
        history = await get_conversation_history(conversation_id)
        question = await question_rewriter.rewrite(question, history)

    # 3. 多路检索
    vector_results = await vector_retriever.search(question, kb_id, top_k=10)
    bm25_results = await bm25_retriever.search(question, kb_id, top_k=10)
    merged = rrf_fusion(vector_results, bm25_results)

    # 4. 重排序
    reranked = await reranker.rerank(question, merged, top_k=5)

    # 5. 拼 Prompt
    prompt = prompt_builder.build(question, reranked, history)

    # 6. 调用 LLM，SSE 流式输出
    async for chunk in llm.stream(prompt):
        yield sse_event("message", chunk)

    yield sse_event("finish", {...})
```

---

## 8. 开发阶段划分

### Phase 1：骨架搭建（3-4 天）
- [x] 项目初始化（FastAPI + Vue3 脚手架）
- [x] 前端环境搭建（npm 依赖与配置）
- [x] Git 初始化与 .gitignore 配置
- [x] MySQL 表建好（SQLAlchemy models）
- [ ] ChromaDB 连接 & collection 管理
- [ ] JWT 认证（注册/登录）
- [ ] 前端登录页 + 路由骨架

### Phase 2：文档入库（3-4 天）
- [ ] 文档上传 API + 本地文件存储（`uploads/{kb_id}/`）
- [ ] 文档解析（PDF/Word/MD/TXT → 纯文本）
- [ ] 智能分块（固定大小 + 结构感知）
- [ ] Embedding + ChromaDB 写入（共用 collection，metadata 隔离 kb_id）
- [ ] Redis + Celery 异步入库任务
- [ ] 前端知识库管理页（上传 + 列表 + 状态轮询）

### Phase 3：核心问答（3-4 天）
- [ ] 单路向量检索 → LLM 生成
- [ ] SSE 流式输出
- [ ] BM25 关键词检索
- [ ] RRF 多路融合（跳过 Rerank，用 NoopReranker 占位）
- [ ] 前端问答界面 + SSE 解析

### Phase 4：会话 & 记忆（2-3 天）
- [ ] 会话 CRUD
- [ ] 多轮对话上下文传递
- [ ] 滑动窗口记忆
- [ ] 问题重写（上下文补全）
- [ ] 前端会话列表 & 切换

### Phase 5：打磨（2-3 天）
- [ ] 意图识别
- [ ] 管理后台统计页面
- [ ] 错误处理 & 日志
- [ ] 简单限流
- [ ] README + 部署文档
- [ ] 准备简历描述文案

**预计总工期**：3-4 周（80-120 小时）

---

## 9. 环境变量配置模板

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

# LLM (OpenAI 兼容)
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-xxx
LLM_MODEL=gpt-4o-mini

# Embedding
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_API_KEY=sk-xxx
EMBEDDING_MODEL=text-embedding-3-small

# Rerank (可选，DashScope)
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

---

## 10. 关键依赖

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
rank-bm25==0.2.*
unstructured==0.16.*
PyPDF2==3.0.*
python-docx==1.1.*
markdown-it-py==3.0.*
redis==5.2.*
celery==5.4.*
httpx==0.28.*
sse-starlette==2.1.*
alembic==1.14.*
```

### 10.1 前端依赖

```
# frontend/package.json dependencies
vue==3.5.*
vue-router==4.*
pinia==2.*
element-plus==2.*
axios==1.*
markdown-it==14.*
@vitejs/plugin-vue==5.*
vite==6.*
```
