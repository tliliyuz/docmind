# API — 接口文档

| 属性 | 值 |
|:---|:---|
| 文档版本 | v1.0 |
| 最后更新 | 2026-06-14 |

---

## 1. 通用约定

### 1.1 基础信息

| 项目 | 值 |
|:---|:---|
| Base URL | `http://localhost:8000/api` |
| 认证方式 | Bearer Token（JWT），登录后携带 `Authorization: Bearer <token>` |
| Content-Type | `application/json`（除文件上传使用 `multipart/form-data`） |
| 字符编码 | UTF-8 |

### 1.2 通用响应格式

> **`code` 字段类型约定**：`code` 字段**统一为字符串类型**。成功时 `"0"`，错误时 `"E1001"` 等错误码字符串。前端解析时勿作整数类型判断。

**成功响应**：

```json
{
  "code": "0",
  "message": "ok",
  "data": { ... }
}
```

**错误响应**：

```json
{
  "code": "E1001",
  "message": "知识库不存在",
  "detail": "kb_id=999 不存在或已被删除"
}
```

### 1.3 时间字段约定

所有 datetime 字段统一返回 ISO 8601 格式的 UTC 时间。

示例：

```json
{
  "created_at": "2026-06-09T12:00:00+00:00",
  "updated_at": "2026-06-09T12:00:00+00:00"
}
```

说明：
- `+00:00` 表示 UTC 时区
- `Z` 与 `+00:00` 在语义上等价
- 前端应使用标准 `Date` API 解析，不应手动补时区后缀

### 1.4 统一错误码

#### 知识库错误（E1xxx）

| 错误码 | HTTP 状态码 | 说明 |
|:---|:---|:---|
| E1001 | 404 | 知识库不存在 |
| E1002 | 409 | 知识库名称已存在（同一用户下名称不可重复） |

#### 文档错误（E2xxx）

| 错误码 | HTTP 状态码 | 说明 |
|:---|:---|:---|
| E2001 | 404 | 文档不存在 |
| E2002 | 415 | 文件格式不支持（仅支持 pdf/docx/md/txt） |
| E2003 | 400 | 文件大小超限（上限 50MB） |
| E2004 | 500 | 文档解析失败 |
| E2005 | 500 | 文档入库失败（Embedding/ChromaDB 写入异常） |
| E2006 | 500 | 存储错误（磁盘满 / IO 异常） |
| E2007 | 500 | 向量存储错误（ChromaDB 写入失败） |
| E2008 | 502 | Embedding 超时 / 限流（DashScope API 异常） |
| E2009 | 400 | 解析器错误（文档格式损坏、无法解析或无有效内容） |
| E2010 | 400 | 重新处理失败（非 FAILED/PARTIAL_FAILED 状态不允许 reprocess） |
| E2011 | 409 | 文档正在处理中（幂等锁冲突，重复触发被拒绝） |
| E2012 | 409 | force=true 但旧文档仍在处理中，无法覆盖 |
| E2013 | 409 | 文档名称已存在（kb_id + filename 冲突，需使用 force=true 覆盖） |

#### 会话错误（E3xxx）

| 错误码 | HTTP 状态码 | 说明 |
|:---|:---|:---|
| E3001 | 404 | 会话不存在 |
| E3002 | 403 | 无权访问此会话（不属于当前用户） |

#### 问答错误（E4xxx）

| 错误码 | HTTP 状态码 | 说明 |
|:---|:---|:---|
| E4001 | 400 | 知识库无可用文档（需先上传文档；仅统计 `completed` / `success_with_warnings` / `partial_failed` 状态） |
| E4002 | 502 | LLM 调用失败 |
| E4003 | 500 | 检索服务异常 |
| E4004 | 429 | LLM 调用频率超限 |
| E4005 | 400 | 问题内容为空 |
| E4006 | 200 | 元问题，无需检索（自动分流，返回固定模板响应） |

#### 认证错误（E5xxx）

| 错误码 | HTTP 状态码 | 说明 |
|:---|:---|:---|
| E5001 | 409 | 用户名已存在 |
| E5002 | 401 | 用户名或密码错误 |
| E5003 | 401 | Token 已过期 |
| E5004 | 401 | Token 无效或格式错误 |
| E5005 | 403 | 无权限执行此操作 |
| E5006 | 401 | Refresh Token 已过期 |
| E5007 | 401 | Refresh Token 已吊销 |
| E5008 | 401 | Refresh Token 无效或格式错误 |
| E5009 | 401 | Token 可能泄露（Rotation 检测到旧 token 被重用，已吊销全部会话） |
| E5010 | 401 | 用户已被禁用（登录/刷新/API 请求时用户 status=disabled） |

#### 用户管理错误（E7xxx）

| 错误码 | HTTP 状态码 | 说明 |
|:---|:---|:---|
| E7002 | 404 | 用户不存在 |
| E7003 | 400 | 不能修改自身（admin 不能修改自己的状态） |

#### 系统错误（E9xxx）

| 错误码 | HTTP 状态码 | 说明 |
|:---|:---|:---|
| E9001 | 500 | 服务器内部错误 |
| E9002 | 503 | 服务暂不可用 |
| E9003 | 422 | 请求参数校验失败 |
| E9004 | 429 | 请求频率超限 |

---

## 2. 认证接口

### POST `/api/auth/register`

**权限**：公开

**请求**：

```json
{
  "username": "zhangsan",
  "password": "mypassword123"
}
```

**响应** (201)：

```json
{
  "code": "0",
  "message": "注册成功",
  "data": {
    "id": 1,
    "username": "zhangsan",
    "role": "user",
    "created_at": "2026-05-11T10:00:00"
  }
}
```

### POST `/api/auth/login`

**权限**：公开

**请求**：

```json
{
  "username": "zhangsan",
  "password": "mypassword123"
}
```

**响应** (200)：

```json
{
  "code": "0",
  "message": "登录成功",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 900
  }
}
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| access_token | string | JWT 访问令牌，有效期 15 分钟 |
| refresh_token | string | JWT 刷新令牌，有效期 7 天（MySQL 持久化，支持 Rotation） |
| token_type | string | 固定 `bearer` |
| expires_in | int | access_token 有效期（秒），900 = 15 分钟 |

> **设计说明**：`access_token` 15 分钟短有效期降低泄露风险；`refresh_token` 7 天长有效期避免频繁登录。前端 Axios 拦截器自动刷新，用户无感。

### POST `/api/auth/refresh`

**权限**：公开（携带 refresh_token）

用 refresh_token 换取新的 token 对。每次刷新后旧 refresh_token 立即失效（Rotation）。

**请求**：

```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**响应** (200)：

```json
{
  "code": "0",
  "message": "Token 刷新成功",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 900
  }
}
```

**错误响应**：

| 场景 | 错误码 | HTTP 码 |
|:---|:---|:---|
| refresh_token 已过期（> 7 天） | E5006 | 401 |
| refresh_token 已被吊销（Rotation 或主动吊销） | E5007 | 401 |
| refresh_token 格式无效 | E5008 | 401 |
| 使用已吊销的旧 token 请求刷新（可能泄露） | E5009 | 401 |

> **泄露检测（E5009）**：当用户正常刷新后攻击者仍使用旧 refresh_token 请求刷新，说明 token 可能已泄露。此时系统吊销该用户所有 refresh_token，强制全部设备重新登录。

### POST `/api/auth/logout`

**权限**：user（需登录）

吊销当前 refresh_token，access_token 在短有效期后自然过期。

**请求**：

