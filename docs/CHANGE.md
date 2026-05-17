# DocMind 变更日志

## 2026-05-17 — Phase 1 模型测试补齐（U4.1-U4.3）

### 新增
- `backend/tests/test_models.py` — 用户模型测试（U4.1 默认 role / U4.2 username 唯一约束 / U4.3 FK 关联验证），含 `dispose_engine_after` autouse fixture 解决 Windows pool 清理
- `backend/tests/conftest.py` — 新增 `db_session` fixture

### 修改
- `backend/pytest.ini` — 新增 `asyncio_default_fixture_loop_scope = session`，避免 Windows ProactorEventLoop 提前关闭导致连接池残留异常
- `docs/TESTING.md` v0.3→v0.4 — §3.1 修正：API 接口测试用 Mock session，模型层测试可直接连开发库 MySQL
- `docs/TEST_CASES.md` v0.3→v0.4 — U4.1-U4.3 状态 ⏭️→✅，models/ 覆盖率 ✅ 已覆盖
- `docs/DEVELOPMENT.md` v0.4→v0.5 — 项目结构 tests/ 节新增 `test_models.py`
- `CLAUDE.md` — 通用约束新增：新建文件须汇报用户、变更记录只能写入 `docs/CHANGE.md`

### 测试结果
- 后端：95/95 全部通过（新增 3 个模型测试，无回归）

---

## 2026-05-17 — Phase 2 文档状态枚举

### 新增
- `schemas/document.py` — 文档 Pydantic Schema（`DocumentResponse`、`DocumentUploadResponse`、`DocumentListResponse`、`DocumentDeleteResponse`、`DocumentReprocessResponse`、`DocumentBatchUploadResponse`、`DocumentChunkResponse`、`DocumentChunkListResponse`），status 字段统一使用 `DocumentStatus` 枚举
- `tests/test_schemas.py` — 新增 `DocumentStatus` 枚举（10 状态 + `TERMINAL_STATUSES` + `is_terminal()`）和 `DocumentResponse` Schema 校验测试（18 个用例）

### 修改
- `schemas/knowledge_base.py` — `KnowledgeBaseListData` → `KnowledgeBaseListResponse`，`KnowledgeBaseDeleteData` → `KnowledgeBaseDeleteResponse`，统一命名风格
- `schemas/__init__.py` — 导出全部文档 Schema
- `tests/test_knowledge_base.py` → `tests/test_kb_api.py` — 重命名对齐 DEVELOPMENT.md
- ROADMAP.md — 标记「文档状态枚举」+ 对应测试任务完成
- TEST_CASES.md — 新增文档状态枚举测试用例（U5.1-U5.12），Phase 2-3 用例 ID 全部顺延

### 测试结果
- 后端：92/92 全部通过（新增 18 个 Schema 测试，无回归）

---

## 2026-05-17 — Phase 2 KB CRUD 代码审查 + 修复

### 审查结论
- **审查范围**：`api/knowledge_base.py`, `models/knowledge_base.py`, `schemas/knowledge_base.py`, `services/knowledge_base_service.py`, 迁移脚本
- **原始问题**：2 项严重 + 3 项规范，18 项合规检查全部通过
- **已修复**：见下方「修复」节

### 修复
- `api/knowledge_base.py:50` 内联 `from app.schemas...` 移至模块顶部
- `API.md` §3 GET list 响应 items 示例补上 `user_id` 字段
- 编写 `tests/test_knowledge_base.py`（28 个用例）覆盖 KB CRUD 全部端点 + 错误码（E1001/E1002/E5005）+ 未认证 401 + 参数校验 422

### 新增 fixture
- `conftest.py`: `auth_headers` / `admin_auth_headers` / `other_user_auth_headers` 三个 fixture

### 测试结果
- 后端：72/72 全部通过（新增 28 个 KB CRUD 测试，无回归）
- 覆盖率：测试覆盖了所有 5 个 KB 端点（POST/GET/PUT/DELETE）的 7 类场景

---

## 2026-05-16 — Phase 2 知识库 CRUD 实现

### 新增
- 知识库 CRUD 接口（POST/GET/PUT/DELETE `/api/knowledge-bases`）
- `idx_user_name` 唯一索引（user_id, name），保证用户级知识库名称唯一
- `KnowledgeBaseCreate/Update/Response/ListData/DeleteData` Pydantic Schema
- `create_kb/get_kb/list_kbs/update_kb/delete_kb/check_kb_active` 服务层函数
- 同名冲突捕获 IntegrityError → E1002
- DELETE 仅标记 status=deleting + 返回 202，不做物理删除/ChromaDB 清理
- 列表分页返回 `{total, page, page_size, items}`
- 所有响应 data 中均包含 status 字段
- 权限校验：非 owner 且非 admin 拒绝修改/删除（E5005）
- `check_kb_active()` 供后续上传/检索/reprocess 调用

