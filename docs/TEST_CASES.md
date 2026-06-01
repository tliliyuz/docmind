# TEST_CASES — 测试用例跟踪

| 属性 | 值 |
|:---|:---|
| 文档版本 | v0.26 |
| 最后更新 | 2026-05-29 |
| 作者 | yuz |
| 状态 | 进行中（Phase 2.5 全部完成，Phase 3 用例已细化） |

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
| U7.8 | 向量检索-metadata int 类型一致性 | `vector_retriever.search()` | metadata kb_id/doc_id/chunk_index 为 int | 入库/查询两端统一 int，无需类型转换 | ✅ | 2026-05-28 | 决策 #21，不使用 _normalize_metadata() |

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
| U7.30 | RRF-标准合并 | `rrf_fusion()` | 两路各 10 结果，k=60 | 按 `Σ 1/(k+rank)` 降序排列，输出 top_k 结果 | ⬜ | — | — |
| U7.31 | RRF-两路有重叠文档 | `rrf_fusion()` | 同一 chunk 在两路中都出现 | 分数累加（两路 rank 分别计算），排名更靠前 | ⬜ | — | — |
| U7.32 | RRF-向量路为空 | `rrf_fusion()` | 向量检索返回 [] | 仅返回 BM25 结果，保持原排序 | ⬜ | — | — |
| U7.33 | RRF-BM25 路为空 | `rrf_fusion()` | BM25 返回 [] | 仅返回向量结果，保持原排序 | ⬜ | — | — |
| U7.34 | RRF-两路均为空 | `rrf_fusion()` | 两路均返回 [] | 返回空列表 | ⬜ | — | — |
| U7.35 | RRF-排名相同处理 | `rrf_fusion()` | 不同 chunk 在同一路中 rank 相同（罕见） | 使用平均 rank 或文档 ID 作为 tiebreaker | ⬜ | — | — |
| U7.36 | RRF-k 值可配置 | `rrf_fusion()` | k=10 / k=60 / k=120 | k 越小排名影响越大，k=60 为默认平衡值 | ⬜ | — | — |

### 5.5 后端 — NoopReranker 测试

| ID | 测试用例 | 被测函数 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U7.40 | NoopReranker-按长度排序 | `NoopReranker.rerank()` | 输入混合长度 chunks | 按 content 长度升序排列（短 chunk 优先） | ⬜ | — | — |
| U7.41 | NoopReranker-截取 top_k | `NoopReranker.rerank()` | 输入 10 chunks, top_k=5 | 排序后返回前 5 个 | ⬜ | — | — |
| U7.42 | NoopReranker-输入不足 top_k | `NoopReranker.rerank()` | 输入 3 chunks, top_k=5 | 返回全部 3 个 | ⬜ | — | — |
| U7.43 | NoopReranker-空输入 | `NoopReranker.rerank()` | 输入 [] | 返回 [] | ⬜ | — | — |
| U7.44 | NoopReranker-不改变 chunk 内容 | `NoopReranker.rerank()` | 正常输入 | 仅改变顺序，chunk 的 content/metadata 不变 | ⬜ | — | — |

### 5.6 后端 — Prompt 模板测试

| ID | 测试用例 | 被测函数 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U7.50 | Prompt-基本拼接 | `prompt_builder.build()` | question + chunks | 返回含 system prompt + context + question 的 messages 数组 | ⬜ | — | — |
| U7.51 | Prompt-检索结果格式化 | `prompt_builder.build()` | 多个 chunks | 每个 chunk 标注 [来源N] 标签（N=chunk_index） | ⬜ | — | — |
| U7.52 | Prompt-软上限控制 | `prompt_builder.build()` | chunks 总长度超预算 | 按长度升序择优填充，超预算时尝试下一更短 chunk | ⬜ | — | Token 估算用中英文自适应算法 |
| U7.53 | Prompt-空检索结果 | `prompt_builder.build()` | chunks=[] | system prompt 包含「知识库中未找到相关信息」 | ⬜ | — | — |
| U7.54 | Prompt-history 参数 | `prompt_builder.build()` | Phase 3 历史为空 | `history=[]` 不注入历史消息，Phase 4 传入历史 | ⬜ | — | — |
| U7.55 | Prompt-预算计算正确 | `prompt_builder._count_tokens()` | 中文/英文/混合 | 中文占比 >30% → ratio=1.5，否则 4.0（复用 chunker 算法） | ⬜ | — | — |
| U7.56 | Prompt-不超过模型上限 80% | `prompt_builder.build()` | 大量 chunks | 最终 prompt tokens ≤ 模型 context_window × 0.8 | ⬜ | — | — |

