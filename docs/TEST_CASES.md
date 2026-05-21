# TEST_CASES — 测试用例跟踪

| 属性 | 值 |
|:---|:---|
| 文档版本 | v0.14 |
| 最后更新 | 2026-05-21 |
| 作者 | yuz |
| 状态 | 进行中（Phase 2 3.2 Celery 入库流水线完成 + 6 项质量修复，全量回归 293 ✅） |

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
| A2.4 | 详情查询 | GET `/{id}` | 正常 | 200 | ✅ | 2026-05-17 | — |
| A2.5 | 详情-不存在 | GET `/{id}` | 无效 ID | 404, E1001 | ✅ | 2026-05-17 | — |
| A2.6 | 更新知识库 | PUT `/{id}` | 正常 | 200 | ✅ | 2026-05-17 | — |
| A2.7 | 删除知识库 | DELETE `/{id}` | 正常 | 202，异步删除 | ✅ | 2026-05-17 | — |
| A2.8 | 越权访问 | GET | 他人 KB | 403, E5005 | ✅ | 2026-05-17 | — |

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
| U6.7 | Embedding 批次 checkpoint | `tasks.py` | 中途失败 | 从 last_success_batch 恢复 | ✅ | 2026-05-21 | Embedding 阶段每批成功后更新 checkpoint |
| U6.8 | 存储-保存文件 | `storage.py` | 上传文件 | 文件写入磁盘，返回路径 `uploads/{kb_id}/{doc_id}/{uuid}_{filename}` | ✅ | 2026-05-21 | tempfile 临时目录 + Mock UploadFile |
| U6.9 | 存储-读取文件 | `storage.py` | 已有文件 | 返回 bytes 内容 | ✅ | 2026-05-21 | — |
| U6.10 | 存储-删除文件 | `storage.py` | 已有文件 | 文件删除，空目录自动清理 | ✅ | 2026-05-21 | 含多级空目录清理 + 同目录有其他文件保留目录 |
| U6.11 | 存储-文件名安全处理 | `storage.py` | 含 `/` `\` 空字节的文件名 | 移除危险字符，保留中文 | ✅ | 2026-05-21 | 16 个 sanitize 用例 |

### 3.5 前端 — 组件测试

| ID | 测试用例 | 组件 | 验证项 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| C2.1 | KnowledgeList 渲染 | `KnowledgeList` | 网格布局 | KB 卡片网格渲染 | ⬜ | — | — |
| C2.2 | KnowledgeList 空状态 | `KnowledgeList` | 无 KB | 显示空状态提示 + 新建按钮 | ⬜ | — | — |
| C2.3 | KnowledgeList 新建弹窗 | `KnowledgeList` | 点击新建 | 弹窗显示，含名称+描述表单 | ⬜ | — | — |
| C2.4 | KnowledgeList 删除确认 | `KnowledgeList` | 点击删除 | 二次确认弹窗 | ⬜ | — | — |
| C2.5 | DocumentList 渲染 | `DocumentList` | 表格 | 文档表格含状态标签 | ⬜ | — | — |
| C2.6 | DocumentList 上传拖拽 | `DocumentList` | 拖拽文件 | 触发上传 | ⬜ | — | — |
| C2.7 | DocumentList 状态轮询 | `DocumentList` | 非终态文档 | 2s 轮询直到终态 | ⬜ | — | — |

---

## 4. Phase 3 测试用例

> 详细用例在 Phase 3 开发时补充。

### 4.1 检索器 & RRF 单元测试

| ID | 测试用例 | 被测模块 | 场景 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| U7.1 | 向量检索-基本 | `retriever.py` | 查询 | 返回 top_k 结果，含 doc_id + score | ⬜ | — | — |
| U7.2 | 向量检索-kb_id 过滤 | `retriever.py` | 指定 kb_id | 仅返回该 kb_id 的结果 | ⬜ | — | — |
| U7.3 | BM25 检索-基本 | `retriever.py` | 中文查询 | 返回 BM25 排序结果 | ⬜ | — | — |
| U7.4 | RRF 融合-排序正确 | `retriever.py` | 两路结果 | k=60 公式正确排序 | ⬜ | — | — |
| U7.5 | RRF 融合-单路为空 | `retriever.py` | BM25 无结果 | 仅返回向量结果 | ⬜ | — | — |
| U7.6 | NoopReranker | `reranker.py` | 任意输入 | 截取 top_k 不改变顺序 | ⬜ | — | — |

### 4.2 问答 SSE 接口测试

| ID | 测试用例 | 端点 | 场景 | 预期 SSE 事件序列 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| A4.1 | 正常问答 | POST `/api/chat` | 有效问题 | meta → message (×N) → sources → finish | ⬜ | — | — |
| A4.2 | 空问题 | POST | question="" | error (E4005) | ⬜ | — | — |
| A4.3 | 空知识库 | POST | kb 无文档 | error (E4001) | ⬜ | — | — |
| A4.4 | 无效 kb_id | POST | 不存在 KB | error (E1001) | ⬜ | — | — |

### 4.3 前端 — 问答页 & SSE 解析测试

| ID | 测试用例 | 组件/模块 | 验证项 | 预期行为 | 状态 | 最后运行 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| C3.1 | ChatInput 发送 | `ChatInput` | 输入+点击 | 触发 send 事件 | ⬜ | — | — |
| C3.2 | ChatInput 停止 | `ChatInput` | 流式中点击 | 触发 abort 事件 | ⬜ | — | — |
| C3.3 | MessageList 渲染 | `MessageList` | 多条消息 | 用户+AI 消息气泡正确排列 | ⬜ | — | — |
| C3.4 | SSE 解析-meta | `sse.js` | event:meta | 解析 type + conversation_id | ⬜ | — | — |
| C3.5 | SSE 解析-message | `sse.js` | event:message | 解析 type + content | ⬜ | — | — |
| C3.6 | SSE 解析-sources | `sse.js` | event:sources | 解析 type + sources 数组 | ⬜ | — | — |
| C3.7 | SSE 解析-finish | `sse.js` | event:finish | 解析 type + 标记流结束 | ⬜ | — | — |
| C3.8 | SSE 解析-error | `sse.js` | event:error | 解析 type + code + message | ⬜ | — | — |
| C3.9 | SSE 解析-格式异常 | `sse.js` | 不完整 data | 容错不崩溃 | ⬜ | — | — |
| C3.10 | MessageItem 来源引用 | `MessageItem` | sources 数据 | 渲染引用文档链接 | ⬜ | — | — |

---

## 5. Phase 4 测试用例

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

## 6. 专项测试用例

### 6.1 离线检索评估（Phase 2 完成执行）

| ID | 评估项目 | 指标 | 目标值 | 实际值 | 状态 | 执行日期 | 备注 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| E1 | 向量检索 Recall@5 | Recall@5 | ≥ 0.85 | — | ⬜ | — | — |
| E2 | BM25 检索 Recall@5 | Recall@5 | ≥ 0.70 | — | ⬜ | — | — |
| E3 | RRF 融合 Recall@5 | Recall@5 | ≥ 0.90 | — | ⬜ | — | — |
| E4 | 向量检索 MRR | MRR | ≥ 0.70 | — | ⬜ | — | — |
| E5 | RRF 融合 Precision@5 | Precision@5 | ≥ 0.60 | — | ⬜ | — | — |

### 6.2 回归测试（每次提交运行）

- 测试集规模：25-30 固定问题
- 通过标准：Recall@5 ≥ 0.85、全部非空、来源有效、SSE 正确、无系统错误

### 6.3 压测（Phase 5 执行）

| ID | 场景 | 并发 | 持续时间 | P50 目标 | P99 目标 | 错误率 | 状态 | 执行日期 |
|:---|:---|:---|:---|:---|:---|:---|:---|:---|
| P1 | 基准 | 1 | — | ≤ 3s | ≤ 10s | 0% | ⬜ | — |
| P2 | 日常 | 5 | 5 min | ≤ 3s | ≤ 10s | ≤ 1% | ⬜ | — |
| P3 | 峰值 | 10 | 5 min | ≤ 3s | ≤ 10s | ≤ 1% | ⬜ | — |
| P4 | 极限 | 20 | 2 min | — | — | ≤ 5% | ⬜ | — |

---

## 7. 测试覆盖率目标

| 模块 | 覆盖率目标 | 当前值 | 备注 |
|:---|:---|:---|:---|
| `core/security.py` | ≥ 90% | ✅ 100% | 10 个测试全覆盖 |
| `core/exceptions.py` | ≥ 80% | ✅ 已覆盖 | E2001-E2013/E5005 等文档异常全部覆盖 |
| `services/auth_service.py` | ≥ 80% | ✅ 100% | 7 个测试全覆盖 |
| `api/auth.py` (接口测试) | ≥ 90% | ✅ 100% | 14 个测试全覆盖 |
| `api/document.py` (接口测试) | ≥ 90% | ✅ 100% | 47 个测试全覆盖（上传/批量/列表/详情/分块/删除/reprocess）|
| `schemas/auth.py` | ≥ 85% | ✅ 100% | 10 个测试全覆盖 |
| `models/` | ≥ 70% | ✅ 已覆盖 | U4.1-U4.3 已实现 |
| `ingest/lock.py` | ≥ 80% | ✅ 100% | 16 个测试全覆盖（幂等锁获取/重复拒绝/过期重入） |
| `rag/parser.py` | ≥ 80% | ✅ 100% | 35 个测试全覆盖（PDF/DOCX逐段容错/MD/TXT 解析 + 容错分级） |
| `rag/chunker.py` | ≥ 80% | ✅ 100% | 37 个测试全覆盖（分隔符优先级/偏移量页码追踪/中英文自适应token估算/重叠） |
| `rag/embedder.py` | ≥ 80% | ✅ 100% | 26 个测试全覆盖（DashScope API/重试/批量/响应解析/指数退避） |
| `core/storage.py` | ≥ 80% | ✅ 100% | 37 个测试全覆盖（sanitize_filename/generate_stored_filename/LocalStorage save/read/delete/空目录清理） |
| 前端 `utils/` | ≥ 80% | ⬜ | sse.js / markdown.js 待 Phase 3 |
| 前端组件 | ≥ 60% | ✅ 100% | LoginPage(9) + AppLayout(3) 全通过 |

---

## 8. 相关文档

- [测试策略文档](TESTING.md) — 6 层测试体系详细说明
- [开发排期](ROADMAP.md) — 各 Phase 测试任务与准入规则
- [开发指南](DEVELOPMENT.md) — 测试命令与项目结构