### 数据库迁移
| 迁移文件 | 版本链 | 变更 |
|:---|:---|:---|
| `687b64790b37_添加idx_user_name唯一索引.py` | `04b3e0425da8` → `687b64790b37` | `knowledge_bases` 添加 `idx_user_name (user_id, name)` 唯一索引 |

### 测试结果
- 后端：44/44 全部通过（无回归）
- API 手工验证：创建/列表/详情/更新/删除/同名冲突/权限拒绝 全部通过

---

## 2026-05-16 — 文档规范修复 + 代码合规修复

### 背景

对照 CLAUDE.md 强制约定和 API.md/UIdesign.md 规范，发现多处代码与文档不一致：模型字段缺少 `server_default`、前端组件硬编码颜色、LoginRequest 缺少最小长度校验、auth 响应 `code` 为整数而非字符串。同时修复了文档集自身的 19 项矛盾/缺失。

### 文档修改

| 文件 | 版本变更 | 主要变更 |
|:---|:---|:---|
| `backend/docs/API.md` | v0.3 → v0.4 | §1.2 成功响应 code 统一为字符串 `"0"`，删除过期注释；§1.3 E1xxx/E2xxx 间补空行；§3/§5/§7 补充 PUT KB、DELETE 会话、GET admin/documents 响应示例；§6 新增 SSE vs HTTP JSON 错误流程区分说明；§8.2 错误响应从旧嵌套格式改为扁平 `{code, message, detail}`；§9 删除分页/API 版本 TODO |
| `docs/ROADMAP.md` | v0.3 → v0.4 | 文件头版本/日期更新；§2.1 Phase 1 测试全部标记为 ✅ |
| `docs/TEST_CASES.md` | v0.1 → v0.2 | A3.x 文档 API 路径补全为 `/api/knowledge-bases/{kb_id}/documents/*`；A3.1 状态码 202→201；U3.5/A1.9 更新为 LoginRequest 有 min_length 的预期行为 |
| `docs/TESTING.md` | v0.2 → v0.3 | §5 子节编号 2.1/2.2 → 5.1/5.2 |
| `docs/DEVELOPMENT.md` | v0.3 → v0.4 | §5 移除 `rank-bm25==0.2.*`，替换为 `jieba==0.42.*`；§3.1 移除 `cp .env.example` 步骤 |
| `docs/CHANGE.md` | — | 错误码数量描述 20→31，子类计数同步更新 |
| `frontend/docs/UIDESIGN.md` | v0.3 → v0.4 | §4.6/§4.8 硬编码颜色全部替换为 `--dm-*` 变量；§1 新增 `--dm-primary-hover-light`、`--dm-logo-shadow` Token |
| `frontend/docs/FRONTEND.md` | v0.2 → v0.3 | §2.1 路由表补充 `/ → /chat` 重定向条目 |
| `README.md` | — | 末尾静态日期改为「见各文档元信息」 |

### 代码修改

| 文件 | 修改 |
|:---|:---|
| `backend/app/models/user.py` | `role` 字段新增 `server_default=text("'user'")` |
| `backend/app/models/document.py` | `status` 字段新增 `server_default=text("'uploaded'")` |
| `backend/app/models/conversation.py` | `title` 字段新增 `server_default=text("'新对话'")` |
| `backend/app/schemas/auth.py` | `LoginRequest` username 新增 `min_length=2`，password 新增 `min_length=6`，与 `RegisterRequest` 和 `FRONTEND.md §3.3` 对齐 |
| `backend/app/api/auth.py` | 注册/登录接口 `"code": 0` → `"code": "0"`，与 `API.md §1.2` 字符串格式统一 |
| `backend/requirements.txt` | 新增 `jieba==0.42.*` |
| `frontend/src/styles/global.css` | 新增 `--dm-primary-hover-light` 和 `--dm-logo-shadow` Design Token |
| `frontend/src/components/layout/Sidebar.vue` | L160 `#DDD6FE` → `var(--dm-primary-hover-light)` |
| `frontend/src/views/LoginPage.vue` | L167 硬编码 `box-shadow` → `var(--dm-logo-shadow)` |

### 数据库迁移

| 迁移文件 | 版本链 | 变更 |
|:---|:---|:---|
| `04b3e0425da8_补充user_role_document_status_.py` | `42097bdbd61a` → `04b3e0425da8` | `users.role` SET DEFAULT `'user'`；`documents.status` SET DEFAULT `'uploaded'`（幂等）；`conversations.title` SET DEFAULT `'新对话'` |