### 5.7 后端 — Chat Service 单元测试

| ID | 测试用例 | 被测函数 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U7.60 | Service-正常问答流程 | `chat_service.chat()` | conversation_id=null | 自动创建会话 → 检索 → RRF → Rerank → Prompt → LLM 流式 → SSE 事件 | ⬜ | — | 全链路 Mock |
| U7.61 | Service-已有会话追加 | `chat_service.chat()` | conversation_id 存在 | 复用已有会话，保存消息到同一 conversation | ⬜ | — | Phase 4 衔接 |
| U7.62 | Service-检索失败 | `chat_service.chat()` | 检索抛异常 | SSE event: error (E4003)，连接正常关闭 | ⬜ | — | — |
| U7.63 | Service-LLM 失败 | `chat_service.chat()` | LLM API 返回 500 | SSE event: error (E4002)，不崩连接 | ⬜ | — | — |
| U7.64 | Service-kb 无文档 | `chat_service.chat()` | kb chunks=0 | SSE event: error (E4001) | ⬜ | — | — |
| U7.65 | Service-用户消息保存 | `chat_service.chat()` | 正常问答 | messages 表写入 role=user + role=assistant 两条 | ⬜ | — | — |
| U7.66 | Service-标题生成 | `chat_service._generate_title()` | 首轮问答 | 截取 question[:12]，去除标点，更新 conversation.title | ⬜ | — | — |
| U7.67 | Service-message_count 递增 | `chat_service.chat()` | 每次问答 | conversation.message_count += 2（user+assistant） | ⬜ | — | — |

### 5.8 后端 — LLM 调用与 thinking 解析测试

| ID | 测试用例 | 被测函数 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U7.70 | LLM-流式调用 | `llm_client.stream_chat()` | 正常请求 | 返回 async generator，逐 chunk yield delta | ⬜ | — | Mock OpenAI SDK |
| U7.71 | LLM-content 事件 | `llm_client.stream_chat()` | 正常响应 | `delta.content` → `event: message` | ⬜ | — | — |
| U7.72 | LLM-thinking 事件 | `llm_client.stream_chat()` | deep_thinking=true | `extra_body={"thinking":{"type":"enabled"}}`，`delta.reasoning_content` → `event: thinking` | ⬜ | — | — |
| U7.73 | LLM-deep_thinking=false 显式禁用 | `llm_client.stream_chat()` | deep_thinking=false | `extra_body={"thinking":{"type":"disabled"}}`，仅 message 事件，无 thinking | ⬜ | — | DeepSeek 默认 enabled，须显式传 disabled |
| U7.74 | LLM-重试 | `llm_client.stream_chat()` | API 返回 500/503 | max_retries=3 指数退避重试 | ⬜ | — | — |
| U7.75 | LLM-重试全部失败 | `llm_client.stream_chat()` | 3 次重试均失败 | 抛出 `LLMException(E4002)` | ⬜ | — | — |
| U7.76 | LLM-限流 | `llm_client.stream_chat()` | API 返回 429 | 等待 Retry-After 或指数退避后重试 | ⬜ | — | — |
| U7.77 | LLM-thinking 不落库 | `chat_service.chat()` | deep_thinking=true | `messages.thinking_content` 写入 null | ⬜ | — | 仅流式展示 |
| U7.78 | LLM-token 消耗记录 | `chat_service.chat()` | 正常问答 | `messages.token_count` 写入 API 返回的 usage 值 | ⬜ | — | — |

### 5.9 后端 — SSE 流式输出测试

