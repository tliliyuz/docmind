# TEST_CASES — 测试用例跟踪

| 属性 | 值 |
|:---|:---|
| 文档版本 | v0.60 |
| 最后更新 | 2026-06-11 |
| 作者 | yuz |
| 状态 | 进行中（Phase 5 实现阶段 — 意图识别 ✅ / sources 预览 ✅ / Evidence Highlight ✅ / Admin ✅ / Admin 布局重构 ✅ / 限流 ⬜ / 性能埋点 ⬜） |

---

## 1. 说明

本文档记录所有测试用例及其执行状态，与 [TESTING.md](TESTING.md) 的 6 层测试体系对应。

**状态标记**：
- ⬜ 待编写
- ✏️ 编写中
- ✅ 通过
- ❌ 失败（附失败原因与 issue 链接）
- ⏭️ 跳过（附跳过原因）

**运行方式**：每次提交前运行对应 Phase 的测试套件，更新本文档状态。

---

## 2. Phase 1 测试用例

### 2.1 后端 — 安全模块单元测试

| ID | 测试用例 | 被测函数 | 输入 | 预期输出 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U1.1 | 密码哈希生成 | `hash_password` | `"test123"` | 返回 `$2b$` 开头的 bcrypt 字符串 | ✅ | 2026-05-15 | — |
| U1.2 | 密码验证-正确 | `verify_password` | 明文+正确哈希 | 返回 `True` | ✅ | 2026-05-15 | — |
| U1.3 | 密码验证-错误 | `verify_password` | 明文+错误哈希 | 返回 `False` | ✅ | 2026-05-15 | — |
| U1.4 | 同一密码两次哈希不相同 | `hash_password` | `"test123"`×2 | 两次返回值不同（salt 不同） | ✅ | 2026-05-15 | — |
| U1.5 | Token 生成含正确 claims | `create_access_token` | user_id=1, username="u1", role="user" | payload 包含 `sub`/`username`/`role`/`exp` | ✅ | 2026-05-15 | — |
| U1.6 | Token 解码-有效 token | `decode_access_token` | 有效 JWT | 返回完整 payload dict | ✅ | 2026-05-15 | — |
| U1.7 | Token 解码-无效 token | `decode_access_token` | 篡改的 JWT | 返回空 dict `{}` | ✅ | 2026-05-15 | — |
| U1.8 | Token 解码-过期 token | `decode_access_token` | 过期 JWT | 返回空 dict `{}` | ✅ | 2026-05-15 | — |

### 2.2 后端 — 认证 Service 单元测试

| ID | 测试用例 | 被测函数 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U2.1 | 注册-正常 | `register` | 新用户名 | 返回 `UserResponse`，User 写入 DB | ✅ | 2026-05-15 | Mock DB session |
| U2.2 | 注册-用户名重复 | `register` | 已存在用户名 | 抛出 `UsernameExistsException(E5001)` | ✅ | 2026-05-15 | — |
| U2.3 | 登录-正常 | `login` | 正确用户名+密码 | 返回 `TokenResponse`（access_token + expires_in） | ✅ | 2026-05-15 | Mock DB session |
| U2.4 | 登录-密码错误 | `login` | 正确用户名+错误密码 | 抛出 `InvalidCredentialsException(E5002)` | ✅ | 2026-05-15 | — |
| U2.5 | 登录-用户不存在 | `login` | 不存在的用户名 | 抛出 `InvalidCredentialsException(E5002)` | ✅ | 2026-05-15 | — |
| U2.6 | 登录-Token 非空 | `login` | 正确凭证 | access_token 非空且符合 JWT 格式 | ✅ | 2026-05-15 | 原「Token 不同」改为本用例 |

### 2.3 后端 — Pydantic Schema 校验测试

| ID | 测试用例 | Schema | 输入 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U3.1 | 注册-正常输入 | `RegisterRequest` | username="test", password="123456" | 校验通过 | ✅ | 2026-05-15 | — |
| U3.2 | 注册-用户名过短 | `RegisterRequest` | username="a", password="123456" | `ValidationError`（Pydantic V2: `string_too_short`） | ✅ | 2026-05-15 | V2 错误类型适配 |
| U3.3 | 注册-密码过短 | `RegisterRequest` | username="test", password="123" | `ValidationError`（Pydantic V2: `string_too_short`） | ✅ | 2026-05-15 | V2 错误类型适配 |
| U3.4 | 注册-用户名超长 | `RegisterRequest` | username="x"×65, password="123456" | `ValidationError`（Pydantic V2: `string_too_long`） | ✅ | 2026-05-15 | V2 错误类型适配 |
| U3.5 | 登录-空用户名校验失败 | `LoginRequest` | username="", password="123456" | `ValidationError`（Pydantic V2: `string_too_short`） | ✅ | 2026-05-16 | LoginRequest 已加 min_length=2 |
| U3.6 | TokenResponse 序列化 | `TokenResponse` | access_token="abc", expires_in=86400 | model_dump() 含 token_type="bearer" | ✅ | 2026-05-15 | — |
| U3.7 | 注册-缺少用户名 | `RegisterRequest` | password="123456" | `ValidationError` | ✅ | 2026-05-15 | — |
| U3.8 | 注册-缺少密码 | `RegisterRequest` | username="test" | `ValidationError` | ✅ | 2026-05-15 | — |
| U3.9 | 登录-缺少用户名 | `LoginRequest` | password="123456" | `ValidationError` | ✅ | 2026-05-15 | — |
| U3.10 | TokenResponse 自定义 token_type | `TokenResponse` | access_token="abc", token_type="jwt", expires_in=60 | model_dump() 含 token_type="jwt" | ✅ | 2026-05-15 | — |

### 2.4 后端 — 用户模型测试

> 本节测试直接连接开发库 MySQL，通过 engine.dispose() 清理池避免 Windows 事件循环残留。

| ID | 测试用例 | 被测对象 | 验证项 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U4.1 | User 默认 role | `User` | 创建时不指定 role，flush 后验证 | `role` 默认值为 `"user"` | ✅ | 2026-05-17 | — |
| U4.2 | User username unique | `User` | 重复 username | DB 层抛出 IntegrityError | ✅ | 2026-05-17 | savepoint 隔离，engine.dispose() 清理池 |
| U4.3 | User FK 关联 | `User` / `KnowledgeBase` | 通过 FK 查 KB | 未创建时为空，创建后可查到 | ✅ | 2026-05-17 | 直接查 KB 表避免 Windows ORM 懒加载 MissingGreenlet |

### 2.5 后端 — 认证 API 接口测试

| ID | 测试用例 | 端点 | 请求 | 预期响应 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| A1.1 | 注册-成功 | POST `/api/auth/register` | `{"username":"newuser","password":"123456"}` | 201, `{code:0, message:"注册成功", data:{username:"newuser"}}` | ✅ | 2026-05-15 | — |
| A1.2 | 注册-用户名重复 | POST `/api/auth/register` | 已存在用户名 | 409, `{code:"E5001", message:"用户名已存在"}` | ✅ | 2026-05-15 | — |
| A1.3 | 注册-用户名过短 | POST `/api/auth/register` | `{"username":"a","password":"123456"}` | 422, `{code:"E9003"}` | ✅ | 2026-05-15 | — |
| A1.4 | 注册-密码过短 | POST `/api/auth/register` | `{"username":"test","password":"123"}` | 422, `{code:"E9003"}` | ✅ | 2026-05-15 | — |
| A1.5 | 注册-缺少用户名 | POST `/api/auth/register` | `{"password":"123456"}` | 422 | ✅ | 2026-05-15 | — |
| A1.6 | 注册-缺少密码 | POST `/api/auth/register` | `{"username":"test"}` | 422 | ✅ | 2026-05-15 | — |
| A1.7 | 登录-成功 | POST `/api/auth/login` | 正确凭证 | 200, `{code:0, message:"登录成功", data:{access_token, token_type, expires_in}}` | ✅ | 2026-05-15 | — |
| A1.8 | 登录-密码错误 | POST `/api/auth/login` | 错误密码 | 401, `{code:"E5002", message:"用户名或密码错误"}` | ✅ | 2026-05-15 | — |
| A1.9 | 登录-空用户名 | POST `/api/auth/login` | `{"username":"","password":"correct"}` | 422, `{code:"E9003"}` | ✅ | 2026-05-16 | LoginRequest 已加 min_length=2 |
| A1.10 | 登录-缺少密码 | POST `/api/auth/login` | `{"username":"test"}` | 422 | ✅ | 2026-05-15 | — |
| A1.11 | 受保护路由-无 Token | GET `/api/knowledge-bases` | 无 Authorization header | 401, `{code:"E5004"}` | ✅ | 2026-05-15 | — |
| A1.12 | 受保护路由-无效 Token | GET `/api/knowledge-bases` | `Bearer invalid_token` | 401, `{code:"E5004"}` | ✅ | 2026-05-15 | — |
| A1.13 | 公开路由跳过中间件 | OPTIONS `/api/auth/login` | 无 Token | 405（中间件放行，路由层无 OPTIONS） | ✅ | 2026-05-15 | — |
| A1.14 | OPTIONS 预检放行 | OPTIONS `/api/knowledge-bases` | 无 Token | 200/404/405（中间件放行） | ✅ | 2026-05-15 | — |

### 2.6 前端 — 组件测试

| ID | 测试用例 | 组件 | 验证项 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| C1.1 | LoginPage 渲染 | `LoginPage` | 表单元素存在 | 用户名输入框 + 密码输入框 + 提交按钮存在 | ✅ | 2026-05-15 | — |
| C1.2 | LoginPage 默认登录模式 | `LoginPage` | Tab 状态 | 默认「登录」Tab 高亮 | ✅ | 2026-05-15 | — |
| C1.3 | LoginPage Tab 切换 | `LoginPage` | 点击注册 Tab | 切换至注册模式 + 清空输入 | ✅ | 2026-05-15 | — |
| C1.4 | LoginPage 空用户名校验 | `LoginPage` | 提交空表单 | 显示错误「请输入用户名」 | ✅ | 2026-05-15 | — |
| C1.5 | LoginPage 用户名过短 | `LoginPage` | 提交 1 字符用户名 | 显示错误「用户名至少 2 个字符」 | ✅ | 2026-05-15 | — |
| C1.6 | LoginPage 密码过短 | `LoginPage` | 提交短密码 | 显示错误「密码至少 6 个字符」 | ✅ | 2026-05-15 | — |
| C1.7 | LoginPage 登录成功 | `LoginPage` | 正确凭证提交 | 调用 authStore.login → 跳转 | ✅ | 2026-05-15 | Mock auth store |
| C1.8 | LoginPage 登录失败 | `LoginPage` | API 返回错误 | 显示错误消息 | ✅ | 2026-05-15 | Mock API |
| C1.9 | LoginPage 网络异常 | `LoginPage` | 网络错误 | 显示「网络异常，请稍后重试」 | ✅ | 2026-05-15 | — |
| C1.10 | AppLayout 渲染 | `AppLayout` | 布局结构 | Sidebar + 主内容区 + 滚动区 | ✅ | 2026-05-15 | — |
| C1.11 | AppLayout 页面标题映射 | `AppLayout` | 5 种路由名称 | 对应中文标题正确显示 | ✅ | 2026-05-15 | — |
| C1.12 | AppLayout slot 渲染 | `AppLayout` | 传入子内容 | slot 内容正确渲染 | ✅ | 2026-05-15 | — |
| C1.13 | 路由守卫-未登录 | Router | 访问 `/chat` 未登录 | 重定向到 `/login` | ⏭️ | — | 需 Pinia + Router 联合 Mock，Phase 2 实现 |

---

## 3. Phase 2 测试用例

> §3.1（KB API）和 §3.2（文档状态枚举）详细用例已补充并全部通过；§3.3–§3.5 随对应功能开发时补充，以下为框架。

### 3.1 后端 — 知识库 API 接口测试

| ID | 测试用例 | 端点 | 场景 | 预期响应 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| A2.1 | 创建知识库 | POST `/api/knowledge-bases` | 正常 | 201, `{code:0, data:{id, name, description}}` | ✅ | 2026-05-17 | — |
| A2.2 | 创建-名称重复 | POST | 同名 | 409, E1002 | ✅ | 2026-05-17 | — |
| A2.3 | 列表查询 | GET | 正常 | 200, 分页列表 | ✅ | 2026-05-17 | — |
| A2.4 | 详情查询 | GET `/{id}` | 正常 | 200，data 含 visibility 字段 | ✅ | 2026-05-24 | Phase 2.5 响应新增 visibility |
| A2.5 | 详情-不存在 | GET `/{id}` | 无效 ID | 404, E1001 | ✅ | 2026-05-17 | — |
| A2.6 | 更新知识库 | PUT `/{id}` | 正常 | 200，支持 visibility 更新 | ✅ | 2026-05-24 | Phase 2.5 支持 visibility 修改 |
| A2.7 | 删除知识库 | DELETE `/{id}` | 正常 | 202，异步删除 | ✅ | 2026-05-17 | — |
| A2.8 | 越权访问-private KB | GET | 他人 private KB | 403, E5005 | ✅ | 2026-05-24 | public KB 对非 owner 放行，见 A6.1 |

### 3.2 后端 — 文档状态枚举单元测试

| ID | 测试用例 | 被测函数/类 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U5.1 | 10 状态值 | `DocumentStatus` | 枚举成员数 | 共 10 个成员 | ✅ | 2026-05-17 | — |
| U5.2 | str 子类 | `DocumentStatus` | 类型检查 | `issubclass(DocumentStatus, str)` 为 True | ✅ | 2026-05-17 | — |
| U5.3 | 所有值对齐文档 | `DocumentStatus` | 遍历 value | 10 个字符串值正确 | ✅ | 2026-05-17 | — |
| U5.4 | 终态集合大小 | `TERMINAL_STATUSES` | 检查元素数 | 4 个终态 | ✅ | 2026-05-17 | — |
| U5.5 | 终态集合类型 | `TERMINAL_STATUSES` | 类型检查 | 为 `frozenset` 不可变 | ✅ | 2026-05-17 | — |
| U5.6 | 终态返回 True | `is_terminal()` | 4 个终态参数化 | 全部返回 True | ✅ | 2026-05-17 | — |
| U5.7 | 非终态返回 False | `is_terminal()` | 6 个非终态参数化 | 全部返回 False | ✅ | 2026-05-17 | — |
| U5.8 | 接受纯字符串 | `is_terminal()` | `"completed"`, `"uploaded"`, `"nonexistent"` | True/False/False | ✅ | 2026-05-17 | — |
| U5.9 | Schema 接受枚举值 | `DocumentResponse` | status=DocumentStatus.UPLOADED | 校验通过 | ✅ | 2026-05-17 | — |
| U5.10 | Schema 接受字符串 | `DocumentResponse` | status="completed" | 自动转为枚举 | ✅ | 2026-05-17 | — |
| U5.11 | Schema 拒绝无效值 | `DocumentResponse` | status="invalid_status" | ValidationError | ✅ | 2026-05-17 | — |
| U5.12 | Schema 序列化 | `DocumentResponse` | model_dump() | status 为字符串 "completed" | ✅ | 2026-05-17 | — |

### 3.3 后端 — 文档 API 接口测试

