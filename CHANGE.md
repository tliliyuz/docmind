# DocMind 变更日志

## 2026-05-12 — Phase 1: JWT 认证（注册/登录 + 中间件 + 异常类）

### 新增

- **`core/exceptions.py`** — 统一异常类体系，覆盖 API.md §1.3 全部 20 个错误码
  - E1xxx 知识库（3）、E2xxx 文档（5）、E3xxx 会话（2）、E4xxx 问答（5）、E5xxx 认证（5）、E9xxx 系统（4）
  - 基类 `AppException(HTTPException)` 携带统一响应格式 `{code, error: {code, message, detail}}`
- **`core/security.py`** — JWT + 密码哈希（bcrypt 直调，未使用 passlib 以避免兼容性问题）
  - `hash_password` / `verify_password` / `create_access_token` / `decode_access_token`
- **`schemas/auth.py`** — RegisterRequest / LoginRequest / UserResponse / TokenResponse
- **`services/auth_service.py`** — register（查重+创建） / login（验证+签发 token）
- **`api/auth.py`** — POST /api/auth/register + POST /api/auth/login
- **`middleware/auth_middleware.py`** — 纯 ASGI 中间件，从 Authorization Bearer 提取 JWT，验证后写入 request.state；OPTIONS 放行；公开路由白名单
- **`dependencies.py`** — 新增 `get_current_user(request)` 从 request.state 读取已认证用户
- **`main.py`** — 注册 AuthMiddleware + auth_router

### 修改

- **`requirements.txt`** — 新增 `bcrypt==4.0.*`（pin 版本兼容 passlib 替代方案）

### 验证

| 场景 | 结果 |
|:---|:---|
| 注册 | 201 Created，返回用户信息 |
| 登录 | 200 OK，返回 access_token（HS256，24h）+ expires_in |
| 重复注册 | 409 Conflict，E5001「用户名已存在」 |
| 密码错误 | 401 Unauthorized，E5002「用户名或密码错误」 |
| 无 Token | 401 Unauthorized，E5004「Token 无效或格式错误」 |
| 有效 Token | 中间件放行，进入路由（返回 404 因路由未实现） |

### 修复

- **错误响应格式** — 外层 `"code": 0` 改为实际错误码（如 `"code": "E5001"`），去掉嵌套的 `error` 包裹层
  - `API.md` §1.2 — 错误响应示例从 `{code: 0, error: {code: "E1001", ...}}` 改为 `{code: "E1001", message: "...", detail: "..."}`
  - `core/exceptions.py` — `AppException` 响应体同步改为扁平结构
  - `middleware/auth_middleware.py` — 两处 `JSONResponse` 同步修正

---

## 2026-05-12 — Phase 1: ChromaDB 连接 & collection 创建

### 新增

- **`core/chroma_client.py`** — ChromaDB PersistentClient 连接管理
  - `init_chroma()` — 初始化 PersistentClient，获取或创建 `docmind` collection
  - `get_collection()` / `get_client()` — 获取全局单例
  - Collection 使用 `hnsw:space=cosine` 余弦相似度
  - 持久化目录：`CHROMA_PERSIST_DIR`（.env 配置，默认 `./chroma_data`）
- **`main.py`** — lifespan 启动时调用 `init_chroma()` 初始化 ChromaDB

### 验证

- Collection `docmind` 创建成功，count = 0
- `chroma.sqlite3` 持久化文件生成在 `backend/chroma_data/`
- FastAPI 启动正常，`/api/health` 返回 200

---

## 2026-05-11 — 设计文档更新: Embedding 方案切换为 DashScope

### 修改

- **CLAUDE.md** — 技术栈行: `text-embedding-3-small` → `DashScope text-embedding-v3`，LLM 标注为 DeepSeek
- **DESIGN.md §2** — 技术选型表 Embedding 行: `OpenAI text-embedding-3-small / 1536维` → `DashScope text-embedding-v3 / 1024维，中文优化`
- **DESIGN.md §9** — .env 模板 Embedding 段: URL 改为 `dashscope.aliyuncs.com/api/v1`，MODEL 改为 `text-embedding-v3`