| ID | 测试用例 | 被测函数 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U7.80 | SSE-事件序列 | `sse_helpers` | 正常问答 | meta → (thinking)×N → message×N → sources → finish | ⬜ | — | — |
| U7.81 | SSE-心跳帧 | `sse_helpers` | 无数据 15s | 发送 `: ping\n\n` 注释帧，浏览器忽略但保持连接 | ⬜ | — | — |
| U7.82 | SSE-中途错误 | `sse_helpers` | LLM 中途失败 | meta → (message)×N → error → 连接关闭 | ⬜ | — | — |
| U7.83 | SSE-客户端断开 | `sse_helpers` | 用户关闭页面 | `asyncio.CancelledError` 被捕获，LLM 流被中断 | ⬜ | — | — |
| U7.84 | SSE-Content-Type | `StreamingResponse` | 正常 | `text/event-stream` + `Cache-Control: no-cache` + `Connection: keep-alive` | ⬜ | — | — |
| U7.85 | SSE-sources 事件数据 | `sse_helpers._build_sources()` | 正常 | chunks 数组每项含 doc_id/doc_name/content/score/page | ⬜ | — | — |
| U7.86 | SSE-finish 事件数据 | `sse_helpers._build_finish()` | 正常 | message_id + title（首轮）+ token_usage{prompt,completion,total} | ⬜ | — | — |

### 5.10 后端 — ChatRequest Schema 校验测试

| ID | 测试用例 | Schema | 输入 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U7.90 | question 为空 | `ChatRequest` | `question=""` | `ValidationError`（min_length=1） | ⬜ | — | — |
| U7.91 | question 超长 | `ChatRequest` | `question="x"×2001` | `ValidationError`（max_length=2000） | ⬜ | — | — |
| U7.92 | kb_id 缺失 | `ChatRequest` | 不传 kb_id | `ValidationError`（required） | ⬜ | — | — |
| U7.93 | conversation_id 可选 | `ChatRequest` | 不传 conversation_id | 校验通过，默认 None | ⬜ | — | — |
| U7.94 | deep_thinking 默认值 | `ChatRequest` | 不传 deep_thinking | 默认 false | ⬜ | — | — |
| U7.95 | reasoning_effort 默认值 | `ChatRequest` | 不传 reasoning_effort | 默认 `"high"` | ⬜ | — | — |
| U7.96 | reasoning_effort 非法值 | `ChatRequest` | reasoning_effort="low" | `ValidationError`（仅允许 high/max） | ⬜ | — | — |
| U7.97 | 正常请求 | `ChatRequest` | 全部合法字段 | 校验通过 | ⬜ | — | — |

### 5.11 后端 — 问答 SSE 接口测试

| ID | 测试用例 | 端点 | 场景 | 预期 SSE 事件序列 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| A4.1 | 正常问答 | POST `/api/chat` | 有效问题 + conversation_id=null | meta → message×N → sources → finish（finish 含新 conversation_id + title） | ⬜ | — | — |
| A4.2 | 正常问答-已有会话 | POST `/api/chat` | 有效问题 + conversation_id 存在 | meta（复用 conversation_id） → message×N → sources → finish | ⬜ | — | — |
| A4.3 | 空问题 | POST `/api/chat` | question="" | HTTP 422 (E9003)，非 SSE | ⬜ | — | 连接建立前校验 |
| A4.4 | kb 无可用文档 | POST `/api/chat` | kb chunks=0 | SSE error event (E4001) | ⬜ | — | — |
| A4.5 | kb 不存在 | POST `/api/chat` | 无效 kb_id | HTTP 404 (E1001)，非 SSE | ⬜ | — | 连接建立前校验 |
| A4.6 | private KB 非 owner 拒绝 | POST `/api/chat` | 其他用户访问 private KB | HTTP 403 (E5005) | ⬜ | — | — |
| A4.7 | public KB 任意用户可检索 | POST `/api/chat` | 其他用户访问 public KB | 正常 SSE 事件序列 | ⬜ | — | — |
| A4.8 | deep_thinking=true | POST `/api/chat` | `deep_thinking: true` | meta → thinking×N → message×N → sources → finish | ⬜ | — | — |
| A4.9 | deep_thinking=false（默认） | POST `/api/chat` | 不传 deep_thinking | meta → message×N → sources → finish（无 thinking 事件） | ⬜ | — | — |
| A4.10 | 未认证 | POST `/api/chat` | 无 Token | HTTP 401 (E5004) | ⬜ | — | — |
| A4.11 | 流式中断-前端内存保留 | POST `/api/chat` | 中途断连 | 前端内存保留已渲染内容（刷新丢失），conversation 已创建可继续追问。**Phase 3 不持久化半条消息** | ⬜ | — | Phase 4 重访是否需要 message.status 字段 |
| A4.12 | 心跳帧存在 | POST `/api/chat` | 长回答 >15s | SSE 流中包含 `: ping\n\n` 注释帧 | ⬜ | — | — |