```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**响应** (200)：

```json
{
  "code": "0",
  "message": "已退出登录",
  "data": null
}
```

### PUT `/api/auth/password`

**权限**：user（需登录）

修改密码后吊销该用户全部 refresh_token，强制所有设备重新登录。

**请求**：

```json
{
  "old_password": "mypassword123",
  "new_password": "newpassword456"
}
```

**响应** (200)：

```json
{
  "code": "0",
  "message": "密码修改成功，所有设备已下线",
  "data": null
}
```

> **安全机制**：改密后吊销全部 refresh_token，防止密码被篡改后攻击者通过未过期的 refresh_token 继续访问。

---

## 3. 知识库接口

### POST `/api/knowledge-bases`

**权限**：user（需登录）

创建知识库。

**请求**：

```json
{
  "name": "公司内部知识库",
  "description": "包含 HR、IT、行政、业务等部门的制度文档",
  "visibility": "private"
}
```

| 字段 | 类型 | 必填 | 说明 |
|:---|:---|:---|:---|
| name | string | 是 | 知识库名称（≤ 50 字符） |
| description | string | 否 | 知识库描述 |
| visibility | string | 否 | `private` / `public`，默认 `private` |

**响应** (201)：

```json
{
  "code": "0",
  "message": "知识库创建成功",
  "data": {
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "name": "公司内部知识库",
    "description": "包含 HR、IT、行政、业务等部门的制度文档",
    "user_id": 1,
    "visibility": "private",
    "status": "active",
    "doc_count": 0,
    "chunk_count": 0,
    "created_at": "2026-05-11T10:30:00"
  }
}
```

### GET `/api/knowledge-bases`

**权限**：user（需登录）

获取当前用户的知识库列表（分页）。仅返回 `user_id == current_user` 的知识库，不包含其他用户的 public KB。

> 如需浏览所有公开知识库，使用 `GET /api/knowledge-bases/public`。

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|:---|:---|:---|:---|
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页条数，默认 20，最大 100 |

**响应** (200)：

```json
{
  "code": "0",
  "message": "ok",
  "data": {
    "total": 8,
    "page": 1,
    "page_size": 20,
    "items": [
      {
        "uuid": "550e8400-e29b-41d4-a716-446655440000",
        "name": "公司内部知识库",
        "description": "...",
        "user_id": 1,
        "visibility": "private",
        "status": "active",
        "doc_count": 5,
        "chunk_count": 128,
        "created_at": "2026-05-11T10:30:00",
        "updated_at": "2026-05-11T14:00:00"
      }
    ]
  }
}
```

### GET `/api/knowledge-bases/public`

**权限**：user（需登录）

获取所有公开知识库列表（分页），跨用户。用于「公共知识库」浏览入口。

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|:---|:---|:---|:---|
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页条数，默认 20，最大 100 |

**响应** (200)：

```json
{
  "code": "0",
  "message": "ok",
  "data": {
    "total": 3,
    "page": 1,
    "page_size": 20,
    "items": [
      {
        "uuid": "660e8400-e29b-41d4-a716-446655440001",
        "name": "IT 制度文档",
        "description": "VPN 配置、系统权限申请等",
        "user_id": 3,
        "username": "zhangsan",
        "visibility": "public",
        "status": "active",
        "doc_count": 12,
        "chunk_count": 256,
        "created_at": "2026-05-11T10:30:00",
        "updated_at": "2026-05-15T14:00:00"
      }
    ]
  }
}
```

> **注意**：此接口仅返回 `status=active` 且 `visibility=public` 的知识库。不返回 `deleting` 状态或 `private` 的 KB。

### GET `/api/knowledge-bases/selectable`

**权限**：user（需登录）

获取当前用户可用于问答的知识库列表，按所有权分组。用于前端知识库选择器（`<el-select>` + `<el-option-group>`）。

**响应** (200)：

```json
{
  "code": "0",
  "message": "ok",
  "data": {
    "mine": [
      {"uuid": "550e8400-e29b-41d4-a716-446655440000", "name": "HR制度", "visibility": "private", "doc_count": 5}
    ],
    "public": [
      {"uuid": "660e8400-e29b-41d4-a716-446655440001", "name": "IT规范", "username": "zhangsan", "doc_count": 12}
    ]
  }
}
```

| 分组 | 数据来源 | 说明 |
|:---|:---|:---|
| `mine` | 当前用户所有 `status=active` 且至少有 1 篇可检索文档的 KB | 可检索文档 = `completed` / `success_with_warnings` / `partial_failed`；不含 `deleting` 状态 |
| `public` | 其他用户的 `visibility=public` + `status=active` 且至少有 1 篇可检索文档的 KB | 不含当前用户自己的 KB（避免重复） |

> **设计意图**：前端直接使用分组数据渲染，无需自行 merge 或去重。后端统一控制权限 scope。接口仅返回有可检索文档的 KB，用户不会看到可选中但无法问答的 KB。

> **空知识库行为**：无任何可检索文档的 KB 不会出现在列表中。`doc_count` 字段为 KnowledgeBase 表的静态计数字段（含所有状态的文档），不代表可检索文档数。

### GET `/api/knowledge-bases/{uuid}`

**权限**：user（需登录，owner 或 admin 或 visibility=public 时可查看）

获取知识库详情。public KB 所有登录用户可查看，private KB 仅 owner 或 admin 可查看。

**路径参数**：

| 参数 | 类型 | 说明 |
|:---|:---|:---|
| uuid | string | 知识库 UUID |

**响应** (200)：同创建响应结构

### PUT `/api/knowledge-bases/{uuid}`

**权限**：user（需登录，仅创建者或 admin 可修改）

更新知识库名称、描述或可见性。

**路径参数**：

| 参数 | 类型 | 说明 |
|:---|:---|:---|
| uuid | string | 知识库 UUID |

**请求**：

```json
{
  "name": "公司内部知识库（更新版）",
  "description": "更新后的描述",
  "visibility": "public"
}
```

| 字段 | 类型 | 必填 | 说明 |
|:---|:---|:---|:---|
| name | string | 否 | 知识库名称 |
| description | string | 否 | 知识库描述 |
| visibility | string | 否 | `private` / `public` |

**响应** (200)：

```json
{
  "code": "0",
  "message": "知识库更新成功",
  "data": {
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "name": "公司内部知识库（更新版）",
    "description": "更新后的描述",
    "user_id": 1,
    "visibility": "public",
    "status": "active",
    "doc_count": 5,
    "chunk_count": 128,
    "created_at": "2026-05-11T10:30:00",
    "updated_at": "2026-05-11T15:00:00"
  }
}
```

### DELETE `/api/knowledge-bases/{uuid}`

**权限**：user（需登录，仅创建者或 admin 可删除）

**路径参数**：

| 参数 | 类型 | 说明 |
|:---|:---|:---|
| uuid | string | 知识库 UUID |

删除知识库及其下所有文档和向量数据（异步批量清理）。

> **Phase 2 实现策略**：当前阶段 DELETE 接口仅标记 `status=deleting` 并返回 202，实际 ChromaDB 向量清理 + 磁盘文件删除 + 物理 DELETE 由后续 Celery 异步任务实现。标记 deleting 后该 KB 拒绝新的上传、检索、reprocess 操作。

**响应** (202)：

```json
{
  "code": "0",
  "message": "知识库删除任务已提交",
  "data": { "kb_uuid": "550e8400-e29b-41d4-a716-446655440000", "status": "deleting" }
}
```

**异步清理流程**：

```
DELETE /api/knowledge-bases/{uuid}
↓
kb.status = deleting（拒绝新的上传/检索/reprocess）
↓ 返回 202 Accepted
↓
Celery Worker（异步）:
  1. collection.delete(where={"kb_id": kb_id})  — 清理 ChromaDB 向量
  2. 批量删除磁盘文件（uploads/{kb_id}/ 目录）
  3. DELETE FROM knowledge_bases WHERE id=?  — 物理删除 KB 记录
     └─ FK ON DELETE CASCADE 自动级联删除 documents → chunks