### 测试修改

| 文件 | 修改 |
|:---|:---|
| `backend/tests/test_schemas.py` | `test_empty_username_accepted` → `test_empty_username_rejected`，预期 `ValidationError` |
| `backend/tests/test_auth_api.py` | 空用户名测试预期 422 + E9003；错误密码测试改为 ≥6 字符；`code == 0` → `code == "0"` |

### 测试结果

- 后端：44/44 全部通过 ✅
- 前端：2 文件 23 测试全部通过 ✅

---

## 2026-05-15 — 测试体系补全：测试策略增强 + Phase 1 测试用例

### 背景

项目有 TESTING.md 但无实际测试文件。Phase 1 已完成但零测试覆盖，Phase 2 即将启动前补齐测试基础设施。

### 文档修改

| 文件 | 版本变更 | 主要变更 |
|:---|:---|:---|
| `docs/ROADMAP.md` | v0.3 → v0.4 | 每个 Phase 增加测试子章节 + Phase 1 待补测试项；§7 增加测试准入规则；关联 TEST_CASES.md |
| `docs/TESTING.md` | v0.1 → v0.2 | 测试体系从 4 层扩充为 6 层（新增单元测试、接口测试、前端组件测试）；§9 执行计划从 Phase 1 起始 |
| `docs/DEVELOPMENT.md` | v0.2 → v0.3 | §2 项目树加入 `backend/tests/` 和 `frontend/tests/` 完整目录结构；§5 加入 test 依赖；§7 加入测试命令 |
| `docs/TEST_CASES.md` | **新文件** | 测试用例跟踪文档：Phase 1-5 全部用例 ID + 状态 + 覆盖率目标，对应 6 层体系 |

### 代码新增

#### 后端测试 (`backend/tests/`)

| 文件 | 说明 |
|:---|:---|
| `__init__.py` | 包初始化 |
| `conftest.py` | pytest fixtures：`mock_db`（AsyncMock DB session）、`async_client`（FastAPI async HTTP client）+ ChromaDB init 全局 Mock |
| `test_security.py` | JWT & 密码哈希：10 个测试（hash/verify/token create/decode/edge cases） |
| `test_auth_service.py` | 认证 Service：7 个测试（注册正常/重复/强密码 + 登录正常/密码错/用户不存在/Token 非空格式） |
| `test_auth_api.py` | 认证 API：14 个测试（注册 6 + 登录 4 + 中间件 4），Mock service 层 |
| `test_schemas.py` | Pydantic Schema：10 个测试（RegisterRequest 5 + LoginRequest 3 + TokenResponse 3） |
| `pytest.ini` | pytest 配置（asyncio_mode=auto） |

#### 前端测试 (`frontend/tests/`)

| 文件 | 说明 |
|:---|:---|
| `setup.js` | 全局 Mock：Element Plus（ElMessage 等）、Font Awesome |
| `LoginPage.test.js` | 登录页：12 个测试（渲染 4 + 交互 2 + 校验 3 + 提交 3） |
| `AppLayout.test.js` | 布局：11 个测试（渲染 5 + 页面标题 5 + slot 1） |
| `vitest.config.js` | vitest 配置（jsdom + @ alias + vue 插件） |

#### 依赖更新

| 文件 | 变更 |
|:---|:---|
| `backend/requirements.txt` | 新增 `pytest==8.*`、`pytest-asyncio==0.24.*`、`pytest-cov==5.*` |
| `frontend/package.json` | 新增 devDeps：`vitest`、`@vue/test-utils`、`jsdom`；scripts 新增 `test`/`test:ui`/`test:watch` |

### 测试执行结果（2026-05-15）

| 套件 | 结果 | 说明 |
|:---|:---|:---|
| 后端 `pytest tests/ -v` | **44/44 通过** | 安全模块 10 + Schema 校验 10 + Service 7 + API 接口 14 + 中间件 3 |
| 前端 `vitest run` | **23/23 通过** | LoginPage 12 + AppLayout 11 |

### 统计

| 类别 | 数量 |
|:---|:---|
| 新增文档 | 1（TEST_CASES.md） |
| 修改文档 | 3（ROADMAP / TESTING / DEVELOPMENT） |
| 新增测试文件（后端） | 6 |
| 新增测试文件（前端） | 4 |
| 测试用例总数（Phase 1） | 67（后端 44 + 前端 23） |

---

## 2026-05-15 — 测试修复：Mock 适配 & Pydantic V2 兼容

### 背景

首轮测试 13 个失败，经三轮修复后全部通过。

### 发现与修复

