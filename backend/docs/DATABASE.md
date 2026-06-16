# DATABASE — 数据库设计文档

| 属性 | 值 |
|:---|:---|
| 文档版本 | v1.0 |
| 最后更新 | 2026-06-16 |

---

## 0. 时区约定

> **所有 DATETIME 列均存储 UTC 时间。** 四层 UTC 统一策略（MySQL → 后端 → API → 前端）详见 [ARCHITECTURE.md §11](../../docs/ARCHITECTURE.md#11-时区策略)。

`app/models/_types.py` 中的 `UTCDateTime` TypeDecorator 在 ORM 层完成 aware ↔ naive 双向转换——写入时剥离 tzinfo 存 naive UTC，读取时附加 UTC tzinfo 返回 aware datetime。Pydantic 收到 aware datetime 后自动序列化为 `2026-06-09T12:00:02+00:00`。底层列依然是 `DATETIME`，不需要数据迁移。

---

## 1. ER 关系

```
users (用户表)
  │
  ├── knowledge_bases (知识库表)
  │     └── documents (文档表)
  │           └── chunks (分块表)
  │
  ├── conversations (会话表)
  │     └── messages (消息表)
  │
  ├── refresh_tokens (刷新令牌表)
  │
  └── traces (链路追踪表)
```

**关系说明**：
- 一个用户可创建多个知识库，每个知识库属于一个用户（1:N）
- 一个知识库包含多个文档，每个文档属于一个知识库（1:N）
- 一个文档被切分为多个分块，每个分块属于一个文档（1:N）
- 一个用户可发起多个会话，每个会话属于一个用户（1:N）
- 一个会话包含多条消息，每条消息属于一个会话（1:N）
- 会话可关联一个知识库（可选），表示当前对话的知识库上下文
- 一个用户可有多个刷新令牌，每个令牌属于一个用户（1:N）
- 一个用户可有多条 Trace 记录，每条 Trace 属于一个用户（1:N）
- 一条 Trace 可关联一个会话（可选），用于关联完整对话内容

---

## 2. 表结构

### 2.1 用户表 `users`

```sql
CREATE TABLE users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    role ENUM('user', 'admin') DEFAULT 'user',
    status ENUM('active', 'disabled') DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| id | BIGINT | 主键 |
| username | VARCHAR(64) | 用户名，唯一索引 |
| password_hash | VARCHAR(256) | bcrypt 哈希后的密码 |
| role | ENUM | 角色：user（普通用户）/ admin（管理员） |
| status | ENUM | 状态：active（正常）/ disabled（禁用），禁用后拒绝登录和 Token 刷新 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间，自动更新 |

### 2.2 知识库表 `knowledge_bases`

```sql
CREATE TABLE knowledge_bases (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    uuid CHAR(36) NOT NULL COMMENT '外部暴露的知识库标识符（UUID），API/URL 使用',
    name VARCHAR(128) NOT NULL,
    description TEXT,
    user_id BIGINT NOT NULL,
    visibility ENUM('private', 'public') DEFAULT 'private' COMMENT 'private（仅owner可见）/ public（所有用户可检索）',
    status ENUM('active', 'deleting') DEFAULT 'active',
    chunk_count INT DEFAULT 0,
    doc_count INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE INDEX idx_uuid (uuid),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    UNIQUE INDEX idx_user_name (user_id, name)
);
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| id | BIGINT | 主键（内部使用，不暴露给 API） |
| uuid | CHAR(36) | 外部暴露的知识库标识符（UUID），唯一索引，API/URL 使用 |
| name | VARCHAR(128) | 知识库名称，与 user_id 联合唯一（同一用户下名称不重复） |
| description | TEXT | 知识库描述 |
| user_id | BIGINT | 创建者用户 ID |
| visibility | ENUM | private（仅 owner 可见可检索）/ public（所有用户可检索），默认 private |
| status | ENUM | active（正常）/ deleting（异步清理中，随后物理删除行） |
| chunk_count | INT | 分块总数（冗余缓存列，Celery 任务内部维护）。**API 响应使用 Chunk 表实时 COUNT，不读此列**，避免 Celery 任务异常导致僵尸计数值 |
| doc_count | INT | 文档总数（冗余缓存）。文档删除时须用 `GREATEST(0, doc_count - 1)` 原子递减 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

### 2.3 文档表 `documents`

```sql
CREATE TABLE documents (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    uuid CHAR(36) NOT NULL COMMENT '外部暴露的文档标识符（UUID），API/URL 使用',
    kb_id BIGINT NOT NULL,
    filename VARCHAR(256) NOT NULL,
    file_type VARCHAR(32) NOT NULL COMMENT 'pdf/docx/md/txt',
    file_path VARCHAR(512) COMMENT '文件存储路径：uploads/{kb_id}/{doc_id}/{uuid}_{sanitized_filename}',
    file_size BIGINT COMMENT 'bytes',
    status ENUM('uploaded','parsing','chunking','embedding','vector_storing','completed','success_with_warnings','partial_failed','failed','deleting') DEFAULT 'uploaded',
    chunk_count INT DEFAULT 0,
    error_msg TEXT,
    current_stage VARCHAR(32) COMMENT '当前处理阶段，用于断点恢复',
    last_success_batch INT DEFAULT 0 COMMENT '最后成功的批次号，用于批次级 checkpoint',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE INDEX idx_uuid (uuid),
    INDEX idx_kb_id (kb_id),
    INDEX idx_kb_filename (kb_id, filename) COMMENT '文档唯一性检查',
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE
);
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| id | BIGINT | 主键（内部使用，不暴露给 API） |
| uuid | CHAR(36) | 外部暴露的文档标识符（UUID），唯一索引，API/URL 使用 |
| kb_id | BIGINT | 所属知识库 ID，有索引 |
| filename | VARCHAR(256) | 原始文件名 |
| file_type | VARCHAR(32) | 文件类型：pdf / docx / md / txt |
| file_path | VARCHAR(512) | 文件存储路径 |
| file_size | BIGINT | 文件大小（字节） |
| status | ENUM | 入库状态，使用 `DocumentStatus(str, Enum)` 统一管理（见 API.md §4.0） |
| chunk_count | INT | 分块数量 |
| error_msg | TEXT | 入库失败时的错误信息 |
| current_stage | VARCHAR(32) | 当前处理阶段（parsing/chunking/embedding/vector_storing），断点恢复用 |
| last_success_batch | INT | 最后成功批次号（Embedding 批次级 checkpoint） |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

**文档状态流转**：

```
uploaded → parsing → chunking → embedding → vector_storing → completed
              ↓         ↓          ↓            ↓
          ───────────→ failed ←───────────────
              ↓         ↓          ↓            ↓
          success_with_warnings / partial_failed

**仅 `partial_failed` / `failed` → reprocess → parsing（重新入库）**
`completed` / `success_with_warnings` / `partial_failed` / `failed` = 终态（`TERMINAL_STATUSES`）
`deleting` = 异步清理中，清理完成后物理删除行（非终态，行删除后不存在）
```

**新增索引**：`idx_kb_filename (kb_id, filename)` 用于文档唯一性检查（同名文档快速查找）。

**状态枚举定义**：详见 [API.md §4.0](./API.md#40-文档状态枚举)。

### 2.4 分块表 `chunks`

```sql
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
    INDEX idx_kb_id (kb_id),
    FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE
);
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| id | BIGINT | 主键 |
| doc_id | BIGINT | 所属文档 ID，有索引 |
| kb_id | BIGINT | 所属知识库 ID，有索引（冗余，便于按知识库统计分块） |
| chroma_id | VARCHAR(256) | ChromaDB 中对应的 chunk id，用于回溯和删除 |
| content | TEXT | 分块文本内容 |
| chunk_index | INT | 在原文档中的顺序（从 0 开始） |
| token_count | INT | 估算的 token 数量 |
| metadata | JSON | 额外元数据（页码、段落标题等） |
| created_at | DATETIME | 创建时间 |