↓
完成（KB 记录已物理删除，FK CASCADE 保证子记录同步清理）
```

**失败恢复**：Worker crash 后若 `status=deleting`，ChromaDB delete 幂等可重试。MySQL 物理 DELETE 前 crash 则重试清理；DELETE 后 crash 无需恢复（记录已清理）。

> **约束**：知识库删除采用 KB 级异步批量清理。即使在单 Collection 架构下，KB 删除也**禁止**使用 API 级联同步删除，必须走 Celery 异步任务以保证大数据量场景下接口不超时。

---

## 4. 文档接口

### 4.0 文档状态枚举

所有接口统一使用 `DocumentStatus`（`str, Enum`），前后端共享：

| 枚举值 | 数据库值 | 说明 | 终态？ |
|:---|:---|:---|:---|
| `UPLOADED` | `uploaded` | 文件已接收，等待入库 | ❌ |
| `PARSING` | `parsing` | 文档解析中 | ❌ |
| `CHUNKING` | `chunking` | 智能分块中 | ❌ |
| `EMBEDDING` | `embedding` | 向量化中 | ❌ |
| `VECTOR_STORING` | `vector_storing` | ChromaDB 写入中 | ❌ |
| `COMPLETED` | `completed` | 全部成功 | ✅ |
| `SUCCESS_WITH_WARNINGS` | `success_with_warnings` | 部分页警告但可接受（失败 < 20%） | ✅ |
| `PARTIAL_FAILED` | `partial_failed` | 部分失败需人工确认（失败 20%-50%） | ✅ |
| `FAILED` | `failed` | 完全失败（失败 > 50%） | ✅ |
| `DELETING` | `deleting` | 异步清理进行中（随后物理删除行） | ❌ |

**终态集合**（`TERMINAL_STATUSES`）：`{completed, success_with_warnings, partial_failed, failed}`

**关键函数**：
```python
def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATUSES
```

- **前端轮询终点**：`is_terminal(status) → True` 停止轮询
- **Celery 幂等**：终态任务拒绝重复入队（需显式 `force=true` 或 `reprocess`）
- **reprocess 接口**：仅 `partial_failed` / `failed` 允许触发

---

### POST `/api/knowledge-bases/{kb_uuid}/documents`

**权限**：user（需登录，仅 owner）

上传文档（`multipart/form-data`），支持 `.pdf` `.docx` `.md` `.txt`。不支持 `.doc`（请先转换为 `.docx`）。

**路径参数**：

| 参数 | 类型 | 说明 |
|:---|:---|:---|
| kb_uuid | string | 知识库 UUID |

**请求**：multipart/form-data

| 字段 | 类型 | 必填 | 说明 |
|:---|:---|:---|:---|
| file | file | 是 | 文档文件（≤ 50MB） |
| force | bool | 否 | 同名文档存在时是否覆盖（默认 false） |

**上传行为规则**：

| 场景 | 默认行为 | `force=true` |
|:---|:---|:---|
| 同名文档不存在 | 正常创建 | 同左 |
| 同名文档存在且终态 | 拒绝，返回 E2013「文档名称已存在」 | 异步删除旧文档 → 创建新文档 |
| 同名文档存在且处理中 | 拒绝，返回 E2011「文档正在处理中」 | 拒绝，返回 E2012「旧文档处理中无法覆盖」 |

**`force=true` 覆盖流程**：
```
检查旧文档状态 → 处理中则拒绝(E2012)
              → 终态则继续
异步删除旧文档（status=deleting + Celery 清理向量/文件）
创建新 document 记录（新 doc_id）
触发新入库任务
```

**幂等性**：基于 Redis 分布式锁 `idempotency_key:{doc_id}:ingest`（TTL=600s）。处理中文档重复提交 → 返回 E2011。

**响应** (201)：

```json
{
  "code": "0",
  "message": "文档上传成功，已加入处理队列",
  "data": {
    "uuid": "770e8400-e29b-41d4-a716-446655440002",
    "kb_uuid": "550e8400-e29b-41d4-a716-446655440000",
    "filename": "入职指南.pdf",
    "file_type": "pdf",
    "file_size": 204800,
    "status": "uploaded"
  }
}
```

---

### POST `/api/knowledge-bases/{kb_uuid}/documents/batch-upload`

**路径参数**：

| 参数 | 类型 | 说明 |
|:---|:---|:---|
| kb_uuid | string | 知识库 UUID |

**权限**：user（需登录，仅 owner）

批量上传文档（`multipart/form-data`，多文件）。适合企业初始化知识库场景。

**请求**：multipart/form-data

| 字段 | 类型 | 必填 | 说明 |
|:---|:---|:---|:---|
| files | file[] | 是 | 多文件（每个 ≤ 50MB） |

**响应** (200) — 部分成功，非事务性。前端**必须**检查 `data.failed` 数组，不能仅依赖 HTTP 状态码判断是否全部成功：

```json
{
  "code": "0",
  "message": "批量上传完成（3 个文件，成功 2 个，失败 1 个）",
  "data": {
    "success": [
      { "uuid": "770e8400-e29b-41d4-a716-446655440002", "filename": "入职指南.pdf", "status": "uploaded" },
      { "uuid": "880e8400-e29b-41d4-a716-446655440003", "filename": "报销制度.md", "status": "uploaded" }
    ],
    "failed": [
      { "filename": "旧文档.doc", "reason": "E2002: 不支持 .doc 格式（扩展名 .doc 不在允许列表中）" },
      { "filename": "入职指南.pdf", "reason": "E2013: 文档名称已存在（kb_id=1，使用 force=true 可覆盖）" }
    ]
  }
}
```

> **message 约定**：批量操作 message 必须包含成功/失败计数摘要（格式：`批量上传完成（N 个文件，成功 M 个，失败 K 个）`），便于前端在不解析 data 的情况下快速感知是否有失败项。

---

### POST `/api/knowledge-bases/{kb_uuid}/documents/{doc_uuid}/reprocess`

**权限**：user（仅知识库 owner/admin）

重新处理失败或部分失败的文档。

**路径参数**：

| 参数 | 类型 | 说明 |
|:---|:---|:---|
| kb_uuid | string | 知识库 UUID |
| doc_uuid | string | 文档 UUID |

**限制**：仅 `partial_failed` / `failed` 终态允许 reprocess。其他状态返回 E2010。

**请求**：

```json
{}

```

**响应** (200)：

```json
{
  "code": "0",
  "message": "重新处理任务已提交",
  "data": { "doc_uuid": "770e8400-e29b-41d4-a716-446655440002", "status": "parsing" }
}
```

**处理流程**：清理旧 chunk 记录 + 旧 ChromaDB 向量 → 重置 status → 重新进入 Celery 入库队列。

---

### GET `/api/knowledge-bases/{kb_uuid}/documents`

**权限**：user（需登录）；public 知识库允许所有登录用户只读访问；private 知识库仅 owner 或 admin

获取知识库下的文档列表（支持筛选、排序和分页）。

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|:---|:---|:---|:---|
| status | string | 否 | 按状态过滤（如 `completed`, `failed`） |
| filename | string | 否 | 按文件名模糊搜索（LIKE %xxx%） |
| sort_by | string | 否 | 排序字段，默认 `created_at` |
| order | string | 否 | `asc` / `desc`，默认 `desc` |
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页条数，默认 20，最大 100 |

**响应** (200)：

```json
{
  "code": "0",
  "message": "ok",
  "data": {
    "total": 15,
    "page": 1,
    "page_size": 20,
    "items": [
      {
        "uuid": "770e8400-e29b-41d4-a716-446655440002",
        "filename": "入职指南.pdf",
        "file_type": "pdf",
        "file_size": 204800,
        "status": "completed",
        "chunk_count": 24,
        "created_at": "2026-05-11T10:35:00",
        "updated_at": "2026-05-11T10:37:00"
      }
    ]
  }
}
```

---

### GET `/api/knowledge-bases/{kb_uuid}/documents/{doc_uuid}`

**路径参数**：

| 参数 | 类型 | 说明 |
|:---|:---|:---|
| kb_uuid | string | 知识库 UUID |
| doc_uuid | string | 文档 UUID |

**权限**：user（需登录）；public 知识库允许所有登录用户只读访问；private 知识库仅 owner 或 admin

获取单个文档详情（含入库状态）。

**响应** (200)：

```json
{
  "code": "0",
  "message": "ok",
  "data": {
    "uuid": "770e8400-e29b-41d4-a716-446655440002",
    "kb_uuid": "550e8400-e29b-41d4-a716-446655440000",
    "filename": "入职指南.pdf",
    "file_type": "pdf",
    "file_size": 204800,
    "status": "completed",
    "chunk_count": 24,
    "error_msg": null,
    "created_at": "2026-05-11T10:35:00",
    "updated_at": "2026-05-11T10:37:00"
  }
}
```

---

### GET `/api/knowledge-bases/{kb_uuid}/documents/{doc_uuid}/chunks`

**路径参数**：

| 参数 | 类型 | 说明 |
|:---|:---|:---|
| kb_uuid | string | 知识库 UUID |
| doc_uuid | string | 文档 UUID |

**权限**：user（需登录）；public 知识库允许所有登录用户只读访问；private 知识库仅 owner 或 admin

查看文档的分块列表（支持分页）。

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|:---|:---|:---|:---|
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页条数，默认 20，最大 100 |

**生产环境安全**：默认 chunk content 截断至 200 字符（`preview` 字段），`DEBUG_CHUNK_FULL=true` 时返回完整 `content`。

**响应** (200)：

```json
{
  "code": "0",
  "message": "ok",
  "data": {
    "total": 150,
    "page": 1,
    "page_size": 20,
    "items": [
      {
        "id": 1,
        "chunk_index": 0,
        "preview": "入职指南\n欢迎加入公司！...",
        "token_count": 480,
        "metadata": { "page": 1 }
      }
    ]
  }
}
```

---

### DELETE `/api/knowledge-bases/{kb_uuid}/documents/{doc_uuid}`

**权限**：user（需登录，仅创建者或 admin）

删除文档及其分块数据（异步清理 MySQL + ChromaDB + 磁盘文件）。

**路径参数**：

| 参数 | 类型 | 说明 |
|:---|:---|:---|
| kb_uuid | string | 知识库 UUID |
| doc_uuid | string | 文档 UUID |

**响应** (202)：

```json
{
  "code": "0",
  "message": "文档删除任务已提交",
  "data": { "doc_uuid": "770e8400-e29b-41d4-a716-446655440002", "status": "deleting" }
}
```

**异步清理流程**：
```
status = deleting
↓ 返回 202 Accepted
↓
Celery Worker（异步）:
  1. collection.delete(where={"doc_id": doc_id})  — 清理 ChromaDB 向量
  2. 删除磁盘文件（uploads/{kb_id}/{doc_id}/ 目录）
  3. DELETE FROM documents WHERE id=?  — 物理删除文档记录
     └─ FK ON DELETE CASCADE 自动级联删除 chunks