---

## 2026-05-11 — Phase 1: 数据库连接 & ORM 模型 & Alembic 迁移

### 操作概述

按照 `DESIGN.md` §4 表结构和 §6 项目结构，完成 MySQL 数据库连接配置、全部 6 张表的 SQLAlchemy 模型、Alembic 异步迁移环境和首次迁移脚本。

### 环境变量配置

- **`.env`** — 从项目根目录移至 `backend/.env`，pydantic-settings 自动从 CWD 读取
- **`config.py`** — `Settings(BaseSettings)` 声明全部字段，`.env` 变量自动映射覆盖默认值，提供 `mysql_url` 计算属性拼接异步连接串

### 数据库连接 (`core/database.py`)

- `engine` — `create_async_engine(settings.mysql_url, pool_size=10, max_overflow=20)`
- `async_session` — `async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)`
- `Base` — `DeclarativeBase` 所有 ORM 模型基类

### SQLAlchemy 模型（6 张表，对齐 DESIGN.md §4.2）

| 模型 | 表名 | 关键字段 |
|---|---|---|
| `User` | `users` | id, username(unique), password_hash, role(Enum: user/admin), created_at, updated_at |
| `KnowledgeBase` | `knowledge_bases` | id, name, description, user_id, chunk_count, doc_count, created_at, updated_at |
| `Document` | `documents` | id, kb_id(索引), filename, file_type, file_size, status(Enum: uploading→failed), chunk_count, error_msg, created_at, updated_at |
| `Chunk` | `chunks` | id, doc_id(索引), kb_id(索引), chroma_id, content, chunk_index, token_count, metadata(JSON), created_at |
| `Conversation` | `conversations` | id, user_id(索引), kb_id, title, message_count, created_at, updated_at |
| `Message` | `messages` | id, conversation_id(索引), role(Enum: user/assistant/system), content, thinking_content, token_count, feedback(Enum: like/dislike), created_at |

- 全部使用 SQLAlchemy 2.0 Mapped 类型注解写法
- Enum 使用 SQL 原生 ENUM 类型
- `created_at` 使用 `server_default=func.current_timestamp()`
- `updated_at` 额外设置 `onupdate=func.current_timestamp()`
- `models/__init__.py` 导入全部模型供 Alembic 发现

### 依赖注入 (`dependencies.py`)

- `get_db()` — `AsyncGenerator[AsyncSession]`，每次请求获取独立 session，成功自动 commit，异常自动 rollback

### Alembic 异步迁移环境

- **`alembic.ini`** — 基本配置（URL 由 env.py 运行时从 config.py 读取，避免硬编码）
- **`alembic/env.py`** — 异步引擎 + 自动发现模型，支持 offline（生成 SQL）和 online（直连 DB）两种模式
- **首次迁移** — `alembic/versions/7588fa83e017_初始化建表.py`，包含全部 6 张表的 DDL（用户手动执行 `alembic upgrade head` 成功）
- 注意：`alembic revision --autogenerate` 因 aiomysql 连接在事件循环关闭后清理报错（`RuntimeError: Event loop is closed`），迁移脚本已生成但需手动执行 upgrade

### FastAPI 入口 (`main.py`)

- `lifespan` 上下文管理器（当前为空，后续注册资源初始化）
- CORS 中间件（开发阶段允许 localhost:5173）
- `/api/health` 健康检查路由

### 版本修正

- **`requirements.txt`** — 版本号对齐 DESIGN.md §10（fastapi 0.115, uvicorn 0.32, aiomysql 0.2, python-jose 3.3, celery 5.4, alembic 1.14 等）

### 修复

- **`dependencies.py`** — 导入路径 `from core.database` → `from app.core.database`（绝对导入）
- **`main.py`** — 导入路径 `from config` → `from app.config`（绝对导入）

### 验证

- `.env` 配置正确加载（DeepSeek + DashScope 凭证）
- 6 个模型全部导入成功，表结构打印验证通过
- Alembic `--autogenerate` 检测到 6 张表 + 4 个索引，生成迁移脚本后由用户手动 `alembic upgrade head` 完成建表