### 5.12 后端 — KB 选择器接口测试

| ID | 测试用例 | 端点 | 场景 | 预期响应 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| A9.1 | 选择器-正常返回 | GET `/api/knowledge-bases/selectable` | 已登录用户 | 200, `{mine: [...], public: [...]}` | ⬜ | — | — |
| A9.2 | 选择器-mine 含全部自己 KB | GET `/api/knowledge-bases/selectable` | 用户有 private+public KB | mine 包含所有自己的 KB（不论 visibility） | ⬜ | — | — |
| A9.3 | 选择器-public 不含自己 | GET `/api/knowledge-bases/selectable` | 自己有 public KB | public 数组不包含自己的 KB（避免重复） | ⬜ | — | — |
| A9.4 | 选择器-仅返回 active | GET `/api/knowledge-bases/selectable` | 有 deleting KB | deleting 状态不在列表中 | ⬜ | — | — |
| A9.5 | 选择器-未认证拒绝 | GET `/api/knowledge-bases/selectable` | 无 Token | 401 (E5004) | ⬜ | — | — |
| A9.6 | 选择器-空数据 | GET `/api/knowledge-bases/selectable` | 无 KB | 200, `{mine: [], public: []}` | ⬜ | — | — |

### 5.13 前端 — SSE 解析工具测试

| ID | 测试用例 | 被测模块 | 验证项 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| UT1.1 | SSE-解析 meta | `sse.js` | `event: meta\ndata: {…}` | 返回 `{type: "meta", conversation_id, task_id}` | ⬜ | — | — |
| UT1.2 | SSE-解析 message | `sse.js` | `event: message\ndata: {"delta":"你好"}` | 返回 `{type: "message", delta: "你好"}` | ⬜ | — | — |
| UT1.3 | SSE-解析 thinking | `sse.js` | `event: thinking\ndata: {"delta":"思考..."}` | 返回 `{type: "thinking", delta: "思考..."}` | ⬜ | — | — |
| UT1.4 | SSE-解析 sources | `sse.js` | `event: sources\ndata: {"chunks":[...]}` | 返回 `{type: "sources", chunks: [...]}` | ⬜ | — | — |
| UT1.5 | SSE-解析 finish | `sse.js` | `event: finish\ndata: {…}` | 返回 `{type: "finish", message_id, title, token_usage}` | ⬜ | — | — |
| UT1.6 | SSE-解析 error | `sse.js` | `event: error\ndata: {…}` | 返回 `{type: "error", code, message, detail}` | ⬜ | — | — |
| UT1.7 | SSE-忽略心跳帧 | `sse.js` | `: ping\n\n` | 不触发任何回调，继续等待下一个事件 | ⬜ | — | — |
| UT1.8 | SSE-多行 data 拼接 | `sse.js` | 多条 `data:` 行 | 按 `\n` 拼接后 JSON.parse | ⬜ | — | — |
| UT1.9 | SSE-格式异常容错 | `sse.js` | data 不是合法 JSON | 跳过该事件，不崩溃，继续处理后续 | ⬜ | — | — |
| UT1.10 | SSE-连接中断 | `sse.js` | `reader.read()` 抛异常 | 触发 onError 回调，清理 reader | ⬜ | — | — |
| UT1.11 | SSE-未知 event 类型 | `sse.js` | `event: unknown` | 跳过不处理，不崩溃 | ⬜ | — | — |
| UT1.12 | SSE-空 data | `sse.js` | `event: meta\ndata:` (空) | 跳过该事件 | ⬜ | — | — |

### 5.14 前端 — Markdown 渲染工具测试

| ID | 测试用例 | 被测模块 | 验证项 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| UT2.1 | Markdown-基本渲染 | `markdown.js` | `# 标题` | 渲染为 `<h1>标题</h1>` | ⬜ | — | — |
| UT2.2 | Markdown-代码块高亮 | `markdown.js` | ` ```js\n...\n``` ` | 代码块有语法高亮 class | ⬜ | — | — |
| UT2.3 | Markdown-XSS 过滤 | `markdown.js` | `<script>alert(1)</script>` | script 标签被转义/移除 | ⬜ | — | — |
| UT2.4 | Markdown-链接处理 | `markdown.js` | `[text](url)` | `<a href="url" target="_blank">` | ⬜ | — | — |
| UT2.5 | Markdown-表格渲染 | `markdown.js` | `\|列1\|列2\|` | 渲染为 `<table>` | ⬜ | — | — |
| UT2.6 | Markdown-空内容 | `markdown.js` | `""` | 返回空字符串 | ⬜ | — | — |

