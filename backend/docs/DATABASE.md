# DATABASE — 数据库设计文档

| 属性 | 值 |
|:---|:---|
| 文档版本 | v0.13 |
| 最后更新 | 2026-06-12 |
| 作者 | yuz |
| 状态 | 草稿（Phase 5 Admin 查询优化备注已补充 + Trace 表已实现） |

---

## 0. 时区约定

> **所有 DATETIME 列均存储 UTC 时间。**

| 层面 | 约定 | 实施方式 |
|:---|:---|:---|
| MySQL 会话 | `time_zone='+00:00'` | 连接串 `init_command=SET time_zone='%2B00:00'`，确保 `CURRENT_TIMESTAMP` 返回 UTC |
| ORM 声明 | `UTCDateTime` TypeDecorator | 自定义 `TypeDecorator(DateTime)` — 写入剥离 tzinfo、读取附加 UTC tzinfo，对 Pydantic 透明 |
| Python 代码 | `datetime.now(timezone.utc)` | 禁止 `datetime.utcnow()`；业务代码写入的时间值也是 UTC |
| API 序列化 | ISO 8601 + `+00:00` | Pydantic 序列化 aware datetime 自动输出 `2026-06-09T11:26:20+00:00` |

> **注意**：MySQL 的 `DATETIME` 类型本身不存储时区信息，UTC 约定是应用层的协议。`app/models/_types.py` 中的 `UTCDateTime` TypeDecorator 在 ORM 层完成 aware ↔ naive 双向转换——写入时剥离 tzinfo 存 naive UTC，读取时附加 UTC tzinfo 返回 aware datetime。Pydantic 自然收到 aware datetime → 自动序列化 `2026-06-09T12:00:02Z`。底层列依然是 `DATETIME`，不需要数据迁移。

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
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间，自动更新 |

### 2.2 知识库表 `knowledge_bases`

```sql
CREATE TABLE knowledge_bases (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(128) NOT NULL,
    description TEXT,
    user_id BIGINT NOT NULL,
    visibility ENUM('private', 'public') DEFAULT 'private' COMMENT 'private（仅owner可见）/ public（所有用户可检索）',
    status ENUM('active', 'deleting') DEFAULT 'active',
    chunk_count INT DEFAULT 0,
    doc_count INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    UNIQUE INDEX idx_user_name (user_id, name)
);
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| id | BIGINT | 主键 |
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
    INDEX idx_kb_id (kb_id),
    INDEX idx_kb_filename (kb_id, filename) COMMENT '文档唯一性检查',
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE
);
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| id | BIGINT | 主键 |
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

**状态枚举定义**（详见 API.md §4.0）：
```python
class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    VECTOR_STORING = "vector_storing"
    COMPLETED = "completed"
    SUCCESS_WITH_WARNINGS = "success_with_warnings"
    PARTIAL_FAILED = "partial_failed"
    FAILED = "failed"
    DELETING = "deleting"

TERMINAL_STATUSES = {
    "completed",
    "success_with_warnings",
    "partial_failed",
    "failed"
}
```

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
    user_id BIGINT NOT NULL,
    kb_id BIGINT COMMENT '关联的知识库',
    title VARCHAR(256) DEFAULT '新对话',
    message_count INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE SET NULL
);
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| id | BIGINT | 主键 |
| user_id | BIGINT | 所属用户 ID，有索引 |
| kb_id | BIGINT | 关联的知识库 ID（可选，表示对话的知识域） |
| title | VARCHAR(256) | 对话标题（可由首条消息自动生成） |
| message_count | INT | 消息总数（冗余缓存） |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

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

> **Phase 4 新增**。配合 Refresh Token 机制（见 ARCHITECTURE.md §9.2），持久化存储刷新令牌哈希。

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
    response_mode VARCHAR(32) COMMENT '顶层字段：RAG / DIRECT_LLM / META / CASUAL / FALLBACK',
    total_duration_ms INT COMMENT '总耗时（毫秒）',
    intent JSON COMMENT '意图识别阶段详情',
    rewrite JSON COMMENT '问题重写阶段详情',
    retrieve JSON COMMENT '检索阶段详情（细粒度拆分：vector/bm25/fusion/match_sentence）',
    rerank JSON COMMENT 'Rerank 阶段详情',
    generate JSON COMMENT 'LLM 生成阶段详情（不存 output）',
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
| response_mode | VARCHAR(32) | 响应模式（顶层字段，用于聚合统计） |
| total_duration_ms | INT | 总耗时（毫秒） |
| intent | JSON | 意图识别阶段详情（span_name/start_time/duration_ms/status/intent_type/method/metadata） |
| rewrite | JSON | 问题重写阶段详情（span_name/start_time/duration_ms/status/original_question/rewritten_question/metadata） |
| retrieve | JSON | 检索阶段详情，**细粒度拆分**：vector/bm25/fusion/match_sentence 各自独立计时 |
| rerank | JSON | Rerank 阶段详情（input_count/output_count/metadata.reranker） |
| generate | JSON | LLM 生成阶段详情（model/ttft_ms/input_tokens/output_tokens/finish_reason），**不存 output** |
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
| knowledge_bases | idx_user_name (user_id, name) | 唯一索引 | 用户级知识库名称唯一性约束 |
| documents | idx_kb_id | 普通索引 | 按知识库列出文档 |
| documents | idx_kb_filename (kb_id, filename) | 复合索引 | 文档唯一性检查 + 同名查找 |
| chunks | idx_doc_id | 普通索引 | 按文档列出分块 |
| chunks | idx_kb_id | 普通索引 | 按知识库统计分块 |
| conversations | idx_user_id | 普通索引 | 按用户列出会话 |
| conversations | idx_conversations_user_updated (user_id, updated_at) | 复合索引 | Phase 4：按用户列出会话并按更新时间倒序排列 |
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

> TODO: [待补充] 如后续文档量和用户量增大，考虑：
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