### 统计

| 操作 | 数量 |
|:---|:---|
| 新增/重写文件 | 13 |
| 模型 | 6 张表 |
| 迁移脚本 | 1 |

### 后续步骤（按 DESIGN.md Phase 1）

- [x] MySQL 表建好（SQLAlchemy models） ✅
- [ ] ChromaDB 连接 & collection 管理
- [ ] JWT 认证（注册/登录）
- [ ] 前端登录页 + 路由骨架

---

## 2026-05-10 — Phase 1: 项目初始化（目录脚手架）

### 操作概述

严格按照 `DESIGN.md` §6 项目结构定义，创建完整的目录脚手架和空占位文件。**所有文件均为空占位文件，未写入任何实现代码。**

### 后端目录 (`backend/`)

**目录创建：**
- `backend/app/` — FastAPI 应用根目录
- `backend/app/api/` — API 路由层（7 个占位文件）
- `backend/app/models/` — SQLAlchemy 数据模型（7 个占位文件）
- `backend/app/schemas/` — Pydantic 请求/响应模型（6 个占位文件）
- `backend/app/services/` — 业务逻辑层（6 个占位文件）
- `backend/app/rag/` — RAG 核心模块（8 个占位文件）
- `backend/app/ingest/` — 文档入库任务模块（3 个占位文件）
- `backend/app/core/` — 基础设施层（7 个占位文件）
- `backend/app/middleware/` — 中间件（2 个占位文件）
- `backend/knowledge_samples/` — 示例知识库文档目录（空）
- `backend/alembic/` — 数据库迁移目录（空）

**根级文件：**
- `backend/requirements.txt` — 依赖清单（空）
- `backend/alembic.ini` — Alembic 配置（空）

### 前端目录 (`frontend/`)

**目录创建：**
- `frontend/src/views/` — 页面组件（3 个占位文件）
- `frontend/src/views/admin/` — 管理后台页面（3 个占位文件）
- `frontend/src/components/chat/` — 聊天相关组件（4 个占位文件）
- `frontend/src/components/layout/` — 布局组件（2 个占位文件）
- `frontend/src/stores/` — Pinia 状态管理（3 个占位文件）
- `frontend/src/api/` — HTTP 请求封装（5 个占位文件）
- `frontend/src/router/` — 路由配置（1 个占位文件）
- `frontend/src/utils/` — 工具函数（2 个占位文件）

**根级文件：**
- `frontend/index.html` — 入口 HTML（空）
- `frontend/package.json` — 依赖清单（空）
- `frontend/vite.config.ts` — Vite 配置（空）

### 项目根目录

- `.gitignore` — Git 忽略规则（已配置 Python / Node / IDE / 环境变量等规则）

### 统计

| 类别 | 数量 |
|:---|:---|
| 后端目录 | 10 |
| 后端占位文件 | 50 |
| 前端目录 | 9 |
| 前端占位文件 | 26 |
| 根目录文件 | 1 (.gitignore) |
| **总计新增** | **96 项** |

### 后续步骤（按 DESIGN.md Phase 1）

- [ ] MySQL 表建好（SQLAlchemy models）
- [ ] ChromaDB 连接 & collection 管理
- [ ] JWT 认证（注册/登录）
- [ ] 前端登录页 + 路由骨架

---

## 2026-05-10 — Phase 1: 前端环境搭建

### 操作概述

根据用户确认的技术选型补充 DESIGN.md 前端章节，随后搭建前端运行环境并验证。

### DESIGN.md 更新

**§2 技术选型** — 前端行拆分为明细条目：
- 前端框架 → Vue 3 + Vite
- UI 组件库 → Element Plus
- 状态管理 → Pinia
- 路由 → Vue Router 4
- HTTP 客户端 → Axios
- Markdown 渲染 → markdown-it
- 包管理器 → npm
- 前端语言 → JavaScript（非 TypeScript）

**§6 项目结构** — 所有 `.ts` 扩展名改为 `.js`

**§10.1** — 新增前端 npm 依赖清单