### 5.15 前端 — ChatInput 组件测试

| ID | 测试用例 | 组件 | 验证项 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| C3.1 | ChatInput-输入发送 | `ChatInput` | 输入文字 + 点击发送 | 触发 `send` 事件，参数含 question + deep_thinking | ⬜ | — | — |
| C3.2 | ChatInput-Enter 发送 | `ChatInput` | 输入文字 + Enter | 触发 `send` 事件（非 Shift+Enter） | ⬜ | — | — |
| C3.3 | ChatInput-Shift+Enter 换行 | `ChatInput` | Shift+Enter | 在输入框中换行，不触发发送 | ⬜ | — | — |
| C3.4 | ChatInput-停止生成 | `ChatInput` | 流式输出中点击 | 按钮变为「停止生成」，触发 `abort` 事件 | ⬜ | — | — |
| C3.5 | ChatInput-空内容拒绝 | `ChatInput` | 空输入点击发送 | 输入框抖动，不触发 `send` | ⬜ | — | — |
| C3.6 | ChatInput-字数计数 | `ChatInput` | 输入文字 | 实时显示 `{n}/2000` 字数 | ⬜ | — | — |
| C3.7 | ChatInput-超长截断 | `ChatInput` | 粘贴 >2000 字符 | 自动截断至 2000 字符 | ⬜ | — | — |
| C3.8 | ChatInput-深度思考开关 | `ChatInput` | 切换 deep_thinking | 开关状态正确切换，参数传入 send 事件 | ⬜ | — | — |
| C3.9 | ChatInput-发送中禁用 | `ChatInput` | 流式输出中 | 输入框禁用，不可编辑或再次发送 | ⬜ | — | — |
| C3.10 | ChatInput-完成后恢复 | `ChatInput` | 流式完成 | 输入框恢复可编辑，按钮恢复为「发送」 | ⬜ | — | — |

### 5.16 前端 — MessageList 组件测试

| ID | 测试用例 | 组件 | 验证项 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| C3.11 | MessageList-消息气泡排列 | `MessageList` | 多条消息 | user 消息右对齐，AI 消息左对齐 | ⬜ | — | — |
| C3.12 | MessageList-自动滚动 | `MessageList` | 新消息到达 | 自动滚动到底部 | ⬜ | — | — |
| C3.13 | MessageList-手动上滚 | `MessageList` | 用户手动上滚 | 显示「↓ 新消息」浮动按钮，点击回到底部 | ⬜ | — | — |
| C3.14 | MessageList-空状态 | `MessageList` | messages=[] | 显示 WelcomeScreen | ⬜ | — | — |
| C3.15 | MessageList-流式追加 | `MessageList` | 收到 message delta | 同一条 AI 消息气泡内逐字追加，实时滚动 | ⬜ | — | — |
| C3.16 | MessageList-thinking 面板 | `MessageList` | 收到 thinking delta | 黄色边框折叠面板，内容逐字追加 | ⬜ | — | — |
| C3.17 | MessageList-sources 卡片 | `MessageList` | 收到 sources 事件 | 消息底部渲染引用文档卡片 | ⬜ | — | — |
| C3.18 | MessageList-typing 动画 | `MessageList` | 发送后等待首 token | AI 气泡显示 typing 动画（三点跳动） | ⬜ | — | — |

### 5.17 前端 — MessageItem 组件测试