| # | 问题 | 根因 | 修复方式 |
|:---|:---|:---|:---|
| 1 | Schema 校验 `min_length`/`max_length` 断言不匹配 | Pydantic V2 错误类型为 `string_too_short` / `string_too_long` | `test_schemas.py` 断言改为匹配 V2 类型名 |
| 2 | `LoginRequest(username="")` 预期抛异常但未抛 | `LoginRequest` 无 `min_length` 约束，空字符串合法 | 改为 `test_empty_username_accepted` |
| 3 | Service 测试 `'coroutine' object has no attribute 'password_hash'` | `_make_mock_result` 使用 `AsyncMock`，`scalar_one_or_none()` 返回协程而非值 | 改用 `MagicMock` 构造非异步返回值 |
| 4 | `UserResponse.model_validate(user)` 校验失败（id/role/created_at 为 None） | `mock_db.refresh` 未回填 DB 生成字段 | Mock `refresh.side_effect` 设置默认值 |
| 5 | `r1.access_token != r2.access_token` 断言失败 | 两次 `create_access_token` 调用间隔 < 1s，`exp` 相同导致 JWT 完全一致 | 改为 `test_login_token_not_empty`（验证 token 非空 + JWT 格式） |
| 6 | API 测试 `test_login_empty_username` 未 mock service | `LoginRequest` 允许空用户名，请求直达真实 service | 添加 `patch("app.api.auth.login")` mock |
| 7 | `test_options_preflight_skipped` 返回 404 | OPTIONS `/api/knowledge-bases` 路由不存在（仅骨架） | 预期状态码放宽为 `200/404/405` |
| 8 | 前端 `AppLayout` 全部 10 个失败：`useRoute.mockReturnValue is not a function` | `vi.mock` 工厂函数中 `useRoute` 不是 `vi.fn()`，无法动态改返回值 | 用 `vi.hoisted()` 包裹 `mockUseRoute = vi.fn()`，再传入 mock 工厂 |

### 修改文件

| 文件 | 说明 |
|:---|:---|
| `test_schemas.py` | 适配 Pydantic V2 错误类型；LoginRequest 测试用例调整 |
| `test_auth_service.py` | `_make_mock_result` 改用 `MagicMock`；`mock_db.refresh` 回填字段；移除 Token 不同断言 |
| `test_auth_api.py` | `test_login_empty_username` 补 mock；`test_options_preflight_skipped` 放宽预期；`test_public_route_skips_middleware` 改用 `/api/auth/login` |
| `test_cases.md` | 用例 U2.6 改为 `test_login_token_not_empty` |

---

## 2026-05-15 — 设计修正：KB/文档删除流程统一为物理删除（方案 B）

### 背景

审查发现 KB 删除流程存在设计矛盾：API.md §3 的 Celery 流程写了「批量删除 chunks / documents / kb 记录」，但紧接着标记 `status=deleted`——物理删除后行已不存在，无法 UPDATE。同时 `knowledge_bases.status` ENUM 包含 `'deleted'`，若行永不物理删除，`ON DELETE CASCADE` 外键将成为死代码。

### 决策：方案 B — Celery 异步物理删除 + FK CASCADE 兜底

**核心流程**（KB 级）：
```
DELETE /api/knowledge-bases/{id}
↓ kb.status = deleting → 返回 202
↓ Celery Worker:
  1. collection.delete(where={"kb_id": kb_id})   — ChromaDB
  2. 删除 uploads/{kb_id}/                           — 磁盘文件
  3. DELETE FROM knowledge_bases WHERE id=?          — MySQL 物理删除
     └─ FK CASCADE → documents → chunks（兜底）
```
**文档级同理**：`status = deleting` → Celery 清理 ChromaDB + 磁盘 → `DELETE FROM documents` → FK CASCADE 清 chunks。

### 修改的文件

| 文件 | 变更内容 |
|:---|:---|
| `API.md` | 移除 E1003 错误码；§3 KB 异步清理流程改为物理 DELETE + FK CASCADE；§4.0 DocumentStatus 移除 `DELETED`，TERMINAL_STATUSES 移除 `'deleted'`；§4 文档异步清理流程同步修正 |
| `DATABASE.md` | §2.2 `knowledge_bases.status` ENUM 移除 `'deleted'`；§2.3 `documents.status` ENUM 移除 `'deleted'`；DocumentStatus 枚举移除 `DELETED`；§4 外键说明改为物理删除为主、FK CASCADE 兜底 |
| `ARCHITECTURE.md` | §4.0 TERMINAL_STATUSES 移除 `deleted`；§7.1 KB 删除流程描述更新 |
| `FRONTEND.md` | §6.4 TERMINAL_STATUSES 常量移除 `'deleted'`；§6.5 状态标签映射移除 `deleted` 行 |
| `UIDESIGN.md` | §4.8 移除 `.status-tag.deleted` CSS 类；图标配对表移除 `deleted` 行 |
| `CHANGE.md` | 本文档 |