### 文件变更

**重命名（12 个）：**
- `src/api/*.ts` → `src/api/*.js`（5 个文件）
- `src/stores/*.ts` → `src/stores/*.js`（3 个文件）
- `src/router/index.ts` → `src/router/index.js`
- `src/utils/*.ts` → `src/utils/*.js`（2 个文件）
- `vite.config.ts` → `vite.config.js`

**新创建（3 个）：**
- `package.json` — npm 依赖声明（vue 3.5, element-plus 2.9, pinia 2.3, vue-router 4.5, axios 1.7, markdown-it 14.1, vite 6, @vitejs/plugin-vue 5.2）
- `vite.config.js` — Vite 配置（Vue 插件 + `/api` 代理到 localhost:8000）
- `index.html` — 入口 HTML（zh-CN, 挂载 #app）

**新增 bootstrap 文件（2 个，环境必需）：**
- `src/main.js` — Vue 应用入口（createApp + Pinia + Router + ElementPlus）
- `src/App.vue` — 根组件（仅 `<router-view />`）

### npm 依赖安装

```
npm install → 89 packages added
```

已安装核心包：vue, vue-router, pinia, element-plus, axios, markdown-it, @vitejs/plugin-vue, vite

### 验证

- Vite 开发服务器正常启动（端口 5173）
- HTTP 200 响应正常

### 统计

| 操作 | 数量 |
|:---|:---|
| DESIGN.md 更新 | 3 处（§2, §6, §10.1） |
| 文件重命名 | 12 |
| 新创建文件 | 5 |
| npm 包安装 | 89 |

### 后续步骤（按 DESIGN.md Phase 1）

- [ ] MySQL 表建好（SQLAlchemy models）
- [ ] ChromaDB 连接 & collection 管理
- [ ] JWT 认证（注册/登录）
- [ ] 前端登录页 + 路由骨架

---

## 2026-05-10 — Phase 1: Git 版本控制初始化

### 操作概述

建立 Git 仓库并推送至 GitHub 远程仓库。

### 操作记录

```
echo "# docmind" > README.md        # 创建项目 README
git init                            # 初始化 Git 仓库
git add README.md                   # 暂存 README
git commit -m "first commit"        # 首次提交（仅 README.md）
git branch -M main                  # 默认分支 master → main
git remote add origin \
  https://github.com/zhenyu-39/docmind.git
git push -u origin main             # 推送至远程
```

### .gitignore 补充

在 Git 初始化前，根据前端环境（Vite + Vue）补充了 `.gitignore` 规则：
- `*.local` — Vite 本地环境变量文件
- `.vite/` — Vite 开发服务器缓存
- `frontend/dist/` — 生产构建产物

### 当前状态

- 远程仓库: `https://github.com/zhenyu-39/docmind.git`
- 默认分支: `main`
- 首次提交: `568de74` (仅 README.md)
- 待提交: `.gitignore`, `DESIGN.md`, `CHANGE.md`, `backend/`, `frontend/`（脚手架文件）

---

## 2026-05-10 — Phase 1: 脚手架提交 & 分支拆分

### 操作概述

提交全部脚手架文件到 main，并创建前后端独立开发分支。

### 操作记录

```
git add .gitignore CHANGE.md DESIGN.md backend/ frontend/
git commit -m "feat: project scaffold — FastAPI backend + Vue3 frontend"
git push origin main

git branch dev-backend
git branch dev-frontend
git push origin dev-backend dev-frontend
```

### 提交详情

- Commit: `90993f7`
- 文件数: 83 files changed
- 内容: 后端 50 + 前端 26 + 根目录 7 个文件

### 分支策略

```
main          ← 稳定主分支（受保护）
├── dev-backend   ← 后端开发分支
└── dev-frontend  ← 前端开发分支
```

### 后续步骤（按 DESIGN.md Phase 1）

- [ ] MySQL 表建好（SQLAlchemy models）
- [ ] ChromaDB 连接 & collection 管理
- [ ] JWT 认证（注册/登录）
- [ ] 前端登录页 + 路由骨架