| ID | 测试用例 | 组件 | 验证项 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| C3.20 | MessageItem-用户消息 | `MessageItem` | role=user | 显示用户头像 + 消息内容，右对齐气泡 | ⬜ | — | — |
| C3.21 | MessageItem-AI Markdown | `MessageItem` | role=assistant + Markdown 内容 | markdown-it 渲染为 HTML | ⬜ | — | — |
| C3.22 | MessageItem-thinking 折叠 | `MessageItem` | 有 thinking_content | 黄色面板，默认展开，可点击折叠 | ⬜ | — | — |
| C3.23 | MessageItem-sources 展示 | `MessageItem` | 有 sources | 文档名 + score + page，点击展开分块预览 | ⬜ | — | — |
| C3.24 | MessageItem-重新生成按钮 | `MessageItem` | AI 消息 hover | 显示「重新生成」按钮，点击重新发送上一条问题 | ⬜ | — | — |
| C3.25 | MessageItem-代码复制 | `MessageItem` | AI 消息含代码块 | hover 显示复制按钮，点击复制到剪贴板 | ⬜ | — | — |
| C3.26 | MessageItem-无 sources | `MessageItem` | sources=[] | 不渲染引用卡片区域 | ⬜ | — | — |
| C3.27 | MessageItem-无 thinking | `MessageItem` | thinking_content=null | 不渲染 thinking 面板 | ⬜ | — | — |

### 5.18 前端 — WelcomeScreen 组件测试

| ID | 测试用例 | 组件 | 验证项 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| C3.30 | WelcomeScreen-渲染 | `WelcomeScreen` | 空消息列表 | Logo + 欢迎语 + 快捷问题卡片 | ⬜ | — | — |
| C3.31 | WelcomeScreen-快捷问题 | `WelcomeScreen` | 点击快捷问题卡片 | 文本填入 ChatInput 并自动发送 | ⬜ | — | — |
| C3.32 | WelcomeScreen-有消息时隐藏 | `WelcomeScreen` | 消息列表非空 | 组件不渲染 | ⬜ | — | — |

### 5.19 前端 — ChatPage 集成测试

| ID | 测试用例 | 组件 | 验证项 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| C6.1 | ChatPage-KB 选择器 | `ChatPage` | 页面挂载 | 加载 KB 选择器数据，默认选中最近使用的 KB | ⬜ | — | — |
| C6.2 | ChatPage-完整问答流程 | `ChatPage` | 选择KB→提问→流式→完成 | 用户消息出现 → AI typing → 逐字追加 → sources → 停止 | ⬜ | — | Mock SSE |
| C6.3 | ChatPage-停止按钮 | `ChatPage` | 流式中点击停止 | `AbortController.abort()`，消息保留当前内容 | ⬜ | — | — |
| C6.4 | ChatPage-切换 KB | `ChatPage` | 流式完成后切换 KB | 消息列表不变（不同 KB 的对话存不同会话） | ⬜ | — | — |
| C6.5 | ChatPage-新建对话 | `ChatPage` | 点击「新建对话」 | 清空消息列表，conversation_id=null | ⬜ | — | — |
| C6.6 | ChatPage-错误处理 | `ChatPage` | SSE error 事件 | 显示错误提示，输入框恢复可用 | ⬜ | — | — |
| C6.7 | ChatPage-网络异常 | `ChatPage` | fetch 网络错误 | 显示「网络异常，请稍后重试」 | ⬜ | — | — |
| C6.8 | ChatPage-deep_thinking 流转 | `ChatPage` | 开启深度思考 | thinking 面板实时追加 → message 内容追加 → sources → finish | ⬜ | — | — |

### 5.20 专项测试（Phase 3 完成执行）

| ID | 评估项目 | 指标 | 目标值 | 实际值 | 状态 | 执行日期 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| E1 | 向量检索 Recall@5 | Recall@5 | ≥ 0.85 | — | ⬜ | — | 见 TESTING.md §5 |
| E2 | BM25 检索 Recall@5 | Recall@5 | ≥ 0.70 | — | ⬜ | — | — |
| E3 | RRF 融合 Recall@5 | Recall@5 | ≥ 0.90 | — | ⬜ | — | — |
| E4 | 向量检索 MRR | MRR | ≥ 0.70 | — | ⬜ | — | — |
| E5 | RRF 融合 Precision@5 | Precision@5 | ≥ 0.60 | — | ⬜ | — | — |
| E6 | 人工答案评分（第 1 轮） | 综合分 ≥ 4.0 | ≥ 4.0/5.0 | — | ⬜ | — | 10 题 × 4 维度，见 TESTING.md §6 |

---

## 6. Phase 4 测试用例

> 详细用例在 Phase 4 开发时补充。