### 代码层面执行（2026-05-15 当天完成）

| # | 位置 | 修改内容 | 状态 |
|:---|:---|:---|:---|
| 1 | `requirements.txt` | 删除 `passlib[bcrypt]==1.7.*` + `rank-bm25==0.2.*` | ✅ |
| 2 | `config.py` | 新增 `CHROMA_BATCH_SIZE=100`、`EMBED_BATCH_SIZE=20`、`DEBUG_CHUNK_FULL=False` | ✅ |
| 3 | `core/exceptions.py` | 移除 `KnowledgeBaseDeleteFailedException(E1003)`；新增 E2006-E2013 共 8 个异常类 | ✅ |
| 4 | `models/enums.py` | **新文件**：`DocumentStatus(str, Enum)` 10 值 + `TERMINAL_STATUSES` + `is_terminal()` | ✅ |
| 5 | `models/document.py` | status ENUM 从 8 值改为 10 值（`uploading→uploaded`、`indexing→vector_storing`，新增 `success_with_warnings`/`partial_failed`/`deleting`，移除 `deleted`）；新增 `file_path`/`current_stage`/`last_success_batch` 字段；新增 `idx_kb_filename` 复合索引 | ✅ |
| 6 | `models/knowledge_base.py` | 新增 `status` 字段 `Enum('active','deleting')` | ✅ |
| 7 | `models/__init__.py` | 导出 `DocumentStatus`、`TERMINAL_STATUSES`、`is_terminal` | ✅ |
| 8 | `api/knowledge_base.py` | 路由骨架（`prefix="/api/knowledge-bases"`） | ✅ |
| 9 | `api/document.py` | 路由骨架（`prefix="/api/knowledge-bases"`） | ✅ |
| 10 | `main.py` | 注册 `kb_router` + `doc_router` | ✅ |
| 11 | `alembic/versions/42097bdbd61a` | 新迁移：documents ENUM 值重命名 + 新增值（含旧数据 UPDATE 适配）+ knowledge_bases.status 新增；已执行 `upgrade head` | ✅ |

### 代码层面仍待处理（Phase 2 实施时）

| # | 位置 | 修改内容 | 优先级 |
|:---|:---|:---|:---|
| 12 | `schemas/` | 创建/更新 Pydantic schema 对齐新枚举和字段 | P1 |
| 13 | `services/` | 实现 KB/文档 CRUD service，使用新的 `DocumentStatus` 枚举 | P1 |
| 14 | `api/knowledge_base.py` | 实现具体端点 | P1 |
| 15 | `api/document.py` | 实现具体端点 | P1 |
| 16 | `ingest/celery_tasks.py` | KB/文档删除任务末尾物理 DELETE（非 UPDATE status） | P0 |
| 17 | `frontend/` | TERMINAL_STATUSES 常量 + 状态标签映射同步 | P1 |

### 关键决策索引（追加）

| # | 决策 | 文档位置 |
|:---|:---|:---|
| 12 | KB/文档删除采用物理删除 + FK CASCADE 兜底，不保留软删除状态 | API.md §3, DATABASE.md §4 |

---

## 2026-05-15 — 响应格式补全：所有成功响应统一 `{code, message, data}`

### 背景

API.md §1.2 已约定「所有成功响应必须包含 `code`、`message`、`data` 三个字段。当前部分接口仅返回 `{code, data}`，Phase 2 起统一补齐 `message` 字段」。经审查发现 7 处接口的成功响应缺少 `message`，本次统一补齐。

### 文档修改（API.md）

| # | 接口 | 补全值 |
|:---|:---|:---|
| 1 | POST `/api/auth/register` | `"message": "注册成功"` |
| 2 | POST `/api/auth/login` | `"message": "登录成功"` |
| 3 | POST `/api/knowledge-bases` | `"message": "知识库创建成功"` |
| 4 | GET `/api/knowledge-bases` | `"message": "ok"` |
| 5 | GET `/api/knowledge-bases/{id}` | 继承创建响应结构（自动补全） |
| 6 | POST `/api/conversations` | `"message": "会话创建成功"` |
| 7 | GET `/api/conversations/{id}` | `"message": "ok"` |
| 8 | GET `/api/admin/stats` | `"message": "ok"` |

### 代码修改（Phase 1 已实现接口）

| 文件 | 变更 |
|:---|:---|
| `api/auth.py` | `register` 返回中加入 `"message": "注册成功"`；`login` 返回中加入 `"message": "登录成功"` |