### 2.5 会话表 `conversations`

```sql
CREATE TABLE conversations (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    uuid CHAR(36) NOT NULL COMMENT '外部暴露的会话标识符（UUID），API/URL 使用',
    user_id BIGINT NOT NULL,
    kb_id BIGINT COMMENT '关联的知识库',
    original_kb_id BIGINT NULL COMMENT 'KB 删除前的原始 kb_id，用于孤儿会话检测',
    original_kb_uuid CHAR(36) NULL COMMENT 'KB 删除前的原始 UUID，用于孤儿会话审计追踪',
    original_kb_name VARCHAR(128) NULL COMMENT 'KB 删除前的原始名称，用于孤儿会话 Banner 展示',
    title VARCHAR(256) DEFAULT '新对话',
    message_count INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_message_at DATETIME NULL DEFAULT NULL COMMENT '最后一次产生消息的时间，用于列表排序。仅 send_message/assistant_reply 更新（不受 FK SET NULL 等非消息 UPDATE 污染）',
    UNIQUE INDEX idx_uuid (uuid),
    INDEX idx_user_id (user_id),
    INDEX idx_conversations_user_last_msg (user_id, last_message_at) COMMENT '会话列表按 last_message_at DESC 排序查询',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE SET NULL
);
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| id | BIGINT | 主键（内部使用，不暴露给 API） |
| uuid | CHAR(36) | 外部暴露的会话标识符（UUID），唯一索引，API/URL 使用 |
| user_id | BIGINT | 所属用户 ID，有索引 |
| kb_id | BIGINT | 关联的知识库 ID（可选，表示对话的知识域） |
| original_kb_id | BIGINT | KB 删除前的原始 ID，用于孤儿会话检测。KB 物理删除前由 Celery 批量备份 |
| original_kb_uuid | CHAR(36) | KB 删除前的原始 UUID，用于孤儿会话审计追踪。与 `original_kb_id` 同步备份 |
| original_kb_name | VARCHAR(128) | KB 删除前的原始名称，用于孤儿会话 Banner 展示 |
| title | VARCHAR(256) | 对话标题（可由首条消息自动生成） |
| message_count | INT | 消息总数（冗余缓存） |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |
| last_message_at | DATETIME | 最后一次产生消息的时间，用于列表排序。仅 send_message/assistant_reply 更新（不受 FK SET NULL 等非消息 UPDATE 污染） |

**设计决策：为什么新增 `last_message_at` 而不复用 `updated_at` 排序？**

> `updated_at` 列由 `ON UPDATE CURRENT_TIMESTAMP` 自动维护，任何 `UPDATE` 操作都会刷新该值——包括：
> - `conversations.kb_id` 外键 `ON DELETE SET NULL` 级联（知识库删除时 kb_id 置空，触发 updated_at 更新）
> - 管理员后台修改会话标题、元数据等非消息操作
> - 未来可能新增的任何 `UPDATE conversations SET ...` 语句
>
> 会话列表的默认排序（"最近有消息的会话排在前面"）应当只反映**真实消息活动**，而非上述元数据变更。因此引入 `last_message_at` 列：
> - **仅**在 `send_message`（用户发送）和 `assistant_reply`（助手回复）时由业务代码显式更新
> - 不受 FK 级联、管理员操作、标题修改等"非消息 UPDATE"影响
> - 配合 `idx_conversations_user_last_msg (user_id, last_message_at)` 复合索引，实现高效的会话列表排序查询

**设计决策：为什么新增 `original_kb_id` / `original_kb_uuid` / `original_kb_name`？**

> FK `ON DELETE SET NULL` 在 MySQL 层自动将 `conversations.kb_id` 置空，导致信息不可逆丢失——无法区分「从未关联 KB」和「KB 已删除」。
>
> 解决方案：在 Celery 物理删除 KB **之前**，批量备份 `kb_id` → `original_kb_id`、`kb.uuid` → `original_kb_uuid` 和 `kb.name` → `original_kb_name`。MySQL FK SET NULL 随后清空 `kb_id`，但 `original_kb_id` 保留原值。
>
> `_enrich_kb_status` 据此判断：
> - `kb_id=NULL` + `original_kb_id` 非空 → `kb_status="deleted"`（孤儿会话）
> - `kb_id=NULL` + `original_kb_id` 为空 → `kb_status=None`（从未关联 KB）
>
> 使用批量 UPDATE（`UPDATE conversations SET original_kb_id=?, original_kb_uuid=?, original_kb_name=? WHERE kb_id=?`）而非 ORM 逐行循环，避免 N 对象实例化 + N 次脏检查。

**设计决策：为什么使用双字段方案（id + uuid）？**

> **架构决策详见**：[ARCHITECTURE.md §8.11](../../docs/ARCHITECTURE.md#811-外部资源-uuid-化)（资源分级改造决策表和各资源 UUID 化范围）。

> 外部暴露的资源（knowledge_bases、documents、conversations）采用双字段方案：
> - `id BIGINT AUTO_INCREMENT`：内部主键，用于外键关联、JOIN 查询、内部逻辑
> - `uuid CHAR(36) UNIQUE`：外部暴露标识符，用于 API 路由、响应、URL。应用层使用 `uuid.uuid4()` 显式生成（v4，随机），`server_default=text("(UUID())")` 为安全网兜底（MySQL `UUID()` 生成 v1）
>
> **优势**：
> - 零影响现有外键关系（`messages.conversation_id`、`traces.conversation_id` 等）——无需迁移子表
> - 内部查询（JOIN、聚合）保持 BIGINT 性能，索引更小、缓存命中率更高
> - UUID 仅在 API 边界解析，影响面最小
> - 防止 ID 枚举攻击，提升安全性
>
> **存储**：CHAR(36) 存储标准 UUID 格式（含连字符），如 `550e8400-e29b-41d4-a716-446655440000`。未来如需优化存储，可迁移至 BINARY(16)（节省约 55% 空间）。
>
> **不改造的资源**：users（Admin 内部使用）、messages（仅 SSE 返回）、chunks（内部结构）保持 BIGINT 主键。

### 2.6 消息表 `messages`

```sql
CREATE TABLE messages (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    conversation_id BIGINT NOT NULL,
    role ENUM('user', 'assistant', 'system') NOT NULL,
    content TEXT NOT NULL,
    thinking_content TEXT COMMENT '深度思考内容',
    token_count INT DEFAULT 0,
    feedback ENUM('like', 'dislike') NULL,
    metadata JSON NULL DEFAULT NULL COMMENT '扩展元数据：未来 Tool Call / Web Search / Agent 等场景的非结构化数据',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_conversation_id (conversation_id),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| id | BIGINT | 主键 |
| conversation_id | BIGINT | 所属会话 ID，有索引 |
| role | ENUM | 消息角色：user / assistant / system |
| content | TEXT | 消息正文 |
| thinking_content | TEXT | DeepSeek 深度思考内容（可空） |
| token_count | INT | 消息消耗的 token 估算 |
| feedback | ENUM | 用户反馈：like / dislike（可空） |
| metadata | JSON | 扩展元数据（可空）。Phase 4 不使用，为 future Tool Call / Web Search / Agent 预留 |
| created_at | DATETIME | 创建时间 |

### 2.7 刷新令牌表 `refresh_tokens`

> **Phase 4 新增**。配合 Refresh Token 机制（见 [ARCHITECTURE.md §9.2](../../docs/ARCHITECTURE.md#92-refresh-token-机制)），持久化存储刷新令牌哈希。

```sql
CREATE TABLE refresh_tokens (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    token_hash VARCHAR(256) NOT NULL COMMENT 'refresh_token 的 SHA-256 哈希，不存明文',
    expires_at DATETIME NOT NULL COMMENT '过期时间（创建后 7 天）',
    revoked_at DATETIME NULL COMMENT '吊销时间（NULL=有效，非NULL=已吊销及吊销时间）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_token_hash (token_hash),
    INDEX idx_user_active (user_id, revoked_at, expires_at) COMMENT '查询某用户有效 token',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| id | BIGINT | 主键 |
| user_id | BIGINT | 所属用户 ID |
| token_hash | VARCHAR(256) | refresh_token 的 SHA-256 哈希值（不存明文，防数据库泄露后伪造） |
| expires_at | DATETIME | Token 过期时间（创建后 +7 天） |
| revoked_at | DATETIME | 吊销时间（NULL=有效；非 NULL=已吊销，值为吊销时间） |
| created_at | DATETIME | 创建时间 |

**安全设计**：
- **不存明文**：数据库仅存 SHA-256 哈希。攻击者获取数据库后无法伪造 refresh_token
- **Rotation 实现**：调用 `POST /api/auth/refresh` 时，旧 token 行 `UPDATE revoked_at = NOW()`，新 token 行 `INSERT`
- **泄露检测**：若用已吊销的旧 token 请求刷新 → 该用户全部 token `UPDATE revoked_at = NOW()`（E5009）
- **改密吊销**：`PUT /api/auth/password` → 该用户全部 token `UPDATE revoked_at = NOW()`
- **过期清理**：`expires_at < NOW()` 的 token 即使 `revoked_at IS NULL` 也视为无效

### 2.8 链路追踪表 `traces`

> **Phase 5 已实现**。记录问答全链路各阶段耗时和详情，用于性能观测和统计分析。

```sql
CREATE TABLE traces (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    trace_id VARCHAR(64) NOT NULL COMMENT 'UUID 追踪 ID',
    user_id BIGINT NOT NULL COMMENT '用户 ID',
    conversation_id BIGINT COMMENT '会话 ID（可为空）',
    kb_id BIGINT COMMENT '知识库 ID',
    question TEXT COMMENT '用户问题',
    status VARCHAR(32) NOT NULL COMMENT '状态：success / error / partial',
    intent_type VARCHAR(32) COMMENT '顶层字段：KNOWLEDGE / CASUAL / META',
    intent_method VARCHAR(32) COMMENT '顶层字段：regex / llm_flash / llm_pro',
    response_mode VARCHAR(32) COMMENT '顶层字段：RAG / DIRECT_LLM / META / CASUAL / FALLBACK / REJECT',
    total_duration_ms INT COMMENT '总耗时（毫秒）',
    intent JSON COMMENT '意图识别阶段详情',
    rewrite JSON COMMENT '问题重写阶段详情',
    retrieve JSON COMMENT '检索阶段详情（细粒度拆分：vector/bm25/fusion/match_sentence）',
    rerank JSON COMMENT 'Rerank 阶段详情',
    generate JSON COMMENT 'LLM 生成阶段详情（不存 output）',
    evidence_review JSON COMMENT '证据审查阶段详情（chunk 分类 + REJECT 决策 + post-LLM 审计结果）',
    error_message TEXT COMMENT '错误信息（status=error 时）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
    UNIQUE INDEX idx_trace_id (trace_id),
    INDEX idx_created_at (created_at),
    INDEX idx_created_status (created_at, status),
    INDEX idx_created_intent (created_at, intent_type),
    INDEX idx_created_response (created_at, response_mode),
    INDEX idx_user_created (user_id, created_at),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL
);
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| id | BIGINT | 主键 |
| trace_id | VARCHAR(64) | UUID 追踪 ID，唯一索引 |
| user_id | BIGINT | 用户 ID，有索引 |
| conversation_id | BIGINT | 会话 ID（可为空），用于关联完整对话内容 |
| kb_id | BIGINT | 知识库 ID |
| question | TEXT | 用户问题 |
| status | VARCHAR(32) | 状态：success / error / partial |
| intent_type | VARCHAR(32) | 意图类型（顶层字段，用于聚合统计） |
| intent_method | VARCHAR(32) | 意图分类方法（顶层字段） |
| response_mode | VARCHAR(32) | 响应模式（顶层字段，用于聚合统计）。枚举值：RAG / DIRECT_LLM / META / CASUAL / FALLBACK / REJECT |
| total_duration_ms | INT | 总耗时（毫秒） |
| intent | JSON | 意图识别阶段详情（span_name/start_time/duration_ms/status/intent_type/method/metadata） |
| rewrite | JSON | 问题重写阶段详情（span_name/start_time/duration_ms/status/original_question/rewritten_question/metadata） |
| retrieve | JSON | 检索阶段详情，**细粒度拆分**：vector/bm25/fusion/match_sentence 各自独立计时 |
| rerank | JSON | Rerank 阶段详情（input_count/output_count/metadata.reranker） |
| generate | JSON | LLM 生成阶段详情（model/ttft_ms/input_tokens/output_tokens/finish_reason），**不存 output** |
| evidence_review | JSON | 证据审查阶段详情（summary/chunk_decisions/sentence_review/post_audit），chunk_decisions 上限 5 条 |
| error_message | TEXT | 错误信息（status=error 时） |
| created_at | DATETIME | 创建时间（UTC） |

**设计要点**：
- **顶层字段**：`intent_type`、`intent_method`、`response_mode` 作为独立列，避免聚合统计时 `JSON_EXTRACT` 性能问题
- **不存 generate.output**：完整对话内容通过 `conversation_id` JOIN 查询，避免重复存储
- **retrieve 细粒度**：拆分 vector/bm25/fusion/match_sentence，便于定位性能瓶颈（如 `bm25.tokenize_ms` 异常）
- **索引设计**：`(created_at, status)` 用于 Dashboard 按时间+状态筛选；`(created_at, intent_type)` 用于意图分类统计；`(user_id, created_at)` 用于按用户筛选

---

## 3. 索引策略

| 表 | 索引 | 类型 | 用途 |
|:---|:---|:---|:---|
| users | username (UNIQUE) | 唯一索引 | 登录查询 |
| knowledge_bases | idx_uuid (uuid) | 唯一索引 | 外部暴露标识符，API/URL 查询 |
| knowledge_bases | idx_user_name (user_id, name) | 唯一索引 | 用户级知识库名称唯一性约束 |
| documents | idx_uuid (uuid) | 唯一索引 | 外部暴露标识符，API/URL 查询 |
| documents | idx_kb_id | 普通索引 | 按知识库列出文档 |
| documents | idx_kb_filename (kb_id, filename) | 复合索引 | 文档唯一性检查 + 同名查找 |
| chunks | idx_doc_id | 普通索引 | 按文档列出分块 |
| chunks | idx_kb_id | 普通索引 | 按知识库统计分块 |
| conversations | idx_uuid (uuid) | 唯一索引 | 外部暴露标识符，API/URL 查询 |
| conversations | idx_user_id | 普通索引 | 按用户列出会话 |
| conversations | idx_conversations_user_updated (user_id, updated_at) | 复合索引 | Phase 4：按用户列出会话并按更新时间倒序排列 |
| conversations | idx_conversations_user_last_msg (user_id, last_message_at) | 复合索引 | 会话列表按 last_message_at DESC 排序查询（替代 updated_at 排序，避免 FK 级联污染） |
| messages | idx_conversation_id | 普通索引 | 按会话列出消息 |
| refresh_tokens | idx_user_id | 普通索引 | 按用户查询刷新令牌 |
| refresh_tokens | idx_token_hash | 普通索引 | 按 token 哈希查找（刷新校验入口） |
| refresh_tokens | idx_user_active (user_id, revoked_at, expires_at) | 复合索引 | 查询用户有效 token + 改密批量吊销 + Rotation 检测 |
| traces | idx_trace_id (trace_id) | 唯一索引 | 按 trace_id 查询详情 |
| traces | idx_created_at (created_at) | 普通索引 | 按时间范围筛选 |
| traces | idx_created_status (created_at, status) | 复合索引 | Dashboard 按时间+状态筛选 |
| traces | idx_created_intent (created_at, intent_type) | 复合索引 | 意图分类统计 |
| traces | idx_created_response (created_at, response_mode) | 复合索引 | 响应模式统计 |
| traces | idx_user_created (user_id, created_at) | 复合索引 | 按用户筛选 |

> **注意**：MySQL 会自动为外键列创建索引（若该列尚未建立索引）。上表中 `chunks.doc_id`、`chunks.kb_id` 等因已有显式索引，不再重复；`conversations.kb_id` 无外键索引，如需频繁按知识库查询会话，可后续补充。

> **Phase 6 优化项**：如后续文档量和用户量增大，考虑：
> - `documents` 表增加 `(kb_id, status)` 复合索引用于状态过滤
> - `messages` 表增加 `(conversation_id, created_at)` 复合索引用于按时间排序
> - `refresh_tokens` 表定期清理过期 token 的定时任务

#### 3.1 Admin 统计接口查询优化

> Phase 5 `GET /api/admin/stats` 对 6 张表执行 `SELECT COUNT(*)` + `SUM()` 聚合。数据量小时（< 10 万条）直接查询即可；数据增长后需考虑以下优化：

| 优化级别 | 方案 | 适用规模 | 说明 |
|:---|:---|:---|:---|
| 当前（Phase 5） | 直接 SQL 聚合 | < 10 万行 | `SELECT COUNT(*)` 在 InnoDB 小表上毫秒级完成，无需额外优化 |
| 中等规模 | Redis 缓存统计数（TTL 60s） | 10-100 万行 | 避免每次 Admin 页面刷新都触发 6 次 `COUNT(*)`。缓存 60s 延迟可接受 |
| 大规模 | 汇总表 `admin_stats` + Celery 定时刷新 | > 100 万行 | 独立汇总表存储预计算统计值，Celery beat 每 5 分钟刷新一次 |

**需关注的表**：

| 表 | `COUNT(*)` 代价 | 说明 |
|:---|:---|:---|
| `messages` | 🟡 中 | 每次问答产生 2 条消息（user + assistant），增长最快。10 万条以下无压力 |
| `chunks` | 🟡 中 | 每个文档产生 10-100+ 条 chunk，与文档量成正比 |
| `conversations` | 🟢 低 | 增长较慢，每个会话可能含多轮消息 |
| `users` / `knowledge_bases` / `documents` | 🟢 低 | 数量级远小于 messages/chunks |

> **实现建议**：Phase 5 先用直接 SQL 方案（简单可靠），Redis 缓存作为 `admin_service.get_stats()` 的可选增强（通过 `RATE_LIMIT_ENABLED` 类似的 `STATS_CACHE_ENABLED` 开关控制）。汇总表方案推迟 Phase 6。

---

## 4. 外键策略

| 字段 | 引用表 | 级联行为 | 设计理由 |
|:---|:---|:---|:---|
| `knowledge_bases.user_id` | `users(id)` | `ON DELETE RESTRICT` | 知识库是组织资产，删除用户前必须先转移或手动删除其知识库，防止误删导致数据丢失 |
| `documents.kb_id` | `knowledge_bases(id)` | `ON DELETE CASCADE` | 删除知识库时自动清空旗下所有文档，与业务「删除知识库及其下所有文档」对齐 |
| `chunks.doc_id` | `documents(id)` | `ON DELETE CASCADE` | 删除文档时自动清空其分块，保证 MySQL 与 ChromaDB 数据一致性 |
| `chunks.kb_id` | `knowledge_bases(id)` | `ON DELETE CASCADE` | 冗余字段，知识库删除时级联清理分块记录，便于按知识库统计 |
| `conversations.user_id` | `users(id)` | `ON DELETE CASCADE` | 用户删除时自动清理其会话历史，避免悬空数据 |
| `conversations.kb_id` | `knowledge_bases(id)` | `ON DELETE SET NULL` | 知识库删除后会话保留，仅解除关联（kb_id 置空），防止历史对话丢失 |
| `messages.conversation_id` | `conversations(id)` | `ON DELETE CASCADE` | 删除会话时自动清理全部消息，与业务「删除会话及其全部消息」对齐 |
| `refresh_tokens.user_id` | `users(id)` | `ON DELETE CASCADE` | 用户删除时自动清理其刷新令牌，避免悬空数据 |
| `traces.user_id` | `users(id)` | `ON DELETE CASCADE` | 用户删除时自动清理其 Trace 记录 |
| `traces.conversation_id` | `conversations(id)` | `ON DELETE SET NULL` | 会话删除后 Trace 保留，仅解除关联（conversation_id 置空），Trace 作为性能观测数据独立于会话生命周期 |

> **重要**：知识库/文档的实际删除采用 **Celery 异步物理删除**（先标记 `deleting` → Worker 清理 ChromaDB 向量 + 磁盘文件 → 物理 `DELETE FROM` MySQL 记录）。`ON DELETE CASCADE` 作为数据库层兜底保障——即使 Celery 仅执行 `DELETE FROM knowledge_bases WHERE id=?`，子记录（documents → chunks）也会由 FK CASCADE 自动级联清理，无需显式逐表删除。

**一致性保障**：
- 外键约束在数据库层保证引用完整性，避免程序 Bug 产生脏数据（如指向不存在的 `kb_id`）
- SQLAlchemy 模型中必须同步声明 `sa.ForeignKey(...)`，与 Alembic 迁移脚本保持一致
- 模型中应补充 `relationship` 定义，支持 ORM 级联操作和跨表查询

**SQLAlchemy ORM 行为注意事项**：
- `ON DELETE CASCADE` 是**数据库层**的级联行为，SQLAlchemy ORM 默认**不会**自动感知
- SQLAlchemy `relationship()` 默认 `passive_deletes=False`：删除父对象前，ORM 会先加载所有子对象并尝试 `SET FK=NULL`，再由数据库执行 CASCADE 删除
- **当子表 FK 列为 NOT NULL 时**（如 `chunks.doc_id`、`chunks.kb_id`），`SET NULL` 操作会触发 `IntegrityError (1048, "Column 'doc_id' cannot be null")`
- **解决方案**：所有 NOT NULL 外键列对应的 `relationship()` 必须添加 `passive_deletes=True`，告知 ORM 跳过 SET NULL 步骤，直接由数据库 FK CASCADE 处理级联删除
- 当前已配置 `passive_deletes=True` 的关系：`Document.chunks`、`KnowledgeBase.documents`、`KnowledgeBase.chunks`

---

## 5. 相关文档

- [架构设计文档](../docs/ARCHITECTURE.md)
- [接口文档](API.md)
- [开发指南](../docs/DEVELOPMENT.md)
- [UI 设计规范](../../frontend/docs/UIDESIGN.md)