↓
完成（文档记录已物理删除，FK CASCADE 保证 chunks 同步清理）
```

> **禁止**接口同步删除磁盘文件/向量，避免大文档场景接口超时。

---

## 5. 会话接口

### POST `/api/conversations`

**权限**：user（需登录）

创建新会话。

**请求**：

```json
{
  "kb_uuid": "550e8400-e29b-41d4-a716-446655440000",
  "title": "关于报销流程"
}
```

**响应** (201)：

```json
{
  "code": "0",
  "message": "会话创建成功",
  "data": {
    "uuid": "990e8400-e29b-41d4-a716-446655440004",
    "user_id": 1,
    "kb_uuid": "550e8400-e29b-41d4-a716-446655440000",
    "title": "关于报销流程",
    "kb_status": "active",
    "kb_name": "公司内部知识库",
    "original_kb_id": null,
    "original_kb_uuid": null,
    "original_kb_name": null,
    "message_count": 0,
    "last_message_at": null,
    "created_at": "2026-05-11T11:00:00",
    "updated_at": "2026-05-11T11:00:00"
  }
}
```

### GET `/api/conversations`

**权限**：user（需登录）

获取当前用户的会话列表（分页），按 last_message_at DESC 排序。

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|:---|:---|:---|:---|
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页条数，默认 20，最大 100 |

**响应** (200)：

```json
{
  "code": "0",
  "message": "ok",
  "data": {
    "total": 12,
    "page": 1,
    "page_size": 20,
    "items": [
      {
        "uuid": "990e8400-e29b-41d4-a716-446655440004",
        "kb_uuid": "550e8400-e29b-41d4-a716-446655440000",
        "title": "关于报销流程",
        "kb_status": "active",
        "kb_name": "公司内部知识库",
        "message_count": 8,
        "last_message_at": "2026-05-11T14:30:00",
        "created_at": "2026-05-11T11:00:00",
        "updated_at": "2026-05-11T14:30:00"
      }
    ]
  }
}
```

### GET `/api/conversations/{uuid}`

**权限**：user（需登录，仅所有者可查看）

获取会话详情（含消息历史）。

**路径参数**：

| 参数 | 类型 | 说明 |
|:---|:---|:---|
| uuid | string | 会话 UUID |

**响应** (200)：

```json
{
  "code": "0",
  "message": "ok",
  "data": {
    "uuid": "990e8400-e29b-41d4-a716-446655440004",
    "user_id": 1,
    "kb_uuid": "550e8400-e29b-41d4-a716-446655440000",
    "title": "关于报销流程",
    "kb_status": "active",
    "kb_name": "公司内部知识库",
    "message_count": 2,
    "last_message_at": "2026-05-11T11:00:05",
    "created_at": "2026-05-11T11:00:00",
    "updated_at": "2026-05-11T11:00:05",
    "messages": [
      {
        "id": 1,
        "role": "user",
        "content": "报销差旅费需要哪些材料？",
        "created_at": "2026-05-11T11:00:00"
      },
      {
        "id": 2,
        "role": "assistant",
        "content": "根据公司报销制度，差旅费报销需要...",
        "thinking_content": null,
        "created_at": "2026-05-11T11:00:05"
      }
    ]
  }
}
```

### PUT `/api/conversations/{uuid}`

**权限**：user（需登录，仅所有者）

重命名会话。

**路径参数**：

| 参数 | 类型 | 说明 |
|:---|:---|:---|
| uuid | string | 会话 UUID |

**请求**：

```json
{
  "title": "差旅报销相关问答"
}
```

### DELETE `/api/conversations/{uuid}`

**权限**：user（需登录，仅所有者）

删除会话及其全部消息。

**路径参数**：

| 参数 | 类型 | 说明 |
|:---|:---|:---|
| uuid | string | 会话 UUID |

**响应** (200)：

```json
{
  "code": "0",
  "message": "会话已删除",
  "data": null
}
```

### 5.1 会话与知识库生命周期解耦（孤儿会话处理）

会话（Conversation）的生命周期**独立于**知识库（Knowledge Base）。知识库被删除后，关联的会话不会被级联删除，而是成为「孤儿会话」继续存在。

**设计原则**：

- **会话保留**：用户的历史对话记录具有长期价值（复盘、审计、知识沉淀），不因知识库删除而丢失
- **数据完整性**：会话记录（含消息历史）永久保留，仅当用户主动删除会话时才清理
- **前端提示**：孤儿会话在列表中通过 `kb_status` 和 `kb_name` 字段标识，前端应展示友好提示（如「关联知识库已删除」）

**孤儿会话状态**：

| 场景 | `kb_id` | `original_kb_id` | `original_kb_uuid` | `kb_status` | `kb_name` | 前端行为 |
|:---|:---|:---|:---|:---|:---|:---|
| 知识库正常 | `1` | `null` | `null` | `"active"` | `"公司内部知识库"` | 正常展示，可继续问答 |
| 知识库已删除 | `null` | `1` | `"550e8400-..."` | `"deleted"` | `"公司内部知识库"` | 展示 Banner「关联知识库已删除」，禁止继续问答 |
| 知识库不可访问（权限变更） | `1` | `null` | `"unavailable"` | `"公司内部知识库"` | 展示提示「知识库不可访问」，禁止继续问答 |
| 无关联知识库 | `null` | `null` | `null` | `null` | 正常展示（独立会话） |

**后端实现**：

- 会话列表/详情接口通过 `selectinload(Conversation.knowledge_base)` 加载 KB 关系，`_enrich_kb_status()` 动态计算 `kb_status` / `kb_name`
- 知识库删除时 FK `ON DELETE SET NULL` 自动清空 `kb_id`；Celery 任务在物理删除前批量备份 `original_kb_id` / `original_kb_uuid` / `original_kb_name`
- 问答接口校验：若 `kb_status != "active"`，拒绝新消息并返回错误提示

> **注意**：`kb_status` 和 `kb_name` 是**动态计算字段**（非数据库存储），`_enrich_kb_status()` 根据 `kb_id` + `original_kb_id` 实时判断。`original_kb_uuid` 为持久化字段，由 Celery 在 KB 物理删除前同步备份。

---

## 6. 问答接口（核心）

> **SSE 实现方式**：手动 `StreamingResponse`（非 `sse-starlette`），完全控制事件序列。每 15 秒发送 `: ping\n\n` 注释帧（SSE 心跳）保持连接，防止 Nginx/Cloudflare 代理超时断连。浏览器忽略注释帧。

> **错误流程说明**：连接建立前的参数校验错误（如 422/E9003、404/E1001）直接返回 HTTP JSON 响应；SSE 连接成功建立后的检索/LLM 错误通过 `event: error` 发送，连接仍正常关闭。

> **SSE 中断时的消息持久化**（Phase 3）：
> - Phase 3 不持久化未完成 assistant 消息。
> - user message 在请求开始时立即写库。
> - assistant message 仅在 LLM 正常完成后一次性写入。
> - 客户端 abort / 网络中断时：
>   - 前端保留当前已渲染内容（仅内存态）
>   - 后端丢弃未完成 assistant message

> **LLM 失败时 sources 仍发送**：检索结果在 LLM 调用前已完成，即使 LLM 失败（E4002），也先发送 `event: sources`（含全部 chunk，因无 `assistant_content` 无法做引用过滤），再发送 `event: error`。注意：若检索无结果则 `sources` 事件不发送。

> **sources 引用过滤**：正常流程下，`event: sources` 仅发送 LLM 回答中实际通过 `[来源N]` 引用的 chunk。LLM 未引用任何来源时（含「未找到相关信息」场景），sources 事件不发送。此规则确保前端展示的引用来源与 LLM 回答中的引用标注精确对应。

> **意图识别（3 类分流）**：Phase 5 实现 LLM 意图分类器（`classify_intent()`），将用户问题分为三类：① **KNOWLEDGE** — 走完整 RAG 链路（检索→RRF→Rerank→Evidence Highlight→Prompt→LLM），发送 `event: sources`；② **CASUAL** — 跳过检索，使用闲谈 System Prompt + 历史消息直接调 LLM，不发送 `event: sources`；③ **META** — 不调 LLM，直接返回固定模板响应（毫秒级），`event: meta` 后紧跟 `event: message`（固定内容）+ `event: finish`。LLM 分类失败时降级回退 Phase 3 正则 stopgap。详见 RAG_PIPELINE.md §6。

### POST `/api/chat`

**权限**：user（需登录）

发送问题，SSE 流式返回答案。这是系统的核心接口。

**请求**：

```json
{
  "conversation_id": null,
  "kb_id": "550e8400-e29b-41d4-a716-446655440000",
  "question": "报销流程是怎样的？",
  "deep_thinking": false
}
```

| 字段 | 类型 | 必填 | 说明 |
|:---|:---|:---|:---|
| conversation_id | string / null | 否 | 会话 UUID，新对话传 null |
| kb_id | string | 是 | 目标知识库 UUID |
| question | string | 是 | 用户问题（≤ 2000 字符） |
| deep_thinking | bool | 否 | 是否启用深度思考模式，默认 false。后端映射：true→`extra_body={"thinking":{"type":"enabled"}}` 并传 `reasoning_effort="high"`；false→`extra_body={"thinking":{"type":"disabled"}}` 且不传 `reasoning_effort`。**注意**：DeepSeek 默认 thinking=enabled，false 时必须显式传 disabled |

**响应**：`text/event-stream` (SSE)

### 6.1 SSE 事件完整格式

#### `event: meta` — 元信息

服务端处理开始，返回会话和任务标识。

```
event: meta
data: {"conversation_id": "990e8400-e29b-41d4-a716-446655440004", "task_id": "550e8400-e29b-41d4-a716-446655440000"}
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| conversation_id | string (UUID) | 会话 UUID（新对话自动创建） |
| task_id | string (UUID) | 本次问答的任务 ID |