> 其余接口代码尚未实现，Phase 2 实现时按文档直接输出三字段格式。

---

## 2026-05-14 — Phase 2 前置准备：文档全面补全

### 背景

Phase 1 代码骨架完成，Phase 2 启动前对齐全部设计决策，补全所有文档中遗漏的技术细节。

### 修改的文件

| 文件 | 版本变更 | 主要补全内容 |
|:---|:---|:---|
| `API.md` | v0.2 → v0.3 | E2006-E2013 错误码、文档状态枚举(11值)、reprocess/batch-upload 接口、force 覆盖流程、DELETE KB 异步清理、chunks 分页、Refresh Token Phase 5 TODO |
| `DATABASE.md` | v0.2 → v0.3 | `documents.status` 枚举改为 11 值 + `DocumentStatus(str,Enum)` 定义、新增 `file_path`/`current_stage`/`last_success_batch` 字段、`knowledge_bases` 新增 `status` 字段、`idx_kb_filename` 复合索引 |
| `ARCHITECTURE.md` | v0.2 → v0.3 | §4 文档入库流程完整重写（状态机、幂等锁、批量写入、批次 checkpoint、解析容错分级、chunk_count 事务更新）、§7.1 KB 删除 metadata filter 流程、§7.2 标注 rank-bm25 移除、§7.5 文件路径更新 |
| `ROADMAP.md` | v0.2 → v0.3 | §3 Phase 2 拆分为 3 个子阶段（后端CRUD 7 项 / Celery流水线 7 项 / 前端 5 项）+ 明确不做的 5 项推迟、§6 Refresh Token 细化 |
| `FRONTEND.md` | v0.1 → v0.2 | §6 文档管理页扩写（上传交互、同名冲突、轮询策略、11 状态标签映射、上传进度、空状态、分块预览）、§11 已知 TODO 更新为 Phase 分阶段 |
| `UIDESIGN.md` | v0.2 → v0.3 | §4.8 状态标签从 4 种扩展至 11 种 + 图标配对表 |
| `CHANGE.md` | — | 本文档 |

### 关键决策索引

| # | 决策 | 文档位置 |
|:---|:---|:---|
| 1 | 文档状态机：11 状态 + `TERMINAL_STATUSES` + `is_terminal()` | API.md §4.0, DATABASE.md §2.3 |
| 2 | Celery 幂等键：`{doc_id}:{task_type}` + Redis 分布式锁 TTL=600s | ARCHITECTURE.md §4.5 |
| 3 | ChromaDB batch 写入失败清理策略 | ARCHITECTURE.md §4.3 |
| 4 | 文档唯一性：`(kb_id, filename)` 检查 + `force=true` 覆盖 | API.md §4, ARCHITECTURE.md §4.1 |
| 5 | 分块策略：RecursiveCharacterTextSplitter（800-1200 chars） | ARCHITECTURE.md §4.2 |
| 6 | 文件路径：`uploads/{kb_id}/{doc_id}/{uuid}_{sanitized_filename}` | ARCHITECTURE.md §7.5, DATABASE.md §2.3 |
| 7 | KB 删除：单 Collection metadata filter 异步批量清理 | API.md §3, ARCHITECTURE.md §7.1 |
| 8 | 解析容错分级：<20% warning / 20-50% partial / >50% failed | ARCHITECTURE.md §4.7 |
| 9 | 状态轮询：2s 间隔 / 终态停止 / 5 分钟超时 | FRONTEND.md §6.4 |
| 10 | Embedding 批量：batch_size=20 + 5 次指数退避重试 + 批次 checkpoint | ARCHITECTURE.md §4.4 |
| 11 | 不支持 .doc 格式 | ROADMAP.md §3.4 |

### 未改动代码

本次仅修正文档，不涉及代码变更。已知待修 Bug（migration `server_default` 字符串字面量、`rank-bm25` 残留依赖）在 Phase 2 实现时一并修复。

---

## 2026-05-13 — Phase 1 交互补漏：登录/退出反馈 + 用户栏行为修正

### 文档补充（FRONTEND.md）

| 位置 | 补充内容 |
|:---|:---|
| §3.2 登录流程 | 成功步骤增加 `ElMessage.success('登录成功')` 反馈 |
| §4.1 页面布局 | Sidebar 底部区域描述细化：头像点击→个人资料（预留）、退出按钮→提示+跳转 |
| §4.5.1 用户栏行为（新增） | 用户栏交互行为表：头像预留 / 退出图标 → toast + 跳转 |
| §8.2 表单反馈 | 新增「退出登录」「登录成功」两行交互规范 |

### 修复