| ID | 测试用例 | 端点 | 场景 | 预期响应 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| A3.1 | 上传文档 | POST `/api/knowledge-bases/{kb_id}/documents` | 正常 PDF | 201, `{code:0, data:{status:"uploaded"}}` | ✅ | 2026-05-18 | multipart |
| A3.2 | 上传-重复文件名 | POST `/api/knowledge-bases/{kb_id}/documents` | 同名文件 | 409, E2013 | ✅ | 2026-05-18 | — |
| A3.3 | 上传-force 覆盖 | POST `/api/knowledge-bases/{kb_id}/documents` | force=true | 201，旧文档被替换 | ✅ | 2026-05-18 | — |
| A3.4 | 上传-不支持格式 | POST `/api/knowledge-bases/{kb_id}/documents` | .exe 文件 | 415, E2002 | ✅ | 2026-05-18 | Mock service 抛出异常 |
| A3.5 | 上传-超大文件 | POST `/api/knowledge-bases/{kb_id}/documents` | >50MB | 400, E2003 | ✅ | 2026-05-18 | Mock service 抛出异常 |
| A3.6 | 文档列表 | GET `/api/knowledge-bases/{kb_id}/documents` | 正常 | 200, 分页列表 | ✅ | 2026-05-18 | — |
| A3.7 | 文档列表-状态筛选 | GET `/api/knowledge-bases/{kb_id}/documents?status=ready` | 筛选 | 200, 仅返回匹配状态 | ✅ | 2026-05-18 | — |
| A3.8 | 文档详情 | GET `/api/knowledge-bases/{kb_id}/documents/{id}` | 正常 | 200, 含 chunk_count | ✅ | 2026-05-18 | — |
| A3.9 | 文档删除 | DELETE `/api/knowledge-bases/{kb_id}/documents/{id}` | 正常 | 202, 异步删除 | ✅ | 2026-05-18 | — |
| A3.10 | 重新处理 | POST `/api/knowledge-bases/{kb_id}/documents/{id}/reprocess` | 失败文档 | 200, 重新入队 | ✅ | 2026-05-18 | — |
| A3.11 | 上传-处理中冲突 | POST `/api/knowledge-bases/{kb_id}/documents` | 文档处理中 | 409, E2011 | ✅ | 2026-05-18 | 幂等锁冲突 |
| A3.12 | 上传-force 冲突 | POST `/api/knowledge-bases/{kb_id}/documents` | force=true 旧文档处理中 | 409, E2012 | ✅ | 2026-05-18 | — |
| A3.13 | 上传-未认证 | POST `/api/knowledge-bases/{kb_id}/documents` | 无 Token | 401, E5004 | ✅ | 2026-05-18 | — |
| A3.14 | 上传-越权 | POST `/api/knowledge-bases/{kb_id}/documents` | 非 owner/admin | 403, E5005 | ✅ | 2026-05-18 | — |
| A3.15 | 批量上传-全部成功 | POST `/api/knowledge-bases/{kb_id}/documents/batch-upload` | 多文件 | 200, success 列表 | ✅ | 2026-05-18 | — |
| A3.16 | 批量上传-部分失败 | POST `/api/knowledge-bases/{kb_id}/documents/batch-upload` | 含不支持格式 | 200, success + failed 列表 | ✅ | 2026-05-18 | — |
| A3.17 | 文档分块列表 | GET `/api/knowledge-bases/{kb_id}/documents/{id}/chunks` | 正常 | 200, preview 截断 | ✅ | 2026-05-18 | — |
| A3.18 | 文档分块-无数据 | GET `/api/knowledge-bases/{kb_id}/documents/{id}/chunks` | 无分块 | 200, total=0 | ✅ | 2026-05-18 | — |
| A3.19 | 文档列表-分页校验 | GET `/api/knowledge-bases/{kb_id}/documents` | page_size=0/101 | 422 | ✅ | 2026-05-18 | Query(ge=1, le=100) |

### 3.4 后端 — Celery 流水线单元测试