#### `event: thinking` — 思考过程（可选）

仅当 `deep_thinking: true` 时输出。包含 LLM 的深度思考链路（来自 DeepSeek `reasoning_content`）。**不落库**（`messages.thinking_content = null`），仅前端实时展示，刷新页面后丢失。

> **设计说明**：thinking_content 可能包含系统 prompt/chain 信息且内容巨大，不使用数据库存储。`messages.thinking_content` 字段已预留但 Phase 3 始终写入 null。
> **DeepSeek API**：`deep_thinking=true` → `extra_body={"thinking":{"type":"enabled"}}` + `reasoning_effort="high"`；`false` → `extra_body={"thinking":{"type":"disabled"}}`，不传 `reasoning_effort`

```
event: thinking
data: {"delta": "用户询问报销流程，我需要从知识库中找到报销相关的文档..."}
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| delta | string | 思考内容增量片段（来自 DeepSeek `reasoning_content`） |

#### `event: message` — 答案内容

LLM 生成的答案，逐 token 流式输出。

```
event: message
data: {"delta": "根据公司报销制度，差旅报销需要提交以下材料：\n\n1. **差旅申请单**（需提前审批）\n2. **交通票据**（机票行程单/火车票）..."}
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| delta | string | 答案内容增量片段（Markdown 格式） |

#### `event: sources` — 引用来源

LLM 实际引用的文档分块，用于溯源。在所有 message 事件之后发送。**仅 KNOWLEDGE 意图发送此事件**（CASUAL/META 意图跳过检索，无 sources）。

**发送规则**：
1. **意图过滤**：仅 KNOWLEDGE 意图走完整 RAG 链路，CASUAL/META 意图不发送 sources
2. **引用过滤**：从 LLM 回答中提取 `[来源N]` 引用编号，仅发送被实际引用的 chunk（而非进入 Prompt 的全部 chunk）
3. **未找到抑制**：LLM 回答首句声明"未找到相关信息"时，不发送此事件
4. **零引用抑制**：LLM 未引用任何 `[来源N]` 时，不发送此事件
5. **检索无结果**：不发送此事件
6. **LLM 失败**：检索结果在 LLM 调用前已完成，即使 LLM 失败也先发送 sources（含全部 chunk），再发送 error

```
event: sources
data: {"chunks": [{"chunk_index": 1, "doc_id": 5, "doc_name": "报销制度.md", "content": "差旅报销需提交：1. 差旅申请单...", "score": 0.92, "page": 3, "preview_text": "差旅报销需提交：1. 差旅申请单 2. 交通票据...", "preview_range": {"start": 0, "end": 200}, "highlight_start": 0, "highlight_end": 18}]}
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| chunks | array | 引用来源数组（仅含 LLM 实际引用的 chunk） |
| chunks[].chunk_index | int | 来源编号，与 LLM 回答中的 `[来源N]` 一一对应（编号保持与 Prompt 一致，不重新编号） |
| chunks[].doc_id | int | 文档 ID |
| chunks[].doc_name | string | 文档名称 |
| chunks[].content | string | 分块文本（完整内容，向前兼容） |
| chunks[].score | float | RRF/Rerank 得分 |
| chunks[].page | int \| null | 页码（如有） |
| chunks[].preview_text | string \| null | Evidence 定位后的预览文本（matched_sentence ±100 字符窗口） |
| chunks[].preview_range | object \| null | 预览窗口在 content 中的起止位置 `{start, end}` |
| chunks[].highlight_start | int \| null | 高亮区间在 preview_text 内的起始偏移（含），前端纯 slice 渲染 |
| chunks[].highlight_end | int \| null | 高亮区间在 preview_text 内的结束偏移（不含），前端纯 slice 渲染 |

#### `event: finish` — 完成

全部内容输出完毕。首轮问答时 `title` 为自动生成的会话标题（截取用户问题前 12 字），后续轮次不返回 title。

```
event: finish
data: {"message_id": 2, "title": "入职需要开通哪些账号", "token_usage": {"prompt": 1500, "completion": 350, "total": 1850}}
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| message_id | int | 保存的回答消息 ID |
| title | string | 自动生成的对话标题（仅首轮时返回，后续为 null） |
| token_usage | object | Token 消耗统计 |

#### `event: error` — 错误

检索或 LLM 调用失败时发送。