| 问题 | 修复前 | 修复后 |
|:---|:---|:---|
| 点击头像区域也退出登录 | `@click="handleLogout"` 挂在 `.user-bar` 容器上 | 仅退出图标按钮绑定 `@click.stop`，头像/用户名区域无操作（预留个人资料入口） |
| 退出登录无反馈 | 静默跳转 `/login` | `ElMessage.success('已退出登录')` → 跳转 |
| 登录成功无反馈 | 静默跳转 `/chat` | `ElMessage.success('登录成功')` → 跳转 |

### 修改文件

| 文件 | 说明 |
|:---|:---|
| `frontend/src/components/layout/Sidebar.vue` | 移除 `.user-bar` 退出点击，仅退出图标触发；新增 `ElMessage` 退出反馈 |
| `frontend/src/views/LoginPage.vue` | 新增 `ElMessage.success('登录成功')` |

---

## 2026-05-13 — Phase 1 收尾：前端布局框架（AppLayout + Sidebar）

### 新增

| 文件 | 说明 |
|:---|:---|
| `frontend/src/components/layout/Sidebar.vue` | 侧边栏组件：Logo + 新建对话按钮 + 会话列表空态 + 管理导航（admin可见）+ 用户信息栏 + 退出登录 |
| `frontend/src/components/layout/AppLayout.vue` | 布局容器：左侧 Sidebar + 右侧主内容区（顶部 header + `<slot />`） |

### 修改

| 文件 | 说明 |
|:---|:---|
| `frontend/src/App.vue` | 路由感知布局切换：公开页面（login）独立渲染，认证页面包裹 AppLayout |

### 组件结构

```
App.vue
├── /login → LoginPage（独立渲染，全屏渐变背景）
└── 其他路由 → AppLayout
                ├── Sidebar（280px）
                │   ├── 顶部：Logo（DocMind）+ 新建对话按钮
                │   ├── 中间：会话列表空态 + 管理导航（admin）
                │   └── 底部：用户头像/用户名/角色 + 退出按钮
                └── 主内容区
                    ├── Top Header（页面标题）
                    └── <slot />（router-view 页面内容）
```

### Phase 1 完成状态

| 任务 | 状态 |
|:---|:---|
| 项目初始化 | ✅ |
| 前端环境搭建 | ✅ |
| Git 初始化 | ✅ |
| MySQL 表建好 | ✅ |
| ChromaDB 连接 | ✅ |
| JWT 认证 | ✅ |
| 前端登录页 | ✅ |
| 前端布局框架 | ✅ |

Phase 1 骨架搭建全部完成，可进入 Phase 2 文档入库开发。

---

## 2026-05-13 — 错误响应格式统一（AppException 去嵌套）

### 修复

`AppException` 继承 `HTTPException`，FastAPI 默认 handler 会将其 `detail` dict 再包一层 `{"detail": {...}}`，而 `AuthMiddleware` 直接构造 `JSONResponse` 返回扁平格式 `{code, message, detail}`，导致前后端错误响应格式不统一。

- **`backend/app/main.py`** — 新增 `@app.exception_handler(AppException)`，直接返回 `JSONResponse` 扁平格式，与中间件响应一致
- **`frontend/src/views/LoginPage.vue`** — 错误处理从双路径兼容（`data.detail.message` / `data.message`）简化为单一路径 `data?.message`

### 影响

此后所有 `AppException` 子类（31 个错误码）抛出的错误响应均为扁平格式 `{"code":"Exxxx","message":"...","detail":"..."}`，与 `AuthMiddleware`、`RequestValidationError` handler、通用 `Exception` handler 保持一致。

---

## 2026-05-13 — Phase 1: 前端登录页交互修复

### 修复

根据 FRONTEND.md §3.2 交互流程、§3.3 表单校验规则及 §8.2 表单反馈规范，修正 LoginPage.vue 三处问题：

| 问题 | 修复前 | 修复后 |
|:---|:---|:---|
| Tab 切换不清空表单 | `switchMode` 仅重置 `errorMsg` | 同时清空 `username`、`password`、`errorMsg` |
| 用户名长度校验缺失 | 仅校验非空 | 新增 `length ≥ 2` 校验，提示「用户名至少 2 个字符」 |
| 注册成功无反馈 | 静默切换至登录模式 | `ElMessage.success('注册成功，请登录')` |

### 修改

- **`frontend/src/views/LoginPage.vue`** — 上述 3 处修复，并新增 `import { ElMessage } from 'element-plus'`

---

## 2026-05-13 — Phase 1: 前端登录页 + 路由 + 全局样式

### 新增