| ID | 测试用例 | 被测对象 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| A5.1 | 会话 CRUD 全套 | API | 创建/列表/详情/重命名/删除 | 各端点正常响应 | ⬜ | — | — |
| A5.2 | 越权访问会话 | API | 访问他人会话 | 403, E3002 | ⬜ | — | — |
| A5.3 | 多轮对话上下文 | Service | 连续 3 轮问答 | 历史消息注入 context | ⬜ | — | — |
| U8.1 | 滑动窗口-10 轮内 | `chat_service` | 8 轮对话 | 历史完整保留 | ⬜ | — | — |
| U8.2 | 滑动窗口-超出 10 轮 | `chat_service` | 12 轮对话 | 前 2 轮被摘要压缩 | ⬜ | — | — |
| U8.3 | 问题重写-指代补全 | `intent.py` | "它多少钱？" | 补全为 "XX 产品多少钱？" | ⬜ | — | — |
| C4.1 | Sidebar 会话列表 | `Sidebar` | 多会话 | 列表渲染 + 当前高亮 | ⬜ | — | — |
| C4.2 | 会话切换 | `Sidebar` | 点击不同会话 | 消息列表切换 | ⬜ | — | — |

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
| `rag/chunker.py` | ≥ 80% | ✅ 100% | 37 个测试全覆盖（分隔符优先级/偏移量页码追踪/中英文自适应token估算/重叠） |
| `rag/embedder.py` | ≥ 80% | ✅ 100% | 26 个测试全覆盖（DashScope API/重试/批量/响应解析/指数退避） |
| `core/storage.py` | ≥ 80% | ✅ 100% | 37 个测试全覆盖（sanitize_filename/generate_stored_filename/LocalStorage save/read/delete/空目录清理） |
| `schemas/knowledge_base.py` | ≥ 85% | ✅ 100% | visibility 字段校验 10 用例（U9.1-U9.8），Phase 2.5 |
| `services/knowledge_base_service.py` | ≥ 80% | ✅ 100% | 权限矩阵 6 用例（A6.1-A6.6）+ 公共列表 5 用例（A7.1-A7.7），Phase 2.5 |
| `api/knowledge_base.py` (public) | ≥ 90% | ✅ 100% | GET /public 端点 5 用例 + 权限变更回归 6 用例，Phase 2.5 |
| `services/document_service.py` | ≥ 80% | ✅ 100% | `owner_only` 权限分离 18 用例（A8.1-A8.18），Phase 2.5 |
| `rag/retriever.py` | ≥ 80% | ✅ | Phase 3：向量检索已覆盖 |
| `rag/bm25.py` | ≥ 80% | ✅ | Phase 3：BM25 检索 + 缓存已覆盖（25 用例，含 7 个真实 jieba 集成测试） |
| `rag/reranker.py` | ≥ 80% | ⬜ | Phase 3：NoopReranker 占位 |
| `rag/prompt_builder.py` | ≥ 80% | ⬜ | Phase 3：Prompt 组装 + Token 预算 |
| `services/chat_service.py` | ≥ 80% | ⬜ | Phase 3：问答核心流程 + SSE |
| `api/chat.py` (接口测试) | ≥ 90% | ⬜ | Phase 3：POST /api/chat SSE 接口 |
| `schemas/chat.py` | ≥ 85% | ⬜ | Phase 3：ChatRequest Schema 校验 |
| 前端 `utils/sse.js` | ≥ 80% | ⬜ | Phase 3：SSE 事件解析 |
| 前端 `utils/markdown.js` | ≥ 80% | ⬜ | Phase 3：Markdown 渲染 |
| 前端 `components/chat/` | ≥ 60% | ⬜ | Phase 3：ChatInput/MessageList/MessageItem/WelcomeScreen |
| 前端 `views/ChatPage.vue` | ≥ 60% | ⬜ | Phase 3：问答页集成 |
| 前端 `stores/chat.js` | ≥ 60% | ⬜ | Phase 3：聊天状态管理 |
| 前端组件 | ≥ 60% | ✅ 59 通过 | LoginPage(12) + AppLayout(14) + KnowledgeList(11) + KnowledgeDetail(12) + PublicKnowledgeList(10) 全部通过 |

---

## 9. 相关文档

- [测试策略文档](TESTING.md) — 6 层测试体系详细说明
- [开发排期](ROADMAP.md) — 各 Phase 测试任务与准入规则
- [开发指南](DEVELOPMENT.md) — 测试命令与项目结构