```
event: error
data: {"code": "E4002", "message": "LLM 调用失败", "detail": "DeepSeek API 返回状态码 500，已重试 3 次"}
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| code | string | 错误码（见 §1.4） |
| message | string | 用户可读的错误描述 |
| detail | string | 技术细节（可选，仅开发环境返回） |

---

## 7. 管理后台接口

> **实现状态**：Phase 5 实现。后端 `app/api/admin.py` + `app/services/admin_service.py` + `app/schemas/admin.py`。
> 权限：所有 `/api/admin/*` 端点要求 `role=admin`，非 admin 返回 `403 E5005`。
> 前端 `/admin/*` 页面在 Phase 2.3.3 已完成占位开发，Phase 5 对接真实数据。

### 7.1 通用约定

| 项目 | 值 |
|:---|:---|
| 权限 | `role=admin`（通过 `require_admin` 依赖注入校验） |
| 非 admin 响应 | `403 {"code": "E5005", "message": "无权限执行此操作"}` |
| 分页 | `page`（默认 1）+ `page_size`（默认 20，最大 100） |
| 排序 | `sort_by` + `order`（`asc` / `desc`） |

---

### GET `/api/admin/stats`

获取系统全局统计概览。

**响应** (200)：

```json
{
  "code": "0",
  "message": "ok",
  "data": {
    "user_count": 12,
    "kb_count": 5,
    "doc_count": 45,
    "chunk_count": 2340,
    "conversation_count": 89,
    "message_count": 520,
    "storage_bytes": 52428800
  }
}
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| `user_count` | int | 注册用户总数 |
| `kb_count` | int | 知识库总数（含 private+public，不含已删除） |
| `doc_count` | int | 文档总数（所有状态） |
| `chunk_count` | int | 分块总数（所有 KB 合计） |
| `conversation_count` | int | 会话总数 |
| `message_count` | int | 消息总数 |
| `storage_bytes` | int | 存储空间占用（字节，磁盘文件大小合计） |

> **实现要点**：使用单次 `SELECT COUNT(*)` + `SUM()` 聚合查询，避免 N+1。统计数据允许一定延迟（Redis 缓存 60s 可选）。
> **性能注意**：`message_count` 和 `conversation_count` 可能随数据增长变慢，后续可在 `messages` 和 `conversations` 表上建立 count 优化索引或使用近似计数。

---

### GET `/api/admin/knowledge-bases`

获取全部知识库列表（跨用户管理视图），含 owner 信息和统计。

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|:---|:---|:---|:---|
| `page` | int | 否 | 页码，默认 1 |
| `page_size` | int | 否 | 每页条数，默认 20，最大 100 |
| `user_id` | int | 否 | 按 owner 过滤 |
| `status` | string | 否 | 按状态过滤（`active` / `deleting`） |
| `visibility` | string | 否 | 按可见性过滤（`private` / `public`）。默认不过滤，admin 可查看所有 |
| `search` | string | 否 | 按名称模糊搜索 |

**响应** (200)：

```json
{
  "code": "0",
  "message": "ok",
  "data": {
    "total": 12,
    "page": 1,
    "page_size": 20,
    "items": [
      {
        "uuid": "550e8400-e29b-41d4-a716-446655440000",
        "name": "公司内部知识库",
        "description": "包含 HR、IT、行政等部门的制度文档",
        "visibility": "public",
        "user_id": 3,
        "username": "zhangsan",
        "status": "active",
        "doc_count": 15,
        "chunk_count": 340,
        "created_at": "2026-05-11T10:30:00+00:00",
        "updated_at": "2026-05-15T14:00:00+00:00"
      }
    ]
  }
}
```

> **前端标识约定**：`visibility=private` 的知识库在前端列表中以 🔒 图标或「私有」标签标注，提示 admin 此为敏感内容（审计可见但应谨慎操作）。

---

### GET `/api/admin/documents`

获取全部文档列表（跨知识库视图），含 KB 名称和 owner 信息。

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|:---|:---|:---|:---|
| `kb_id` | string | 否 | 按知识库 UUID 过滤 |
| `page` | int | 否 | 页码，默认 1 |
| `page_size` | int | 否 | 每页条数，默认 20，最大 100 |
| `status` | string | 否 | 按状态过滤（见 `DocumentStatus` 枚举） |
| `filename` | string | 否 | 按文件名模糊搜索 |
| `sort_by` | string | 否 | 排序字段，默认 `created_at` |
| `order` | string | 否 | `asc` / `desc`，默认 `desc` |

**响应** (200)：

```json
{
  "code": "0",
  "message": "ok",
  "data": {
    "total": 45,
    "page": 1,
    "page_size": 20,
    "items": [
      {
        "uuid": "770e8400-e29b-41d4-a716-446655440002",
        "kb_uuid": "550e8400-e29b-41d4-a716-446655440000",
        "kb_name": "公司内部知识库",
        "kb_visibility": "public",
        "owner_id": 3,
        "owner_username": "zhangsan",
        "filename": "入职指南.pdf",
        "file_type": "pdf",
        "file_size": 204800,
        "status": "completed",
        "current_stage": null,
        "chunk_count": 24,
        "error_message": null,
        "created_at": "2026-05-11T10:35:00+00:00",
        "updated_at": "2026-05-11T10:36:00+00:00"
      }
    ]
  }
}
```

> **与普通用户文档列表的区别**：Admin 文档列表额外返回 `kb_name` / `kb_visibility` / `owner_id` / `owner_username` 字段，便于跨库审计。普通用户仅能看到自己 KB 下的文档（不含跨用户信息）。

---

### 7.4 实现文件

```
backend/app/schemas/admin.py           ← 新建：AdminStatsResponse / AdminKBListResponse / AdminDocListResponse
backend/app/services/admin_service.py  ← 新建：get_stats() / list_all_kbs() / list_all_documents()
backend/app/api/admin.py               ← 修改：3 个端点 + router（prefix="/api/admin"）
backend/app/main.py                    ← 修改：注册 admin_router
```

---

### 7.5 Trace 链路追踪接口

> **实现状态**：已实现（Phase 5）。
> **权限**：所有 `/api/admin/traces/*` 端点要求 `role=admin`。

#### GET `/api/admin/traces`

获取 Trace 列表（分页+筛选）。

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|:---|:---|:---|:---|
| `page` | int | 否 | 页码，默认 1 |
| `page_size` | int | 否 | 每页条数，默认 20，最大 100 |
| `user_id` | int | 否 | 按用户筛选 |
| `status` | string | 否 | success / error / partial |
| `intent_type` | string | 否 | KNOWLEDGE / CASUAL / META |
| `response_mode` | string | 否 | RAG / DIRECT_LLM / META / CASUAL / FALLBACK |
| `start_date` | string | 否 | 开始时间（ISO 8601） |
| `end_date` | string | 否 | 结束时间（ISO 8601） |
| `search` | string | 否 | 按问题模糊搜索 |

**响应** (200)：

```json
{
  "code": "0",
  "message": "ok",
  "data": {
    "total": 1520,
    "page": 1,
    "page_size": 20,
    "items": [
      {
        "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "user_id": 3,
        "username": "zhangsan",
        "conversation_uuid": "990e8400-e29b-41d4-a716-446655440004",
        "kb_uuid": "550e8400-e29b-41d4-a716-446655440000",
        "kb_name": "公司内部知识库",
        "question": "报销流程是怎样的？",
        "status": "success",
        "intent_type": "KNOWLEDGE",
        "intent_method": "llm_flash",
        "response_mode": "RAG",
        "total_duration_ms": 2892,
        "created_at": "2026-06-12T10:30:00+00:00"
      }
    ]
  }
}
```

#### GET `/api/admin/traces/{trace_id}`

获取 Trace 详情（含各阶段 JSON 详情）。

**响应** (200)：

```json
{
  "code": "0",
  "message": "ok",
  "data": {
    "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "user_id": 3,
    "username": "zhangsan",
    "conversation_uuid": "990e8400-e29b-41d4-a716-446655440004",
    "conversation_title": "报销流程咨询",
    "kb_uuid": "550e8400-e29b-41d4-a716-446655440000",
    "kb_name": "公司内部知识库",
    "question": "报销流程是怎样的？",
    "status": "success",
    "intent_type": "KNOWLEDGE",
    "intent_method": "llm_flash",
    "response_mode": "RAG",
    "total_duration_ms": 2892,
    "intent": {
      "span_name": "intent",
      "start_time": "2026-06-12T10:30:00.000+00:00",
      "duration_ms": 1200,
      "status": "success",
      "intent_type": "KNOWLEDGE",
      "method": "llm_flash",
      "metadata": {"model": "deepseek-v4-flash", "confidence": null}
    },
    "rewrite": {
      "span_name": "rewrite",
      "start_time": "2026-06-12T10:30:00.012+00:00",
      "duration_ms": 320,
      "status": "success",
      "original_question": "报销流程是怎样的？",
      "rewritten_question": null,
      "metadata": {"model": "deepseek-v4-flash", "input_tokens": 87, "output_tokens": 23}
    },
    "retrieve": {
      "span_name": "retrieve",
      "start_time": "2026-06-12T10:30:00.332+00:00",
      "duration_ms": 1812,
      "status": "success",
      "vector": {"duration_ms": 874, "result_count": 12},
      "bm25": {"duration_ms": 920, "redis_cache": "local_hit", "tokenize_ms": 5, "score_ms": 120, "candidate_count": 52, "result_count": 12},
      "fusion": {"duration_ms": 14, "method": "rrf", "result_count": 8},
      "match_sentence": {"duration_ms": 12}
    },
    "rerank": {
      "span_name": "rerank",
      "start_time": "2026-06-12T10:30:00.244+00:00",
      "duration_ms": 0,
      "status": "success",
      "input_count": 8,
      "output_count": 5,
      "metadata": {"reranker": "noop"}
    },
    "generate": {
      "span_name": "generate",
      "start_time": "2026-06-12T10:30:00.244+00:00",
      "duration_ms": 2340,
      "status": "success",
      "model": "deepseek-v4-pro",
      "ttft_ms": 120,
      "input_tokens": 1520,
      "output_tokens": 421,
      "finish_reason": "stop"
    },
    "error_message": null,
    "created_at": "2026-06-12T10:30:00+00:00"
  }
}
```

> **字段说明**：
> - `conversation_title`：通过 `conversation_id` LEFT JOIN `conversations` 表获取。会话不存在时为 `null`，前端显示为 `—`
> - `generate` 阶段不存储 `output`（LLM 回答内容），完整对话内容通过 `conversation_id` JOIN `messages` 表获取
> - `intent.metadata.model`：规则路径为 `null`，LLM 路径为实际模型名（如 `"deepseek-v4-flash"`）
> - `intent.metadata.confidence`：当前始终为 `null`（模型不返回置信度），预留字段
> - `rewrite.metadata.model`：未触发重写时为 `null`，触发时为实际模型名
> - `bm25.redis_cache`：缓存命中类型（`local_hit` / `redis_hit` / `miss`）
> - `bm25.tokenize_ms`：jieba 分词耗时（仅 `miss` 时有值，缓存命中时接近 0）
> - `fusion.method`：融合算法名称，由融合函数自身设置（当前为 `"rrf"`）

---

### 7.6 统计增强接口

#### GET `/api/admin/stats/traces`

Trace 统计数据，用于 ECharts 图表渲染。

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|:---|:---|:---|:---|
| `days` | int | 否 | 过去 N 天，默认 7 |
| `group_by` | string | 否 | day / hour，默认 day |

**响应** (200)：

```json
{
  "code": "0",
  "message": "ok",
  "data": {
    "trend": [
      {"date": "2026-06-06", "success": 128, "error": 2, "partial": 1},
      {"date": "2026-06-07", "success": 145, "error": 3, "partial": 0}
    ],
    "latency": [
      {"date": "2026-06-06", "p50": 820, "p95": 2100, "p99": 3800},
      {"date": "2026-06-07", "p50": 790, "p95": 2180, "p99": 4210}
    ],
    "tokens": [
      {"date": "2026-06-06", "input": 152000, "output": 45000},
      {"date": "2026-06-07", "input": 168000, "output": 52000}
    ],
    "intent_distribution": [
      {"type": "KNOWLEDGE", "count": 1024},
      {"type": "CASUAL", "count": 256},
      {"type": "META", "count": 64}
    ],
    "response_distribution": [
      {"mode": "RAG", "count": 980},
      {"mode": "DIRECT_LLM", "count": 156},
      {"mode": "META", "count": 64},
      {"mode": "CASUAL", "count": 96},
      {"mode": "FALLBACK", "count": 48}
    ]
  }
}
```

#### GET `/api/admin/stats`（已有接口增强）

响应新增 `charts` 字段：

```json
{
  "code": "0",
  "message": "ok",
  "data": {
    "user_count": 12,
    "kb_count": 5,
    "doc_count": 45,
    "chunk_count": 2340,
    "conversation_count": 89,
    "message_count": 520,
    "storage_bytes": 52428800,
    "charts": {
      "trend": [...],
      "latency": [...],
      "tokens": [...]
    }
  }
}
```

---

### 7.7 用户管理接口

> **实现状态**：已实现（Phase 5）。后端 `app/api/admin.py` + `app/services/admin_service.py` + `app/schemas/admin.py`。
> **权限**：所有 `/api/admin/users/*` 端点要求 `role=admin`。

#### GET `/api/admin/users`

获取用户列表（分页+筛选）。

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|:---|:---|:---|:---|
| `page` | int | 否 | 页码，默认 1 |
| `page_size` | int | 否 | 每页条数，默认 20，最大 100 |
| `role` | string | 否 | user / admin |
| `status` | string | 否 | active / disabled |
| `search` | string | 否 | 按用户名模糊搜索 |

**响应** (200)：

```json
{
  "code": "0",
  "message": "ok",
  "data": {
    "total": 15,
    "page": 1,
    "page_size": 20,
    "items": [
      {
        "id": 3,
        "username": "zhangsan",
        "role": "user",
        "status": "active",
        "kb_count": 2,
        "doc_count": 15,
        "conversation_count": 28,
        "last_active_at": "2026-06-12T10:30:00+00:00",
        "created_at": "2026-05-06T08:00:00+00:00"
      }
    ]
  }
}
```

#### GET `/api/admin/users/{user_id}`

获取用户详情（含统计）。

**响应** (200)：

```json
{
  "code": "0",
  "message": "ok",
  "data": {
    "id": 3,
    "username": "zhangsan",
    "role": "user",
    "status": "active",
    "kb_count": 2,
    "doc_count": 15,
    "conversation_count": 28,
    "message_count": 156,
    "total_input_tokens": 524000,
    "total_output_tokens": 128000,
    "last_active_at": "2026-06-12T10:30:00+00:00",
    "created_at": "2026-05-06T08:00:00+00:00"
  }
}
```

#### PUT `/api/admin/users/{user_id}/status`

禁用/启用用户。

**请求**：

```json
{"status": "disabled"}
```

| 字段 | 类型 | 必填 | 说明 |
|:---|:---|:---|:---|
| `status` | string | 是 | active / disabled |

**响应** (200)：

```json
{
  "code": "0",
  "message": "用户已禁用",
  "data": {"id": 3, "username": "zhangsan", "status": "disabled"}
}
```

#### POST `/api/admin/users/{user_id}/reset-password`

重置用户密码。

**请求**：

```json
{"new_password": "TempPass123!"}
```

| 字段 | 类型 | 必填 | 说明 |
|:---|:---|:---|:---|
| `new_password` | string | 是 | 新密码（≥ 6 字符） |

**响应** (200)：

```json
{
  "code": "0",
  "message": "密码重置成功",
  "data": {"id": 3, "username": "zhangsan"}
}
```

---

### 7.8 Admin 实现文件

```
backend/app/schemas/admin.py           ← 修改：新增 TraceSchema / UserSchema / StatsChartSchema
backend/app/services/admin_service.py  ← 修改：新增 Trace/用户管理 Service 方法 + 统计增强
backend/app/api/admin.py               ← 修改：新增 Trace/用户管理/统计增强端点
backend/app/models/trace.py            ← 新建：Trace ORM 模型
backend/app/rag/trace_recorder.py      ← 新建：TraceRecorder 上下文管理器
backend/alembic/versions/xxx_add_traces.py ← 新建：traces 表迁移
```

---

## 8. 完整请求/响应示例

### 8.1 正常问答流程

**Step 1 — 发起提问**：

```
POST /api/chat
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
Content-Type: application/json

{
  "conversation_id": null,
  "kb_id": "550e8400-e29b-41d4-a716-446655440000",
  "question": "入职需要开通哪些账号？",
  "deep_thinking": false
}
```

> 完整参数示例（含思考模式）：`{"conversation_id": "990e8400-e29b-41d4-a716-446655440004", "kb_id": "550e8400-e29b-41d4-a716-446655440000", "question": "...", "deep_thinking": true}`

**Step 2 — 服务端 SSE 流式返回**：

```
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive

event: meta
data: {"conversation_id": "990e8400-e29b-41d4-a716-446655440004", "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"}

event: message
data: {"delta": "根据《入职指南》，新员工入职需要开通以下账号：\n\n"}

event: message
data: {"delta": "1. **企业邮箱**（入职当天由 IT 自动开通）\n"}

event: message
data: {"delta": "2. **企业微信/钉钉**（HR 提前发送邀请链接）\n"}

event: message
data: {"delta": "3. **VPN 账号**（参考《VPN配置指南》自助开通）\n"}

event: message
data: {"delta": "4. **内部系统账号**（OA、报销系统等，由直属领导提交权限申请）"}

event: sources
data: {"chunks": [{"chunk_index": 1, "doc_id": 1, "doc_name": "入职指南.md", "content": "新员工入职当天需开通以下账号：1. 企业邮箱（入职当天由 IT 自动开通）2. 企业微信/钉钉（HR 提前发送邀请链接）3. VPN 账号（参考《VPN配置指南》自助开通）4. 内部系统账号（OA、报销系统等，由直属领导提交权限申请）", "score": 0.95, "page": 2, "preview_text": "新员工入职当天需开通以下账号：1. 企业邮箱（入职当天由 IT 自动开通）2. 企业微信/钉钉（HR 提前发送邀请链接）", "preview_range": {"start": 0, "end": 200}, "highlight_start": 0, "highlight_end": 20}, {"chunk_index": 2, "doc_id": 11, "doc_name": "VPN配置指南.md", "content": "VPN账号申请步骤：1. 访问 IT 自助平台 2. 填写工号和手机号 3. 提交申请后 24 小时内开通", "score": 0.78, "page": 1, "preview_text": "VPN账号申请步骤：1. 访问 IT 自助平台 2. 填写工号和手机号", "preview_range": {"start": 0, "end": 100}, "highlight_start": 0, "highlight_end": 15}]}

event: finish
data: {"message_id": 10, "title": "入职账号开通", "token_usage": {"prompt": 1200, "completion": 180, "total": 1380}}
```

### 8.2 错误流程：知识库无文档

```
POST /api/chat
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
Content-Type: application/json

{
  "conversation_id": null,
  "kb_id": "00000000-0000-0000-0000-000000000000",
  "question": "入职需要开通哪些账号？",
  "deep_thinking": false
}
```

**响应**（非流式，直接返回 HTTP JSON）：

```json
HTTP/1.1 404 Not Found
Content-Type: application/json

{
  "code": "E1001",
  "message": "知识库不存在",
  "detail": "kb_uuid=00000000-0000-0000-0000-000000000000 不存在或已被删除"
}
```

### 8.3 错误流程：LLM 调用异常

```
POST /api/chat
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
Content-Type: application/json

{
  "conversation_id": "990e8400-e29b-41d4-a716-446655440004",
  "kb_id": "550e8400-e29b-41d4-a716-446655440000",
  "question": "入职需要开通哪些账号？",
  "deep_thinking": true
}
```

**SSE 返回**（检索成功但 LLM 调用失败，sources 仍发送）：

```
event: meta
data: {"conversation_id": "990e8400-e29b-41d4-a716-446655440004", "task_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901"}

event: sources
data: {"chunks": [{"doc_id": 1, "doc_name": "入职指南.md", "content": "新员工入职当天需开通以下账号：...", "score": 0.95, "page": 2}]}

event: error
data: {"code": "E4002", "message": "LLM 调用失败", "detail": "DeepSeek API 返回 503 Service Unavailable，已重试 3 次"}
```

### 8.4 META 意图：固定模板响应

用户询问助手能力等 META 类问题时，不调用 LLM，直接返回固定模板（毫秒级响应）。

```
POST /api/chat
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
Content-Type: application/json

{
  "conversation_id": null,
  "kb_id": "550e8400-e29b-41d4-a716-446655440000",
  "question": "你能做什么？",
  "deep_thinking": false
}
```

**SSE 返回**（META 意图分流，不调 LLM，不检索）：

```
event: meta
data: {"conversation_id": "aa0e8400-e29b-41d4-a716-446655440005", "task_id": "c3d4e5f6-a7b8-9012-cdef-123456789012"}

event: message
data: {"delta": "我是 DocMind，一个企业知识库智能问答助手。\n\n我可以帮你：\n1. 查询知识库中的文档信息\n2. 回答关于公司制度、流程、规范等问题\n3. 检索相关文档并提供引用来源\n\n请直接向我提问，或选择一个知识库开始问答。"}

event: finish
data: {"message_id": 12, "title": "你能做什么", "token_usage": {"prompt": 0, "completion": 0, "total": 0}}
```

> **特点**：`event: meta` 后直接 `event: message`（固定模板），无 `event: sources`，`token_usage` 全为 0（未调 LLM）。

### 8.5 CASUAL 意图：闲谈跳过检索

日常闲聊、问候、致谢等 CASUAL 类问题时，跳过检索链路，使用闲谈 System Prompt 直接调 LLM。

```
POST /api/chat
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
Content-Type: application/json

{
  "conversation_id": "990e8400-e29b-41d4-a716-446655440004",
  "kb_id": "550e8400-e29b-41d4-a716-446655440000",
  "question": "你好",
  "deep_thinking": false
}
```

**SSE 返回**（CASUAL 意图分流，跳过检索，无 sources）：

```
event: meta
data: {"conversation_id": "990e8400-e29b-41d4-a716-446655440004", "task_id": "d4e5f6a7-b8c9-0123-defa-234567890123"}

event: message
data: {"delta": "你好！有什么我可以帮你的吗？"}

event: finish
data: {"message_id": 13, "title": null, "token_usage": {"prompt": 80, "completion": 15, "total": 95}}
```

> **特点**：无 `event: sources`（跳过检索），`title` 为 null（非首轮），`token_usage` 较小（无检索结果拼入 Prompt）。

---

## 9. 接口权限速查表

| 方法 | 路径 | 权限 | 说明 | 实现 |
|:---|:---|:---|:---|:---|
| POST | `/api/auth/register` | 公开 | 注册 | Phase 1 ✅ |
| POST | `/api/auth/login` | 公开 | 登录（Phase 4 新增 refresh_token 字段） | Phase 1 ✅ |
| POST | `/api/auth/refresh` | 公开（携带 refresh_token） | Token 刷新（Rotation） | Phase 4 |
| POST | `/api/auth/logout` | user | 吊销 refresh_token | Phase 4 |
| PUT | `/api/auth/password` | user | 改密并吊销全部 refresh_token | Phase 4 |
| POST | `/api/knowledge-bases` | user | 创建知识库（可指定 visibility） | Phase 2 ✅ |
| GET | `/api/knowledge-bases` | user | 我的知识库列表（仅当前用户） | Phase 2 ✅ |
| GET | `/api/knowledge-bases/public` | user | 公开知识库列表（跨用户，仅 public+active） | Phase 2.5 ✅ |
| GET | `/api/knowledge-bases/selectable` | user | 可检索知识库分组列表（mine + public），供 KB 选择器使用 | Phase 3 ✅ |
| GET | `/api/knowledge-bases/{uuid}` | user（owner/admin/public KB 可读） | 知识库详情；admin 可查看含 private 的全部 KB | Phase 2 ✅ |
| PUT | `/api/knowledge-bases/{uuid}` | owner + admin | 更新知识库元数据（name/desc/visibility）；admin 可修正不当内容 | Phase 2 ✅ |
| DELETE | `/api/knowledge-bases/{uuid}` | owner + admin | 删除知识库（异步）；admin 可违规清理 | Phase 2 ✅ |
| POST | `/api/knowledge-bases/{kb_uuid}/documents` | 仅 owner | 上传文档；admin 不越权写入 | Phase 2 ✅ |
| POST | `/api/knowledge-bases/{kb_uuid}/documents/batch-upload` | 仅 owner | 批量上传文档；admin 不越权写入 | Phase 2 ✅ |
| POST | `/api/knowledge-bases/{kb_uuid}/documents/{doc_uuid}/reprocess` | 仅 owner | 重新处理失败文档 | Phase 2 ✅ |
| GET | `/api/knowledge-bases/{kb_uuid}/documents` | owner + admin（private）；所有登录用户（public） | 文档列表；public KB 允许所有登录用户只读访问 | Phase 2 ✅ |
| GET | `/api/knowledge-bases/{kb_uuid}/documents/{doc_uuid}` | owner + admin（private）；所有登录用户（public） | 文档详情；public KB 允许所有登录用户只读访问 | Phase 2 ✅ |
| GET | `/api/knowledge-bases/{kb_uuid}/documents/{doc_uuid}/chunks` | owner + admin（private）；所有登录用户（public） | 查看分块；public KB 允许所有登录用户只读访问 | Phase 2 ✅ |
| DELETE | `/api/knowledge-bases/{kb_uuid}/documents/{doc_uuid}` | owner + admin | 删除文档（异步）；admin 可逐文档违规清理 | Phase 2 ✅ |
| POST | `/api/conversations` | user | 创建会话 | Phase 4 |
| GET | `/api/conversations` | user | 会话列表 | Phase 4 |
| GET | `/api/conversations/{uuid}` | user（所有者） | 会话详情 | Phase 4 |
| PUT | `/api/conversations/{uuid}` | user（所有者） | 重命名会话 | Phase 4 |
| DELETE | `/api/conversations/{uuid}` | user（所有者） | 删除会话 | Phase 4 |
| POST | `/api/chat` | user | 问答 SSE（kb_id 需有检索权限：own KB 或 public KB） | Phase 3 |
| GET | `/api/admin/knowledge-bases` | admin | 全部知识库（跨用户） | Phase 5 |
| GET | `/api/admin/documents` | admin | 全部文档（跨库） | Phase 5 |
| GET | `/api/admin/stats` | admin | 概览统计（含 charts 图表数据） | Phase 5 |
| GET | `/api/admin/stats/traces` | admin | Trace 统计（trend/latency/tokens/distribution） | Phase 5 |
| GET | `/api/admin/traces` | admin | Trace 列表（分页+筛选） | Phase 5 |
| GET | `/api/admin/traces/{trace_id}` | admin | Trace 详情（含各阶段 JSON） | Phase 5 |
| GET | `/api/admin/users` | admin | 用户列表（分页+筛选） | Phase 5 |
| GET | `/api/admin/users/{user_id}` | admin | 用户详情（含统计） | Phase 5 |
| PUT | `/api/admin/users/{user_id}/status` | admin | 禁用/启用用户 | Phase 5 |
| POST | `/api/admin/users/{user_id}/reset-password` | admin | 重置用户密码 | Phase 5 |

---

## 10. 相关文档

- [架构设计文档](../docs/ARCHITECTURE.md)
- [数据库设计文档](DATABASE.md)
- [开发指南](../docs/DEVELOPMENT.md)
- [UI 设计规范](../../frontend/docs/UIDESIGN.md)