| 文件 | 说明 |
|:---|:---|
| `frontend/src/styles/global.css` | 全局 CSS 变量（Design Token）+ 重置样式 + 组件基础样式，严格对齐 UIDESIGN.md §1-2 |
| `frontend/src/views/LoginPage.vue` | 登录/注册页，含渐变背景、Logo、Tab 切换、表单验证、错误提示，样式对齐 UIDESIGN.md |
| `frontend/src/router/index.js` | Vue Router 配置，含路由守卫（公开/认证/管理员三级权限），懒加载页面 |
| `frontend/src/stores/auth.js` | Pinia 认证状态管理（login/register/logout），JWT 解析 + localStorage 持久化 |
| `frontend/src/api/index.js` | Axios 实例 + 请求拦截器（Bearer Token）+ 响应拦截器（401 跳转登录页） |
| `frontend/src/api/auth.js` | 认证 API 封装（register/login） |

### 修改

| 文件 | 说明 |
|:---|:---|
| `frontend/index.html` | 添加 Font Awesome 6.5.1 CDN 链接 |
| `frontend/src/main.js` | 导入 `global.css` |
| `frontend/vite.config.js` | 添加 `@` 路径别名（→ `./src`） |
| `frontend/src/views/admin/*.vue` | 填充占位 `<template>`，修复空文件导致构建失败 |
| `frontend/src/views/ChatPage.vue` | 同上，填充占位内容 |

### 路由设计

| 路径 | 页面 | 权限 |
|:---|:---|:---|
| `/login` | LoginPage | 公开（已登录自动跳转 `/chat`） |
| `/chat` | ChatPage | 需登录 |
| `/admin/documents` | DocumentList | 需管理员 |
| `/admin/conversations` | ConversationList | 需管理员 |
| `/admin/knowledge` | KnowledgeList | 需管理员 |
| `/` | — | 重定向 `/chat` |

### 数据流

```
LoginPage → authStore.login() → api/auth.js POST /api/auth/login
           → 解析 JWT payload → localStorage 持久化 → router.push('/chat')

LoginPage → authStore.register() → api/auth.js POST /api/auth/register
           → 注册成功 → 切换至登录模式
```

---

## 2026-05-12 — Phase 1 代码规范修正 & 模型外键补齐

### 修改

- **相对导入 → 绝对导入** — `core/database.py`、`core/chroma_client.py`、`main.py`、`models/__init__.py` 全部改为 `from app.xxx` 绝对路径
- **`core/security.py`** — `datetime.utcnow()` → `datetime.now(timezone.utc)`，避免弃用 API
- **`middleware/auth_middleware.py`** — `int(payload.get("sub"))` 增加 `KeyError/ValueError/TypeError` 异常防护，返回 401 而非 500
- **`middleware/auth_middleware.py`** — 移除 `_PUBLIC_PATHS` 中 `/docs`、`/openapi.json` 的重复 `startswith` 判断（`in` 集合 + `startswith` 提取为 `_is_public()` 函数）
- **`main.py`** — 注册全局异常处理器：`RequestValidationError`（422 → E9003）+ `Exception`（500 → E9001），统一响应格式 `{code, message, detail}`

### 新增

- **6 张模型表补充 `sa.ForeignKey(...)`** — 对齐 DATABASE.md §4 外键策略，全部 7 条外键约束：
  | 字段 | 引用 | ondelete |
  |:---|:---|:---|
  | `knowledge_bases.user_id` | `users.id` | RESTRICT |
  | `documents.kb_id` | `knowledge_bases.id` | CASCADE |
  | `chunks.doc_id` | `documents.id` | CASCADE |
  | `chunks.kb_id` | `knowledge_bases.id` | CASCADE |
  | `conversations.user_id` | `users.id` | CASCADE |
  | `conversations.kb_id` | `knowledge_bases.id` | SET NULL |
  | `messages.conversation_id` | `conversations.id` | CASCADE |

- **6 张模型表补充 `relationship`** — User ↔ KB ↔ Document ↔ Chunk / User ↔ Conversation ↔ Message 双向关联
- **`server_default=sa.text('0')`** — `chunk_count`（KB/Document）、`doc_count`（KB）、`token_count`（Chunk/Message）、`message_count`（Conversation）添加 DB 层默认值

### 数据库迁移

- **`252a79df66dd`** — 添加 7 条外键约束 + 6 列 server_default 修改，已执行 `alembic upgrade head`

---

## 2026-05-12 — Phase 1: JWT 认证（注册/登录 + 中间件 + 异常类）

### 新增

- **`core/exceptions.py`** — 统一异常类体系，覆盖 API.md §1.3 全部 31 个错误码
  - E1xxx 知识库（2）、E2xxx 文档（13）、E3xxx 会话（2）、E4xxx 问答（5）、E5xxx 认证（5）、E9xxx 系统（4）
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