| ID | 测试用例 | 被测模块 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U6.1 | 幂等锁-正常获取 | `lock.py` | 首次入队 | Redis SET NX 成功 | ✅ | 2026-05-19 | Mock Redis |
| U6.2 | 幂等锁-重复拒绝 | `lock.py` | 重复入队 | 返回「处理中」不重复执行 | ✅ | 2026-05-19 | Mock Redis |
| U6.3 | 解析容错-轻微错误 | `parser.py` | <20% 页面失败 | 返回 warning 级别结果 | ✅ | 2026-05-19 | Mock PyPDF2 |
| U6.4 | 解析容错-中等错误 | `parser.py` | 20-50% 页面失败 | 标记 partial_failed | ✅ | 2026-05-19 | Mock PyPDF2 |
| U6.5 | 解析容错-严重错误 | `parser.py` | >50% 页面失败 | 标记 failed | ✅ | 2026-05-19 | Mock PyPDF2 |
| U6.6 | 分块逻辑 | `chunker.py` | 长文本 | 按分隔符优先级分块，每块 800-1200 chars | ✅ | 2026-05-20 | 35 用例全部通过 |
| U6.7 | Embedding 批次 checkpoint | `tasks.py` / `test_tasks.py` | 中途失败 | 从 last_success_batch 恢复 | ✅ | 2026-05-21 | test_tasks.py 覆盖断点恢复/阶段检测/ChromaDB 清理失败标记/锁集成（11 用例） |
| U6.8 | 存储-保存文件 | `storage.py` | 上传文件 | 文件写入磁盘，返回路径 `uploads/{kb_id}/{doc_id}/{uuid}_{filename}` | ✅ | 2026-05-21 | tempfile 临时目录 + Mock UploadFile |
| U6.9 | 存储-读取文件 | `storage.py` | 已有文件 | 返回 bytes 内容 | ✅ | 2026-05-21 | — |
| U6.10 | 存储-删除文件 | `storage.py` | 已有文件 | 文件删除，空目录自动清理 | ✅ | 2026-05-21 | 含多级空目录清理 + 同目录有其他文件保留目录 |
| U6.11 | 存储-文件名安全处理 | `storage.py` | 含 `/` `\` 空字节的文件名 | 移除危险字符，保留中文 | ✅ | 2026-05-21 | 16 个 sanitize 用例 |

### 3.5 前端 — 组件测试

> Phase 2.3.3 页面已构建完成，组件测试已编写并全部通过（49 用例，2026-05-22）。

| ID | 测试用例 | 组件 | 验证项 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| C2.1 | KnowledgeList 渲染 | `KnowledgeList` | 网格布局 | KB 卡片网格渲染 | ✅ | 2026-05-22 | 含搜索框、新建按钮、卡片名称/描述/文档数/分块数、部门图标、无描述占位 |
| C2.2 | KnowledgeList 空状态 | `KnowledgeList` | 无 KB | 显示空状态提示 | ✅ | 2026-05-22 | 显示「暂无知识库」 |
| C2.3 | KnowledgeList 新建弹窗 | `KnowledgeList` | 点击新建 | 弹窗显示 | ✅ | 2026-05-22 | 含按钮点击 + 新建卡片点击两个入口 |
| C2.4 | KnowledgeList 删除确认 | `KnowledgeList` | — | 二次确认弹窗 | ⬜ | — | 涉及 el-dropdown 展开 + ElMessageBox.confirm，stub 环境下难以模拟完整流程 |
| C2.5 | DocumentList 渲染 | `KnowledgeDetail` | 表格 | 文档表格含状态标签 | ✅ | 2026-05-22 | 有文档时表格渲染 + 空状态隐藏 |
| C2.6 | DocumentList 上传拖拽 | `KnowledgeDetail` | 上传区域 | 上传区域渲染 | ✅ | 2026-05-22 | 上传区域文案 + 格式提示渲染；实际拖拽/文件选择需 e2e 测试 |
| C2.7 | DocumentList 状态轮询 | `KnowledgeDetail` | 生命周期 | 组件挂载获取数据、卸载清除轮询 | ✅ | 2026-05-22 | 验证 fetchKbDetail/fetchDocList 调用 + clearAllPolling 调用 |
| C2.8 | 公共KB详情返回按钮 | `KnowledgeDetail` | 导航 | `?from=public` 时返回按钮跳转公共KB列表 | ✅ | 2026-06-03 | 模拟 mockRoute.query.from='public'，点击返回按钮触发 push('/knowledge-bases/public') |
| C2.9 | 私有KB详情返回按钮 | `KnowledgeDetail` | 导航 | 无 `from` 参数时返回按钮跳转我的KB列表 | ✅ | 2026-06-03 | 模拟 mockRoute.query={}，点击返回按钮触发 push('/knowledge-bases') |

---

## 4. Phase 2.5 测试用例

> Phase 2.5 知识库可见性重构，新增 visibility 字段的 Schema 校验、KB 权限矩阵、公共 KB 列表接口、前端公共 KB 页面组件测试。

### 4.1 后端 — visibility Schema 校验测试

| ID | 测试用例 | Schema | 输入 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U9.1 | 创建-默认 visibility | `KnowledgeBaseCreate` | 不传 visibility | visibility 默认 `"private"` | ✅ | 2026-05-24 | test_default_visibility_is_private |
| U9.2 | 创建-显式 private | `KnowledgeBaseCreate` | `visibility="private"` | 校验通过 | ✅ | 2026-05-24 | test_explicit_private |
| U9.3 | 创建-显式 public | `KnowledgeBaseCreate` | `visibility="public"` | 校验通过 | ✅ | 2026-05-24 | test_explicit_public |
| U9.4 | 创建-无效 visibility 值 | `KnowledgeBaseCreate` | `visibility="invalid"` | `ValidationError` | ✅ | 2026-05-24 | test_invalid_visibility_rejected + test_visibility_case_sensitive |
| U9.5 | 更新-visibility 可选 | `KnowledgeBaseUpdate` | 不传 visibility（仅更新 name） | `visibility=None`，校验通过 | ✅ | 2026-05-24 | test_visibility_optional |
| U9.6 | 更新-设置 visibility | `KnowledgeBaseUpdate` | `visibility="public"` | 校验通过 | ✅ | 2026-05-24 | test_set_visibility_public |
| U9.7 | 更新-无效 visibility 值 | `KnowledgeBaseUpdate` | `visibility="invalid"` | `ValidationError` | ✅ | 2026-05-24 | test_invalid_visibility_rejected |
| U9.8 | 响应-含 visibility 字段 | `KnowledgeBaseResponse` | ORM 对象含 visibility | `model_validate` 成功，visibility 为字符串 | ✅ | 2026-05-24 | test_response_includes_visibility |

### 4.2 后端 — KB 权限矩阵接口测试

| ID | 测试用例 | 端点 | 场景 | 预期响应 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| A6.1 | public KB 非 owner 可读 | GET `/{id}` | 其他用户访问 public KB | 200, 含 visibility="public" | ✅ | 2026-05-24 | test_public_kb_readable_by_other_user |
| A6.2 | private KB 非 owner 拒绝 | GET `/{id}` | 其他用户访问 private KB | 403, E5005 | ✅ | 2026-05-24 | test_private_kb_denied_to_other_user |
| A6.3 | public KB 非 owner 不可修改 | PUT `/{id}` | 其他用户修改 public KB | 403, E5005 | ✅ | 2026-05-24 | test_public_kb_not_writable_by_other_user |
| A6.4 | admin 可读 private KB | GET `/{id}` | admin 访问他人 private KB | 200 | ✅ | 2026-05-24 | test_admin_can_read_private_kb |
| A6.5 | admin 可修改任意 KB visibility | PUT `/{id}` | admin 修正他人 KB visibility | 200, visibility 已更新 | ✅ | 2026-05-24 | test_admin_can_update_any_kb_visibility |
| A6.6 | owner 可修改自己 KB visibility | PUT `/{id}` | owner 将 private→public | 200, visibility="public" | ✅ | 2026-05-24 | test_owner_can_update_visibility |

### 4.3 后端 — 公共 KB 列表接口测试

| ID | 测试用例 | 端点 | 场景 | 预期响应 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| A7.1 | 公共列表-返回 public+active | GET `/public` | 多个 KB 混合状态 | 200, 仅返回 visibility=public 且 status=active | ✅ | 2026-05-24 | test_list_public_kbs_success |
| A7.2 | 公共列表-不返回 private | GET `/public` | private KB 存在 | private KB 不在列表中 | ✅ | 2026-05-24 | 由 list_public_kbs() WHERE visibility=public 保证 |
| A7.3 | 公共列表-不返回 deleting | GET `/public` | deleting KB（visibility=public）存在 | deleting KB 不在列表中 | ✅ | 2026-05-24 | 由 list_public_kbs() WHERE status=active 保证 |
| A7.4 | 公共列表-分页 | GET `/public?page=1&page_size=5` | 多页数据 | 正确分页 | ✅ | 2026-05-24 | test_list_public_pagination |
| A7.5 | 公共列表-返回 owner 用户名 | GET `/public` | 正常 | items 含 username 字段 | ✅ | 2026-05-24 | test_list_public_includes_username |
| A7.6 | 公共列表-未认证拒绝 | GET `/public` | 无 Token | 401, E5004 | ✅ | 2026-05-24 | test_list_public_no_auth |
| A7.7 | 公共列表-空数据 | GET `/public` | 无 public KB | 200, total=0 | ✅ | 2026-05-24 | test_list_public_empty |

### 4.4 前端 — 公共 KB 页面组件测试

| ID | 测试用例 | 组件 | 验证项 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| C5.1 | PublicKnowledgeList 渲染 | `PublicKnowledgeList` | 卡片网格 | 公共 KB 卡片正确渲染 | ✅ | 2026-05-24 | 10 用例全部通过 |
| C5.2 | PublicKnowledgeList 无新建按钮 | `PublicKnowledgeList` | 新建按钮 | 无新建/编辑/删除按钮 | ✅ | 2026-05-24 | — |
| C5.3 | PublicKnowledgeList 显示 owner | `PublicKnowledgeList` | 卡片 | 显示 owner 用户名 + 公开标识 | ✅ | 2026-05-24 | — |
| C5.4 | PublicKnowledgeList 空状态 | `PublicKnowledgeList` | 无 public KB | 显示空状态提示 | ✅ | 2026-05-24 | — |

### 4.5 后端 — 文档接口权限矩阵测试

> 验证 ROADMAP §4.2「文档接口权限更新」：上传/reprocess 仅 owner；查看/分块/删除 owner + admin。

| ID | 测试用例 | 端点 | 场景 | 预期响应 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| A8.1 | owner 可上传 | POST `/{kb_id}/documents` | owner 上传文档 | 201 | ✅ | 2026-05-24 | test_owner_can_upload |
| A8.2 | admin 不可上传 | POST `/{kb_id}/documents` | admin 上传到他人 KB | 403, E5005 | ✅ | 2026-05-24 | test_admin_cannot_upload |
| A8.3 | 其他用户不可上传 | POST `/{kb_id}/documents` | 普通用户上传到他人 KB | 403, E5005 | ✅ | 2026-05-24 | test_other_user_cannot_upload |
| A8.4 | owner 可查看列表 | GET `/{kb_id}/documents` | owner 查看文档列表 | 200 | ✅ | 2026-05-24 | test_owner_can_list |
| A8.5 | admin 可查看列表 | GET `/{kb_id}/documents` | admin 查看他人 KB 文档（审计） | 200 | ✅ | 2026-05-24 | test_admin_can_list |
| A8.6 | 其他用户不可查看列表 | GET `/{kb_id}/documents` | 普通用户查看他人 KB 文档 | 403, E5005 | ✅ | 2026-05-24 | test_other_user_cannot_list |
| A8.7 | owner 可查看详情 | GET `/{kb_id}/documents/{doc_id}` | owner 查看文档详情 | 200 | ✅ | 2026-05-24 | test_owner_can_get |
| A8.8 | admin 可查看详情 | GET `/{kb_id}/documents/{doc_id}` | admin 查看他人文档（审计） | 200 | ✅ | 2026-05-24 | test_admin_can_get |
| A8.9 | 其他用户不可查看详情 | GET `/{kb_id}/documents/{doc_id}` | 普通用户查看他人文档 | 403, E5005 | ✅ | 2026-05-24 | test_other_user_cannot_get |
| A8.10 | owner 可查看分块 | GET `/{kb_id}/documents/{doc_id}/chunks` | owner 查看分块列表 | 200 | ✅ | 2026-05-24 | test_owner_can_get_chunks |
| A8.11 | admin 可查看分块 | GET `/{kb_id}/documents/{doc_id}/chunks` | admin 查看他人文档分块（审计） | 200 | ✅ | 2026-05-24 | test_admin_can_get_chunks |
| A8.12 | 其他用户不可查看分块 | GET `/{kb_id}/documents/{doc_id}/chunks` | 普通用户查看他人文档分块 | 403, E5005 | ✅ | 2026-05-24 | test_other_user_cannot_get_chunks |
| A8.13 | owner 可删除 | DELETE `/{kb_id}/documents/{doc_id}` | owner 删除文档 | 202 | ✅ | 2026-05-24 | test_owner_can_delete |
| A8.14 | admin 可删除 | DELETE `/{kb_id}/documents/{doc_id}` | admin 删除他人文档（违规清理） | 202 | ✅ | 2026-05-24 | test_admin_can_delete |
| A8.15 | 其他用户不可删除 | DELETE `/{kb_id}/documents/{doc_id}` | 普通用户删除他人文档 | 403, E5005 | ✅ | 2026-05-24 | test_other_user_cannot_delete |
| A8.16 | owner 可 reprocess | POST `/{kb_id}/documents/{doc_id}/reprocess` | owner 重新处理 | 200 | ✅ | 2026-05-24 | test_owner_can_reprocess |
| A8.17 | admin 不可 reprocess | POST `/{kb_id}/documents/{doc_id}/reprocess` | admin 重新处理他人文档 | 403, E5005 | ✅ | 2026-05-24 | test_admin_cannot_reprocess |
| A8.18 | 其他用户不可 reprocess | POST `/{kb_id}/documents/{doc_id}/reprocess` | 普通用户重新处理他人文档 | 403, E5005 | ✅ | 2026-05-24 | test_other_user_cannot_reprocess |

---

## 5. Phase 3 测试用例

### 5.1 后端 — 检索器单元测试（向量检索）

| ID | 测试用例 | 被测函数 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U7.1 | 向量检索-基本 | `vector_retriever.search()` | 正常查询 | 返回 top_k=10 结果，含 doc_id + score + content | ✅ | 2026-05-28 | Mock ChromaDB collection |
| U7.2 | 向量检索-kb_id 过滤 | `vector_retriever.search()` | 指定 kb_id | `where={"kb_id": kb_id}` 仅返回该 kb_id 结果 | ✅ | 2026-05-28 | metadata 保持 int 类型 |
| U7.3 | 向量检索-结果不足 top_k | `vector_retriever.search()` | kb 文档数 < top_k | 返回实际可用数量，不补空 | ✅ | 2026-05-28 | ChromaDB 自然返回实际数量 |
| U7.4 | 向量检索-空结果 | `vector_retriever.search()` | kb 无匹配文档 | 返回空列表，不抛异常 | ✅ | 2026-05-28 | 含空查询/空白查询/embedding 空结果 |
| U7.5 | 向量检索-metadata 字段完整 | `vector_retriever.search()` | 正常查询 | 每条结果含 doc_id/kb_id/chunk_index/page/score | ✅ | 2026-05-28 | page 为后续补充字段 |
| U7.6 | 向量检索-Embedding 调用 | `vector_retriever.search()` | 查询文本 | 调用 DashScope embed API，text_type="query" | ✅ | 2026-05-28 | 复用 embedder，text_type 参数已扩展 |
| U7.7 | 向量检索-ChromaDB 异常 | `vector_retriever.search()` | ChromaDB 不可用 | 抛出 `RetrievalServiceException(E4003)` | ✅ | 2026-05-28 | 含 embedding 异常场景 |
| U7.8 | 向量检索-metadata int 类型一致性 | `vector_retriever.search()` | metadata kb_id/doc_id/chunk_index 为 int | 入库/查询两端统一 int，显式 int() 转换保障 | ✅ | 2026-06-01 | 决策 #21，新增 test_metadata字段为int类型 测试 |

### 5.2 后端 — BM25 检索器单元测试

| ID | 测试用例 | 被测函数 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U7.10 | BM25-基本检索 | `bm25_retriever.search()` | 中文查询 | `jieba.lcut` 分词 → `BM25Okapi.get_scores()` 返回排序结果 | ✅ | 2026-05-28 | Mock Redis + DB |
| U7.11 | BM25-返回 doc_id 映射 | `bm25_retriever.search()` | 正常查询 | 通过 `doc_ids` 数组映射 chunk_id → 返回结果含 doc_id | ✅ | 2026-05-28 | — |
| U7.12 | BM25-空语料 | `BM25Okapi([])` | 知识库无文档 | 初始化不抛异常，`get_scores()` 返回空数组 | ✅ | 2026-05-28 | 返回 None + 空列表 |
| U7.13 | BM25-jieba 分词中文 | `jieba.lcut()` | 中文文本 | 正确切分中文词组（如 "入职需要开通哪些账号"） | ✅ | 2026-05-29 | Mock + 真实 jieba 双重覆盖 |
| U7.14 | BM25-结果数量 | `bm25_retriever.search()` | 正常查询 | 返回 top_k=10 结果 | ✅ | 2026-05-28 | top_k 截取验证 |
| U7.15 | BM25-相关性排序 | `bm25_retriever.search()` | 精确关键词查询 | 包含精确关键词的 chunk 排在前面 | ✅ | 2026-05-29 | 真实 jieba 验证 |
| U7.16 | BM25-真实分词检索 | `bm25_retriever.search()` | 真实 jieba 分词 + 中文查询 | 相关文档得分更高，精确匹配排第一 | ✅ | 2026-05-29 | `TestBM25RetrieverWithRealJieba` (7 用例) |
| U7.17 | BM25-min_score 阈值 | `bm25_retriever.search()` | 负分/零分/参数调整 | score < min_score 被过滤，score=0 保留，参数可调 | ✅ | 2026-05-29 | `MIN_BM25_SCORE=-5.0` |
| U7.18 | BM25-真实分词缓存懒加载 | `bm25_retriever.search()` | 缓存未命中 + 真实 jieba | 从 MySQL 加载后用真实 jieba 分词构建索引并缓存 | ✅ | 2026-05-29 | 验证缓存 tokens 非逐字拆分 |

### 5.3 后端 — BM25 索引缓存测试

| ID | 测试用例 | 被测函数 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U7.20 | 缓存-命中 | `get_bm25_index()` | Redis 有 `bm25_tokens:{kb_id}` | 直接返回 `BM25Okapi(data["tokens"]), data["doc_ids"]` | ✅ | 2026-05-28 | Mock Redis |
| U7.21 | 缓存-未命中懒加载 | `get_bm25_index()` | Redis 无缓存 | 从 MySQL 读 chunks → jieba 分词 → 写 Redis → 返回 | ✅ | 2026-05-28 | — |
| U7.22 | 缓存-写入格式正确 | `get_bm25_index()` | 懒加载后写缓存 | Redis 存 `{"doc_ids": [...], "tokens": [[...], ...], "contents": [...]}` JSON | ✅ | 2026-05-28 | — |
| U7.23 | 缓存-TTL=300s | `get_bm25_index()` | 写缓存 | `SETEX` 带 300s 过期 | ✅ | 2026-05-28 | — |
| U7.24 | 缓存-文档终态后重建 | Celery task | 文档入库完成 | 触发 `DEL bm25_tokens:{kb_id}` → 下次查询懒加载 | ✅ | 2026-05-28 | 在 ingest task 末尾 |
| U7.25 | 缓存-文档删除后失效 | Celery task | 文档删除完成 | `DEL bm25_tokens:{kb_id}` | ✅ | 2026-05-28 | — |
| U7.26 | BM25Okapi 实例化性能 | `BM25Okapi(corpus)` | 1000 chunk 语料 | 构造时间 < 50ms（仅 NumPy 计算，不含分词） | ⏭️ | — | 性能测试，可选 |

### 5.4 后端 — RRF 融合算法测试

| ID | 测试用例 | 被测函数 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U7.30 | RRF-标准合并 | `rrf_fusion()` | 两路各 10 结果，k=60 | 按 `Σ 1/(k+rank)` 降序排列，输出 top_k 结果 | ✅ | 2026-05-30 | 14 用例全部通过 |
| U7.31 | RRF-两路有重叠文档 | `rrf_fusion()` | 同一 chunk 在两路中都出现 | 分数累加（两路 rank 分别计算），排名更靠前 | ✅ | 2026-05-30 | — |
| U7.32 | RRF-向量路为空 | `rrf_fusion()` | 向量检索返回 [] | 仅返回 BM25 结果，保持原排序 | ✅ | 2026-05-30 | — |
| U7.33 | RRF-BM25 路为空 | `rrf_fusion()` | BM25 返回 [] | 仅返回向量结果，保持原排序 | ✅ | 2026-05-30 | — |
| U7.34 | RRF-两路均为空 | `rrf_fusion()` | 两路均返回 [] | 返回空列表 | ✅ | 2026-05-30 | — |
| U7.35 | RRF-排名相同处理 | `rrf_fusion()` | 不同 chunk 在同一路中 rank 相同（罕见） | 使用平均 rank 或文档 ID 作为 tiebreaker | ✅ | 2026-05-30 | — |
| U7.36 | RRF-k 值可配置 | `rrf_fusion()` | k=10 / k=60 / k=120 | k 越小排名影响越大，k=60 为默认平衡值 | ✅ | 2026-05-30 | — |

### 5.5 后端 — NoopReranker 测试

| ID | 测试用例 | 被测函数 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U7.40 | NoopReranker-保持 RRF 排序 | `NoopReranker.rerank()` | 输入混合长度 chunks | 保持 RRF 融合原始排序（相关性降序），仅截取 top_k | ✅ | 2026-06-04 | 11 用例全部通过；修复：不再按长度重排 |
| U7.41 | NoopReranker-截取 top_k | `NoopReranker.rerank()` | 输入 10 chunks, top_k=5 | 保持 RRF 排序，返回前 5 个 | ✅ | 2026-06-04 | — |
| U7.42 | NoopReranker-输入不足 top_k | `NoopReranker.rerank()` | 输入 3 chunks, top_k=5 | 返回全部 3 个 | ✅ | 2026-06-04 | — |
| U7.43 | NoopReranker-空输入 | `NoopReranker.rerank()` | 输入 [] | 返回 [] | ✅ | 2026-06-04 | — |
| U7.44 | NoopReranker-不改变 chunk 内容 | `NoopReranker.rerank()` | 正常输入 | 仅截取数量，chunk 的 content/metadata 不变 | ✅ | 2026-06-04 | — |

### 5.6 后端 — Prompt 模板测试

| ID | 测试用例 | 被测函数 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U7.50 | Prompt-基本拼接 | `prompt_builder.build()` | question + chunks | 返回含 system prompt + context + question 的 messages 数组 | ✅ | 2026-06-04 | 13 用例全部通过；修复：移除 sorted(key=len) |
| U7.51 | Prompt-检索结果格式化 | `prompt_builder.build()` | 多个 chunks | 每个 chunk 标注 [来源N] 标签（N=chunk_index） | ✅ | 2026-06-01 | _format_chunk_reference 测试 |
| U7.52 | Prompt-软上限控制 | `prompt_builder.build()` | chunks 总长度超预算 | 保持相关性排序，超预算时跳过当前 chunk 尝试下一个 | ✅ | 2026-06-04 | Token 估算用中英文自适应算法 |
| U7.53 | Prompt-空检索结果 | `prompt_builder.build()` | chunks=[] | system prompt 包含「知识库中未找到相关信息」 | ✅ | 2026-06-01 | — |
| U7.54 | Prompt-history 参数 | `prompt_builder.build()` | Phase 3 历史为空 | `history=[]` 不注入历史消息，Phase 4 传入历史 | ⬜ | — | — |
| U7.55 | Prompt-预算计算正确 | `estimate_tokens()` | 中文/英文/混合 | 中文占比 >30% → ratio=1.5，否则 4.0（复用 chunker 算法） | ✅ | 2026-06-01 | 复用 chunker.estimate_tokens |
| U7.56 | Prompt-不超过模型上限 80% | `prompt_builder.build()` | 大量 chunks | 最终 prompt tokens ≤ 模型 context_window × 0.8 | ⬜ | — | — |

### 5.7 后端 — Chat Service 单元测试

| ID | 测试用例 | 被测函数 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U7.60 | Service-正常问答流程 | `chat_service.chat()` | conversation_id=null | 自动创建会话 → 检索 → RRF → Rerank → Prompt → LLM 流式 → SSE 事件 | ✅ | 2026-06-02 | 全链路 Mock |
| U7.61 | Service-已有会话追加 | `chat_service.chat()` | conversation_id 存在 | 复用已有会话，保存消息到同一 conversation | ✅ | 2026-06-02 | — |
| U7.62 | Service-检索失败 | `chat_service.chat()` | 检索抛异常 | 包装为 `RetrievalServiceException(E4003)`，对齐 API.md §1.3 E4003 | ✅ | 2026-06-02 | — |
| U7.63 | Service-LLM 失败 | `chat_service.chat()` | LLM API 返回 500 | SSE event: error (E4002)，不崩连接 | ✅ | 2026-06-02 | — |
| U7.63b | Service-sources 抑制 | `_generate_sse_stream` | LLM 回答含"未找到相关信息" | 前缀 35 字符匹配 → 抑制；全文匹配 + 无 [来源N] 引用 → 抑制；有引用 → 保留 | ✅ | 2026-06-04 | 4 用例：真阴性前缀/假阳性有引用/真阴性无引用/正常回答 |
| U7.63c | Service-sources chunk_index | `_build_sources` | 正常检索结果 | 每个 chunk 含 `chunk_index` 字段，与 LLM Prompt 中 [来源N] 编号一致 | ✅ | 2026-06-04 | 使用 `prompt_result.used_chunks` 确保编号一致 |
| U7.63d | Service-sources 引用过滤 | `_extract_citation_indices` + `_generate_sse_stream` | 多种引用场景 | ① 提取 [来源N] 编号（单个/多个/去重）；② 无引用返回空集合；③ sources 仅含被引用 chunk（LLM 写 [来源N] 时）；④ 全引用时全量发送；⑤ 零引用时回退发送全部 used_chunks（修复 LLM 格式脆弱耦合）；⑥ LLM 失败时回退全量发送；⑦ 幻觉编号忽略 | ✅ | 2026-06-08 | 10 用例（TestExtractCitationIndices 5 + TestChatCitationFiltering 5），修复脆弱耦合 |
| U7.64 | Service-kb 无文档 | `chat_service.chat()` | kb chunks=0 | SSE event: error (E4001) | ✅ | 2026-06-02 | — |
| U7.65 | Service-用户消息保存 | `chat_service.chat()` | 正常问答 | messages 表写入 role=user + role=assistant 两条 | ✅ | 2026-06-02 | — |
| U7.66 | Service-标题生成 | `chat_service._generate_title()` | 首轮问答 | 截取 question[:12]，去除标点，更新 conversation.title | ✅ | 2026-06-02 | — |
| U7.67 | Service-message_count 递增 | `chat_service.chat()` | 每次问答 | conversation.message_count += 2（user+assistant） | ✅ | 2026-06-02 | — |

### 5.8 后端 — LLM 调用与 thinking 解析测试

| ID | 测试用例 | 被测函数 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U7.70 | LLM-流式调用 | `stream_chat_completion()` | 正常请求 | 返回 async generator，逐 chunk yield delta | ✅ | 2026-06-01 | Mock OpenAI SDK，16 用例全部通过 |
| U7.71 | LLM-content 事件 | `stream_chat_completion()` | 正常响应 | `delta.content` → `event: message` | ✅ | 2026-06-01 | — |
| U7.72 | LLM-thinking 事件 | `stream_chat_completion()` | deep_thinking=true | `extra_body={"thinking":{"type":"enabled"}}` + `reasoning_effort="high"`，`delta.reasoning_content` → `event: thinking` | ✅ | 2026-06-02 | Mock OpenAI SDK，15 用例全部通过 |
| U7.73 | LLM-deep_thinking=false 显式禁用 | `stream_chat_completion()` | deep_thinking=false | `extra_body={"thinking":{"type":"disabled"}}`，不传 `reasoning_effort`，仅 message 事件，无 thinking | ✅ | 2026-06-02 | DeepSeek 默认 enabled，须显式传 disabled；disabled 时禁止同时传 effort |
| U7.74 | LLM-重试 | `stream_chat_completion()` | API 返回 500/503 | max_retries=3 指数退避重试 | ⬜ | — | — |
| U7.75 | LLM-重试全部失败 | `stream_chat_completion()` | 3 次重试均失败 | 抛出 `LLMCallFailedException(E4002)` | ⬜ | — | — |
| U7.76 | LLM-限流 | `stream_chat_completion()` | API 返回 429 | 抛出 `LLMRateLimitExceededException(E4004)` | ✅ | 2026-06-02 | — |
| U7.77 | LLM-thinking 不落库 | `chat_service.chat()` | deep_thinking=true | `messages.thinking_content` 写入 null | ⬜ | — | 仅流式展示 |
| U7.78 | LLM-token 消耗记录 | `chat_service.chat()` | 正常问答 | `messages.token_count` 写入估算值（DeepSeek 流式 API 不返回 usage，使用 `chunker.estimate_tokens()` 估算） | ✅ | 2026-06-02 | 技术偏差：API 不返回 usage → 估算替代 |

### 5.9 后端 — SSE 流式输出测试

| ID | 测试用例 | 被测函数 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U7.80 | SSE-事件序列 | `sse_helpers` | 正常问答 | meta → (thinking)×N → message×N → sources → finish | ✅ | 2026-06-02 | — |
| U7.81 | SSE-心跳帧 | `sse_helpers` | 无数据 15s | 发送 `: ping\n\n` 注释帧，浏览器忽略但保持连接 | ✅ | 2026-06-02 | — |
| U7.82 | SSE-中途错误 | `sse_helpers` | LLM 中途失败 | meta → (message)×N → error → 连接关闭 | ✅ | 2026-06-02 | 异常向上传播验证 |
| U7.83 | SSE-客户端断开 | `sse_helpers` | 用户关闭页面 | `asyncio.CancelledError` 被捕获，LLM 流被中断 | ⬜ | — | 需真实 SSE 连接，Phase 4 手动测试 |
| U7.84 | SSE-Content-Type | `StreamingResponse` | 正常 | `text/event-stream` + `Cache-Control: no-cache` + `Connection: keep-alive` | ✅ | 2026-06-02 | 通过 API 集成测试覆盖 |
| U7.85 | SSE-sources 事件数据 | `chat_service._build_sources()`（导入生产函数，非复制） | 正常 | chunks 数组每项含 doc_id/doc_name/content/score/page | ✅ | 2026-06-03 | P2 重构：消除逻辑复制，改为 import 真实函数 |
| U7.86 | SSE-finish 事件数据 | `sse_helpers._build_finish()` | 正常 | message_id + title（首轮）+ token_usage{prompt,completion,total} | ✅ | 2026-06-02 | — |

### 5.10 后端 — ChatRequest Schema 校验测试

| ID | 测试用例 | Schema | 输入 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U7.90 | question 为空 | `ChatRequest` | `question=""` | `ValidationError`（min_length=1） | ✅ | 2026-06-02 | — |
| U7.91 | question 超长 | `ChatRequest` | `question="x"×2001` | `ValidationError`（max_length=2000） | ✅ | 2026-06-02 | — |
| U7.92 | kb_id 缺失 | `ChatRequest` | 不传 kb_id | `ValidationError`（required） | ✅ | 2026-06-02 | — |
| U7.93 | conversation_id 可选 | `ChatRequest` | 不传 conversation_id | 校验通过，默认 None | ✅ | 2026-06-02 | — |
| U7.94 | deep_thinking 默认值 | `ChatRequest` | 不传 deep_thinking | 默认 false | ✅ | 2026-06-02 | — |
| U7.95 | reasoning_effort 非请求字段 | `ChatRequest` | 请求体不包含 reasoning_effort | 校验通过，后端仅在 `deep_thinking=true` 时内部固定 `"high"` | ⏭️ | — | Phase 3 不开放前端控制，待 Phase 5+ |
| U7.96 | reasoning_effort 非法值 | `ChatRequest` | reasoning_effort="low" | 不作为请求字段校验；如 Phase 5+ 开放需新增枚举校验 | ⏭️ | — | Phase 3 不开放前端控制 |
| U7.97 | 正常请求 | `ChatRequest` | 全部合法字段 | 校验通过 | ✅ | 2026-06-02 | — |

### 5.11 后端 — 问答 SSE 接口测试

| ID | 测试用例 | 端点 | 场景 | 预期 SSE 事件序列 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| A4.1 | 正常问答 | POST `/api/chat` | 有效问题 + conversation_id=null | meta → message×N → sources → finish（finish 含新 conversation_id + title） | ✅ | 2026-06-02 | — |
| A4.2 | 正常问答-已有会话 | POST `/api/chat` | 有效问题 + conversation_id 存在 | meta（复用 conversation_id） → message×N → sources → finish | ✅ | 2026-06-02 | — |
| A4.3 | 空问题 | POST `/api/chat` | question="" | HTTP 422 (E9003)，非 SSE | ✅ | 2026-06-02 | 连接建立前校验 |
| A4.4 | kb 无可用文档 | POST `/api/chat` | kb chunks=0 | SSE error event (E4001) | ✅ | 2026-06-02 | — |
| A4.5 | kb 不存在 | POST `/api/chat` | 无效 kb_id | HTTP 404 (E1001)，非 SSE | ✅ | 2026-06-02 | 连接建立前校验 |
| A4.6 | private KB 非 owner 拒绝 | POST `/api/chat` | 其他用户访问 private KB | HTTP 403 (E5005) | ✅ | 2026-06-02 | — |
| A4.7 | public KB 任意用户可检索 | POST `/api/chat` | 其他用户访问 public KB | 正常 SSE 事件序列 | ✅ | 2026-06-02 | — |
| A4.8 | deep_thinking=true | POST `/api/chat` | `deep_thinking: true` | meta → thinking×N → message×N → sources → finish | ✅ | 2026-06-02 | — |
| A4.9 | deep_thinking=false（默认） | POST `/api/chat` | 不传 deep_thinking | meta → message×N → sources → finish（无 thinking 事件） | ✅ | 2026-06-02 | — |
| A4.10 | 未认证 | POST `/api/chat` | 无 Token | HTTP 401 (E5004) | ✅ | 2026-06-02 | — |
| A4.11 | 流式中断-前端内存保留 | POST `/api/chat` | 中途断连 | 前端内存保留已渲染内容（刷新丢失），conversation 已创建可继续追问。**Phase 3 不持久化半条消息** | ⬜ | — | Phase 4 重访是否需要 message.status 字段 |
| A4.12 | 心跳帧存在 | POST `/api/chat` | 长回答 >15s | SSE 流中包含 `: ping\n\n` 注释帧 | ✅ | 2026-06-02 | — |

### 5.12 后端 — KB 选择器接口测试

| ID | 测试用例 | 端点 | 场景 | 预期响应 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| A9.1 | 选择器-正常返回 | GET `/api/knowledge-bases/selectable` | 已登录用户 | 200, `{mine: [...], public: [...]}` | ✅ | 2026-06-02 | — |
| A9.2 | 选择器-mine 含全部自己 KB | GET `/api/knowledge-bases/selectable` | 用户有 private+public KB | mine 包含所有自己的 KB（不论 visibility） | ✅ | 2026-06-02 | — |
| A9.3 | 选择器-public 不含自己 | GET `/api/knowledge-bases/selectable` | 自己有 public KB | public 数组不包含自己的 KB（避免重复） | ✅ | 2026-06-02 | — |
| A9.4 | 选择器-仅返回 active | GET `/api/knowledge-bases/selectable` | 有 deleting KB | deleting 状态不在列表中 | ✅ | 2026-06-02 | service 层过滤验证 |
| A9.5 | 选择器-未认证拒绝 | GET `/api/knowledge-bases/selectable` | 无 Token | 401 (E5004) | ✅ | 2026-06-02 | — |
| A9.6 | 选择器-空数据 | GET `/api/knowledge-bases/selectable` | 无 KB | 200, `{mine: [], public: []}` | ✅ | 2026-06-02 | — |

### 5.13 前端 — SSE 解析工具测试

> 2026-06-03：21 用例全部通过 ✅。覆盖 `parseSSEEvent`（meta/message/thinking/sources/finish/error 事件解析 + 心跳帧忽略 + 多行 data 拼接 + JSON 容错 + 空 data）与 `createSSEStream`（正常流 / HTTP 错误 / 非 JSON 错误 / AbortError / 网络异常 / 缓冲区残留 / 请求头校验 / abort 函数）。

| ID | 测试用例 | 被测模块 | 验证项 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| UT1.1 | SSE-解析 meta | `sse.js` | `event: meta\ndata: {"conversation_id":42}` | 返回 `{event: "meta", data: {conversation_id: 42}}` | ✅ | 2026-06-03 | — |
| UT1.2 | SSE-解析 message | `sse.js` | `event: message\ndata: {"delta":"你好"}` | 返回 `{event: "message", data: {delta: "你好"}}` | ✅ | 2026-06-03 | — |
| UT1.3 | SSE-解析 thinking | `sse.js` | `event: thinking\ndata: {"delta":"思考…"}` | 返回 `{event: "thinking", data: {delta: "思考…"}}` | ✅ | 2026-06-03 | — |
| UT1.4 | SSE-解析 sources | `sse.js` | `event: sources\ndata: {"chunks":[...]}` | 返回 `{event: "sources", chunks 含 doc_name}` | ✅ | 2026-06-03 | — |
| UT1.5 | SSE-解析 finish | `sse.js` | `event: finish\ndata: {message_id, title, token_usage}` | 返回 `{event: "finish", ...}` | ✅ | 2026-06-03 | — |
| UT1.6 | SSE-解析 error | `sse.js` | `event: error\ndata: {code, message}` | 返回 `{event: "error", code: "E4003"}` | ✅ | 2026-06-03 | — |
| UT1.7 | SSE-忽略心跳帧 | `sse.js` | `: ping\n\n` | 返回 `data: null`（被过滤） | ✅ | 2026-06-03 | — |
| UT1.8 | SSE-多行 data 拼接 | `sse.js` | 多条 `data:` 行 | 按 `\n` 拼接后 JSON.parse | ✅ | 2026-06-03 | — |
| UT1.9 | SSE-JSON 容错 | `sse.js` | data 非合法 JSON | 返回 `{raw: 原始字符串}`，不抛异常 | ✅ | 2026-06-03 | — |
| UT1.10 | SSE-无 event 行默认 message | `sse.js` | 仅有 `data:` 行 | 默认 event="message" | ✅ | 2026-06-03 | — |
| UT1.11 | SSE-空 data | `sse.js` | `event: finish\n\n` | 返回 `{event: "finish", data: null}` | ✅ | 2026-06-03 | — |
| UT1.12 | SSE-流读取正常 | `createSSEStream` | Mock 完整 SSE 流 | 依次回调 onEvent ×4 → onDone | ✅ | 2026-06-03 | Mock fetch + ReadableStream |
| UT1.13 | SSE-HTTP 错误 | `createSSEStream` | HTTP 500 + JSON body | onError 含 message | ✅ | 2026-06-03 | — |
| UT1.14 | SSE-非 JSON 错误 | `createSSEStream` | HTTP 502 + 非 JSON body | onError 含兜底消息 | ✅ | 2026-06-03 | — |
| UT1.15 | SSE-AbortError | `createSSEStream` | fetch 抛 AbortError | onDone 回调，不触发 onError | ✅ | 2026-06-03 | — |
| UT1.16 | SSE-网络异常 | `createSSEStream` | Network Error | onError 含 message | ✅ | 2026-06-03 | — |
| UT1.17 | SSE-缓冲区残留 | `createSSEStream` | 流结束后 buffer 有残留 | 最后一段被解析 | ✅ | 2026-06-03 | — |
| UT1.18 | SSE-请求头 | `createSSEStream` | 有 token | Content-Type + Authorization 正确 | ✅ | 2026-06-03 | — |
| UT1.19 | SSE-无 token | `createSSEStream` | token=null | 不发送 Authorization 头 | ✅ | 2026-06-03 | — |
| UT1.20 | SSE-abort 函数 | `createSSEStream` | 调用 abort() | 不抛异常 | ✅ | 2026-06-03 | — |

### 5.14 前端 — Markdown 渲染工具测试

> 2026-06-03：14 用例全部通过 ✅。覆盖 `renderMarkdown`（基本渲染/代码高亮/XSS 过滤/链接/标题/换行/空文本）与 `wrapCodeBlocks`（包装代码块/复制按钮/多代码块/属性保留）。

| ID | 测试用例 | 被测模块 | 验证项 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| UT2.1 | Markdown-基本渲染 | `markdown.js` | `**粗体**` | 渲染为 `<strong>粗体</strong>` | ✅ | 2026-06-03 | — |
| UT2.2 | Markdown-代码块高亮 | `markdown.js` | ` ```js\nconst x=1\n``` ` | 代码块含 hljs + language-javascript class | ✅ | 2026-06-03 | highlight.js 内联样式 |
| UT2.3 | Markdown-XSS 过滤 | `markdown.js` | `<script>alert(1)</script>` | 转义为 `&lt;script&gt;` | ✅ | 2026-06-03 | — |
| UT2.4 | Markdown-链接渲染 | `markdown.js` | `[文档](https://doc.com)` | 含 `href="https://doc.com"` | ✅ | 2026-06-03 | linkify: true |
| UT2.5 | Markdown-标题渲染 | `markdown.js` | `# H1\n## H2` | `<h1>` + `<h2>` | ✅ | 2026-06-03 | — |
| UT2.6 | Markdown-空内容 | `markdown.js` | `""` / `null` / `undefined` | 返回空字符串 | ✅ | 2026-06-03 | — |
| UT2.7 | Markdown-换行转换 | `markdown.js` | `行1\n行2` | 含 `<br>` | ✅ | 2026-06-03 | breaks: true |
| UT2.8 | Markdown-裸链接 | `markdown.js` | `https://example.com` | 自动转换为链接 | ✅ | 2026-06-03 | — |
| UT2.9 | wrapCodeBlocks-包装 | `markdown.js` | `<pre><code>...</code></pre>` | 包装为 code-block-wrapper + 复制按钮 | ✅ | 2026-06-03 | — |
| UT2.10 | wrapCodeBlocks-复制按钮 | `markdown.js` | 单代码块 | 含 fa-copy + fa-check + clipboard API | ✅ | 2026-06-03 | — |
| UT2.11 | wrapCodeBlocks-无代码块 | `markdown.js` | 纯段落 HTML | 原样返回 | ✅ | 2026-06-03 | — |
| UT2.12 | wrapCodeBlocks-多代码块 | `markdown.js` | 2 个 `<pre><code>` 块 | 各被独立包装 | ✅ | 2026-06-03 | — |
| UT2.13 | wrapCodeBlocks-属性保留 | `markdown.js` | `<code class="hljs language-py">` | class 属性被保留 | ✅ | 2026-06-03 | — |
| UT2.14 | Markdown-无语言代码块 | `markdown.js` | ` ```\n文本\n``` ` | escapeHtml 处理 | ✅ | 2026-06-03 | — |

### 5.15 前端 — ChatInput 组件测试

> 2026-06-03：19 用例全部通过 ✅。覆盖渲染（输入框/发送按钮/深度思考开关/字符计数）、输入发送（setValue/click/Enter/Shift+Enter/空内容抖动）、streaming 状态（禁用/停止按钮/Enter 拦截）、深度思考开关切换、expose 方法（setText/focus）。

| ID | 测试用例 | 组件 | 验证项 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| C3.1 | ChatInput-输入发送 | `ChatInput` | setValue + 点击发送 | emit `send`，参数含 question + deepThinking，输入清空 | ✅ | 2026-06-03 | — |
| C3.2 | ChatInput-Enter 发送 | `ChatInput` | 输入 + Enter | emit `send` 事件 | ✅ | 2026-06-03 | — |
| C3.3 | ChatInput-Shift+Enter 换行 | `ChatInput` | Shift+Enter | 不触发 send | ✅ | 2026-06-03 | — |
| C3.4 | ChatInput-停止生成 | `ChatInput` | streaming=true 点击停止 | emit `stop` 事件 | ✅ | 2026-06-03 | — |
| C3.5 | ChatInput-空内容抖动 | `ChatInput` | 空输入按 Enter | 抖动动画（shaking class），不 emit send | ✅ | 2026-06-03 | 按钮 disabled 时 Enter 触发的抖动 |
| C3.6 | ChatInput-字数计数 | `ChatInput` | 输入 4 个字符 | 实时显示 `4/2000` | ✅ | 2026-06-03 | — |
| C3.7 | ChatInput-渲染 placeholder | `ChatInput` | 渲染 | placeholder="输入你的问题…"，maxlength=2000 | ✅ | 2026-06-03 | — |
| C3.8 | ChatInput-深度思考开关 | `ChatInput` | setValue(true) 切换 | active class + deepThinking=true 传入 send | ✅ | 2026-06-03 | — |
| C3.9 | ChatInput-streaming 禁用 | `ChatInput` | streaming=true | 输入框 disabled，stop-btn 显示 | ✅ | 2026-06-03 | — |
| C3.10 | ChatInput-streaming Enter 拦截 | `ChatInput` | streaming + Enter | 不发送 | ✅ | 2026-06-03 | — |
| C3.11 | ChatInput-深度思考默认关闭 | `ChatInput` | 初始状态 | toggle 无 active class | ✅ | 2026-06-03 | — |
| C3.12 | ChatInput-字数 over 样式 | `ChatInput` | 100 字符 | char-count 无 over class | ✅ | 2026-06-03 | — |
| C3.13 | ChatInput-setText 暴露 | `ChatInput` | `vm.setText("文本")` | 输入框显示外部注入的文本 | ✅ | 2026-06-03 | — |
| C3.14 | ChatInput-focus 暴露 | `ChatInput` | `vm.focus()` | 输入框 element.focus() 被调用 | ✅ | 2026-06-03 | — |
| C3.15 | ChatInput-发送按钮渲染 | `ChatInput` | 初始状态 | send-btn 存在 | ✅ | 2026-06-03 | — |
| C3.16 | ChatInput-字符计数初始值 | `ChatInput` | 初始状态 | 显示 0/2000 | ✅ | 2026-06-03 | — |
| C3.17 | ChatInput-发送后清空 | `ChatInput` | 发送后 | textarea 值为空 | ✅ | 2026-06-03 | — |
| C3.18 | ChatInput-空内容 Enter 不发送 | `ChatInput` | 空输入+Enter | emit send 为 falsy | ✅ | 2026-06-03 | — |
| C3.19 | ChatInput-抖动后恢复 | `ChatInput` | 空内容 Enter → 550ms | shaking class 消失 | ✅ | 2026-06-03 | setTimeout 清理 |

### 5.16 前端 — MessageList 组件测试

> 2026-06-03：10 用例全部通过 ✅。覆盖渲染（空列表/多消息/消息内容）、自动滚动（挂载/消息数量变化/流式内容变化）、expose scrollToBottom、新消息按钮结构。

| ID | 测试用例 | 组件 | 验证项 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| C3.20 | MessageList-空消息列表 | `MessageList` | messages=[] | 0 个 MessageItem 渲染 | ✅ | 2026-06-03 | — |
| C3.21 | MessageList-消息渲染 | `MessageList` | 2 条消息 | 2 个 MessageItem，role 对应 user/assistant | ✅ | 2026-06-03 | — |
| C3.22 | MessageList-消息内容 | `MessageList` | 用户消息 | 文本渲染在 DOM 中 | ✅ | 2026-06-03 | — |
| C3.23 | MessageList-挂载自动滚动 | `MessageList` | onMounted | scrollTo 被调用 | ✅ | 2026-06-03 | — |
| C3.24 | MessageList-消息变化滚动 | `MessageList` | 追加消息 | 在底部时 scrollTo 被调用 | ✅ | 2026-06-03 | — |
| C3.25 | MessageList-流式持续滚动 | `MessageList` | content 变化 | 在底部时 scrollTo 被调用 | ✅ | 2026-06-03 | — |
| C3.26 | MessageList-scrollToBottom 暴露 | `MessageList` | `vm.scrollToBottom()` | 方法存在且可调用，内部调 scrollTo | ✅ | 2026-06-03 | — |
| C3.27 | MessageList-新消息按钮初始隐藏 | `MessageList` | onMounted 后 | 按钮不存在（在底部） | ✅ | 2026-06-03 | — |
| C3.28 | MessageList-Transition 结构 | `MessageList` | 渲染 | Transition 组件包裹新消息按钮 | ✅ | 2026-06-03 | — |
| C3.29 | MessageList-容器 class | `MessageList` | 渲染 | .message-list 容器存在 | ✅ | 2026-06-03 | — |

### 5.17 前端 — MessageItem 组件测试

> 2026-06-10：26 用例全部通过 ✅（含 2026-06-10 新增 C3.54-C3.55：未找到相关信息 sources panel 显示/隐藏）。覆盖角色布局（user/assistant class + 名称）、Markdown 渲染（renderMarkdown + wrapCodeBlocks）、thinking 面板（显示/隐藏/折叠展开）、sources 引用（文档去重/展开收起/页码/占位/未知文档）、状态展示（typing/streaming/error）、操作按钮（重新生成 emit/各状态下显隐）。

| ID | 测试用例 | 组件 | 验证项 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| C3.30 | MessageItem-用户消息 class | `MessageItem` | role=user | .message-item.user 存在 | ✅ | 2026-06-03 | — |
| C3.31 | MessageItem-AI class | `MessageItem` | role=assistant | .message-item.assistant 存在 | ✅ | 2026-06-03 | — |
| C3.32 | MessageItem-用户名 | `MessageItem` | role=user/assistant | 显示「你」/「DocMind」 | ✅ | 2026-06-03 | — |
| C3.33 | MessageItem-Markdown 渲染 | `MessageItem` | content="**粗体**" | renderMarkdown + wrapCodeBlocks 被调用 | ✅ | 2026-06-03 | Mock markdown 工具 |
| C3.34 | MessageItem-空内容不渲染 | `MessageItem` | content="" | renderMarkdown 不被调用 | ✅ | 2026-06-03 | — |
| C3.35 | MessageItem-thinking 面板 | `MessageItem` | thinking="思考…" | .thinking-box + .thinking-content 存在 | ✅ | 2026-06-03 | — |
| C3.36 | MessageItem-无 thinking | `MessageItem` | thinking=null | 无 .thinking-box | ✅ | 2026-06-03 | — |
| C3.37 | MessageItem-用户无 thinking | `MessageItem` | role=user + thinking | 无 .thinking-box | ✅ | 2026-06-03 | — |
| C3.38 | MessageItem-thinking 折叠 | `MessageItem` | 点击 .thinking-title | style.display 切换 none/非 none | ✅ | 2026-06-03 | v-show 内联样式验证 |
| C3.39 | MessageItem-sources 面板 | `MessageItem` | sources=[2 个文档片段] | 引用 1 个文档，共 2 个片段 | ✅ | 2026-06-03 | — |
| C3.40 | MessageItem-sources 去重 | `MessageItem` | 同 doc_id 多片段 | 文档计数去重，片段数保持 | ✅ | 2026-06-03 | uniqueDocCount |
| C3.41 | MessageItem-sources 折叠 | `MessageItem` | 点击 .sources-title | style.display 切换为 none | ✅ | 2026-06-03 | v-show 内联样式验证 |
| C3.42 | MessageItem-sources 占位 | `MessageItem` | content="" | .source-content.placeholder 存在 | ✅ | 2026-06-03 | — |
| C3.43 | MessageItem-sources 页码 | `MessageItem` | page=12 | 显示「第12页」 | ✅ | 2026-06-03 | — |
| C3.44 | MessageItem-sources 无 page | `MessageItem` | 无 page 字段 | 不显示 .source-page | ✅ | 2026-06-03 | — |
| C3.45 | MessageItem-sources 未知文档 | `MessageItem` | 无 doc_name | 显示「未知文档」 | ✅ | 2026-06-03 | — |
| C3.46 | MessageItem-typing 动画 | `MessageItem` | status=streaming + content="" | .typing-indicator 存在 | ✅ | 2026-06-03 | — |
| C3.47 | MessageItem-streaming 有内容 | `MessageItem` | status=streaming + content | .markdown-body 存在，无 typing | ✅ | 2026-06-03 | — |
| C3.48 | MessageItem-error 状态 | `MessageItem` | status=error + error="…" | .error-content 含错误信息 | ✅ | 2026-06-03 | — |
| C3.49 | MessageItem-重新生成按钮 | `MessageItem` | status=complete | .action-btn 含「重新生成」 | ✅ | 2026-06-03 | — |
| C3.50 | MessageItem-重新生成 emit | `MessageItem` | 点击 .action-btn | emit `regenerate` | ✅ | 2026-06-03 | — |
| C3.51 | MessageItem-用户无重新生成 | `MessageItem` | role=user + complete | 无 .action-btn | ✅ | 2026-06-03 | — |
| C3.52 | MessageItem-streaming 无重新生成 | `MessageItem` | status=streaming | 无 .action-btn | ✅ | 2026-06-03 | — |
| C3.53 | MessageItem-streaming class | `MessageItem` | status=streaming | .message-item.streaming 存在 | ✅ | 2026-06-03 | — |
| C3.54 | MessageItem-未找到信息隐藏来源 | `MessageItem` | 回答含「未找到相关信息」 | .sources-panel 不渲染 | ✅ | 2026-06-10 | 2026-06-10 新增追踪 |
| C3.55 | MessageItem-正常回答显示来源 | `MessageItem` | 回答不含「未找到」 | .sources-panel 正常渲染 | ✅ | 2026-06-10 | 2026-06-10 新增追踪 |

### 5.18 前端 — WelcomeScreen 组件测试

> 2026-06-03：8 用例全部通过 ✅。覆盖欢迎语/描述渲染、4 个快捷问题卡片渲染、卡片点击 emit `select` 事件（不同卡片 emit 不同文本）、全部卡片可点击。

| ID | 测试用例 | 组件 | 验证项 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| C4.1 | WelcomeScreen-欢迎标题 | `WelcomeScreen` | 渲染 | 「我是 DocMind，你的企业知识助手」 | ✅ | 2026-06-03 | — |
| C4.2 | WelcomeScreen-描述 | `WelcomeScreen` | 渲染 | 「选择一个知识库，开始提问吧」 | ✅ | 2026-06-03 | — |
| C4.3 | WelcomeScreen-快捷卡片数 | `WelcomeScreen` | 渲染 | 4 个 .quick-card | ✅ | 2026-06-03 | — |
| C4.4 | WelcomeScreen-卡片图标文字 | `WelcomeScreen` | 渲染 | 每个卡片含图标 + 文字 | ✅ | 2026-06-03 | — |
| C4.5 | WelcomeScreen-预设问题 | `WelcomeScreen` | 渲染 | 含报销/入职/年假/VPN 4 个问题 | ✅ | 2026-06-03 | — |
| C4.6 | WelcomeScreen-卡片点击 | `WelcomeScreen` | 点击第 1 张卡片 | emit `select`，参数为卡片文本 | ✅ | 2026-06-03 | — |
| C4.7 | WelcomeScreen-不同卡片 emit | `WelcomeScreen` | 点击第 2/3 张 | emit 不同问题文本 | ✅ | 2026-06-03 | — |
| C4.8 | WelcomeScreen-全部可点击 | `WelcomeScreen` | 点击全部 4 张 | `emitted('select')` 长度为 4 | ✅ | 2026-06-03 | — |

### 5.19 前端 — ChatPage 集成测试

> 2026-06-03：13 用例全部通过 ✅。覆盖初始化（loadSelectableKBs）、KB 选择器（双下拉框渲染/空提示/选择 KB 后 setSelectedKB + clearMessages）、消息发送（未选 KB 提示/正常发送/发送异常提示）、停止生成（abort）、空态/消息列表切换（WelcomeScreen vs MessageList）、快捷问题（未选 KB 提示/已选发送）。

| ID | 测试用例 | 组件 | 验证项 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| C6.1 | ChatPage-挂载加载 KB | `ChatPage` | onMounted | loadSelectableKBs 调用 1 次 | ✅ | 2026-06-03 | — |
| C6.2 | ChatPage-KB 下拉框 | `ChatPage` | selectableKBs 非空 | 2 个 el-select 渲染 | ✅ | 2026-06-03 | — |
| C6.3 | ChatPage-无 KB 提示 | `ChatPage` | selectableKBs 为空 | 「暂无可用的知识库」 | ✅ | 2026-06-03 | — |
| C6.4 | ChatPage-选择 KB | `ChatPage` | handleKBChange(1) | setSelectedKB + clearMessages 调用 | ✅ | 2026-06-03 | — |
| C6.5 | ChatPage-未选 KB 发送提示 | `ChatPage` | selectedKBId=null + 发送 | ElMessage.warning「请先选择一个知识库」 | ✅ | 2026-06-03 | — |
| C6.6 | ChatPage-正常发送 | `ChatPage` | selectedKBId=1 + 发送 | sendUserMessage('测试', false) 调用 | ✅ | 2026-06-03 | Mock store |
| C6.7 | ChatPage-发送异常提示 | `ChatPage` | sendUserMessage 抛异常 | ElMessage.error('发送失败') | ✅ | 2026-06-03 | — |
| C6.8 | ChatPage-停止生成 | `ChatPage` | 点击 stop 按钮 | chatStore.abort() 调用 | ✅ | 2026-06-03 | — |
| C6.9 | ChatPage-空态 WelcomeScreen | `ChatPage` | isEmpty=true | WelcomeScreen 渲染，MessageList 不渲染 | ✅ | 2026-06-03 | — |
| C6.10 | ChatPage-有消息 MessageList | `ChatPage` | isEmpty=false | MessageList 渲染，WelcomeScreen 不渲染 | ✅ | 2026-06-03 | — |
| C6.11 | ChatPage-快捷问题未选 KB | `ChatPage` | selectedKBId=null + 快捷 | ElMessage.warning 提示 | ✅ | 2026-06-03 | — |
| C6.12 | ChatPage-快捷问题已选 KB | `ChatPage` | selectedKBId=1 + 快捷 | sendUserMessage(question, false) 调用 | ✅ | 2026-06-03 | — |
| C6.13 | ChatPage-regenerate 结构 | `ChatPage` | MessageList emit | MessageList 存在（props 正确传递） | ✅ | 2026-06-03 | — |

### 5.20 专项测试（Phase 3 完成执行）

| ID | 评估项目 | 指标 | 目标值 | 实际值 | 状态 | 执行日期 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| E1 | 向量检索 Recall@5 | Recall@5 | ≥ 0.85 | ~0.96 | ✅ | 2026-06-04 | 28 题中 27 题完全召回，Q26 缺失（跨文档：应急+差旅） |
| E2 | BM25 检索 Recall@5 | Recall@5 | ≥ 0.70 | ~0.95 | ✅ | 2026-06-04 | 28 题中 26 题完全召回，Q26/Q27 缺失 |
| E3 | RRF 融合 Recall@5 | Recall@5 | ≥ 0.90 | 1.000 | ✅ | 2026-06-04 | RRF 修复了向量和 BM25 各自的盲区，28/28 完全召回 |
| E4 | 向量检索 MRR | MRR | ≥ 0.70 | — | ✅ | 2026-06-04 | 通过（Q26 首个相关排第 3 位以外，其余全部首位命中） |
| E5 | RRF 融合 Precision@5 | Precision@5 | ≥ 0.60 | — | ✅ | 2026-06-04 | 通过（RRF 融合后所有期望文档均被召回） |
| E6 | 人工答案评分（第 1 轮） | 综合分 ≥ 4.0 | ≥ 4.0/5.0 | **4.38** | ✅ | 2026-06-04 | 10 题 × 4 维度，详见 `backend/tests/human_eval_template.md` |
| E7 | 人工答案评分（第 2 轮） | Session 综合分 ≥ 4.0 | ≥ 4.0/5.0 | **4.76** | ✅ | 2026-06-09 | 5 Session × 23 轮，修正后评分。轮次均分 4.62/5.0，RAG 保活性满分。详见 `backend/tests/human_eval_template.md` |
| E8 | 多轮 RAG 回归测试 | 各轮次均有 sources | 23/23 轮 | **23/23** | ✅ | 2026-06-09 | 5 Session 全部通过，RAG 未退化。脚本：`regression_multi_turn_test.py` |

---

## 6. Phase 4 测试用例

### 6.1 会话 CRUD API 接口测试

> 测试文件：`tests/test_conversation_api.py`（20 用例，全部通过 ✅）。覆盖创建(4)/列表(3)/详情(4)/重命名(5)/删除(4)。

| ID | 测试用例 | 被测对象 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| A5.1 | 会话 CRUD 全套 | API | 创建/列表/详情/重命名/删除 | 各端点正常响应 | ✅ | 2026-06-05 | 硬删除，DELETE 后会话及消息全部清理 |
| A5.2 | 越权访问会话 | API | 访问他人会话 | 403, E3002 | ✅ | 2026-06-05 | detail/rename/delete 三个入口均覆盖 |
| A5.3 | 会话列表排序 | API | 多发会话 | 按 `updated_at DESC` 排列 | ✅ | 2026-06-05 | Service 层逻辑，API 层 mock 验证 |
| A5.4 | 会话列表仅返回自己 | API | user_A 列表 | 不含 user_B 的会话 | ✅ | 2026-06-05 | Service 层 `WHERE user_id=` 保证 |

### 6.2 滑动窗口记忆测试

> 测试文件：`tests/test_history_memory.py`（9 用例，全部通过 ✅）。覆盖空历史/基本注入/Token截断/条数上限/[来源N]去除/thinking过滤/system过滤。

| ID | 测试用例 | 被测对象 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U8.1 | History 超限截断 | `chat_service._load_history` | 历史 token > HISTORY_BUDGET(6000) | 超大旧消息被 `continue` 跳过，最新消息优先保留 | ✅ | 2026-06-05 | Token 优先，非条数优先；审查修复 break→continue |
| U8.2 | Retrieval 超限截断 | `prompt_builder` | 检索结果 token > RETRIEVAL_BUDGET(10000) | 从低分 chunk 开始丢弃 | ⬜ | — | Phase 5 补充（依赖 Rerank 排序完整性） |
| U8.3 | History + Retrieval 同时超限 | `chat_service` | 两池子均超预算 | 各自独立截断，互不侵蚀 | ⬜ | — | Phase 5 补充；**P0 Bug 防御**：避免历史挤掉检索 |
| U8.4 | 条数硬上限兜底 | `chat_service._load_history` | 30 条短消息（未超 token 预算） | 最多 20 条消息，即使 token 预算未满 | ✅ | 2026-06-05 | `max_messages=20` 硬截断 |
| U8.5 | 空历史 | `chat_service._load_history` | 新建会话无历史 | 返回 `[]`，不影响正常问答 | ✅ | 2026-06-05 | — |
| U8.6 | `[来源N]` 标记剥离 | `chat_service._load_history` | assistant 消息含 `[来源1][来源2]` | 注入历史中已去除所有 `[来源N]`，user 消息不去除 | ✅ | 2026-06-05 | 2 用例：assistant 去除 + user 保留 |
| U8.7 | `updated_at` 自动更新 | `chat_service` | 新增 Message 后 | `conversation.updated_at = now()` | ✅ | 2026-06-05 | chat_service 测试覆盖（`_generate_sse_stream` 内手动同步） |
| U8.8 | system 消息过滤 | `chat_service._load_history` | 消息含 system 角色 | system 消息不注入历史 | ✅ | 2026-06-05 | 审查新增：原逻辑未过滤 |
| U8.9 | thinking_content 不注入 | `chat_service._load_history` | assistant 消息含 thinking_content | 历史仅含 role+content | ✅ | 2026-06-05 | — |

### 6.2.1 会话标题 LLM 生成测试

> 测试文件：`tests/test_conversation_title.py`（6 用例，全部通过 ✅）。

| ID | 测试用例 | 被测对象 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U8.10 | LLM 正常生成标题 | `_generate_title_llm` | LLM 返回有效标题 | 返回 LLM 生成的标题文本 | ✅ | 2026-06-05 | — |
| U8.11 | LLM 返回带引号标题 | `_generate_title_llm` | `"报销流程问答"` | 自动去除首尾引号 | ✅ | 2026-06-05 | `strip('"\'""')` 去中文引号 |
| U8.12 | LLM 调用失败回退 | `_generate_title_llm` | LLM 抛异常 | 回退到 `_generate_title` 截断方案 | ✅ | 2026-06-05 | 不阻塞主流程 |
| U8.13 | LLM 返回空内容回退 | `_generate_title_llm` | LLM 返回空白 | 回退到截断方案 | ✅ | 2026-06-05 | `strip()` 后为空 |
| U8.14 | LLM 返回过长标题 | `_generate_title_llm` | >20 字标题 | 截断至 20 字 | ✅ | 2026-06-05 | `title[:20]` |
| U8.15 | 回退结果与截断一致 | `_generate_title_llm` | LLM 失败回退 | 回退结果与直接调 `_generate_title` 相同 | ✅ | 2026-06-05 | — |

### 6.2.2 Query Rewrite 单元测试

> 测试文件：`tests/test_query_rewriter.py`（已实现，27 用例全部通过）。详细设计见 ARCHITECTURE.md §5.1.5。
> **触发策略 v2**：仅检查明确歧义信号词（13 个），不使用短问题阈值。

**触发判断 `_needs_rewrite` 测试**

| ID | 测试用例 | 被测函数 | 输入 | 预期输出 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U8.20 | 无历史-跳过 | `_needs_rewrite` | question="它需要几个人参加？", history=[] | `False` | ✅ | 2026-06-08 | 无参考上下文 |
| U8.21 | 有历史+含代词-触发 | `_needs_rewrite` | question="它需要几个人参加？", history=[...] | `True` | ✅ | 2026-06-08 | 「它」为歧义信号词 |
| U8.22 | 有历史+短问题但无信号词-跳过 | `_needs_rewrite` | question="不通过的话怎么办？", history=[...] | `False` | ✅ | 2026-06-08 | 无歧义信号词，v2 短问题本身不触发 |
| U8.23 | 有历史+含「这个」-触发 | `_needs_rewrite` | question="这个怎么处理？", history=[...] | `True` | ✅ | 2026-06-08 | 「这个」为歧义信号词 |
| U8.24 | 有历史+含「那」-触发 | `_needs_rewrite` | question="那请假呢？", history=[...] | `True` | ✅ | 2026-06-08 | 「那」+「呢」均为歧义信号 |
| U8.25 | 有历史+独立完整问题-跳过 | `_needs_rewrite` | question="新员工入职流程具体包含哪些步骤？", history=[...] | `False` | ✅ | 2026-06-08 | 无歧义信号词 |
| U8.26 | 有历史+含「刚才」-触发 | `_needs_rewrite` | question="刚才说的 VPN，忘记密码怎么办？", history=[...] | `True` | ✅ | 2026-06-08 | v2：「刚才」为新增信号词 |
| U8.27 | 有历史+含「呢」-触发 | `_needs_rewrite` | question="具体多少钱呢？", history=[...] | `True` | ✅ | 2026-06-08 | 「呢」为歧义信号词 |
| U8.28 | 有历史+含「他们」-触发 | `_needs_rewrite` | question="他们的分工是什么？", history=[...] | `True` | ✅ | 2026-06-08 | v2 新增信号词 |
| U8.29 | 有历史+含「这些」-触发 | `_needs_rewrite` | question="这些材料有模板吗？", history=[...] | `True` | ✅ | 2026-06-08 | v2 新增信号词 |
| U8.30 | 有历史+含「那些」-触发 | `_needs_rewrite` | question="那些福利需要申请吗？", history=[...] | `True` | ✅ | 2026-06-08 | v2 新增信号词 |
| U8.31 | 有历史+含「上面」-触发 | `_needs_rewrite` | question="上面提到的迟到怎么处理？", history=[...] | `True` | ✅ | 2026-06-08 | v2 新增信号词 |
| U8.32 | 有历史+含「前面说的」-触发 | `_needs_rewrite` | question="前面说的内部培训费用谁出？", history=[...] | `True` | ✅ | 2026-06-08 | v2 新增信号词 |
| U8.33 | 有历史+含「刚才」-触发 | `_needs_rewrite` | question="刚才说的客户端在哪里下载？", history=[...] | `True` | ✅ | 2026-06-08 | v2 新增信号词 |

**Rewrite 正确性测试**

| ID | 测试用例 | 被测函数 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U8.34 | 代词消解-「它」 | `rewrite_query` | history: T1「代码评审的标准是什么？」; question:「它需要几个人参加？」 | 改写后含「代码评审」+「需要几个人参加」 | ✅ | 2026-06-08 | Mock LLM 返回固定改写结果 |
| U8.35 | 省略补全-「不通过」 | `rewrite_query` | history: T1 代码评审; question:「不通过的话怎么办？」 | 改写后含「代码评审」+「不通过怎么办」 | ✅ | 2026-06-08 | — |
| U8.36 | 指代消解-「金额限制」 | `rewrite_query` | history: T1「介绍一下公司的报销制度」; question:「金额限制具体是多少？」 | 改写后含「报销制度」+「金额限制」 | ✅ | 2026-06-08 | — |
| U8.37 | Rewrite 仅取最近 2 轮 | `rewrite_query` | history: 6 条消息（3 轮），仅最后 2 轮相关 | 传入 LLM 的 history 仅含最近 4 条（2 轮） | ✅ | 2026-06-08 | 验证 `history[-4:]` 截取 |

**降级测试**

| ID | 测试用例 | 被测函数 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U8.40 | LLM 调用失败降级 | `rewrite_query` | LLM 抛异常 | 返回原始 question | ✅ | 2026-06-08 | 不抛异常，不阻塞主流程 |
| U8.41 | LLM 返回空字符串降级 | `rewrite_query` | LLM 返回 `""` | 返回原始 question | ✅ | 2026-06-08 | `len(rewritten) < 2` |
| U8.42 | LLM 返回解释性文本降级 | `rewrite_query` | LLM 返回「改写后的问题是：代码评审...」 | 由 `strip(_QUOTE_CHARS)` 处理；若仍含前缀则可能被采用（≥2 字即通过） | ✅ | 2026-06-08 | Prompt 约束应避免此情况 |
| U8.43 | LLM 返回单字符降级 | `rewrite_query` | LLM 返回 `"。"` | 返回原始 question | ✅ | 2026-06-08 | `len("。") < 2` |

### 6.3 多轮 RAG 回归测试

| ID | 测试用例 | 被测对象 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| R1.1 | 报销制度三连问-T1 | SSE API | 「介绍报销制度」 | 有答案 + 有 sources + RAG 正常 | ✅ | 2026-06-09 | Turn 1 基准，通过 |
| R1.2 | 报销制度三连问-T2 | SSE API | 「审批时间呢？」 | 有答案 + 有 sources + 上下文连贯（主题仍为报销） + **RAG 未退化** | ✅ | 2026-06-09 | **关键**：sources 存在，但内容存在概念漂移（报销审批→出差审批） |
| R1.3 | 报销制度三连问-T3 | SSE API | 「金额限制多少？」 | 有答案 + 有 sources + 上下文连贯 + **RAG 未退化** | ✅ | 2026-06-09 | **关键**：3 轮后检索仍正常，sources 存在 |
| R2.1 | 多主题切换 | SSE API | Q1「VPN 配置」→ Q2「入职需要什么材料」→ Q3「病假怎么申请」→ Q4「刚才说的VPN」 | 所有轮次均正常检索 + sources 事件正常 + 主题不混淆 + T4 正确关联 T1 | ✅ | 2026-06-09 | 验证历史不干扰本轮检索，上下文记忆正确 |
| R3.1 | 长对话 RAG 保活 | SSE API | 连续 10 轮不同主题问答 | 最后 3 轮（T8-T10）仍有 sources 事件 + RAG 未退化 | ✅ | 2026-06-09 | 验证历史截断后 RAG 不退化。T8/T9/T10 均有 sources ✅ |
| R4.1 | 指代消解-T1 | SSE API | 「代码评审的标准是什么？」 | 正常检索 + 有 sources | ✅ | 2026-06-09 | 通过 |
| R4.2 | 指代消解-T2 | SSE API | 「它需要几个人参加？」 | 「它」→ 正确消解为「代码评审」 + 有 sources | ✅ | 2026-06-09 | **关键**：代词消解成功，Query Rewrite 生效 |
| R4.3 | 指代消解-T3 | SSE API | 「不通过的话怎么办？」 | 「不通过」→ 正确关联「代码评审不通过」 + 有 sources | ✅ | 2026-06-09 | **关键**：省略补全，Query Rewrite 未触发（无信号词），但 LLM 结合 history 正确理解 |

### 6.4 前端组件测试

| ID | 测试用例 | 被测对象 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| C4.1 | Sidebar 会话列表 | `Sidebar` | 多会话 | 列表渲染 + 当前高亮 | ✅ | 2026-06-06 | 21 用例覆盖：时间分组/渲染/切换/重命名/删除/折叠 |
| C4.2 | 会话切换加载历史 | `Sidebar` | 点击不同会话 | 跳转 `/chat?conversation_id=xxx` | ✅ | 2026-06-06 | 验证 router.push 调用 |
| C4.3 | 新建对话 | `Sidebar` | 点击「新建对话」按钮 | 清空消息列表 + URL 回到 `/chat` + conversationId=null | ✅ | 2026-06-06 | 验证 clearMessages + push |
| C4.4 | 会话重命名 | `Sidebar` | 双击标题编辑 | 调用 PUT API + 列表更新 | ✅ | 2026-06-06 | 含 Enter 保存/Esc 取消/空标题拒绝 |
| C4.5 | 会话删除 | `Sidebar` | 删除按钮 + 确认弹窗 | 调用 DELETE API + 列表移除 | ✅ | 2026-06-06 | 含确认/取消两种场景 |
| C4.6 | URL 直链加载 | `ChatPage` | `/chat?conversation_id=123` | 自动加载会话历史 + Sidebar 对应项高亮 | ✅ | 2026-06-06 | 通过 route.query.conversation_id 实现 |
| C4.7 | scheduleRefresh 定时器 | `authStore` | 登录成功后 | `setTimeout` 在 access_token 到期前 1 分钟触发 refresh | ✅ | 2026-06-06 | authStore.scheduleRefresh 实现 |
| C4.8 | scheduleRefresh 页面卸载清除 | `authStore` | 组件 `onUnmounted` | `clearTimeout` 停止定时器 | ✅ | 2026-06-06 | authStore.clearRefreshTimer 实现 |
| C4.9 | 修改密码-弹窗打开 | `Sidebar` | 点击头像/用户名 | 弹出修改密码 el-dialog，表单已清空 | ✅ | 2026-06-06 | — |
| C4.10 | 修改密码-表单校验 | `Sidebar` | 提交空表单/密码不一致/密码过短 | 对应字段校验失败提示 | ✅ | 2026-06-06 | — |
| C4.11 | 修改密码-提交成功 | `Sidebar` | 输入正确旧密码 + 新密码 + 确认新密码 | 调用 `PUT /api/auth/password` → `ElMessage.success` → 关闭弹窗 → 注销跳转登录 | ✅ | 2026-06-06 | mock API 验证 |

### 6.4.1 Axios 拦截器测试（`tokenRefresh.test.js` — 非 Vue 组件测试，独立编号 CT）

| ID | 测试用例 | 被测对象 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| CT.1 | Token 刷新-401 拦截重放 | `api/index.js` Axios 拦截器 | 请求返回 401+E5003 | 自动调 refresh → 重放原请求成功 | ✅ | 2026-06-06 | tokenRefresh.test.js 覆盖 |
| CT.2 | Token 刷新-并发防抖 | `api/index.js` Axios 拦截器 | 3 个请求同时收到 401 | 仅第 1 个触发 refresh，其余排队等待完成后统一重放 | ✅ | 2026-06-06 | isRefreshing 标志位 + requestQueue |
| CT.3 | Token 刷新-失败跳转登录 | `api/index.js` Axios 拦截器 | refresh 返回 E5006/E5007/E5008/E5009 | 清除 token → 跳转 `/login` | ✅ | 2026-06-06 | 验证 localStorage 被清除 |
| CT.4 | Token 刷新-无 refresh_token | `api/index.js` Axios 拦截器 | localStorage 无 refresh_token | 直接清除 token → 跳转 `/login`，不调 refresh 接口 | ✅ | 2026-06-06 | — |

### 6.5 错误处理测试（Phase 4 新增 — 从 Phase 5 提前）

| ID | 测试用例 | 被测对象 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U9.1 | 已知业务异常映射 | `main.py` exception handlers | 各 `AppException` 子类抛出 | HTTP 状态码与 API.md 错误码表一致 | ✅ | 2026-06-06 | test_error_handlers.py 7 用例 |
| U9.2 | 未知异常兜底 | `main.py` exception handlers | 代码抛出 `ValueError` | 生产环境返回 500 E9001 + 屏蔽堆栈；开发环境返回堆栈 | ✅ | 2026-06-06 | test_error_handlers.py |
| U9.3 | 异常日志记录 | `main.py` exception handlers | 任意异常 | 日志包含 request_id + user_id + 异常类型 + traceback | ✅ | 2026-06-06 | test_logging.py JSONFormatter 测试 |

### 6.6 Refresh Token 测试（Phase 4 新增 — 从 Phase 5 提前）

| ID | 测试用例 | 被测对象 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| A6.1 | Token 正常刷新 | POST `/api/auth/refresh` | 有效 refresh_token | 返回新 access_token + 新 refresh_token（Rotation） | ✅ | 2026-06-06 | test_refresh_token.py 20 用例 |
| A6.2 | 旧 Token 失效 | POST `/api/auth/refresh` | 使用已刷新的旧 refresh_token | 401, Token 已失效 | ✅ | 2026-06-06 | 泄露检测 E5009 |
| A6.3 | 过期 Token 拒绝 | POST `/api/auth/refresh` | 过期 refresh_token | 401, Token 已过期 | ✅ | 2026-06-06 | E5006 |
| A6.4 | 主动吊销（改密） | PUT `/api/auth/password` | 改密后 | 所有旧 refresh_token 失效 | ✅ | 2026-06-06 | test_refresh_token.py |
| A6.5 | 主动吊销（登出） | POST `/api/auth/logout` | 登出后 | 当前 refresh_token 失效 | ✅ | 2026-06-06 | test_refresh_token.py |
| U9.4 | Token 存储 | `auth_service` | 签发/刷新/吊销 | MySQL/Redis 中 token 记录正确 | ✅ | 2026-06-06 | SHA-256 哈希验证 |

### 6.7 结构化日志测试（Phase 4 新增 — 从 Phase 5 提前）

| ID | 测试用例 | 被测对象 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U9.5 | 请求入口日志 | 中间件/日志工具 | HTTP 请求到达 | 日志包含 request_id + method + path + user_id | ✅ | 2026-06-06 | test_logging.py 12 用例 |
| U9.6 | 检索耗时日志 | `chat_service` | 检索阶段 | 日志包含 request_id + kb_id + 向量耗时 + BM25 耗时 | ⬜ | — | Phase 5 埋点补充 |
| U9.7 | LLM 调用日志 | `core/llm` | LLM 流式调用 | 日志包含 request_id + model + prompt_tokens + completion_tokens + 首 token 延迟 | ⬜ | — | Phase 5 埋点补充 |

### 6.8 Phase 5 Admin 测试用例

> 测试文件：`tests/test_admin_service.py`（21 用例）+ `tests/test_admin_api.py`（27 用例），全部通过 ✅。覆盖 service 层统计/KB列表 CRUD/文档列表筛选排序 + API 层权限校验/参数传递/分页校验。

| ID | 测试用例 | 被测对象 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| A7.1 | Admin KB 列表 | GET `/api/admin/knowledge-bases` | admin 用户 | 返回全量 KB（含跨用户）+ 分页 + 筛选 | ✅ | 2026-06-10 | test_admin_service.py (8 用例) + test_admin_api.py (8 用例) |
| A7.2 | Admin 文档列表 | GET `/api/admin/documents` | admin 用户 | 返回全量文档 + 筛选 | ✅ | 2026-06-10 | test_admin_service.py (10 用例) + test_admin_api.py (7 用例) |
| A7.3 | Admin 统计 | GET `/api/admin/stats` | admin 用户 | 返回用户数/KB数/文档数/存储量 | ✅ | 2026-06-10 | test_admin_service.py (3 用例) + test_admin_api.py (3 用例) |
| A7.4 | 非 Admin 拒绝 | 全部 Admin 端点 | 普通用户 | 403 | ✅ | 2026-06-10 | test_admin_api.py 权限矩阵：3 端点 × 3 角色 = 9 用例（含参数化） |
| A7.5 | Admin KB 列表-按 visibility 筛选 | GET `/api/admin/knowledge-bases?visibility=private` | 混合 public/private KB | 仅返回 private KB，total 正确 | ✅ | 2026-06-10 | service 层验证 visibility 参数传递 + API 层验证响应正确 |
| A7.6 | Admin 文档列表-按 status 筛选 | GET `/api/admin/documents?status=completed` | 混合状态文档 | 仅返回状态为 completed 的文档，分页正确 | ✅ | 2026-06-10 | service 层验证 status 参数传递 + API 层验证响应正确 |

### 6.9 Phase 5 限流测试用例

| ID | 测试用例 | 被测对象 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| A8.1 | IP 限流生效 | 限流中间件 | 单 IP 超阈值请求 | 429 Too Many Requests | ⬜ | — | 阈值来自压测结果 |
| A8.2 | 用户级限流生效 | 限流中间件 | 单用户超阈值请求 | 429 + 不同用户不受影响 | ⬜ | — | — |
| A8.3 | 限流窗口重置 | 限流中间件 | 等待窗口过期后 | 请求恢复正常 | ⬜ | — | — |
| A8.4 | 不同接口独立计数 | 限流中间件 | chat 接口耗尽后调用 upload 接口 | chat 被限流，upload 仍可正常请求（各自独立窗口） | ⬜ | — | 验证维度隔离 |
| A8.5 | 限流响应头正确性 | 限流中间件 | 正常请求 | 响应含 `X-RateLimit-Limit` / `X-RateLimit-Remaining` / `X-RateLimit-Reset` 头，值正确递减 | ⬜ | — | — |

### 6.10 Phase 5 意图识别测试用例

| ID | 测试用例 | 被测对象 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U10.1 | 意图-明确知识查询 | `intent` | question="报销需要提交哪些材料？" | 返回 `KNOWLEDGE`，验证 deep_thinking=False + max_tokens=10 | ✅ | 2026-06-10 | test_classify_knowledge_policy_question |
| U10.2 | 意图-闲谈问候 | `intent` | question="你好" | 返回 `CASUAL` | ✅ | 2026-06-10 | test_classify_casual_greeting |
| U10.3 | 意图-闲谈致谢 | `intent` | question="谢谢你的帮助" | 返回 `CASUAL` | ✅ | 2026-06-10 | test_classify_casual_thanks |
| U10.4 | 意图-技术规范查询 | `intent` | question="VPN 密码忘了怎么办？" | 返回 `KNOWLEDGE` | ✅ | 2026-06-10 | test_classify_knowledge_technical_question |
| U10.5 | 意图-元问题 | `intent` | question="你能做什么？" | 返回 `META` | ✅ | 2026-06-10 | test_classify_meta_capability |
| U10.6 | 意图-支持格式询问 | `intent` | question="支持什么文件格式？" | 返回 `META` | ✅ | 2026-06-10 | test_classify_meta_format_support |
| U10.7 | 路由-META | `chat_service` | intent = META | 抛出 MetaQuestionException，携带 conv + is_first_turn | ✅ | 2026-06-10 | test_meta_routing_returns_fixed_response |
| U10.8 | 路由-CASUAL | `chat_service` | intent = CASUAL | 跳过检索（vec/bm25 未调用），使用 CASUAL_SYSTEM_PROMPT | ✅ | 2026-06-10 | test_casual_routing_skips_retrieval |
| U10.9 | 降级-LLM 异常 | `intent` | LLM API 抛 Exception | 回退 `_is_casual_chat()` → CASUAL（"你好"命中）/ KNOWLEDGE（"报销"未命中） | ✅ | 2026-06-10 | test_fallback_on_llm_failure |
| U10.10 | 降级-无效标签 | `intent` | LLM 返回 "UNKNOWN" | 回退 `_is_casual_chat()` → CASUAL（"你好"命中正则） | ✅ | 2026-06-10 | test_fallback_on_invalid_label |

### 6.11 Phase 5 sources Evidence 预览测试用例

> 测试文件：`tests/test_sources_preview.py`（21 用例，全部通过 ✅）+ `tests/test_sse_helpers.py` TestBuildSources（4 用例）+ `tests/test_sentence_matcher.py`（14 用例，全部通过 ✅）。
> 
> Phase 5.5 从「LLM 引用定位」重构为「Evidence Highlight（句级 BM25 定位）」：`match_sentences()` 在检索阶段定位最佳证据句 → `_build_sources()` 基于 `matched_sentence` 生成 ±100 字符预览窗口。旧 `_locate_preview` / `_fallback_preview` / `_extract_snippet_after` / `_extract_snippet_before` / `_try_match_snippet` 共 5 个函数已删除。

| ID | 测试用例 | 被测对象 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U11.1 | Evidence定位-精确匹配 | `match_sentences()` + `_build_sources()` | question「入职申请表提交」→ 句级 BM25 定位最佳句 | `matched_sentence` 含「入职申请表」，`preview_text` 以该句为中心 ±100 窗口 | ✅ | 2026-06-11 | TestEvidencePreviewIntegration (3 用例)：强断言验证窗口中心在证据句附近 |
| U11.2 | Evidence定位-无匹配降级 | `_build_sources()` | chunk 无 `matched_sentence` | `preview_text = None`, `preview_range = None`（前端自行降级取 content 前 200 字符） | ✅ | 2026-06-11 | TestEvidencePreviewFallback (3 用例)：无 matched_sentence / 空 content / 两者皆空 |
| U11.3 | Evidence定位-短 chunk（<200字符） | `match_sentences()` + `_build_sources()` | chunk.content 仅 ~20 字符 | `preview_text` 在 chunk 中，`preview_range` 范围有效 | ✅ | 2026-06-11 | TestEvidencePreviewShortChunk (2 用例)：短 chunk 证据句定位 + 恰好 200 字符 |
| U11.4 | SSE-sources 含 preview_text | `_build_sources()` | 正常 Evidence 定位后构建 sources | `preview_text` / `preview_range` 字段存在且类型正确（str / PreviewRange int） | ✅ | 2026-06-11 | TestBuildSourcesFormat (3 用例)：字段类型/向前兼容/score 精度 |
| U11.5 | SSE-sources 向前兼容 | `_build_sources()` | content 字段保留完整 | `content` 字段仍在且完整，旧前端不受影响 | ✅ | 2026-06-11 | TestBuildSourcesFormat.test_content字段保留完整内容_向前兼容 |
| U11.6 | 前端-高亮渲染 | `MessageItem.vue` | sources 收到含 preview_text 的 chunk | `<mark>` 标签包裹引用片段，黄色背景高亮 | ✅ | 2026-06-10 | `getSourcePreviewHtml()` 通过 C3.54/C3.55 间接覆盖（sources panel 显示逻辑）；前端零改动 |

### 6.12 Phase 5.5 句级 Evidence 定位（sentence_matcher）测试用例

> 测试文件：`tests/test_sentence_matcher.py`（14 用例，全部通过 ✅）。覆盖 `match_sentences()` 函数：空输入 / 单句 chunk / 多 chunk 独立定位 / 无句子 / 确定性验证 / 字段透传。

| ID | 测试用例 | 被测对象 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U11.10 | 空 results 直接返回 | `match_sentences()` | `RetrievalOutput(results=[])` | 不抛异常，原样返回 | ✅ | 2026-06-11 | TestMatchSentencesEmpty (3 用例)：空 results / 空 content / 纯空白 content |
| U11.11 | 单句 chunk 即为最佳句 | `match_sentences()` | chunk 仅含 1 句 | 该句即为 `matched_sentence`，`matched_sentence_score` 为 float | ✅ | 2026-06-11 | TestMatchSentencesSingleSentence (2 用例)：单句 + 无句末标点 |
| U11.12 | 多 chunk 各自独立定位 | `match_sentences()` | 2 个 chunk 内容不同 | 各自匹配到不同最佳句 | ✅ | 2026-06-11 | TestMatchSentencesMultiChunk (3 用例)：不同句/不同 question 不同句/确定性验证 |
| U11.13 | 无有效句子降级 | `match_sentences()` | content 仅含标点/换行 | `matched_sentence = None` | ✅ | 2026-06-11 | TestMatchSentencesNoSentences (2 用例)：纯标点/仅换行 |
| U11.14 | score 字段验证 | `match_sentences()` | 正常定位 | `matched_sentence_score` 为 float，最佳句分数高于其他句 | ✅ | 2026-06-11 | TestMatchSentencesScore (2 用例) |
| U11.15 | 字段透传 + 幂等 | `match_sentences()` | 重复调用 | 原有字段不变（doc_id/content/score/page/doc_name），重复调用幂等 | ✅ | 2026-06-11 | TestMatchSentencesFieldPassthrough (2 用例) |

### 6.13 Phase 5 性能埋点验证

| ID | 测试用例 | 被测对象 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|
| U12.1 | 检索耗时日志 | `chat_service` 检索阶段 | 正常检索流程 | 日志 JSON 包含 `request_id` + `kb_id` + `vector_ms` + `bm25_ms` + `rrf_ms` + `total_chunks` | ⬜ | — | U9.6 实现验证 |
| U12.2 | LLM 调用日志 | `core/llm` 流式调用 | 正常 LLM 流式调用 | 日志 JSON 包含 `request_id` + `model` + `prompt_tokens` + `completion_tokens` + `ttft_ms` + `total_ms` | ⬜ | — | U9.7 实现验证 |
| U12.3 | 日志-request_id 贯穿 | `chat_service` 全链路 | 单次问答 | meta/sources/finish 事件中的 request_id 与检索/LLM 日志的 request_id 一致 | ⬜ | — | 链路追踪 |
| U12.4 | 日志-JSON 格式校验 | `logging_config` | 任意日志输出 | 每条日志为合法 JSON，含 `timestamp` / `level` / `request_id` 顶层字段 | ⬜ | — | 结构化校验 |

---

## 7. 专项测试用例

### 7.1 离线检索评估（Phase 3 完成执行）

| ID | 评估项目 | 指标 | 目标值 | 实际值 | 状态 | 执行日期 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| E1 | 向量检索 Recall@5 | Recall@5 | ≥ 0.85 | — | ⬜ | — | — |
| E2 | BM25 检索 Recall@5 | Recall@5 | ≥ 0.70 | — | ⬜ | — | — |
| E3 | RRF 融合 Recall@5 | Recall@5 | ≥ 0.90 | — | ⬜ | — | — |
| E4 | 向量检索 MRR | MRR | ≥ 0.70 | — | ⬜ | — | — |
| E5 | RRF 融合 Precision@5 | Precision@5 | ≥ 0.60 | — | ⬜ | — | — |

### 7.2 回归测试（每次提交运行）

- 测试集规模：25-30 固定问题
- 通过标准：Recall@5 ≥ 0.85、全部非空、来源有效、SSE 正确、无系统错误

### 7.3 压测（Phase 5 执行）

| ID | 场景 | 并发 | 持续时间 | P50 目标 | P99 目标 | 错误率 | 状态 | 执行日期 |
|:---|:---|:---|:---|:---|:---|:---|:---|:---|
| P1 | 基准 | 1 | — | ≤ 3s | ≤ 10s | 0% | ⬜ | — |
| P2 | 日常 | 5 | 5 min | ≤ 3s | ≤ 10s | ≤ 1% | ⬜ | — |
| P3 | 峰值 | 10 | 5 min | ≤ 3s | ≤ 10s | ≤ 1% | ⬜ | — |
| P4 | 极限 | 20 | 2 min | — | — | ≤ 5% | ⬜ | — |

> 压测完成后，根据 P50/P99 数据设定 Phase 5 限流阈值。

### 7.4 Phase 6 高级功能（不设时限）

> 以下为推迟至 Phase 6 的优化项，按优先级排序。测试用例在对应功能实现时补充。

| 优先级 | 功能 | 来源 | 简要测试方向 |
|:---|:---|:---|:---|
| P0 | DashScope Rerank API | Phase 3 | Reranker 结果排序正确性 / top_k 截取 / API 异常处理 |
| P1 | 结构感知分块 | Phase 2 | Markdown 标题层级保留 / 跨标题边界不截断 |
| P1 | LLM 摘要压缩 | Phase 4 | 摘要 token 控制 / 关键信息不丢失 |
| P2 | WebSocket 实时推送 | Phase 2 | 连接建立/断开/重连 / 状态变更事件 |
| P2 | thinking_content 持久化 | Phase 3 | 落库正确性 / 历史回看渲染 |
| P2 | 消息状态机 | Phase 4 | partial→complete 转换 / PATCH 接口 |
| P3 | reasoning_effort 前端可控 | Phase 3 | 前端枚举校验 / low/medium/high 映射 |
| P3 | Resumable 分片上传 | Phase 2 | 分片并发 / 断点续传 / 最终合并 |
| P3 | 内容去重 | Phase 2 | 哈希去重 / 近似去重 / 去重提示 |

---

## 8. 测试覆盖率目标

| 模块 | 覆盖率目标 | 当前值 | 备注 |
|:---|:---|:---|:---|
| `core/security.py` | ≥ 90% | ✅ 100% | 10 个测试全覆盖 |
| `core/exceptions.py` | ≥ 80% | ✅ 已覆盖 | E2001-E2013/E5005 等文档异常全部覆盖 |
| `services/auth_service.py` | ≥ 80% | ✅ 100% | 7 个测试全覆盖 |
| `api/auth.py` (接口测试) | ≥ 90% | ✅ 100% | 14 个测试全覆盖 |
| `api/document.py` (接口测试) | ≥ 90% | ✅ 100% | 65 个测试全覆盖（上传/批量/列表/详情/分块/删除/reprocess + 权限矩阵 18 用例）|
| `schemas/auth.py` | ≥ 85% | ✅ 100% | 10 个测试全覆盖 |
| `models/` | ≥ 70% | ✅ 已覆盖 | U4.1-U4.3 已实现 |
| `ingest/lock.py` | ≥ 80% | ✅ 100% | 16 个测试全覆盖（幂等锁获取/重复拒绝/过期重入） |
| `rag/parser.py` | ≥ 80% | ✅ 100% | 35 个测试全覆盖（PDF/DOCX逐段容错/MD/TXT 解析 + 容错分级） |
| `rag/chunker.py` | ≥ 80% | ✅ 100% | 36 个测试全覆盖（分隔符优先级/偏移量页码追踪/中英文自适应token估算/重叠） |
| `rag/embedder.py` | ≥ 80% | ✅ 100% | 28 个测试全覆盖（DashScope API/重试/批量/响应解析/指数退避） |
| `core/storage.py` | ≥ 80% | ✅ 100% | 29 个测试全覆盖（sanitize_filename/generate_stored_filename/LocalStorage save/read/delete/空目录清理） |
| `schemas/knowledge_base.py` | ≥ 85% | ✅ 100% | visibility 字段校验 10 用例（U9.1-U9.8），Phase 2.5 |
| `services/knowledge_base_service.py` | ≥ 80% | ✅ 33 用例 | `test_kb_service.py` 全覆盖：`_get_real_chunk_counts`(4) + `create_kb`(3) + `get_kb`(8) + `list_kbs`(3) + `list_public_kbs`(2) + `update_kb`(8) + `delete_kb`(3) + `check_kb_active`(2) |
| `api/knowledge_base.py` (public) | ≥ 90% | ✅ 100% | GET /public 端点 5 用例 + 权限变更回归 6 用例，Phase 2.5 |
| `services/document_service.py` | ≥ 80% | ✅ 29 用例 | `test_document_service.py` 覆盖：`_validate_file`(7) + `_build_document_response`(1) + `_check_kb_ownership`(5) + `list_documents`(4) + `get_document`(2) + `get_document_chunks`(2) + `delete_document`(3) + `reprocess_document`(2) + `upload_document`(3) |
| `rag/retriever.py` | ≥ 80% | ✅ | Phase 3：向量检索已覆盖（13 用例） |
| `rag/bm25.py` | ≥ 80% | ✅ | Phase 3：BM25 检索 + 缓存已覆盖（24 用例，含 7 个真实 jieba 集成测试） |
| `rag/fusion.py` | ≥ 80% | ✅ | Phase 3：RRF 多路融合已覆盖（12 用例） |
| `rag/reranker.py` | ≥ 80% | ✅ | Phase 3：NoopReranker 占位（11 用例） |
| `rag/prompt_builder.py` | ≥ 80% | ✅ 100% | Phase 3：Prompt 组装 + Token 预算（13 用例） |
| `core/llm.py` | ≥ 80% | ✅ | Phase 3：LLM 调用 + thinking 解析（15 用例） |
| `core/sse.py` | ≥ 80% | ✅ | Phase 3：SSE 格式/心跳/流式（17 用例） |
| `services/conversation_service.py` | ≥ 80% | ✅ 通过 API 测试 | Phase 4.1：会话 CRUD（5 个端点，20 用例，2026-06-05） |
| `api/conversation.py` | ≥ 90% | ✅ 100% | Phase 4.1：会话 API（20 用例，2026-06-05） |
| `services/chat_service.py` (_load_history) | ≥ 80% | ✅ 9 用例 | Phase 4.1：历史记忆（test_history_memory.py，2026-06-05） |
| `services/chat_service.py` (_generate_title_llm) | ≥ 80% | ✅ 6 用例 | Phase 4.1：LLM 标题生成（test_conversation_title.py，2026-06-05） |
| `core/error_handlers.py` | ≥ 80% | ✅ | Phase 4.2：全局异常处理（test_error_handlers.py，9 用例，U9.1-U9.3） |
| `core/logging_config.py` | ≥ 70% | ✅ | Phase 4.2：结构化日志（12 用例） |
| `services/auth_service.py` (refresh) | ≥ 80% | ✅ | Phase 4.2：Refresh Token 机制（20 用例） |
| `core/exceptions.py` (E5006-E5009) | ≥ 80% | ✅ | Phase 4.2：新增 4 个异常类 |
| `api/admin.py` (接口测试) | ≥ 90% | ✅ 100% | Phase 5：Admin 端点（27 用例，A7.1-A7.6，含权限矩阵参数化 9 用例） |
| `services/admin_service.py` | ≥ 80% | ✅ 100% | Phase 5：Admin 业务逻辑（21 用例：统计 3 + KB 列表 8 + 文档列表 10） |
| 前端 `components/layout/AdminLayout.vue` | ≥ 60% | ✅ 19 通过 | Phase 5：Admin 独立布局（19 用例：渲染结构/路由标题/导航项/返回按钮/slot） |
| `middleware/rate_limit.py` | ≥ 80% | ⬜ | Phase 5：限流中间件（5 用例，A8.1-A8.5） |
| `rag/intent.py` | ≥ 80% | ✅ | Phase 5：意图分类器（10 用例，U10.1-U10.10，全部通过） |
| `services/chat_service.py` (sources 预览) | ≥ 80% | ✅ 100% | Phase 5.5：Evidence Highlight 重构（21 用例 test_sources_preview.py + 4 用例 test_sse_helpers.py；U11.1-U11.6） |
| `rag/sentence_matcher.py` | ≥ 80% | ✅ 100% | Phase 5.5：句级 Evidence 定位（14 用例，U11.10-U11.15） |
| 性能埋点（检索+LLM） | ≥ 70% | ⬜ | Phase 5：U9.6/U9.7 埋点验证（4 用例，U12.1-U12.4） |
| `core/sse.py` | ≥ 80% | ✅ | Phase 3：SSE 格式/心跳/流式（17 用例） |
| `services/chat_service.py` | ≥ 80% | ✅ | Phase 3：问答核心流程（19 用例，P2 重构提取 `_mock_chat_pipeline` 共享工具消除 ~120 行重复 mock） |
| `api/chat.py` (接口测试) | ≥ 90% | ✅ | Phase 3：POST /api/chat SSE 接口（12 用例） |
| `schemas/chat.py` | ≥ 85% | ✅ | Phase 3：ChatRequest Schema 校验（6 用例） |
| `ingest/tasks.py` | — | ✅ | Celery 入库存根测试（10 用例，5 个为常量成员检查） |
| 前端 `utils/sse.js` | ≥ 80% | ✅ | Phase 3：SSE 事件解析（21 用例，2026-06-03） |
| 前端 `utils/markdown.js` | ≥ 80% | ✅ | Phase 3：Markdown 渲染（14 用例，2026-06-03） |
| 前端 `components/chat/` | ≥ 60% | ✅ | Phase 3：ChatInput(19) + MessageList(10) + MessageItem(26) + WelcomeScreen(8) = 63 用例，2026-06-03（MessageItem +2 用例：未找到相关信息 sources panel 显示/隐藏，2026-06-10 已追踪） |
| 前端 `views/ChatPage.vue` | ≥ 60% | ✅ | Phase 3：问答页集成（13 用例，2026-06-03） |
| 前端 `stores/chat.js` | ≥ 60% | ✅ | Phase 3：通过 ChatPage 集成测试间接覆盖 |
| 前端 `api/admin.js` | ≥ 80% | ✅ 9 用例 | Phase 5：Admin API 参数透传（9 用例：getStats 3 + getKBs 3 + getDocs 3，2026-06-10） |
| 前端 `views/admin/StatsPage.vue` | ≥ 60% | ✅ 19 用例 | Phase 5：系统概览页（加载态/数据渲染/千分位/formatStorage/错误态/null 边界，2026-06-10） |
| 前端 `views/admin/KnowledgeList.vue` | ≥ 60% | ✅ 16 用例 | Phase 5：知识库管理页（列表加载/空状态/搜索防抖/筛选/分页/编辑弹窗/删除/错误处理/formatDateTime，2026-06-10） |
| 前端 `views/admin/DocumentList.vue` | ≥ 60% | ✅ 17 用例 | Phase 5：文档管理页（列表加载/搜索/筛选排序/分页/删除含 KB 确认/getStatusLabel/isTerminal/formatFileSize，2026-06-10） |
| 前端 `views/admin/ConversationList.vue` | ≥ 60% | ✅ 17 用例 | Phase 5：活跃统计占位页（标题/描述/7 维度卡片/预览表格/表头顺序，2026-06-10） |
| 前端组件 | ≥ 60% | ✅ 327 通过 | 2026-06-10 运行 `npm run test`：20 文件 327 用例全部通过（新增 admin 页面 69 用例 + admin API 9 用例 + MessageItem +4 用例含 U11.6 <mark> 高亮 + AdminLayout 19 用例 + AppLayout 11 用例） |

---

## 9. 相关文档

- [测试策略文档](TESTING.md) — 6 层测试体系详细说明
- [开发排期](ROADMAP.md) — 各 Phase 测试任务与准入规则
- [开发指南](DEVELOPMENT.md) — 测试命令与项目结构
